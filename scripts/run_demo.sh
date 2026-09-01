#!/usr/bin/env bash
# Sightline — launch the demo container with verified GPU + GUI passthrough.
#
# The env vars below are NOT optional decoration. Verified on Fedora 44 / Wayland
# 2026-09-01: without the three __NV_* / __GLX_* vars the container renders on the
# AMD Radeon 780M iGPU, not the RTX 4060, and Gazebo crawls.
set -euo pipefail

IMAGE="${IMAGE:-ugv-slam:demo}"
NAME="${NAME:-sightline}"
WS="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Allow container X clients through. Harmless to re-run.
xhost +local:docker >/dev/null

# Reattach to a running container instead of starting a second one.
if [ -n "$(docker ps -q -f name="^${NAME}$")" ]; then
  echo "[sightline] attaching to running container '${NAME}'"
  exec docker exec -it "${NAME}" bash
fi
docker rm -f "${NAME}" >/dev/null 2>&1 || true

exec docker run -it --rm \
  --name "${NAME}" \
  --gpus all \
  --net=host --ipc=host --pid=host \
  -e DISPLAY="${DISPLAY:-:0}" \
  -e QT_X11_NO_MITSHM=1 \
  -e NVIDIA_DRIVER_CAPABILITIES=all \
  -e __NV_PRIME_RENDER_OFFLOAD=1 \
  -e __GLX_VENDOR_LIBRARY_NAME=nvidia \
  -e __VK_LAYER_NV_optimus=NVIDIA_only \
  -v /tmp/.X11-unix:/tmp/.X11-unix:rw \
  -v "${WS}:/ws:rw" \
  --security-opt label=disable \
  "${IMAGE}" bash
