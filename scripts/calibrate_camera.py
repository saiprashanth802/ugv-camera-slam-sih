#!/usr/bin/env python3
"""
Sightline — phone camera intrinsic calibration for ORB-SLAM3 / pySLAM.

Monocular SLAM needs fx, fy, cx, cy and the distortion coefficients. Wrong intrinsics
are the most common cause of "ORB-SLAM3 initialises then immediately loses tracking".

USAGE
  1. Print a chessboard (default 9x6 INNER corners = a 10x7 square board).
     Tape it FLAT to something rigid. A curled print silently poisons the calibration.
  2. Shoot ~20 stills or a slow video of the board, from the SAME phone, SAME lens,
     SAME resolution and SAME zoom you will use for the outdoor walk. Vary the angle
     and fill different parts of the frame, especially the corners.
  3. Run:
       python3 calibrate_camera.py --images 'calib/*.jpg'
       python3 calibrate_camera.py --video calib.mp4 --every 15
  4. It writes phone_calib.yaml in the ORB-SLAM3 monocular format.

GOTCHA: if you record the walk at a different resolution than you calibrated at,
the intrinsics are wrong by the scale factor. Lock the phone to one video mode.
"""
import argparse
import glob
import sys

import cv2
import numpy as np


def collect_corners(frames, board, verbose=True):
    """Detect chessboard corners across frames. Returns (objpoints, imgpoints, size)."""
    cols, rows = board
    # Board coordinates in an arbitrary unit; monocular SLAM has no metric scale
    # anyway, so square size only scales tvecs, never the intrinsics we care about.
    objp = np.zeros((rows * cols, 3), np.float32)
    objp[:, :2] = np.mgrid[0:cols, 0:rows].T.reshape(-1, 2)

    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
    objpoints, imgpoints, size = [], [], None

    for name, img in frames:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        if size is None:
            size = gray.shape[::-1]
        elif gray.shape[::-1] != size:
            print(f"  SKIP {name}: resolution {gray.shape[::-1]} != {size}")
            continue

        found, corners = cv2.findChessboardCorners(
            gray, (cols, rows),
            cv2.CALIB_CB_ADAPTIVE_THRESH + cv2.CALIB_CB_NORMALIZE_IMAGE + cv2.CALIB_CB_FAST_CHECK,
        )
        if not found:
            if verbose:
                print(f"  ---- {name}: no board")
            continue

        corners = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)
        objpoints.append(objp)
        imgpoints.append(corners)
        if verbose:
            print(f"  OK   {name}")

    return objpoints, imgpoints, size


def load_images(pattern):
    paths = sorted(glob.glob(pattern))
    if not paths:
        sys.exit(f"No images matched {pattern!r}")
    for p in paths:
        img = cv2.imread(p)
        if img is None:
            print(f"  SKIP {p}: unreadable")
            continue
        yield p, img


def load_video(path, every):
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        sys.exit(f"Cannot open video {path!r}")
    i = 0
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            if i % every == 0:
                yield f"frame{i:05d}", frame
            i += 1
    finally:
        cap.release()


def write_orbslam_yaml(path, K, dist, size, fps, rms):
    fx, fy = K[0, 0], K[1, 1]
    cx, cy = K[0, 2], K[1, 2]
    d = dist.ravel()
    k1, k2, p1, p2 = d[0], d[1], d[2], d[3]
    k3 = d[4] if len(d) > 4 else 0.0

    with open(path, "w") as f:
        f.write(f"""%YAML:1.0
# Sightline phone calibration. RMS reprojection error: {rms:.4f} px
# Valid ONLY for {size[0]}x{size[1]} from this phone/lens/zoom.

File.version: "1.0"

Camera.type: "PinHole"
Camera1.fx: {fx:.6f}
Camera1.fy: {fy:.6f}
Camera1.cx: {cx:.6f}
Camera1.cy: {cy:.6f}

Camera1.k1: {k1:.6f}
Camera1.k2: {k2:.6f}
Camera1.p1: {p1:.6f}
Camera1.p2: {p2:.6f}
Camera1.k3: {k3:.6f}

Camera.width: {size[0]}
Camera.height: {size[1]}
Camera.fps: {fps}
Camera.RGB: 1

# --- ORB extractor: 1250 features suits a handheld outdoor walk ---
ORBextractor.nFeatures: 1250
ORBextractor.scaleFactor: 1.2
ORBextractor.nLevels: 8
ORBextractor.iniThFAST: 20
ORBextractor.minThFAST: 7

# --- Viewer ---
Viewer.KeyFrameSize: 0.05
Viewer.KeyFrameLineWidth: 1.0
Viewer.GraphLineWidth: 0.9
Viewer.PointSize: 2.0
Viewer.CameraSize: 0.08
Viewer.CameraLineWidth: 3.0
Viewer.ViewpointX: 0.0
Viewer.ViewpointY: -0.7
Viewer.ViewpointZ: -1.8
Viewer.ViewpointF: 500.0
""")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--images", help="glob of calibration stills, e.g. 'calib/*.jpg'")
    src.add_argument("--video", help="calibration video file")
    ap.add_argument("--every", type=int, default=15,
                    help="with --video: use every Nth frame (default 15)")
    ap.add_argument("--board", default="9x6",
                    help="INNER corners, cols x rows (default 9x6)")
    ap.add_argument("--fps", type=int, default=30, help="fps of the walk clip (default 30)")
    ap.add_argument("-o", "--out", default="phone_calib.yaml")
    args = ap.parse_args()

    try:
        cols, rows = (int(v) for v in args.board.lower().split("x"))
    except ValueError:
        sys.exit(f"--board must look like 9x6, got {args.board!r}")

    frames = load_images(args.images) if args.images else load_video(args.video, args.every)
    print(f"Detecting a {cols}x{rows} inner-corner board...")
    objpoints, imgpoints, size = collect_corners(frames, (cols, rows))

    n = len(objpoints)
    print(f"\n{n} usable view(s).")
    if n < 8:
        sys.exit("Need at least 8 good views (aim for ~20). Reshoot with more angles.")

    rms, K, dist, _, _ = cv2.calibrateCamera(objpoints, imgpoints, size, None, None)

    print(f"\nRMS reprojection error: {rms:.4f} px")
    if rms > 1.0:
        print("  WARNING: >1.0 px is poor. Usually a non-flat board or too few angles.")
    print(f"  fx={K[0,0]:.2f}  fy={K[1,1]:.2f}  cx={K[0,2]:.2f}  cy={K[1,2]:.2f}")
    print(f"  dist={np.round(dist.ravel(), 5).tolist()}")

    write_orbslam_yaml(args.out, K, dist, size, args.fps, rms)
    np.savez(args.out.replace(".yaml", ".npz"), K=K, dist=dist, size=size, rms=rms)
    print(f"\nWrote {args.out} (+ .npz) for {size[0]}x{size[1]}.")


if __name__ == "__main__":
    main()
