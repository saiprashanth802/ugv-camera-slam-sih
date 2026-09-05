#!/bin/bash
set -o pipefail
source /opt/conda/etc/profile.d/conda.sh
conda activate pyslam
mkdir -p /tmp/shim && printf '#!/bin/sh\necho 1\n' > /tmp/shim/nproc && chmod +x /tmp/shim/nproc
export PATH=/tmp/shim:$PATH MAKEFLAGS=-j1

cd /pyslam/thirdparty/gtsam_local/build || exit 1

echo "=== cmake regenerate ($(date +%H:%M:%S)) ==="
cmake . > /tmp/cmake_regen.log 2>&1 || { echo "FAILED: cmake regen"; tail -20 /tmp/cmake_regen.log; exit 1; }
ls python/CMakeFiles/gtsam_py.dir/build.make >/dev/null || { echo "FAILED: build.make still missing"; exit 1; }
echo "build.make regenerated"

echo "=== make python-install -j1 ($(date +%H:%M:%S)) ==="
make python-install -j1 2>&1 | tail -25
[ "${PIPESTATUS[0]}" -ne 0 ] && { echo "FAILED: python-install"; exit 1; }

echo "=== verify ($(date +%H:%M:%S)) ==="
SO=/opt/conda/envs/pyslam/lib/python3.11/site-packages/gtsam/gtsam.cpython-311-x86_64-linux-gnu.so
ls -la "$SO"
echo "PyInit symbols: $(nm -D "$SO" 2>/dev/null | grep -c PyInit)"
python -c "import gtsam; print('gtsam import OK')" || { echo "FAILED: gtsam import"; exit 1; }
echo "ALL_OK"
