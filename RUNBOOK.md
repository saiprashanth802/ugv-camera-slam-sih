# RUNBOOK — Sightline (vision-based GPS-denied UGV navigation)

Companion to `SPEC.md`. SPEC holds the *decisions*; this holds the *commands*.

**Verification status** is marked on every section:
`[VERIFIED 2026-09-01]` = actually run on this laptop, output checked.
`[UNVERIFIED]` = written from docs, still to be run.

Host of record: Fedora 44, Ryzen 7840HS + **RTX 4060 8 GB**, driver 610.57.04,
Docker 29.6.0, nvidia-container-toolkit 1.19.1.

---

## 0. The one thing that will eat your night

SPEC §3 predicted GUI passthrough would be the biggest trap and prescribed logging out
into an X11 session. **That prediction was half wrong, and the real trap is worse:**

- **XWayland works fine.** No X11 session, no logout. GL apps in the container render
  correctly against `DISPLAY=:0` on a stock Fedora 44 Wayland session.
- **The actual trap is hybrid graphics.** This laptop has an AMD Radeon 780M iGPU *and*
  the RTX 4060. By default the container renders on the **iGPU** — everything "works",
  looks fine, and Gazebo is quietly crawling. You will not get an error.

The fix is three env vars, already baked into `scripts/run_demo.sh`:

```
-e __NV_PRIME_RENDER_OFFLOAD=1
-e __GLX_VENDOR_LIBRARY_NAME=nvidia
-e __VK_LAYER_NV_optimus=NVIDIA_only
```

**Always run `check_gpu.sh` first.** If it does not say `NVIDIA GeForce RTX 4060`,
stop and fix that before touching ROS.

---

## 1. Host prerequisites  [VERIFIED 2026-09-01]

```bash
nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv   # RTX 4060, 8188 MiB
docker --version                                                       # 29.6.0
rpm -q nvidia-container-toolkit                                        # 1.19.1-1
docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi -L
```

Last line must print the 4060. If it fails, the container toolkit is not wired into
Docker: `sudo nvidia-ctk runtime configure --runtime=docker && sudo systemctl restart docker`.

---

## 2. Build the demo image  [VERIFIED 2026-09-01 — builds clean]

Bake everything once, at home. **Never apt-install at the venue** (SPEC §3).

```bash
cd ~/claude_code_projects/sih_sightline/docker
docker build -t ugv-slam:demo .
```

Contents: `osrf/ros:humble-desktop-full` (Gazebo Classic 11 + RViz2) + `rtabmap_ros`
+ `navigation2`/`nav2_bringup` + TurtleBot3 (incl. `turtlebot3_gazebo`) + `gazebo_ros_pkgs`
+ teleop + mesa-utils. `TURTLEBOT3_MODEL=waffle` and `ROS_DOMAIN_ID=42` are preset.

Two non-obvious env choices in the Dockerfile, both deliberate:
- `GAZEBO_MODEL_DATABASE_URI=""` — otherwise Gazebo stalls for minutes fetching online
  models over a bad venue network.
- `ROS_LOCALHOST_ONLY=1` + `ROS_DOMAIN_ID=42` — stops your nodes from discovering
  another team's ROS2 traffic on the venue LAN, which presents as ghost topics.

### Backup the image (do this before you leave home)
```bash
docker save ugv-slam:demo | gzip > ~/claude_code_projects/sih_sightline/ugv-slam-demo.tar.gz
# restore on the backup machine:
gunzip -c ugv-slam-demo.tar.gz | docker load
```

---

## 3. Launch + smoke test  [VERIFIED 2026-09-01]

```bash
./scripts/run_demo.sh          # host: starts/attaches the container
./scripts/check_gpu.sh          # INSIDE container: must print PASS + RTX 4060
```

`run_demo.sh` mounts the project at `/ws`, so anything you write in the container
lands in the repo. Re-running it attaches to the running container rather than
starting a second one.

Extra shells into the same container: just run `./scripts/run_demo.sh` again.

---

## 4. The sim demo — one command  [VERIFIED 2026-09-02, end to end]

**Use the upstream demo launch.** RTAB-Map ships an officially maintained TurtleBot3
RGB-D demo that brings up Gazebo + RTAB-Map + Nav2 + RViz together:

```bash
export TURTLEBOT3_MODEL=waffle
ros2 launch rtabmap_demos turtlebot3_sim_rgbd_demo.launch.py
```

This replaces the hand-wired launch chain that earlier drafts of this runbook described.
Rolling our own RTAB-Map invocation cost hours and reproduced a worse version of what
this file already does correctly.

Verified 2026-09-02: it builds a live occupancy grid on `/map` (172x119 cells at 0.05 m)
and Nav2 drives to a commanded goal.

### The money shot, verified
```bash
ros2 action send_goal /navigate_to_pose nav2_msgs/action/NavigateToPose \
  "{pose: {header: {frame_id: map}, pose: {position: {x: -1.0, y: 1.0}, orientation: {w: 1.0}}}}"
```
Result on this machine: goal accepted, robot drove from (-3.15, 2.04) to (-1.25, 1.03)
against a target of (-1.0, 1.0). In the demo you do this by clicking **2D Goal Pose**
in RViz instead. Rehearse the click until it is muscle memory, and record a backup capture.

### Choosing a goal that will actually plan  [VERIFIED 2026-09-05]

Do not hand-guess goal coordinates. Verified on this machine: the goal `(-1.0, -0.3)`
looks like open floor on screen but sits inside a wall of `turtlebot3_house`, and
Nav2 aborts it every time:

```
planner_server: GridBased failed to generate a valid path to (-1.00, -0.30)
bt_navigator:   Goal failed
```

`scripts/pick_goal.py` removes the guesswork. It reads the live `/map` occupancy grid
plus the `map -> base_footprint` transform and returns a cell that is known-free, has
0.3 m of known-free clearance on every side, and sits ~2.5 m from the robot:

```bash
python3 /ws/scripts/pick_goal.py
# MAP 202x205 res=0.050 origin=(-8.03,-4.54)
# ROBOT map=(-6.39,-1.86)
# GOAL -6.21 0.63  (dist 2.50 m, 0.3m clearance all round)
```

A goal chosen this way planned and drove on the first attempt. Note the robot pose
must be read in the **map** frame (`tf2_echo map base_footprint`), not from `/odom` —
RTAB-Map corrects the map->odom transform, so the two frames diverge as the map
grows, and a goal computed from `/odom` will land in the wrong place.

---

## 5. The waffle has NO depth camera — the image patches it  [VERIFIED 2026-09-02]

**SPEC.md §2 is wrong on this point.** It chose the waffle because it "has a depth camera
(needed for RTAB-Map RGB-D)". Checked against `ros-humble-turtlebot3-gazebo` 2.3.8:
waffle and waffle_pi each carry exactly three sensors — imu, ray (lidar), and a
**monocular RGB camera**. There is no depth sensor. Leftover `camera_depth_*` TF frames
in the URDF are what make the assumption look correct until you list the topics.

