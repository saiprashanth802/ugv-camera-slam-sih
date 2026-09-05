# pySLAM environment build scripts

These five scripts built the working pySLAM environment on 2026-09-05. They lived in
`/tmp` **inside** container `pyslam-build` — not in git, not in the mounted repo, on a
box that had already been OOM-killed once that morning. They are here so the environment
can be rebuilt without rediscovering any of it.

They are **recovery scripts, not a clean installer.** Each was written to resume a build
that had died partway, so they assume paths inside the container (`/pyslam`,
`/opt/conda`) and they start from a tree that `install_all.sh` has already partly
populated. Read them before running them.

## The one thing that matters: `-j2`

Every script shims `nproc` to return 2 (or 1) and exports `MAKEFLAGS`:

```bash
mkdir -p /tmp/shim && printf '#!/bin/sh\necho 2\n' > /tmp/shim/nproc
chmod +x /tmp/shim/nproc
export PATH=/tmp/shim:$PATH MAKEFLAGS=-j2
```

The shim exists because the vendored build scripts call `make -j$(nproc)` internally,
where overriding `MAKEFLAGS` alone does not reach them. `nproc` reports **16** on this
laptop, which has **14 GiB**. `make -j16` on GTSAM is what hard-crashed the host on
2026-09-05 (OOM kills at 08:30 and 08:57, then an unclean shutdown at 11:09) and lost an
in-flight build. GTSAM's Python binding TU (`gtsam.cpp`) is a big enough RAM hog that it
needs `-j1`, not `-j2` — hence the two different shim values.

## Order they were actually run in

**Stage 0 is `00_bootstrap.sh`** — run that first, from the repo root. It clones the
pinned upstream tree, applies `patches/`, creates the container, installs conda (which
is what makes upstream's installer take its working branch), and runs `install_all.sh`.
Everything below resumes from where that stops.

| # | Script | Why it exists |
| 0 | `00_bootstrap.sh` | Pinned clone + patches + container + conda + `install_all.sh`. Assembled from the commands that worked, but never run start-to-finish on a clean machine. |
|---|---|---|
| 1 | `resume_build.sh` | The main resume: GTSAM `make` (restarted at 61%), `make install`, `python-install`, then `gtsam_factors` and the pySLAM C++ core. |
| 2 | `build_gtsam_py.sh` | GTSAM's Python bindings came out corrupt — the `.so` existed but had no `PyInit` symbol. Purges the artifacts and rebuilds at `-j1`. |
| 3 | `build_gtsam_py2.sh` | The purge in (2) removed `python/CMakeFiles/gtsam_py.dir`, so `build.make` was gone and make had nothing to run. Regenerates it with `cmake .` first, then rebuilds. Run this one if (2) fails the same way. |
| 4 | `build_utils.sh` | `install_all_conda.sh` never got past step 60 (`install_pip3_packages.sh`), so `install_cpp.sh` had never run and `pyslam_utils` + 6 sibling modules were missing entirely. |
| 5 | `thirdparty.sh` | Same cause: `install_thirdparty.sh` had never run. Builds pydbow3/pydbow2/pyibow/orbslam2_features/g2opy and reports a per-library `.so` count at the end. |

## Status

Stage 0 is a reconstruction; stages 1-5 each succeeded when they were run, and the environment they produced runs
KITTI 06 end to end on both cores (RUNBOOK §7c). **The sequence as a whole has not been
re-run from a clean clone**, so treat the order above as a record of what worked, not as
a tested one-shot installer.

`thirdparty.sh` reports 0 `.so` for `thirdparty/pangolin` — pangolin does not build here
(GCC 15 rejects 8 files that are missing `#include <cstdint>`). That is a known gap, not
a script failure: it costs the 3D viewer, not the SLAM.

After any rebuild, reapply the source patches — pySLAM does not work without them:

```bash
./patches/apply_patches.sh
```
