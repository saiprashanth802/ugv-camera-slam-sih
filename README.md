# Sightline

**Camera-only navigation for a GPS-denied autonomous ground rover.** A hardware-free
proof of concept built for an overnight university hackathon feeding into Smart India
Hackathon (SIH).

Outdoor UGVs for search-and-rescue, agriculture and delivery operate exactly where
satellite positioning stops being trustworthy — under canopy, between buildings, indoors,
under jamming. Sightline demonstrates that the sensor already on the robot is enough to
navigate without it.

Every number on this page was measured on the runs recorded in `RUNBOOK.md`, not
estimated. Where something does not work, it says so.

---

## What is demonstrated

**Half A — perception on real imagery.** Monocular visual SLAM on outdoor phone footage:
a sparse 3D map and camera trajectory recovered from a single moving camera, with no
depth sensor and no positioning.

**Half B — the autonomy loop, live.** In Gazebo, RTAB-Map builds an occupancy grid from
the robot's camera and Nav2 plans and drives to a commanded goal pose with obstacle
avoidance. No GPS anywhere in the loop.

The two halves connect by narrative, not by a shared map — they are different coordinate
frames, and we say so rather than implying one map.

---

## Results

Visual SLAM, KITTI sequence 06 (1101 frames, 1222 m of travel). Trajectory error is
absolute pose error after Umeyama sim3 alignment — the only honest comparison for
monocular, which recovers no metric scale. Reproduce with `scripts/eval_trajectory.py`.

| Engine | s/frame | APE RMSE | as % of path | Frames tracked |
|---|---:|---:|---:|---|
| **C++ core + GTSAM** (default) | **0.04** | **49.5 m** | **4.05 %** | 1101 / 1101, 1 lost (0.09 %) |
| Python core (fallback) | 0.19 | 132.7 m | 10.86 % | 1101 / 1101, 1 lost (0.09 %) |

Map built: 321 keyframes, 11,893 points, 0 SLAM resets.

Autonomous navigation, Gazebo `turtlebot3_house`:

| Measurement | Value |
|---|---|
| Occupancy grid growth during the run | 78×53 → 202×205 cells @ 0.05 m |
| Goal commanded | (−6.21, 0.63) |
| Robot path | (−6.40, −1.86) → (−6.36, 0.47) |
| Final distance to goal | 0.21 m, inside Nav2 tolerance |
| Nav2 recovery behaviours triggered | 3 (normal; noted rather than hidden) |

---

## What this proves, and what it does not

Stating the second list is what makes the first one credible.

**Proven:** the vision → map → autonomous-navigation pipeline works end to end, on real
outdoor imagery and in simulation.

**Not claimed:**

- **Monocular recovers no metric scale.** The phone map is qualitative. No measured
  distance is quoted from it.
- **The simulated half is GPS-denied but not camera-only.** RTAB-Map does the RGB-D
  mapping and loop closure from the camera, but the odometry it consumes is Gazebo's
  wheel encoders (`/odom`); no `rgbd_odometry` node runs, and pure visual odometry does
  not survive the stock textureless worlds. Half A is the genuinely camera-only result.
- **Loop closure does not currently fire.** Place recognition finds candidates and they
  pass the consistency check; RANSAC Sim3 geometry verification rejects every one. The
  4 % drift above is what that costs. Diagnosed in detail in `RUNBOOK.md` §7c, not fixed.
- **Simulated depth is noise-free**, so the sim result looks cleaner than hardware would.
- **Robustness to real terrain, noise and lighting extremes is untested.** That needs
  field trials on real hardware — the next phase, not this one.

---

## Reproducing it

Built and verified on Fedora with an RTX 4060; everything runs in Docker.

### Half B — the simulated demo

Self-contained in this repository.

```bash
docker build -t ugv-slam:demo docker/    # once
./scripts/run_demo.sh                    # host: launches with GPU + GUI passthrough
./scripts/check_gpu.sh                   # inside: must print NVIDIA, not AMD
```

Then follow `RUNBOOK.md` §4. `scripts/pick_goal.py` reads the live occupancy grid and
returns a goal that is provably in free space — hand-picked coordinates land inside walls
and the planner aborts with no useful error.