`docker/patch_depth_camera.py` fixes this at build time, applying the modifications the
RTAB-Map maintainer documents in the "Requirements" header of
`rtabmap_demos/launch/turtlebot3/turtlebot3_sim_rgbd_demo.launch.py`:
sensor type `camera` -> `depth`, image 1920x1080 -> 640x480, and the
`camera_rgb_optical_frame` link/joint rework so image topics resolve in the optical
convention (without it the map comes out rotated 90 degrees).

**Do not improvise this patch.** A hand-rolled earlier version changed the far clip and
stripped the `<noise>` block; the camera then published at a healthy 28 Hz while
rendering **entirely blank frames**, and RTAB-Map reported `features=0, lost=true` with
the robot visibly moving. Nothing errored. Follow the upstream recipe verbatim.

Verified after patching: RGB 640x480 renders real content, depth is 9999/9999 finite
in 0.75–4.56 m.

### Verifying the camera yourself
```bash
ros2 topic hz /camera/image_raw          # ~30 Hz (measured 30.04 on 2026-09-05)
ros2 topic hz /camera/depth/image_raw    # ~30 Hz (measured 29.94 on 2026-09-05)
ros2 topic echo /rtabmap/odom_info_lite --once | grep -E "lost|features|inliers"
```
`features: 0` means the camera is rendering blank or the scene is too dark — that is a
rendering problem, not a SLAM tuning problem. Do not tune RTAB-Map to fix it.

---

## 6. Known limitation — odometry is NOT visual  [VERIFIED 2026-09-02]

**This affects what you may claim to judges.**

The upstream demo runs no `rgbd_odometry` node. RTAB-Map does RGB-D **mapping** and loop
closure from the camera, but the **odometry it consumes is Gazebo's wheel encoders**
(`/odom`). The sim half is therefore genuinely **GPS-denied**, but it is not **camera-only**.

Pure visual odometry was attempted and does not survive these worlds:

| World | features | inliers | outcome |
|---|---|---|---|
| `turtlebot3_world` | 43 | 0 | odometry lost, pose frozen at 0,0,0 |
| `turtlebot3_house` | 0 | 0 | interior too dark (pixel mean 49, max 85) |

Both stock worlds are textureless or dim — there is not enough visual structure for
`rgbd_odometry` to find inliers. This is a property of the simulated worlds, not of the
approach.

**So be precise in the pitch:**
- The **phone half** (ORB-SLAM3 monocular, §7) is the genuinely camera-only result.
- The **sim half** proves the map -> plan -> autonomous-drive loop with no GPS.
- Say "GPS-denied", and say the camera builds the map. Do not say the sim navigates on
  vision alone — a robotics judge will ask which node produces odometry.

If camera-only odometry in sim is wanted, the fix is a texture-rich custom world, not
RTAB-Map parameters. That is unbuilt work, not a tuning exercise.

---

## 7. Phone half — calibration + outdoor walk  [calibration VERIFIED 2026-09-01]

### 7a. Calibrate  [VERIFIED — recovers known intrinsics to 0.03 %]
Print a 9x6-inner-corner chessboard, tape it **flat** to something rigid.
Shoot ~20 stills at varied angles, **same phone / lens / resolution / zoom** as the walk.

```bash
cd ~/claude_code_projects/sih_sightline
./.venv/bin/python scripts/calibrate_camera.py --images 'media/calib/*.jpg'
# or from a slow video:
./.venv/bin/python scripts/calibrate_camera.py --video media/calib.mp4 --every 15
```
Writes `phone_calib.yaml` in ORB-SLAM3 monocular format. **RMS must be < 1.0 px** —
above that, the board was curled or you shot too few angles. Reshoot.

pySLAM cannot read that file; §7d converts it. Note also that the
`ORBextractor.nFeatures: 1250` this script bakes in is **not** carried through — 2000
measurably beats it (§7d).

Validation done 2026-09-01: run against synthetic views from a known camera
(fx=fy=900, cx=640, cy=360 at 1280x720) it recovered fx=900.28, cx=639.65,
RMS 0.070 px. The script and the YAML format are trustworthy.

### 7b. The walk  [SHOT 2026-09-06 — but NOT to this brief; see §7e]
**A shoot happened on 2026-09-06 and two clips came back. Neither was shot to the rules
below** — pre-dawn rather than daylight, covered walkway and indoor corridor rather than
outdoors, and delivered through WhatsApp, which re-encoded them. No chessboard stills were
shot at all, so §7a never ran. What that cost, and what was recovered anyway, is §7e.
The rules below are unchanged and are the brief for the reshoot; the non-engineer version
of them is `docs/CAMERA_DAY.md`.

- Shoot **outdoors, in daylight** (SPEC §2 — this is the disclosed tested condition).
- **Gimbal on.** Smooth motion is the single biggest factor in mono tracking survival.
- Walk a **loop** and return to the start. **Caveat: loop closure does not currently fire at
  all** (§7c, known-bad) — walk the loop anyway so the footage is ready when it is fixed, but
  do not build the narration around the loop visibly snapping shut.
- Avoid: fast rotation with no translation (mono cannot triangulate from pure rotation —
  this is the classic way to lose tracking), blank walls, and large moving objects.
- Lock the phone to one video mode so the intrinsics stay valid.

