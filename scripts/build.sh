#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
workspace_dir="$(cd -- "${script_dir}/.." && pwd)"

if [[ ! -r /opt/ros/jazzy/setup.bash ]]; then
  echo "ROS 2 Jazzy no está instalado." >&2
  echo "Ejecuta: sudo bash scripts/install_ros2_jazzy.sh" >&2
  exit 1
fi

set +u
# shellcheck disable=SC1091
source /opt/ros/jazzy/setup.bash
set -u

cd "${workspace_dir}"
rosdep install --from-paths src --ignore-src --rosdistro jazzy -r -y
colcon build --symlink-install

echo
echo "Compilación terminada. Activa el overlay con:"
echo "  source scripts/ros2_env.sh"
