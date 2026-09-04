# SPEC / HANDOFF — Vision-Based GPS-Denied UGV Navigation (Hackathon PoC)

> Paste this whole file into a new chat to restore context. It captures every decided approach,
> the reasoning, and the exact repos/tools. Companion files: `RUNBOOK.md` (commands), 
> `calibrate_camera.py` (phone calibration), plan at `~/.claude/plans/my-laptop-is-a-rippling-pike.md`.

## 1. What this is

A **hardware-free proof of concept** for a camera-based autonomous outdoor UGV, built for an
**overnight university hackathon** that feeds into **Smart India Hackathon (SIH)**.

**Problem statement:** Outdoor UGVs face unpredictable terrain, changing light, and unreliable GPS.
Autonomy for search-and-rescue / agriculture / delivery must rely on **onboard computer vision** for
GPS-denied navigation.

**The demo = two halves + pitch:**
1. **Real outdoor phone footage → visual SLAM map** — proves perception works on real imagery.
2. **Simulated robot → autonomous navigation to a goal, GPS-free** — proves the autonomy loop (runs live).
3. **3-slide pitch** — problem → live demo → hardware roadmap.

## 2. Locked decisions (with reasoning)

| Area | Decision | Why |
|---|---|---|
| Host | RTX 4060 laptop, **Fedora**, everything in **Docker** | Only hardware on hand; ROS2/Gazebo are Ubuntu-native → containerize |
| GPU in Docker | NVIDIA Container Toolkit, `--gpus all` | Needed for Gazebo rendering |
| Simulator | **Gazebo Classic** (via `osrf/ros:humble-desktop-full`) | Lightweight, reliable, runs whole stack on one 4060; Isaac Sim rejected as overkill |
| Sim SLAM | **RTAB-Map** (`ros-humble-rtabmap-ros`) | ROS2-native, **BSD**, apt-installable, outputs occupancy grid Nav2 consumes directly |
| Navigation | **Nav2** | Standard ROS2 nav stack; goal-pose → path + obstacle avoidance is the money shot |
| Robot model | **TurtleBot3 `waffle`** | Chosen for its camera + lidar. **Correction (2026-09-02): the waffle ships a MONOCULAR RGB camera, not a depth camera** — see RUNBOOK §5. `docker/patch_depth_camera.py` converts it to depth at image-build time, following the upstream RTAB-Map recipe. Rugged Husky/Jackal deferred to future work |
| Phone SLAM | **ORB-SLAM3 monocular**, pre-recorded clip | Recognizable "real SLAM" look; **pySLAM** = fallback. **Correction (2026-09-05): pySLAM is NOT pip-installable.** The PyPI package named `pyslam` is an unrelated chat library by a different author. The real `luigifreda/pyslam` is a git clone + `./install_all.sh` and builds C++ components, so it must be **containerised** and built at home, never at the venue. It needs **Python 3.11.9** specifically — install conda first so the installer takes its conda branch; the plain-venv path fails on every stock Ubuntu image. Full reasoning in RUNBOOK §7c |
| Calibration | **OpenCV** chessboard (`calibrate_camera.py`) | Required for ORB-SLAM3 intrinsics |
| Camera rig | **1 phone + gimbal, NO stereo** | 2-phone stereo needs frame-sync + rigid baseline + stereo calib — fragile overnight, only buys metric scale we already disclaim. Gimbal kept: smooth motion = far better mono tracking |
| Lighting | Shot **outdoors in daylight**; stated as tested condition | Honest caveat: translatable to harder lighting with some tracking loss |

## 3. Critical risks / non-obvious gotchas

- **#1 risk: do NOT compile ORB-SLAM3 during the hackathon.** Pangolin/Eigen/OpenCV version fights
  can eat the whole night. Build it (or pySLAM) at home; the phone map is a **pre-recorded clip**.
  **This applies to pySLAM too** — the "live-safe, no compile" premise was wrong (see §2). The
  fallback has the same build risk as the primary, so both must be containerised at home.
- **GUI passthrough.** **Correction (2026-09-01): this prediction was half wrong.** XWayland
  works fine — no X11 session and no logout are needed; `xhost +local:docker` and SELinux
  `label=disable` are still required. The real trap is **hybrid graphics**: the container
  renders on the AMD 780M iGPU with no error and Gazebo quietly crawls. Fixed by the three
  `__NV_*`/`__GLX_*` vars in `run_demo.sh`; always run `check_gpu.sh` first. See RUNBOOK §0.
- **Wayland also breaks screen recording (2026-09-05).** `ffmpeg -f x11grab` captures a black
  screen and exits 0 — XWayland surfaces never reach the X root window. Use
  `scripts/record_screen.py` (GNOME D-Bus screencast). See RUNBOOK §8.
- **Bake all apt packages into a committed image** (`ugv-slam:demo`) — never reinstall at the venue.
- **Monocular = no metric scale** — qualitative "it maps" only; don't claim measured distances.
- **Phone map ≠ sim map** (different coordinate frames) — the two halves connect by *narrative*, not
  a shared map. This is fine and expected; say so.
- **TB3 camera topic names vary by package version** — verify with `ros2 topic list | grep camera`.
- **Sim result looks cleaner than real hardware** (simulated depth sensor is noise-free) — a feature,
  frame it as "what the real depth camera gives us."

## 4. Scope line (say it out loud to judges)

