#!/usr/bin/env bash
set -euo pipefail

if [[ ! -r /opt/ros/jazzy/setup.bash ]]; then
  echo "ROS 2 Jazzy no está instalado." >&2
  exit 1
fi

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
set +u
# shellcheck disable=SC1090
source "${script_dir}/ros2_env.sh"
set -u

echo "Distribución: ${ROS_DISTRO}"
echo "CLI: $(ros2 --help >/dev/null && command -v ros2)"
echo "Demos: $(ros2 pkg prefix demo_nodes_cpp)"
python3 -c 'import rclpy; print("rclpy: OK")'

echo
PYTHONWARNINGS=ignore ros2 doctor
