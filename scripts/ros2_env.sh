#!/usr/bin/env bash

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  echo "Este archivo debe cargarse en la terminal actual:" >&2
  echo "  source scripts/ros2_env.sh" >&2
  exit 1
fi

_ros2_env_script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
_ros2_env_workspace="$(cd -- "${_ros2_env_script_dir}/.." && pwd)"
_ros2_env_had_nounset=0

if [[ ! -r /opt/ros/jazzy/setup.bash ]]; then
  echo "ROS 2 Jazzy no está instalado." >&2
  echo "Ejecuta: sudo bash scripts/install_ros2_jazzy.sh" >&2
  unset _ros2_env_script_dir _ros2_env_workspace _ros2_env_had_nounset
  return 1
fi

if [[ "${-}" == *u* ]]; then
  _ros2_env_had_nounset=1
  set +u
fi

# shellcheck disable=SC1091
source /opt/ros/jazzy/setup.bash

if [[ -r "${_ros2_env_workspace}/install/setup.bash" ]]; then
  # shellcheck disable=SC1090
  source "${_ros2_env_workspace}/install/setup.bash"
fi

export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-13}"

echo "ROS_DISTRO=${ROS_DISTRO}"
echo "ROS_DOMAIN_ID=${ROS_DOMAIN_ID}"
echo "Workspace=${_ros2_env_workspace}"

unset _ros2_env_script_dir _ros2_env_workspace
if (( _ros2_env_had_nounset )); then
  unset _ros2_env_had_nounset
  set -u
else
  unset _ros2_env_had_nounset
fi