- **Proves:** the vision → map → autonomous-navigation *pipeline* works, on real outdoor imagery +
  in simulation.
- **The sim half is GPS-denied but NOT camera-only.** RTAB-Map does the RGB-D mapping and loop
  closure from the camera, but the odometry it consumes is **Gazebo's wheel encoders** (`/odom`) —
  the upstream demo runs no `rgbd_odometry` node, and pure visual odometry does not survive the
  stock textureless/dim worlds. See RUNBOOK §6 for the measured numbers. The **phone half** is the
  genuinely camera-only result. Say "GPS-denied"; do not say the sim navigates on vision alone — a
  robotics judge will ask which node produces odometry.
- **Does NOT prove:** robustness to real terrain/noise/lighting extremes — needs hardware field
  trials = next phase. Stating this = credibility.

## 5. Future-work slide (named, NOT built — shows we get the real problem)

- **Stereo / RGB-D hardware** (RGB-D IR depth dies in sun → stereo outdoors)
- **Rugged robot:** Clearpath **Husky** / **Jackal**
- **Light-robust learned features:** SuperPoint / ALIKED / LightGlue — **trained on our 92 GB×2 GPU
  cluster** (the one genuinely multi-GPU task)
- **Dense mapping:** DROID-SLAM
- **Visual-inertial + wheel-odom fusion:** VINS-Fusion, `robot_localization`
- **Traversability / elevation mapping** for rough terrain

## 6. Repos & references (all verified current)

**Core stack (used in the demo):**
- ROS2 Humble docs — https://docs.ros.org/en/humble/
- RTAB-Map (project) — http://introlab.github.io/rtabmap/
- RTAB-Map ROS2 (`humble-devel`) — https://github.com/introlab/rtabmap_ros/tree/humble-devel
- Nav2 — https://github.com/ros-navigation/navigation2 · docs https://docs.nav2.org
- TurtleBot3 — https://github.com/ROBOTIS-GIT/turtlebot3 · manual https://emanual.robotis.com/docs/en/platform/turtlebot3/overview/
- Gazebo — https://classic.gazebosim.org/
- NVIDIA Container Toolkit — https://github.com/NVIDIA/nvidia-container-toolkit
- ORB-SLAM3 — https://github.com/UZ-SLAMLab/ORB_SLAM3 · paper https://arxiv.org/abs/2007.11898
- pySLAM (fallback) — https://github.com/luigifreda/pyslam
- OpenCV calibration tutorial — https://docs.opencv.org/4.x/dc/dbb/tutorial_py_calibration.html

**Future-work references:**
- DROID-SLAM — https://github.com/princeton-vl/DROID-SLAM
- VINS-Fusion — https://github.com/HKUST-Aerial-Robotics/VINS-Fusion
- SuperPoint — https://github.com/magicleap/SuperPointPretrainedNetwork
- LightGlue — https://github.com/cvg/LightGlue
- Clearpath Husky — https://github.com/husky/husky
- robot_localization — https://github.com/cra-ros-pkg/robot_localization
- RTAB-Map paper — https://arxiv.org/pdf/2403.06341

**Watch-these videos (working links, grouped by demo piece):**

_Perception · phone SLAM_
- ORB-SLAM3 mono handheld (closest feel to our phone walk) — https://www.youtube.com/watch?v=VOHloE1mnos
- Official ORB-SLAM3 overview (mono/stereo/VI + loop closure) — https://www.youtube.com/watch?v=UVb3AFgabu8
- ORB-SLAM3 on GoPro 9 (why smooth motion matters) — https://www.youtube.com/watch?v=0wIqkUEjhiw

_Sim SLAM · RTAB-Map_
- RTAB-Map in Gazebo (sim mapping, our exact tool) — https://youtu.be/beUP-1fil3c
- Visual SLAM & odometry with RTAB-Map (RGB-D pipeline) — https://www.youtube.com/watch?v=S5CJ7tdzYJw
- RTAB-Map on a Clearpath Husky (bonus: our roadmap rover) — https://www.youtube.com/watch?v=lm5mTd_OyvU

_Navigation · Nav2_
- Nav2 bringup on TurtleBot3, Humble (the money-shot workflow) — https://www.youtube.com/watch?v=6CO58W3i1h8
- First Nav2 test, TurtleBot3 + Humble (goal pose → drive) — https://www.youtube.com/watch?v=WW8ZAippDxY

_Reference_
- TurtleBot3 3D-SLAM w/ RTAB-Map (repo + clips) — https://github.com/ROBOTIS-JAPAN-GIT/turtlebot3_slam_3d

## 7. Build order (see RUNBOOK.md for exact commands)

**[PRE-EVENT] at home:** host driver+Docker+Toolkit → GUI passthrough → ROS2+Gazebo+TB3 image →
RTAB-Map map → Nav2 goal-nav (money shot) → phone calib + outdoor walk clip → `docker save` backup.
**[OVERNIGHT]:** dress outdoor scene + obstacle → shoot best daylight take → assemble flow →
rehearse 3+× → 3 slides → test every fallback.

## 8. Team task split (suggested)

- **A — Sim/Nav:** owns RUNBOOK steps 3–5, gets Nav2 goal-nav rock-solid + records backup clip.
- **B — Perception:** owns phone calibration + ORB-SLAM3/pySLAM, shoots + records the outdoor walk.
- **C — Pitch/backup:** owns the 3 slides, the narrative script, the cloned backup machine, timing.
