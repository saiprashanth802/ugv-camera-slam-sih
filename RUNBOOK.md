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

Validation done 2026-09-01: run against synthetic views from a known camera
(fx=fy=900, cx=640, cy=360 at 1280x720) it recovered fx=900.28, cx=639.65,
RMS 0.070 px. The script and the YAML format are trustworthy.

### 7b. The walk  [UNVERIFIED]
- Shoot **outdoors, in daylight** (SPEC §2 — this is the disclosed tested condition).
- **Gimbal on.** Smooth motion is the single biggest factor in mono tracking survival.
- Walk a **loop** and return to the start — loop closure is the visually impressive moment.
- Avoid: fast rotation with no translation (mono cannot triangulate from pure rotation —
  this is the classic way to lose tracking), blank walls, and large moving objects.
- Lock the phone to one video mode so the intrinsics stay valid.

### 7c. Run SLAM on the clip  [pySLAM build IN PROGRESS 2026-09-05]
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

#### Good news: the test sequence ships with the repo

No dataset download is needed to prove the toolchain. `data/videos/kitti06/` contains a
real 46 MB `video_color.mp4` plus `groundtruth.txt` and `times.txt`, and `config.yaml`
already defaults to `type: VIDEO_DATASET` pointing at it. That same `VIDEO_DATASET` mode
is what the **phone clip** will use — so proving KITTI runs proves the path the phone
footage will take, and only the settings YAML (from `calibrate_camera.py`, §7a) changes.

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
| 2 | ORB-SLAM3 on the phone clip | pySLAM on the same clip (see §7c for build status) |
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
