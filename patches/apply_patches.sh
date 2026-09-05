#!/usr/bin/env bash
# Reapply local fixes to vendor/pyslam after a fresh clone or rebuild.
# vendor/ is gitignored, so these patches are the only record of the changes.
# Idempotent: already-applied patches are detected and skipped.
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VENDOR="$REPO_ROOT/vendor/pyslam"

# Upstream has NO release tags, so the only stable reference is a commit hash.
# These patches were generated against this exact tree; applying them to a moving
# master is how you get a silent half-application months from now.
UPSTREAM_COMMIT="a5ff2562eb929ed9a08420f528a120a3cca65585"

if [[ ! -d "$VENDOR" ]]; then
    cat >&2 <<EOF
ERROR: $VENDOR not found.

Clone the pinned upstream tree first:

  git clone https://github.com/luigifreda/pyslam.git "$VENDOR"
  git -C "$VENDOR" checkout $UPSTREAM_COMMIT
  git -C "$VENDOR" submodule update --init --recursive

Then re-run this script. See RUNBOOK.md section 7c for the full build.
EOF
    exit 1
fi

# Refuse to patch a tree that is not the one these patches were made against.
# Override with ALLOW_COMMIT_MISMATCH=1 if you have deliberately moved upstream and
# are prepared to fix up the rejects by hand.
actual="$(git -C "$VENDOR" rev-parse HEAD 2>/dev/null || echo unknown)"
if [[ "$actual" != "$UPSTREAM_COMMIT" ]]; then
    if [[ "${ALLOW_COMMIT_MISMATCH:-0}" == "1" ]]; then
        echo "WARNING: upstream is $actual, expected $UPSTREAM_COMMIT -- continuing anyway" >&2
    else
        echo "ERROR: $VENDOR is at commit $actual" >&2
        echo "       these patches were generated against $UPSTREAM_COMMIT" >&2
        echo "       check that commit out, or set ALLOW_COMMIT_MISMATCH=1 to force." >&2
        exit 1
    fi
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
