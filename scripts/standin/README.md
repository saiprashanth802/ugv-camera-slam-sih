# Stand-in clip — rehearsing the phone-half pipeline without phone footage

These two scripts fabricate the inputs RUNBOOK §7d was verified against, so the
rehearsal can be repeated after a fresh clone. **Neither is part of the demo.** Delete
`vendor/pyslam/data/videos/phone_walk/` and `media/calib_standin/` once real footage
exists.

```bash
./.venv/bin/python scripts/standin/make_standin_clip.py   # KITTI06 -> 1280x720 @30fps clip
./.venv/bin/python scripts/standin/make_calib_views.py    # 22 synthetic chessboard stills
./.venv/bin/python scripts/calibrate_camera.py --images 'media/calib_standin/*.png' \
    --fps 30 -o media/calib_standin/phone_calib.yaml
./.venv/bin/python scripts/make_pyslam_settings.py media/calib_standin/phone_calib.yaml \
    -o vendor/pyslam/settings/SIGHTLINE_PHONE.yaml
```

Why this shape:

- The clip is KITTI 06 resampled to a resolution and frame rate nothing else here uses,
  so wrong-size and wrong-fps bugs surface. **Anisotropic scaling is exact in the pinhole
  model**, which is what makes the implied intrinsics derivable rather than guessed —
  hence `fx != fy`, which is unusual for a phone but geometrically honest.
- `cv2.VideoWriter`/`mp4v` does the transcode, not ffmpeg: Fedora's ffmpeg ships no
  libx264 encoder and its openh264 decoder fails on the KITTI mp4. pySLAM reads frames
  with `cv2.VideoCapture` anyway, so OpenCV is the right compatibility target.
- The chessboard views are rendered *from the clip's own intrinsics* and fed to the real
  `calibrate_camera.py`, which recovers them to 0.098 px RMS. That exercises the actual
  calibration code path rather than hand-writing a calibration file.
