#!/usr/bin/env bash
# Smoke test: run INSIDE the container, before anything else.
# PASS = "NVIDIA GeForce RTX 4060". FAIL = anything with "AMD" or "llvmpipe".
set -uo pipefail
echo "--- renderer ---"
glxinfo -B 2>/dev/null | grep -E "OpenGL (vendor|renderer)" || echo "glxinfo FAILED - no X connection"
R="$(glxinfo -B 2>/dev/null | grep 'OpenGL renderer' || true)"
case "$R" in
  *NVIDIA*) echo "PASS: rendering on the dGPU" ;;
  *AMD*|*llvmpipe*|*softpipe*) echo "FAIL: on iGPU/software - the __NV_PRIME_RENDER_OFFLOAD env vars did not reach the container" ;;
  *) echo "FAIL: no GL at all - check 'xhost +local:docker' on the host" ;;
esac