### Half A — visual SLAM

```bash
./scripts/pyslam_build/00_bootstrap.sh   # pinned clone, patches, container, conda, build
```

Two things make this reproducible rather than approximate:

- **Upstream is pinned by commit** (`a5ff256…`). pySLAM publishes no release tags, and
  `patches/apply_patches.sh` refuses to run against any other tree rather than
  half-applying months from now.
- **The two patches in `patches/` are mandatory.** Without them pySLAM writes a 0-byte
  trajectory: one fixes two debug assertions that no caller can satisfy, the other
  switches the frontend pose optimiser to GTSAM because the g2o path is inert on this
  build (verified against upstream's own unit test — it leaves RMSE bit-identical).

Host-side tools:

```bash
python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt
./.venv/bin/python scripts/calibrate_camera.py --images 'media/calib/*.jpg'
./.venv/bin/python scripts/make_pyslam_settings.py phone_calib.yaml \
    -o vendor/pyslam/settings/SIGHTLINE_PHONE.yaml
```

The second step is not optional plumbing: `calibrate_camera.py` writes the ORB-SLAM3
format and pySLAM cannot parse it — it fails on the `%YAML:1.0` header before reading a
key, and namespaces intrinsics differently. `RUNBOOK.md` §7d has the details and the
`config.yaml` block that goes with it.

Calibration is validated against synthetic views from a known camera: it recovers
fx = 900.28 against a true 900, at 0.070 px RMS.

---

## Repository map

| Path | What |
|---|---|
| `SPEC.md` | Every locked decision with its reasoning, plus the risks and the rejected alternatives. |
| `RUNBOOK.md` | Every command, each section carrying its own verification status and date. |
| `docker/` | The `ugv-slam:demo` image, and the patch that gives the TurtleBot3 waffle a depth camera it does not ship with. |
| `patches/` | The two mandatory pySLAM source fixes, with the reasoning in each patch header. |
| `scripts/` | Calibration, pySLAM settings generation, trajectory scoring, goal selection, screen capture, GPU smoke test. |
| `scripts/pyslam_build/` | The pySLAM environment build, stage by stage. |
| `scripts/standin/` | Fabricates a stand-in clip and calibration so the phone-half pipeline can be rehearsed before real footage exists. Not part of the demo. |

Not in version control, and regenerable: `vendor/` (14 GB upstream clone), `media/`
(recordings), the built image tarball, and `phone_calib.yaml`.

---

## Open work

| Item | State |
|---|---|
| Loop closure | Localised to RANSAC Sim3 geometry verification; suspects ranked in `RUNBOOK.md` §7c. One hypothesis tested and disproved. |
| Pangolin 3D viewer | Does not build — conda's GCC 15 toolchain cannot see the system EGL headers. `--headless` avoids it; costs the 3D view, not the SLAM. |
| Outdoor walk footage | Not yet shot. |

## Roadmap

Each item answers a named limitation above, not a wishlist.

- **Stereo rather than RGB-D** — IR and structured-light depth wash out in sunlight.
- **Visual-inertial + wheel-odometry fusion** (VINS-Fusion, `robot_localization`) and a
  working loop closure — the two largest error terms today.
- **Learned features** (SuperPoint, ALIKED, LightGlue) for light robustness, trained on
  our 2 × 92 GB GPU cluster. The one component that genuinely needs that hardware.
- **Dense reconstruction** (DROID-SLAM) plus traversability and elevation mapping.
- **A field chassis** — Clearpath Husky or Jackal.

## Environment note

The reference machine has **hybrid graphics** (AMD 780M iGPU + RTX 4060). Without the
`__NV_PRIME_RENDER_OFFLOAD` variables set in `run_demo.sh`, the container renders on the
iGPU **with no error message** and Gazebo silently crawls. `check_gpu.sh` exists to catch
exactly that; run it before debugging anything else. See `RUNBOOK.md` §0.

## Licence

MIT — see `LICENSE`. Note that the patches in `patches/` are modifications to pySLAM and
are therefore GPLv3; the third-party licences are listed in that file.
