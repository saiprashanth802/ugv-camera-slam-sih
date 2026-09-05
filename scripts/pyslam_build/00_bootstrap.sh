#!/usr/bin/env bash
# Stage 0 of the pySLAM build: everything up to and including install_all.sh.
#
# Run this from the repo root ON THE HOST. It creates the build container, installs
# conda inside it, clones the pinned upstream tree into vendor/pyslam, applies our two
# patches, and runs upstream's installer. Stages 1-5 (the scripts alongside this one)
# resume from there; see README.md in this directory for their order.
#
# HONEST STATUS: assembled from the commands that did work on 2026-09-05, but this
# script has not been run start-to-finish on a clean machine. Expect to babysit it.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VENDOR="$REPO_ROOT/vendor/pyslam"
CONTAINER="pyslam-build"
UPSTREAM_COMMIT="a5ff2562eb929ed9a08420f528a120a3cca65585"

step() { echo; echo "=============== $* ($(date +%H:%M:%S)) ==============="; }

# --- 1. the pinned upstream tree -------------------------------------------------
# Upstream publishes no release tags. Pin by hash or the patches in patches/ will
# eventually apply to something they were not written for.
step "1/5 clone upstream pySLAM @ ${UPSTREAM_COMMIT:0:7}"
if [[ ! -d "$VENDOR/.git" ]]; then
    mkdir -p "$(dirname "$VENDOR")"
    git clone https://github.com/luigifreda/pyslam.git "$VENDOR"
fi
git -C "$VENDOR" fetch --all --tags
git -C "$VENDOR" checkout "$UPSTREAM_COMMIT"
git -C "$VENDOR" submodule update --init --recursive

step "2/5 apply our source patches (pySLAM does not work without them)"
"$REPO_ROOT/patches/apply_patches.sh"

# --- 2. the build container ------------------------------------------------------
# ubuntu:24.04 is only a shell to build in; the Python that matters comes from conda
# below. Do NOT try to build against the distro python -- see RUNBOOK.md section 7c
# for why 22.04 (3.10) and 24.04 (3.12) both fail.
step "3/5 create container $CONTAINER"
if ! docker inspect "$CONTAINER" >/dev/null 2>&1; then
    docker run -d --name "$CONTAINER" --gpus all \
        -v "$VENDOR:/pyslam:rw" \
        -e DEBIAN_FRONTEND=noninteractive \
        --security-opt label=disable \
        ubuntu:24.04 sleep infinity
else
    docker start "$CONTAINER"
fi

docker exec "$CONTAINER" bash -lc 'apt-get update -qq && apt-get install -y -qq \
    sudo git curl wget unzip build-essential cmake pkg-config python3 python3-dev \
    python3-venv python3-pip libglew-dev libgl1-mesa-dev libglu1-mesa-dev libeigen3-dev \
    libsuitesparse-dev libboost-all-dev libopencv-dev ca-certificates rsync'

# --- 3. conda ---------------------------------------------------------------------
# install_all.sh branches on `command -v conda`. With conda present it calls
# install_all_conda.sh, which creates the env at Python 3.11 -- the only version that
# satisfies upstream's >=3.11.9 pin AND has a prebuilt scikit-image==0.21.0 wheel.
# Without conda it takes the venv branch, which fails on every stock Ubuntu image.
step "4/5 install miniforge (this is what selects the working install path)"
docker exec "$CONTAINER" bash -lc '
    command -v /opt/conda/bin/conda >/dev/null && { echo "conda already present"; exit 0; }
    cd /tmp && curl -fsSL -o mf.sh \
      https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh \
    && bash mf.sh -b -p /opt/conda'

# --- 4. upstream installer ---------------------------------------------------------
# -j2 throughout: the vendored scripts call make -j$(nproc) internally, nproc reports 16
# on a 14 GiB machine, and make -j16 on GTSAM OOM-killed this host on 2026-09-05.
step "5/5 install_all.sh (long: expect hours, memory-capped at -j2)"
docker exec "$CONTAINER" bash -lc '
    export PATH=/opt/conda/bin:$PATH; source /opt/conda/etc/profile.d/conda.sh
    mkdir -p /tmp/shim && printf "#!/bin/sh\necho 2\n" > /tmp/shim/nproc && chmod +x /tmp/shim/nproc
    export PATH=/tmp/shim:$PATH MAKEFLAGS=-j2
    cd /pyslam && ./install_all.sh 2>&1 | tee install_all.log'

cat <<'DONE'

=============== stage 0 complete ===============
install_all.sh has been known to stop early at step 60 (install_pip3_packages.sh),
leaving install_thirdparty.sh and install_cpp.sh unrun. Check for the C++ modules:

    docker exec pyslam-build bash -lc 'ls /pyslam/cpp/lib/ /pyslam/pyslam/slam/cpp/lib/'

If they are missing, run the recovery scripts in this directory in the order given by
its README.md. Then verify end to end with RUNBOOK.md section 7c.
DONE
