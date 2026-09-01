# Sightline

Camera-only (vision-based) navigation for a **GPS-denied autonomous ground rover**.
Hardware-free proof of concept for an overnight university hackathon feeding into
Smart India Hackathon (SIH).

The demo is two halves plus a pitch:
1. **Real outdoor phone footage → visual SLAM map** — perception works on real imagery.
2. **Simulated robot → autonomous navigation to a goal, GPS-free** — the autonomy loop, live.
3. **3-slide pitch** — problem → live demo → hardware roadmap.

## Layout

| Path | What |
|---|---|
| `SPEC.md` | Locked decisions, reasoning, risks, repos, team split. Read first. |
| `RUNBOOK.md` | Every command, with verification status per section. |
| `docker/Dockerfile` | The `ugv-slam:demo` image: ROS2 Humble + Gazebo + RTAB-Map + Nav2 + TurtleBot3. |
| `scripts/run_demo.sh` | Launch the container with verified GPU + GUI passthrough. |
| `scripts/check_gpu.sh` | Smoke test. Run it first, every time. |
| `scripts/calibrate_camera.py` | Phone intrinsics → ORB-SLAM3 YAML. |
| `media/` | Calibration stills, the outdoor walk clip, backup screen captures. |

## Quick start

```bash
cd docker && docker build -t ugv-slam:demo .   # once, at home
./scripts/run_demo.sh                          # host
./scripts/check_gpu.sh                         # inside: must print RTX 4060
```

Then follow `RUNBOOK.md` §4 onward.

## Read this before you debug anything

This laptop has **hybrid graphics** (AMD 780M iGPU + RTX 4060). Without the
`__NV_PRIME_RENDER_OFFLOAD` env vars in `run_demo.sh`, the container renders on the
**iGPU with no error message** and Gazebo crawls. `check_gpu.sh` exists to catch exactly
this. See `RUNBOOK.md` §0.

## Source of record

Canonical copy lives on the NAS at `/srv/media/project_docs/SIH-Hackathon/`.
