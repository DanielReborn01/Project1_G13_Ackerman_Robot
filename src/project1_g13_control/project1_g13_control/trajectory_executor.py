#!/usr/bin/env python3
"""Follow a figure-eight path and publish planned and executed paths."""

import math

import rclpy
from geometry_msgs.msg import PoseStamped, TwistStamped
from nav_msgs.msg import Odometry, Path
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy


def normalize_angle(angle):
    """Normalize an angle to the [-pi, pi] interval."""
    return math.atan2(math.sin(angle), math.cos(angle))


def yaw_from_quaternion(quaternion):
    """Extract planar yaw from a geometry_msgs quaternion."""
    sin_yaw = 2.0 * (
        quaternion.w * quaternion.z + quaternion.x * quaternion.y
    )
    cos_yaw = 1.0 - 2.0 * (
        quaternion.y * quaternion.y + quaternion.z * quaternion.z
    )
    return math.atan2(sin_yaw, cos_yaw)


class TrajectoryExecutor(Node):
    """Track a Gerono lemniscate with a Pure Pursuit controller."""

    def __init__(self):
        super().__init__('trajectory_executor')

        self.declare_parameter('width', 2.0)
        self.declare_parameter('height', 1.0)
        self.declare_parameter('samples', 300)
        self.declare_parameter('linear_velocity', 0.15)
        self.declare_parameter('lookahead_distance', 0.25)
        self.declare_parameter('goal_tolerance', 0.08)
        self.declare_parameter('wheelbase', 0.15)
        self.declare_parameter('max_steering_angle', 0.60)
        self.declare_parameter('trace_min_distance', 0.02)

        self.linear_velocity = float(
            self.get_parameter('linear_velocity').value
        )
        self.lookahead_distance = float(
            self.get_parameter('lookahead_distance').value
        )
        self.goal_tolerance = float(
            self.get_parameter('goal_tolerance').value
        )
        self.wheelbase = float(self.get_parameter('wheelbase').value)
        self.max_steering_angle = float(
            self.get_parameter('max_steering_angle').value
        )
        self.trace_min_distance = float(
            self.get_parameter('trace_min_distance').value
        )

        self.waypoints = self.generate_figure_eight()
        self.current_index = 0
        self.current_pose = None
        self.latest_odom_stamp = None
        self.finished = False
        self.waiting_message_printed = False

        path_qos = QoSProfile(
            depth=1,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
        )

        self.command_publisher = self.create_publisher(
            TwistStamped,
            '/ackermann_steering_controller/reference',
            10,
        )
        self.planned_path_publisher = self.create_publisher(
            Path,
            '/planned_path',
            path_qos,
        )
        self.executed_path_publisher = self.create_publisher(
            Path,
            '/executed_path',
            path_qos,
        )
        self.odometry_subscription = self.create_subscription(
            Odometry,
            '/ackermann_steering_controller/odometry',
            self.odometry_callback,
            10,
        )

        self.planned_path = self.create_planned_path_message()
        self.executed_path = Path()
        self.executed_path.header.frame_id = 'odom'

        self.planned_path_publisher.publish(self.planned_path)
        self.path_timer = self.create_timer(1.0, self.publish_planned_path)
        self.control_timer = self.create_timer(0.05, self.control_callback)

        self.get_logger().info(
            f'Trayectoria infinito creada con {len(self.waypoints)} puntos.'
        )

    def generate_figure_eight(self):
        """Generate a horizontal Gerono lemniscate starting toward +X."""
        width = float(self.get_parameter('width').value)
        height = float(self.get_parameter('height').value)
        sample_count = max(20, int(self.get_parameter('samples').value))

        half_width = width / 2.0
        half_height = height / 2.0

        # At pi/4, dy/dt is zero and dx/dt is positive. This makes the
        # initial path tangent agree with a robot initially facing +X.
        start_parameter = math.pi / 4.0
        start_x = half_width * math.sin(start_parameter)
        start_y = half_height * math.sin(2.0 * start_parameter)

        points = []
        for index in range(sample_count):
            fraction = index / (sample_count - 1)
            parameter = start_parameter + fraction * 2.0 * math.pi
            x = half_width * math.sin(parameter) - start_x
            y = half_height * math.sin(2.0 * parameter) - start_y
            points.append((x, y))

        return points

    def create_planned_path_message(self):
        """Convert generated waypoints into a nav_msgs/Path message."""
        path = Path()
        path.header.frame_id = 'odom'

        for index, (x, y) in enumerate(self.waypoints):
            pose = PoseStamped()
            pose.header.frame_id = 'odom'
            pose.pose.position.x = x
            pose.pose.position.y = y

            if index < len(self.waypoints) - 1:
                next_x, next_y = self.waypoints[index + 1]
            else:
                previous_x, previous_y = self.waypoints[index - 1]
                next_x = x + x - previous_x
                next_y = y + y - previous_y

            yaw = math.atan2(next_y - y, next_x - x)
            pose.pose.orientation.z = math.sin(yaw / 2.0)
            pose.pose.orientation.w = math.cos(yaw / 2.0)
            path.poses.append(pose)

        return path

    def publish_planned_path(self):
        """Republish the plan so late RViz subscribers also receive it."""
        if self.latest_odom_stamp is not None:
            self.planned_path.header.stamp = self.latest_odom_stamp
        self.planned_path_publisher.publish(self.planned_path)

    def odometry_callback(self, message):
        """Store vehicle pose and append it to the executed path."""
        position = message.pose.pose.position
        yaw = yaw_from_quaternion(message.pose.pose.orientation)
        self.current_pose = (position.x, position.y, yaw)
        self.latest_odom_stamp = message.header.stamp

        should_append = not self.executed_path.poses
        if self.executed_path.poses:
            last_position = self.executed_path.poses[-1].pose.position
            distance = math.hypot(
                position.x - last_position.x,
                position.y - last_position.y,
            )
            should_append = distance >= self.trace_min_distance

        if should_append:
            pose = PoseStamped()
            pose.header = message.header
            pose.pose = message.pose.pose
            self.executed_path.header.stamp = message.header.stamp
            self.executed_path.poses.append(pose)
            self.executed_path_publisher.publish(self.executed_path)

    def find_target_index(self):
        """Find a lookahead target while only progressing along the path."""
        robot_x, robot_y, _ = self.current_pose

        search_end = min(self.current_index + 50, len(self.waypoints))
        nearest_index = min(
            range(self.current_index, search_end),
            key=lambda index: math.hypot(
                self.waypoints[index][0] - robot_x,
                self.waypoints[index][1] - robot_y,
            ),
        )
        self.current_index = max(self.current_index, nearest_index)

        target_index = self.current_index
        while target_index < len(self.waypoints) - 1:
            target_x, target_y = self.waypoints[target_index]
            if math.hypot(target_x - robot_x, target_y - robot_y) >= (
                self.lookahead_distance
            ):
                break
            target_index += 1

        self.current_index = max(self.current_index, target_index)
        return target_index

    def control_callback(self):
        """Calculate and publish a Pure Pursuit velocity command."""
        if self.finished:
            return

        if self.current_pose is None or self.latest_odom_stamp is None:
            if not self.waiting_message_printed:
                self.get_logger().info('Esperando odometría del controlador...')
                self.waiting_message_printed = True
            return

        robot_x, robot_y, robot_yaw = self.current_pose
        final_x, final_y = self.waypoints[-1]
        final_distance = math.hypot(final_x - robot_x, final_y - robot_y)

        if (
            self.current_index >= len(self.waypoints) - 3
            and final_distance <= self.goal_tolerance
        ):
            self.stop_robot()
            self.finished = True
            self.get_logger().info('Trayectoria infinito completada.')
            return

        target_index = self.find_target_index()
        target_x, target_y = self.waypoints[target_index]
        target_angle = math.atan2(target_y - robot_y, target_x - robot_x)
        heading_error = normalize_angle(target_angle - robot_yaw)
        target_distance = max(
            math.hypot(target_x - robot_x, target_y - robot_y),
            0.01,
        )

        curvature = 2.0 * math.sin(heading_error) / target_distance
        maximum_curvature = math.tan(self.max_steering_angle) / self.wheelbase
        curvature = max(-maximum_curvature, min(maximum_curvature, curvature))

        curvature_ratio = abs(curvature) / maximum_curvature
        speed_scale = max(0.35, 1.0 - 0.60 * curvature_ratio)
        speed = self.linear_velocity * speed_scale

        command = TwistStamped()
        command.header.stamp = self.latest_odom_stamp
        command.header.frame_id = 'base_link'
        command.twist.linear.x = speed
        command.twist.angular.z = speed * curvature
        self.command_publisher.publish(command)

    def stop_robot(self):
        """Publish a zero body velocity command."""
        command = TwistStamped()
        if self.latest_odom_stamp is not None:
            command.header.stamp = self.latest_odom_stamp
        command.header.frame_id = 'base_link'
        self.command_publisher.publish(command)


def main(args=None):
    rclpy.init(args=args)
    node = TrajectoryExecutor()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.stop_robot()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