### 7c. Run SLAM on the clip  [pySLAM VERIFIED end to end 2026-09-05]
**Do NOT compile ORB-SLAM3 at the venue** (SPEC §3, risk #1). Either way the phone map is
played back from a **pre-recorded clip** — never live on stage.

#### pySLAM is NOT "pip, no compile" — SPEC §2 was wrong

Verified 2026-09-05. Three corrections to what SPEC assumed:

1. **`pip install pyslam` gets you the wrong package.** The name `pyslam` on PyPI is an
   unrelated chat/comms library by a different author. The SLAM one is
   `github.com/luigifreda/pyslam`, installed by cloning and running `./install_all.sh`.
2. **It compiles C++ and pulls ~GB of models.** It is not a lightweight pip install. It
   must be built at home and baked, exactly like the ROS image (SPEC §3).
3. **Neither Ubuntu 22.04 nor 24.04 works with the plain venv install.** Both were
   tried on 2026-09-05 and both fail, for *different* reasons. This is the single most
   time-expensive thing to rediscover, so it is written out in full:

   | Base | Python | Failure |
   |---|---|---|
   | `ubuntu:22.04` | 3.10.12 | `ERROR: Package 'pyslam' requires a different Python: 3.10.12 not in '>=3.11.9'` |
   | `ubuntu:24.04` | 3.12.3 | pySLAM pins `scikit-image==0.21.0`, which has **no cp312 wheel**. pip falls back to a source build, whose pythran/GCC-13 compile dies with `fatal error: template instantiation depth exceeds maximum of 900`. |

   The two constraints leave a **narrow gap at Python 3.11**, and that is not an
   accident — it is what upstream targets:

   ```
   pyproject.toml:            requires-python = ">=3.11.9"
   pyproject.toml:            "scikit-image==0.21.0"
   scripts/pyenv-conda-create.sh:  PYSLAM_PYTHON_VERSION="${2:-3.11.9}"
   ```

   Python 3.11 satisfies `>=3.11.9` **and** has a prebuilt `scikit-image==0.21.0`
   wheel, so nothing compiles. No stock Ubuntu image ships 3.11.9.

   **Therefore: install conda first and let the installer take its conda branch.**
   `install_all.sh` checks `command -v conda` and, if found, calls
   `install_all_conda.sh`, which creates the env at exactly Python 3.11.9. The venv
   branch is the trap; the conda branch is the supported path.

   ```bash
   docker exec pyslam-build bash -lc '
     cd /tmp && curl -fsSL -o mf.sh \
       https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh \
     && bash mf.sh -b -p /opt/conda'
   docker exec pyslam-build bash -lc '
     export PATH=/opt/conda/bin:$PATH; source /opt/conda/etc/profile.d/conda.sh
     cd /pyslam && ./install_all.sh 2>&1 | tee install_conda.log'
   ```

The build runs in a container against the repo at `vendor/pyslam` (gitignored):

```bash
docker run -d --name pyslam-build --gpus all \
  -v "$PWD/vendor/pyslam:/pyslam:rw" -e DEBIAN_FRONTEND=noninteractive \
  --security-opt label=disable ubuntu:24.04 sleep infinity
docker exec pyslam-build bash -lc 'apt-get update -qq && apt-get install -y -qq \
  sudo git curl wget unzip build-essential cmake pkg-config python3 python3-dev \
  python3-venv python3-pip libglew-dev libgl1-mesa-dev libglu1-mesa-dev libeigen3-dev \
  libsuitesparse-dev libboost-all-dev libopencv-dev ca-certificates rsync'
docker exec pyslam-build bash -lc 'cd /pyslam && ./install_all.sh 2>&1 | tee install.log'
```

`install_all.sh` detects `/.dockerenv` and skips its sudo prompt, so it runs unattended.
It creates its venv at **`/root/.python/venvs/pyslam` inside the container**, NOT in the
mounted repo — so the container must be `docker commit`ed (and `docker save`d) to keep
the build. Destroying the container loses the install.

#### Build constraints that cost a machine crash

`make -j$(nproc)` is what OOM-killed this laptop mid-build. `nproc` reports **16**; the
box has 14 GiB. Every build step here runs under a **`-j2` shim**. If you rebuild, keep
it. `/home` sits at 89% (38 GB free), so watch it during any rebuild.

The conda env lives at `/root/.python/venvs/` **inside** container `pyslam-build`, not in
the mounted repo, and the container has been OOM-killed once. It survives a restart
(`docker start pyslam-build`) but not a `docker rm`. Backups are on the USB drive, made
with `docker export` (streams, needs no local layer — `docker commit` needs ~37 GB and
will not fit).

#### Source patches: the first two are required — pySLAM does not work without them

`vendor/` is gitignored, so `patches/` in this repo is the **only** durable record.
After any fresh clone or rebuild:

```bash
./patches/apply_patches.sh      # idempotent; already-applied patches are skipped
```

| Patch | Fixes |
|---|---|
| `0001-map_point-fix-remove_frame_view-asserts` | Two `__debug__` asserts in `MapPoint.remove_frame_view()` that no caller can satisfy. Killed the Python core at frame 13 (first outlier) and again at frame 93. |
| `0002-use-gtsam-frontend-pose-optimizer` | The C++ core's g2o pose optimizer is **inert on this build** — it never writes the optimised pose back, so 100% of points were flagged outliers and tracking reset 152 times. Switches `kOptimizationFrontEndUseGtsam` to True. |
| `0003-pangolin-cstdint-gcc15` | *Not required to run SLAM.* Adds `<cstdint>` to nine pangolin headers/sources that GCC 15 no longer includes transitively. Solves cause (1) of the parked 3D viewer; cause (2) remains open, so pangolin still does not build. |

#### Measured results on KITTI 06, both cores, after the patches

Both cores now process **1101/1101 frames with 1 lost frame (0.09%)** and 0 SLAM resets.
Score them with `scripts/eval_trajectory.py` (Umeyama sim3 alignment — monocular has no
metric scale, so a raw position diff is meaningless):

```bash
python scripts/eval_trajectory.py results/<run>/trajectory_final.txt \
                                  data/videos/kitti06/groundtruth.txt
```

| Core | s/frame | APE RMSE vs groundtruth | % of 1222 m path |
|---|---|---|---|
| C++ + GTSAM (`PYSLAM_USE_CPP=true`, default) | **0.04** | **49.5 m** | **4.05%** |
| Python (`PYSLAM_USE_CPP=false --headless`) | 0.19 | 132.7 m | 10.86% |

**Use the C++ core.** It is 5x faster *and* 2.7x more accurate — which inverts the earlier
assumption that the Python core was the "correct but slow" reference. The two agree with
each other to 4.5% of path length, so they are running the same algorithm; the C++ one
just optimises better. Keep the Python core as the fallback if `cpp_core.so` ever breaks.

The earlier "20-30 s/frame" figure for the Python core was wrong — it included startup and
the one-time vocabulary download. A full 1101-frame run takes about 4 minutes.

#### Known-bad: loop closure never fires

**0 loop closures across all 1101 frames of KITTI 06 — a sequence that demonstrably
closes.** This is the direct cause of the 4% drift above; nothing ever corrects it.
`pydbow3` builds and imports, so this is a live bug, not a missing dependency.

Investigated 2026-09-05 and **localised, not fixed.** The pipeline is healthy right up
to the last stage, which is worth knowing before anyone re-debugs it from the top:

| Stage | Result |
|---|---|
| DBoW3 place recognition | **Works.** Runs on every keyframe, ~0.09 s each. |
| Candidate detection | **Works.** 309 keyframes produced candidates (up to 4 each). |
| Group consistency check | **Works.** 108 checks, candidates pass through. |
| **RANSAC Sim3 geometry verification** | **Fails, always.** 173 candidates "didnt converge". |

The failure signature is the interesting part: `num_inliers` is **0 in 159 of those 173
cases**, while the same candidates carry a *median of 156* feature matches (p90 386,
max 782). Only 75 candidates were thrown out for genuinely too few matches (min 20).
Hundreds of matches yielding zero inliers is not what a merely hard scene looks like.

**Tested and ruled out — the RANSAC iteration budget.** `loop_closing.py:298` calls
`solvers[i].iterate(5)` exactly once per candidate although the solver above it is
configured `set_ransac_parameters(0.99, 20, 300)`, i.e. 5 draws to find 20 inliers
against a 300-iteration budget, with no loop back (upstream ORB-SLAM3 iterates until
convergence or exhaustion). Raising it to `iterate(300)` **did not produce a single
closure and made the run worse**: keyframes reaching loop closing collapsed 455 -> 24,
relocalization attempts went to 1014 with 1010 failures, and lost frames rose 1 -> 5.
The longer geometry check starves the shared loop-detection queue that relocalization
also feeds from. Reverted. Do not retry this.

**Remaining suspects, in order:** (a) the 3D map points handed to `Sim3Solver` are too
poorly triangulated for a 3D-3D fit — plausible given monocular and the 4% drift;
(b) a coordinate-frame or units mismatch in `solver_input_data` (`points_3d_w2`,
`sigmas2_1/2`); (c) a bug in the `sim3solver` binding itself. Note the Sim3 optimizer
switch (`kOptimizationLoopClosingUseGtsam`) is **not** a suspect — `optimize_sim3` is
only reached *after* RANSAC converges, which never happens, so g2o-vs-GTSAM cannot be
the cause here.

Consequences, both of which matter on stage:

- The map will visibly drift on any loop you walk. Do not promise a closing loop.
- SPEC §1 calls loop closure "the visually impressive moment". It is currently not
  available. Plan the phone walk narration without it until this is fixed.

#### Parked: the pangolin 3D viewer does not build

Costs the 3D viewer only — **SLAM itself is unaffected**, and `--headless` is the flag
that avoids it (`main_slam.py` sets `viewer3D = None`, so no X passthrough is needed).
Without pangolin the phone half can produce trajectory plots but not the live
"recognizable real SLAM look" that SPEC §1 asks for.

Two separate causes, both traced 2026-09-05:

1. **GCC 15 no longer transitively includes `<cstdint>`.** Nine headers/sources need it
   added, not the eight in the earlier note — `include/pangolin/factory/factory_registry.h`
   was missing from that list. **This part is solved**; driving the fix from the
   compiler's own `note: 'uint32_t' is defined in header '<cstdint>'` diagnostics
   converges without needing the list to be right. The nine edits are recorded as
   `patches/0003-pangolin-cstdint-gcc15.patch` — reapply them with
   `./patches/apply_patches.sh` rather than re-deriving them from this paragraph.
2. **The conda toolchain cannot see `/usr/include`.** `conda activate pyslam` puts
   **g++ 15.3.0** on PATH (the *system* gcc is 13.3 — checking the wrong one is
   misleading), and it compiles against `$CONDA_PREFIX/x86_64-conda-linux-gnu/sysroot`.
   So `apt-get install libegl1-mesa-dev` installs headers the build genuinely cannot
   find. Pangolin then fails on `EGL/egl.h`, and after that on `dc1394/conversions.h`,
   and so on through its optional video drivers.

**Do not set `CPATH=/usr/include` to bridge this.** It drags the system glibc headers
into a conda-glibc build and every translation unit dies on `bits/timesize.h`. Copying
just the needed headers (`EGL/`, `KHR/`) into `$CONDA_PREFIX/include` is the safe
version and is already done.

The next thing to try is **disabling pangolin's optional video drivers at configure
time** rather than satisfying them one at a time — the dc1394 (FireWire camera) driver
is not something this demo needs. Installing the missing libs into the conda env was
deliberately *not* attempted: that env is the only thing that runs SLAM, and dependency
churn in it is a worse risk than a missing viewer.

#### Good news: the test sequence ships with the repo

No dataset download is needed to prove the toolchain. `data/videos/kitti06/` contains a
real 46 MB `video_color.mp4` plus `groundtruth.txt` and `times.txt`, and `config.yaml`
already defaults to `type: VIDEO_DATASET` pointing at it. That same `VIDEO_DATASET` mode
is what the **phone clip** will use — so proving KITTI runs proves the path the phone
footage will take, and only the settings YAML (from `calibrate_camera.py`, §7a) changes.

---

### 7d. Wiring the walk clip into pySLAM  [VERIFIED 2026-09-06 on a stand-in clip]

§7c ends by saying the phone clip takes the same `VIDEO_DATASET` path as KITTI and "only
the settings YAML changes". That is true of the *path*. It is not true that
`phone_calib.yaml` can be dropped in as that settings YAML — it cannot be loaded by
pySLAM at all. Rehearsed end to end on a stand-in clip 2026-09-06, so that the real
footage is a file swap and not a debugging session.

**`vendor/` is gitignored, so the `config.yaml` edit below is not in git.** This section
is its only durable record. After any fresh clone, redo it.

#### The two formats are not compatible, and neither failure is graceful

`calibrate_camera.py` writes the **ORB-SLAM3** format. pySLAM reads its own:

| | calibrate_camera.py writes | pySLAM reads |
|---|---|---|
| Header | `%YAML:1.0` (OpenCV FileStorage) | plain YAML, parsed by PyYAML |
| Intrinsics | `Camera1.fx` (per-camera namespace) | `Camera.fx` (`pyslam/config.py:239`) |
| Features | `ORBextractor.nFeatures` | `FeatureTrackerConfig.nFeatures` |
| Viewer | — | `Viewer.on` |

The header alone is fatal, before a single key is read:

```
yaml.scanner.ScannerError: while scanning a directive
  in "phone_calib.yaml", line 1, column 1
```

#### Generate the settings file — do not hand-write it

```bash
./.venv/bin/python scripts/make_pyslam_settings.py media/calib/phone_calib.yaml \
    -o vendor/pyslam/settings/SIGHTLINE_PHONE.yaml
```

It reads the ORB-SLAM3 file with `cv2.FileStorage` (the only reader that accepts the
`%YAML:1.0` directive), writes the pySLAM keys, then **parses its own output back with
PyYAML** and asserts every key `config.py` requires is present. If that readback fails
you find out here, not eight seconds into a run in front of judges.

`phone_calib.yaml` stays the archival record of what the phone measured; the generated
file is derived. Never hand-edit the derived one — rerun the script.

#### The config.yaml block

Paste over `VIDEO_DATASET:` in `vendor/pyslam/config.yaml` (the script prints this too):

```yaml
VIDEO_DATASET:
  type: video
  sensor_type: mono
  base_path: ./data/videos/phone_walk
  settings: settings/SIGHTLINE_PHONE.yaml
  name: walk.mp4
```

**Both `groundtruth_file` and `timestamps` must be absent, not blank.** A phone walk has
neither. If the key is present and the file is not, pySLAM raises `FileNotFoundError`
(`pyslam/io/dataset.py:211`); absent keys fall through cleanly to
`GroundTruthType.NONE` (`pyslam/io/ground_truth.py:150`). Keep the KITTI lines commented
out below it — that is the scored reference run and you will want it back.

#### Run it  — this command was not written down anywhere before

```bash
docker start pyslam-build
docker exec pyslam-build bash -lc '
  source /opt/conda/etc/profile.d/conda.sh && conda activate pyslam
  cd /pyslam && export PYSLAM_USE_CPP=true
  python main_slam.py --headless'
```

Results land in `vendor/pyslam/results/metrics_<UTC timestamp>/`. **The container clock
is UTC**, so the newest directory is stamped ~5.5 h behind local time — sort by mtime,
not by name. `other_metrics_info.txt` carries the frame/lost counts.

#### The stand-in rehearsal, and what it does and does not prove

No phone footage existed yet, so the clip was faked honestly: KITTI 06's colour video
resampled to **1280x720 @ 30 fps** (`cv2.VideoWriter`, `mp4v` — Fedora's ffmpeg has no
libx264 and its openh264 decoder fails on this input). Anisotropic scaling is exact in
the pinhole model, so the implied intrinsics are exactly derivable, and 22 synthetic
chessboard views were rendered from *those* intrinsics and fed to the real
`calibrate_camera.py` — the same validation trick as §7a. It recovered
fx 738.22 against a true 738.2355 at **0.098 px RMS**.

**Proven:** the whole chain runs — calibration YAML → generated settings → `config.yaml`
→ `main_slam.py --headless` on the C++ core → a trajectory file, on a clip with no
groundtruth and no timestamps, at a resolution and frame rate nothing else here uses.

**Not proven:** anything about how the real walk will score. The stand-in is an upscaled
re-encode of the sequence the reference numbers came from, and each row below is a single
run, not a repeated measurement.

#### Finding: the 1250 baked into calibrate_camera.py is the wrong feature count

The two stand-in runs differ **only** in `FeatureTrackerConfig.nFeatures`:

| Run | nFeatures | Frames | Lost | Poses | APE RMSE | % of path |
|---|---:|---|---:|---:|---:|---:|
| stand-in | 1250 (inherited from the calib file) | 1101/1101 | 1 | 891 | 99.5 m | 9.89% |
| stand-in | **2000** | 1101/1101 | **0** | **1089** | **10.1 m** | **0.83%** |
| KITTI 06 native, C++ core (§7c reference) | 2000 | 1101/1101 | 1 | 1088 | 49.5 m | 4.05% |

`calibrate_camera.py` hard-codes `ORBextractor.nFeatures: 1250`, which has nothing to do
with calibration — it rides along because ORB-SLAM3 settings files bundle intrinsics and
extractor config in one file. Carried into pySLAM unexamined it dropped 198 poses and one
tracked frame. `make_pyslam_settings.py` therefore **defaults to 2000 and reports the
calib file's value rather than obeying it**; override with `--features` if a run on the
real footage argues otherwise.

`config.yaml` has been left pointing at **KITTI 06**, not at the stand-in, so that
fallback-ladder rung 2 keeps working and nobody demos the fake clip by accident. The
phone block sits commented directly beneath it; swap the comments when the footage
lands. `settings/SIGHTLINE_PHONE.yaml` and
`vendor/pyslam/data/videos/phone_walk/walk.mp4` are left in place so the rehearsal can
be repeated — both are gitignored and regenerable via `scripts/standin/`.

Do not read the 0.83% as "better than KITTI". Upsampling adds no information; it changes
what the ORB pyramid sees, and a single run of a monocular pipeline with RANSAC in it is
not a measurement. The honest claim is that the plumbing is verified and 1250 is worse
than 2000 on this clip.

### 7e. The real walk — what came back, and what it cost  [VERIFIED 2026-09-06, all three clips run end to end]

§7d rehearsed the ingest path on a fabricated clip so that real footage would be "a file swap
and not a debugging session". The footage landed on 2026-09-06 and the swap did hold — both
clips ran end to end on the first attempt. Everything that went wrong went wrong **before** the
pipeline, in the shoot and the delivery, and that is what this section is mostly about.

#### What was delivered

Three takes came back, all through WhatsApp. **All three are ~1.4–1.6 Mb/s re-encodes** — the
phone originals were never transferred.

| | Source file | Native | Aspect | Frames | Duration | Size | Ingested as |
|---|---|---|---:|---:|---:|---:|---|
| **A** | `WhatsApp Video 2026-09-06 at 5.43.59 AM.mp4` | 848×478 | 1.774 | 1953 | 65.2 s | 11.0 MB | `walkA.mp4` |
| **B** | `WhatsApp Video 2026-09-06 at 5.33.42 AM.mp4` | 1280×544 | 2.353 | 3771 | 125.7 s | 25.7 MB | `walkB.mp4` |
| **C** | `WhatsApp Video 2026-09-06 at 5.43.59 AM (1).mp4` | 1280×544 | 2.353 | 5063 | 169.0 s | 29.2 MB | `walkC.mp4` |

**Clip C is a third take, not a duplicate of A.** It carries the same message timestamp in its
filename and got WhatsApp's `(1)` collision suffix, which is exactly what a duplicate download
looks like. It is a different, longer recording — 169 s against A's 65 s — and it is the
longest take of the three. It has never been run. Check the frame count, never the filename.

#### Four deviations from the brief, and what each one cost

`docs/CAMERA_DAY.md` and §7b asked for daylight, outdoors, gimbal, chessboard stills, and
untouched original files. None of those five held.

| Asked for | What happened | Cost |
|---|---|---|
| Broad daylight, outdoors | Shot ~05:30–05:45, before sunrise. A is a covered walkway with a dark sky visible; B is an interior corridor under fluorescent light. | The disclosed tested condition in SPEC §2 is *outdoor daylight*. **We currently have no footage in the condition we claim.** |
| Chessboard stills, same phone/lens/mode | None shot. §7a never ran. | No measured intrinsics. Recovered geometrically instead — see below — at roughly ±10 % instead of 0.03 %. |
| Original files, not through a chat app | Delivered through WhatsApp. | Re-encoded to ~1.4 Mb/s, and A additionally downscaled to 848×478. Compression noise is what a feature detector eats. |
| Gimbal on, no spinning on the spot | Not verifiable from the footage, but the motion statistics say handheld for at least part of B. | B spends 12.7 % of frames in violent motion and loses tracking; see the two tables below. |

The polished granite floor in both clips is a fifth problem nobody thought to warn about: it
mirrors the ceiling lights, so a large fraction of the strongest corners in frame are
**specular highlights that move with the camera rather than with the world**. Add it to the
card before the reshoot.

#### Intrinsics with no chessboard — vanishing-point recovery

`scripts/estimate_focal_vp.py`. These are corridors: floor joints, wall edges and handrails
give two mutually orthogonal world directions. With the principal point assumed at the image
centre and square pixels, orthogonality of the two vanishing points gives

```
f² = −(v₁−c)·(v₂−c)
```

which is a measurement rather than a guess. The script runs an LSD line detector, finds the
dominant vanishing point by RANSAC, removes its inliers, finds a second one in the remainder,
skips blurred frames (Laplacian variance < 60) and near-parallel VP pairs (which carry almost
no focal information), and takes the **median over ~140 sampled frames**.

```bash
./.venv/bin/python scripts/estimate_focal_vp.py     # prints f, HFOV and f/width per clip
```

| Clip | f (px) | f / width | HFOV |
|---|---:|---:|---:|
| A | 710.3 | 0.838 | 61.7° |
| B | 1110.2 | 0.867 | 59.9° |

**The cross-check is the point.** The two clips were measured independently, at different
capture resolutions, and agree on f/width to 3.5 % — consistent with one phone and one lens,
which is what makes the number believable at all. Results are written to
`media/calib/phone_calib_walkA.yaml` and `..._walkB.yaml` in ORB-SLAM3 format, so they go
through `make_pyslam_settings.py` (§7d) unchanged, and each file carries its own provenance
header saying it is estimated rather than measured.

**What this does not give you.** Distortion is **assumed zero** — defensible only because
phone video pipelines correct it in-camera, and not verified here. The principal point is
**assumed centred**. Confidence on the focal is roughly ±10 %, against the 0.03 % §7a
achieves with a board. Replace these files with a real `calibrate_camera.py` run before
quoting any number derived from them as measured.

**Watch the aspect ratios.** A is 1.774 (16:9); B and C are 2.353. That is not a rescale of
the same frame — 848×478 scaled to 1280 wide would be 1280×721, not 1280×544. If B and C are
vertically cropped, the centred-principal-point assumption survives **only if the crop was
symmetric**, and nothing here verifies that. `cy` for B and C is the weakest number in either
file.

#### Running a specific clip

`scripts/set_dataset.py` swaps the active `VIDEO_DATASET` block in `vendor/pyslam/config.yaml`
and always leaves the KITTI 06 reference run commented directly beneath it, one edit away
(§7c, fallback-ladder rung 2).

```bash
./.venv/bin/python scripts/set_dataset.py A        # or: B | kitti
docker start pyslam-build
docker exec pyslam-build bash -lc '
  source /opt/conda/etc/profile.d/conda.sh && conda activate pyslam
  cd /pyslam && export PYSLAM_USE_CPP=true
  python main_slam.py --headless'
```

As in §7d, `groundtruth_file` and `timestamps` stay **absent, not blank**. Results land in
`results/metrics_<UTC>/` — container clock is UTC, so sort by mtime — and were copied to
`results/walkA_run/` and `results/walkB_run/` so the next run does not bury them.

#### Results

Both clips tracked to the end of the footage. **There is no ground truth for a phone walk, so
there is no APE and no trajectory-error number here** — the KITTI figures in `README.md` remain
the only scored ones.

| Clip | Frames processed | Lost | Poses, online | Poses, final |
|---|---:|---:|---:|---:|
| **A** | 1953 / 1953 | 1 (0.05 %) | 1938 | **1889** |
| **B** | 3771 / 3771 | 3 (0.08 %) | 3707 | **1648** |
| **C** | 5063 / 5063 | 5 (0.10 %) | 5049 | **1318** |

The lost-frame counts flatter B. **Clip B's final trajectory retains 1648 of its 3707 online
poses — 56 % of the run is discarded in the final map**, against a 2.5 % drop for A. Watching
it run, B sat in a failed relocalization loop (`num_matched_map_points: 0`) for a long stretch
around frame 2350 while the online trajectory stopped growing. `percent_lost` counts frames the
tracker declared lost; it does not count a map that was rebuilt from scratch after one. **Read
the online-vs-final gap, not `percent_lost`.** Not further diagnosed.

Why B is the harder clip, measured at a common 848-px width so the comparison is of the walk
and not of the encoder (both clips, every 2nd frame):

| | Clip A | Clip B |
|---|---:|---:|
| Sharpness, median Laplacian variance | 95.3 | 107.5 |
| Frames blurry (< 100) | 54.8 % | 45.7 % |
| ORB keypoints, median | 967 | 823 |
| Keypoint-starved frames (< 300) | 9.6 % | 11.6 % |
| Consecutive matches, median | 623 | 575 |
| Flow px/frame, median | 1.73 | 1.79 |
| Flow px/frame, p90 | 5.48 | **17.47** |
| Flow px/frame, p99 | 27.95 | 35.37 |
| Frames in violent motion (> 15 px/frame) | 5.9 % | **12.7 %** |

Sharpness and feature counts are close, and B is marginally the sharper clip. The difference
that matters is motion: **B's 90th-percentile inter-frame flow is 3.2× A's**, and it spends
more than twice as long above the 15 px/frame threshold. Median flow is nearly identical, so
this is not a faster walk — it is the same walk with far worse tails, which is what handheld
jerk and turning look like. Over half of *both* clips is blurry by the < 100 threshold, which
is the pre-dawn exposure time.

**Loop closure still does not fire**, on real footage as on KITTI. The detector proposes
candidates and closes none — the §7c signature, now confirmed to be a property of the pipeline
rather than of KITTI. Note the pySLAM logs are appended across runs, so this is a weaker
observation than the per-run frame counts above.

#### What to do with this

1. **Reshoot to the card.** Outdoor, daylight, gimbal, chessboard stills first, files off the
   phone by cable or cloud link — never a messaging app. That single reshoot fixes the SPEC §2
   condition mismatch, the ±10 % intrinsics and most of the blur in one go.
2. ~~Run clip C.~~ **Done 2026-09-06 — C is the worst of the three, not the best.**
   Being the longest take did not help it: it keeps **1318 of 5049 online poses (26.1 %)**,
   against B's 44.5 % and A's 97.5 %. Its map is not a blob like B's — extent 5.32 × 9.73
   in map units, a long straight corridor run — but the last third degenerates into a
   tangle of 11 discontinuities, which is what a repeatedly-relocalizing tracker draws.
   C's own vanishing-point focal estimate is also the weakest of the three: only **31**
   frames yielded a usable orthogonal VP pair (A: 94, B: 51), IQR 789–1266 px, and its
   f/width of **0.771** sits well below A's 0.838 and B's 0.867. Three clips agree less
   well than the two did — see `media/calib/phone_calib_walkC.yaml`.
3. **Demo clip A, not B**, if a phone clip is shown before a reshoot. It is the shorter,
   steadier take and the only one whose final trajectory keeps essentially all of its poses.
4. `config.yaml` was left pointing at **`kitti`** after the clip-C run, so fallback-ladder
   rung 2 works and nobody demos a walk clip by accident. `scripts/set_dataset.py A|B|C|kitti`
   swaps it.

#### Verdict: demo clip A

All three ran under identical settings (C++ core + GTSAM, `nFeatures: 2000`, headless).
Ranked by the only metric that separates them — how much of the walk survives into the
final map:

| | Coverage of clip | Final / online poses | Discontinuities | Map |
|---|---:|---:|---:|---|
| **A** | **96.7 %** | **97.5 %** | **0** | 214 kf / 12,124 pts |
| B | 43.7 % | 44.5 % | 31 | 180 kf / 9,457 pts |
| C | 26.0 % | 26.1 % | 11 | 124 kf / 7,984 pts |

A is not marginally better, it is the only one that works. Its recovered path is a clean
**U** — straight, turn, straight, turn, back — with zero discontinuities, matching the
walkway. It does not close the loop, so nothing on stage depends on the loop closure §7c
documents as broken. **A is also the shortest and lowest-resolution take**, which is worth
saying to whoever shoots the reshoot: steadiness beat both duration and pixel count here,
by a factor of two.

#### Demo artifacts

```
media/phone_walk_slam_demo.mp4        81 s, 1996x720 — the full phone half
                                        0-65 s  footage + top-down map, side by side
                                        65-81 s 3D sparse map, orbiting fly-around
media/phone_walk_map_3d.mp4           16 s — the 3D orbit on its own
media/phone_walk_slam_demo_small.mp4  the 81 s cut at ~2.6 Mb/s, for sharing
media/phone_walk_clip_selection.png   all three trajectories at one shared scale
```

Rendered by `scripts/make_slam_demo.py` (left: the clip with its ORB features drawn on;
right: the top-down trajectory growing in step) and `scripts/render_map_3d.py` (the
orbit). Both carry **"scale is ARBITRARY — monocular"** and **"0 loop closures"** on
every frame on purpose — those are the two questions a judge asks, and the answer should
already be on screen.

Pose-to-frame alignment in the side-by-side is a **linear index mapping** (1889 poses over
1953 frames), not a recorded correspondence — pySLAM's KITTI-format trajectory carries no
frame index. Drift is bounded by the 64 unmatched frames, under half a second at the end.
Fine for a demo; do not use this video to make a timing claim.

##### Getting a 3D map at all, without pangolin  [patches/0004]

The 3D view is the obvious thing to show and it was **not** reachable, for a reason worth
writing down: upstream only ever sets `is_map_save` from the pangolin GUI checkbox
(`is_map_save = viewer3D.is_map_save() ...`), and `--headless` sets `viewer3D = None`. So
every headless run built a full map and then **discarded it**. Combined with §7c's parked
pangolin build, the map was unreachable by both routes at once.

`patches/0004-dump-sparse-map-headless.patch` adds an env-gated dump:

```bash
./.venv/bin/python scripts/set_dataset.py A
docker exec pyslam-build bash -lc '
  source /opt/conda/etc/profile.d/conda.sh && conda activate pyslam
  cd /pyslam && export PYSLAM_USE_CPP=true PYSLAM_DUMP_MAP=true
  python -u main_slam.py --headless'
# -> results/metrics_<UTC>/map_lite.npz   (points, colors, kf_centers)

./.venv/bin/python scripts/render_map_3d.py map_lite.npz -o media/phone_walk_map_3d.mp4
```

Clip A's map: **12,305 points, 220 keyframes, ~180 KB**.

Three things cost time here; none of them announce themselves.

1. **Do not go via `save_system_state()`.** It is the upstream way to persist a map, but
   with `USE_CPP_CORE=true` it writes `map["map"]` as a single **escaped JSON string**
   ~440 MB long. A streaming parser sees one scalar, so `ijson` spent 8 minutes returning
   **zero** points before the structure was even visible. The patch dumps the three arrays
   straight from memory instead.
2. **`pt` and `Ow` are methods, not properties** (`p.pt()`, `kf.Ow()`). Written as
   attributes they yield bound-method objects, `np.array(...)` then raises, and the whole
   dump fails inside its `except`.
3. **The dump must run AFTER the final-trajectory metrics block.** Placed before it, it
   takes the map lock while local mapping is still draining and **deadlocks the run** —
   observed as a complete `trajectory_online.txt`, an empty `trajectory_final.txt`, and
   ~2% CPU forever. `save_system_state()` calls `wait_for_local_mapping()` first for
   exactly this reason; the patch does too.

A fourth trap is not in the patch but will bite anyone debugging it: **pySLAM exits without
flushing stdout**, so `python main_slam.py > log` loses the last buffered chunk — including
any error the dump printed. Run it with `python -u`. The patch also writes any traceback to
`map_dump_error.txt` next to where the npz should have been, because a demo failing silently
the night before an event is the worst case.

##### Reading the 3D view

Framing the orbit needed a measured fit rather than a chosen multiplier. The point cloud
spans **37 x 15 x 42** map units while the camera path spans only **11 x 2 x 8**: monocular
triangulation throws a halo of badly-conditioned points far outside the scene, and left in,
that halo sets the view scale and the corridor collapses to a smear. `render_map_3d.py`
clips on distance from the path centroid (keeps 92%, 11,320 of 12,305 points) and then
**auto-fits the orbit radius by projecting and measuring**, because hand-picked multipliers
were wrong in both directions — 2.6x left the map a thin band across the middle, 1.9x
overflowed the frame.

Point colour is sampled from the frames, then lifted by a **1.55x display gain**: the walk
was shot before sunrise and the cloud reads as mud at unity. That is a display gain on the
render, not a change to the map, and the caption on every frame says so.

Pose-to-frame alignment in the video is a **linear index mapping** (1889 poses over 1953
frames), not a recorded correspondence — pySLAM's KITTI-format trajectory carries no frame
index. Drift is bounded by the 64 unmatched frames, under half a second at the end. Fine
for a demo; do not use this video to make a timing claim.

Both files are under `media/`, which `.gitignore` excludes except for `media/calib/*.yaml`.
They are regenerable from the clips and `results/walk{A,B,C}_run/`.

---

### 7f. Ground-truth demo, and a reproducibility problem it exposed  [MEASURED 2026-09-06]

#### There is no ground truth for the phone walk, and there cannot be one

Asked for "SLAM running with the ground truth path", the honest answer is that **the walk
has none**. Nobody surveyed that corridor. There is no reference trajectory, and drawing an
invented one would put a fabricated number in the most prominent place on screen. Every
phone-walk artifact says so, and `eval_trajectory.py` refuses to score without a GT file.

So the ground-truth demo is built on **KITTI 06** — the scored reference sequence, which
does have one — and it is labelled as KITTI on every frame so it can never be mistaken for
the walk.

```bash
./.venv/bin/python scripts/make_gt_demo.py \
    data/videos/kitti06/video_color.mp4 \
    results/kitti06_gt_run/trajectory_final.txt \
    data/videos/kitti06/groundtruth.txt \
    -o media/kitti06_gt_demo_raw.mp4 --note "<run-to-run spread>"
```

```
media/kitti06_gt_demo.mp4      110 s, 1600x1042 — real time (KITTI is 10 Hz)
media/kitti06_gt_demo_3x.mp4   37 s — 3x stage cut
```

Top: the sequence with its ORB features. Middle: ground truth in white, estimate in green,
both growing in step, with a line joining the two current positions so the error is visible
as a gap rather than only as a number. Bottom: absolute position error over time.

Two rendering choices worth knowing. Alignment is **Umeyama sim3** via `eval_trajectory.py`
— monocular has no metric scale, so a raw difference against GT is meaningless; the fitted
scale here is 23.0. And the estimate is **1089 poses against 1101 GT rows**, so rather than
assume where the missing 12 sit, both head- and tail-alignment are scored and the better is
used — the same choice `eval_trajectory.py` makes when reporting APE. Tail wins here
(14.2 m vs 26.7 m), so the video draws GT row `i` against estimate row `i-12`.

The top-down view is **rotated onto the route's principal axis**. KITTI 06 is a long thin
loop; in a square panel at equal scale it is a sliver down the middle. Yaw about the
vertical is an arbitrary choice of viewing direction, so this costs nothing — unlike
scaling the two axes independently, which would fill the frame by distorting the geometry.

#### The headline APE number does not reproduce

Building this meant re-running KITTI 06, and the run scored **14.2 m (1.16%)** against the
**49.5 m (4.05%)** in §7c, README and the judge pitch. Three more runs were made to find out
which was wrong. **Neither is: the number is unstable, and 49.5 m is the outlier.**

| Run | Poses | Lost | APE RMSE | % of 1223 m |
|---|---:|---:|---:|---:|
| 2026-09-05 07:29 — the documented reference | 1088 | 1 | **49.47 m** | 4.05% |
| 2026-09-06 #1 | 1089 | 0 | 14.17 m | 1.16% |
| 2026-09-06 #2 | 1089 | 0 | 14.37 m | 1.17% |
| 2026-09-06 #3 | 1089 | 0 | 12.20 m | 1.00% |
| 2026-09-06 #4 | 1089 | 0 | 14.22 m | 1.16% |

**The evaluator is not the variable.** Re-scoring the archived 2026-09-05 runs with today's
`eval_trajectory.py` reproduces every documented figure exactly — 99.5 m and 10.1 m for the
two stand-in runs (§7d), 132.7 m for the Python core (§7c), and 49.47 m for the reference
run itself. Same scorer, same ground truth; the trajectories differ.

Today's four runs are tightly clustered (12.2–14.4 m, all with **0 lost frames**), while the
2026-09-05 reference lost a frame and scored 3.5x worse. **The cause is not established.**
It is not `patches/0004`, which only runs after the metrics block and touches no SLAM state.
Do not write it up as "we improved it" — nothing was tuned; four runs simply landed
somewhere the single archived run did not.

What this actually means:

- **§7c's own warning was right** — "a single run of a monocular pipeline with RANSAC in it
  is not a measurement" — and the project then quoted a single run as a headline anyway.
- **`README.md`, the mission-control UI and the 3-slide judge pitch all display 49.5 m /
  4.05% as verified.** They are consistent with the archive and pessimistic by 3.5x versus
  anything reproducible today. Decide deliberately which number ships; do not let the two
  coexist, because the GT demo video puts 14.2 m on screen next to a dashboard saying 49.5.
- The right fix is to **quote a range from n runs, not a point from one**. `make_gt_demo.py`
  takes `--note` for exactly this, and the shipped video carries
  "4 runs 2026-09-06 spanned 12.2–14.4 m; the 2026-09-05 reference run scored 49.5 m".

Archived runs: `results/kitti06_gt_run`, `results/kitti_rep{2,3,4}` in the container.

---

## 8. Recording backup captures — BOTH halves  [VERIFIED 2026-09-05]

**`ffmpeg -f x11grab` does not work on this laptop. Do not reach for it.**

This is a GNOME **Wayland** session. Gazebo and RViz are X11 clients drawn through
XWayland, and their surfaces are composited by the Wayland compositor — they never
appear in the X root window. Measured 2026-09-05 with a GL client visibly on screen:
`ffmpeg -f x11grab -i :0` produced frames with **mean pixel value 0.01, std 1.04** —
a black screen, with **no error message**. Same failure class as the iGPU trap in §0:
it looks like it worked. `wf-recorder` is also out (wlroots compositors only).

GNOME's own screencast D-Bus API does work, but has its own trap: the recording is
bound to the D-Bus **sender**, so a `gdbus call` one-liner starts the capture and then
immediately kills it as gdbus exits, leaving a **48-byte mp4** and this in the journal:

```
org.gnome.Shell.Screencast: JS LOG: Fatal error while recording: Sender has vanished
```

`scripts/record_screen.py` holds one connection open for the whole take, which is the
only reason it is a script and not a one-liner:

```bash
./scripts/record_screen.py media/nav2_goal_run --seconds 85
```

Pass the basename **without** an extension — GNOME appends `.mp4` itself. Ctrl-C stops
cleanly and keeps the footage. The script warns if the output is under 100 KB, which is
the signature of the failure above.

**Always play the file back before trusting it.** A capture that silently recorded a
black screen is worse than no capture, because you will not find out until demo day.

### Captures recorded 2026-09-05

| File | Length | What it shows |
|---|---|---|
| `media/map_building.mp4` | 170 s, 106 MB | RTAB-Map building the map live while Nav2 drives the robot through `turtlebot3_house`. Occupancy grid grows **78x53 -> 202x205 cells**; dense 3D point cloud fills in; loop-closure counter advancing. |
| `media/nav2_goal_run.mp4` | 85 s, 4.7 MB | The money shot. Goal `(-6.21, 0.63)` sent via the §4 action call; robot drove `(-6.40, -1.86) -> (-6.36, 0.47)`, finishing ~0.21 m from target, inside Nav2's tolerance. |

Both verified non-blank by sampling frames across the file, not just at the start.

**`media/` is in `.gitignore`** — these files are NOT in git. The NAS is their only
backup. Copy them there before leaving home.

Honest note for the pitch: the RViz Nav2 panel in `map_building.mp4` shows
`Recoveries: 3`. That is Nav2 running recovery behaviours mid-run. It is normal, and
better acknowledged than hidden if a judge spots it.

---

## 9. Demo-day fallback ladder

Each rung is what you fall back to when the rung above fails. Test every rung (SPEC §7).

| # | If this fails | Fall back to |
|---|---|---|
| 1 | Live Nav2 run in Gazebo | **`media/nav2_goal_run.mp4`** — recorded 2026-09-05 |
| 2 | ORB-SLAM3 on the phone clip | **pySLAM, C++ core** — verified end to end on KITTI 06 (§7c). Needs `patches/` applied. |
| 3 | Any live SLAM | **`media/map_building.mp4`** — recorded 2026-09-05 |
| 4 | The laptop | Cloned backup machine (SPEC §8, owner C) |
| 5 | Everything | The 3 slides + narration |

---

## 10. Things to say out loud to judges (SPEC §4)

- **Monocular gives no metric scale** — the phone map is qualitative. Never claim
  measured distances from it.
- **Phone map and sim map are different coordinate frames.** The two halves connect by
  narrative, not by a shared map. Say so before a judge asks.
- **The simulated depth sensor is noise-free**, so the sim result looks cleaner than real
  hardware would. Frame it as "what a real depth camera gives us", not as a field result.
- **Proves:** the vision → map → autonomous-navigation pipeline works.
  **Does not prove:** robustness to real terrain, noise, or lighting extremes.
  Stating the second half is what buys credibility for the first.
