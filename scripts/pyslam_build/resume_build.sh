#!/bin/bash
# Resume the pySLAM build after the 2026-09-05 host crash. Memory-capped at -j2.
set -o pipefail

source /opt/conda/etc/profile.d/conda.sh
conda activate pyslam

# Shim nproc -> 2 so vendored `make -j$(nproc)` calls stay memory-bounded.
mkdir -p /tmp/shim
printf '#!/bin/sh\necho 2\n' > /tmp/shim/nproc
chmod +x /tmp/shim/nproc
export PATH=/tmp/shim:$PATH
export MAKEFLAGS=-j2

step() { echo; echo "=============== $* ($(date +%H:%M:%S)) ==============="; }

step "1/5 gtsam_local: make -j2 (resuming from 61%)"
cd /pyslam/thirdparty/gtsam_local/build || exit 1
make -j2 || { echo "FAILED: gtsam make"; exit 1; }

step "2/5 gtsam_local: make install"
make install || { echo "FAILED: gtsam install"; exit 1; }

step "verify install prefix populated"
ls -la /pyslam/thirdparty/gtsam_local/install/lib/cmake/GTSAM/ || { echo "FAILED: no GTSAM cmake config"; exit 1; }

step "3/5 gtsam_local: make python-install"
make python-install || echo "WARN: python-install failed (non-fatal for cpp core)"

step "4/5 gtsam_factors"
cd /pyslam/thirdparty/gtsam_factors || exit 1
./build.sh -DWITH_MARCH_NATIVE=ON || { echo "FAILED: gtsam_factors"; exit 1; }

step "5/5 pySLAM C++ core"
cd /pyslam || exit 1
./build_cpp_core.sh || { echo "FAILED: cpp core"; exit 1; }

step "DONE - checking artifacts"
ls -la /pyslam/pyslam/slam/cpp/lib/ 2>&1
echo "ALL_OK"
