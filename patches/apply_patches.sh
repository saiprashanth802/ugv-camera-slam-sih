#!/usr/bin/env bash
# Reapply local fixes to vendor/pyslam after a fresh clone or rebuild.
# vendor/ is gitignored, so these patches are the only record of the changes.
# Idempotent: already-applied patches are detected and skipped.
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENDOR="$SCRIPT_DIR/../vendor/pyslam"

if [[ ! -d "$VENDOR" ]]; then
    echo "ERROR: $VENDOR not found. Clone luigifreda/pyslam there first." >&2
    exit 1
fi

rc=0
for p in "$SCRIPT_DIR"/[0-9][0-9][0-9][0-9]-*.patch; do
    [[ -e "$p" ]] || { echo "No patches found in $SCRIPT_DIR"; exit 0; }
    name=$(basename "$p")
    if patch -d "$VENDOR" -p1 --dry-run --reverse --force < "$p" >/dev/null 2>&1; then
        echo "SKIP    $name (already applied)"
    elif patch -d "$VENDOR" -p1 --forward < "$p" >/dev/null 2>&1; then
        echo "APPLIED $name"
    else
        echo "FAILED  $name" >&2
        rc=1
    fi
done
exit $rc
