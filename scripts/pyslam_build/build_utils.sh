#!/bin/bash
# Build the top-level cpp/ dir -> pyslam_utils (the module missing after the crash).
set -o pipefail
source /opt/conda/etc/profile.d/conda.sh
conda activate pyslam
mkdir -p /tmp/shim
printf '#!/bin/sh\necho 2\n' > /tmp/shim/nproc
chmod +x /tmp/shim/nproc
export PATH=/tmp/shim:$PATH
export MAKEFLAGS=-j2

cd /pyslam || exit 1
echo "=============== install_cpp.sh ($(date +%H:%M:%S)) ==============="
. scripts/install_cpp.sh || { echo "FAILED: install_cpp"; exit 1; }

echo "=============== artifacts ==============="
ls -la /pyslam/cpp/lib/ 2>&1
echo "ALL_OK"
