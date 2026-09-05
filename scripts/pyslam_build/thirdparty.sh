#!/bin/bash
set -o pipefail
source /opt/conda/etc/profile.d/conda.sh
conda activate pyslam
mkdir -p /tmp/shim && printf '#!/bin/sh\necho 2\n' > /tmp/shim/nproc && chmod +x /tmp/shim/nproc
export PATH=/tmp/shim:$PATH MAKEFLAGS=-j2

cd /pyslam || exit 1
echo "=== install_thirdparty.sh ($(date +%H:%M:%S)) ==="
. scripts/install_thirdparty.sh
echo "THIRDPARTY_EXIT=$?"

echo "=== lib status ==="
for p in thirdparty/pydbow3/lib thirdparty/pydbow2/lib thirdparty/pyibow/lib \
         thirdparty/pangolin thirdparty/orbslam2_features/lib thirdparty/g2opy/lib \
         thirdparty/gtsam_factors/lib cpp/lib; do
  echo "$(ls $p/*.so 2>/dev/null | wc -l)  $p"
done
echo "DONE"
