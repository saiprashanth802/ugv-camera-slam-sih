#!/bin/bash
# Rebuild GTSAM python bindings from source. -j1: gtsam.cpp binding TU is a RAM hog.
set -o pipefail
source /opt/conda/etc/profile.d/conda.sh
conda activate pyslam
mkdir -p /tmp/shim && printf '#!/bin/sh\necho 1\n' > /tmp/shim/nproc && chmod +x /tmp/shim/nproc
export PATH=/tmp/shim:$PATH MAKEFLAGS=-j1

cd /pyslam/thirdparty/gtsam_local/build || exit 1

echo "=== purging corrupt artifacts ($(date +%H:%M:%S)) ==="
rm -f python/gtsam/gtsam.cpython-311-x86_64-linux-gnu.so
rm -f python/build/lib/gtsam/gtsam.cpython-311-x86_64-linux-gnu.so
rm -rf python/CMakeFiles/gtsam_py.dir

echo "=== make python-install -j1 ($(date +%H:%M:%S)) ==="
make python-install -j1 || { echo "FAILED: python-install"; exit 1; }

echo "=== verify ($(date +%H:%M:%S)) ==="
SO=/opt/conda/envs/pyslam/lib/python3.11/site-packages/gtsam/gtsam.cpython-311-x86_64-linux-gnu.so
ls -la "$SO"
echo "PyInit symbols: $(nm -D "$SO" 2>/dev/null | grep -c PyInit)"
python -c "import gtsam; print('gtsam import OK')" || { echo "FAILED: gtsam import"; exit 1; }
echo "ALL_OK"
