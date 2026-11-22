#!/usr/bin/env bash
set -euo pipefail

readonly ROS_DISTRO_NAME="jazzy"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Ejecuta este instalador con sudo:" >&2
  echo "  sudo bash scripts/install_ros2_jazzy.sh" >&2
  exit 1
fi

if [[ ! -r /etc/os-release ]]; then
  echo "No se pudo identificar el sistema operativo." >&2
  exit 1
fi

# shellcheck disable=SC1091
source /etc/os-release
if [[ "${ID:-}" != "ubuntu" || "${VERSION_CODENAME:-}" != "noble" ]]; then
  echo "Este instalador requiere Ubuntu 24.04 (Noble)." >&2
  echo "Sistema detectado: ${PRETTY_NAME:-desconocido}" >&2
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive

apt-get update
apt-get install -y curl locales software-properties-common
add-apt-repository -y universe

locale-gen en_US en_US.UTF-8
update-locale LANG=en_US.UTF-8 LC_ALL=en_US.UTF-8
export LANG=en_US.UTF-8
export LC_ALL=en_US.UTF-8

apt-get update

ros_apt_source_version="$({
  curl -fsSL https://api.github.com/repos/ros-infrastructure/ros-apt-source/releases/latest \
    | sed -n 's/.*"tag_name":[[:space:]]*"\([^"]*\)".*/\1/p'
} | head -n 1)"

if [[ -z "${ros_apt_source_version}" ]]; then
  echo "No se pudo determinar la versión actual de ros2-apt-source." >&2
  exit 1
fi

ros_apt_source_deb="/tmp/ros2-apt-source.deb"
curl -fL \
  "https://github.com/ros-infrastructure/ros-apt-source/releases/download/${ros_apt_source_version}/ros2-apt-source_${ros_apt_source_version}.noble_all.deb" \
  -o "${ros_apt_source_deb}"
dpkg -i "${ros_apt_source_deb}"

apt-get update
apt-get install -y "ros-${ROS_DISTRO_NAME}-desktop" ros-dev-tools

if [[ ! -e /etc/ros/rosdep/sources.list.d/20-default.list ]]; then
  rosdep init
fi

echo
echo "ROS 2 ${ROS_DISTRO_NAME} quedó instalado correctamente."
echo "Como usuario normal, ejecuta:"
echo "  rosdep update"
echo "  source scripts/ros2_env.sh"
