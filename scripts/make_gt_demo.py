#!/usr/bin/env python3
"""Sightline — SLAM running against GROUND TRUTH, side by side.

This exists only for KITTI 06. A phone walk has no ground truth: nobody surveyed
that corridor, there is no reference path, and drawing an invented one would put
a fabricated number in the most prominent place on screen. So the honest
ground-truth demo is the scored reference sequence, not the walk.

Left  : the sequence, with the ORB features tracking keys off drawn on it.
Right : top-down map. Ground truth in white, the SLAM estimate in green, both
        growing in step, plus live absolute position error.

Alignment is Umeyama sim3 (scale + rotation + translation) via
scripts/eval_trajectory.py -- monocular has no metric scale, so a raw position
difference against ground truth is meaningless. The estimate is 1089 poses
against 1101 ground-truth rows, and rather than assume where the missing rows
sit, both head- and tail-alignment are scored and the better one is used, which
is what eval_trajectory.py does when reporting APE.

USAGE
    ./.venv/bin/python scripts/make_gt_demo.py \
        kitti06/video_color.mp4 run/trajectory_final.txt kitti06/groundtruth.txt \
        -o media/kitti06_gt_demo_raw.mp4
"""
import argparse
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eval_trajectory import load_est, load_gt, umeyama_sim3   # noqa: E402

BG   = (18, 20, 24)
FG   = (235, 238, 242)
DIM  = (120, 128, 140)
GT_C = (232, 232, 232)
EST_C = (150, 220, 120)
WARN = (90, 150, 250)
CUR  = (200, 200, 90)


def best_alignment(est, gt):
    """Return (gt_slice, offset, err, scale) for whichever of head/tail alignment
    scores better -- same choice eval_trajectory.py makes."""
    n = len(est)
    best = None
    for offset in (0, len(gt) - n):
        g = gt[offset:offset + n]
        scale, R, t = umeyama_sim3(est, g)
        aligned = (scale * (R @ est.T)).T + t
        err = np.linalg.norm(aligned - g, axis=1)
        rmse = float(np.sqrt((err ** 2).mean()))
        if best is None or rmse < best[0]:
            best = (rmse, g, offset, err, scale, aligned)
    rmse, g, offset, err, scale, aligned = best
    return g, offset, err, scale, aligned, rmse


def put(img, text, org, sc=0.5, col=FG, th=1):
    cv2.putText(img, text, org, cv2.FONT_HERSHEY_SIMPLEX, sc, col, th, cv2.LINE_AA)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("traj")
    ap.add_argument("gt")
    ap.add_argument("-o", "--out", default="media/kitti06_gt_demo_raw.mp4")
    ap.add_argument("--panel", type=int, default=720)
    ap.add_argument("--note", default=None,
                    help="extra caption line, e.g. the run-to-run spread. A single "
                         "monocular run is not a measurement (RUNBOOK 7c), so if you "
                         "print an APE on screen, print what it varies by too.")
    args = ap.parse_args()

    est = load_est(args.traj)
    gt_all = load_gt(args.gt)
    gt, offset, err, scale, aligned, rmse = best_alignment(est, gt_all)
    path_len = float(np.linalg.norm(np.diff(gt, axis=0), axis=1).sum())
    print(f"aligned: offset={offset}  sim3 scale={scale:.4f}  "
          f"APE RMSE={rmse:.2f} m  ({100*rmse/path_len:.2f}% of {path_len:.0f} m)")

    cap = cv2.VideoCapture(args.video)
    W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)); H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    NF = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)); FPS = cap.get(cv2.CAP_PROP_FPS) or 10.0

    # KITTI 06 is a long thin loop: in a square panel at equal scale it is a
    # sliver down the middle and most of the frame is empty. Rotate the top-down
    # view onto the route's principal axis and lay it out wide. Yaw about the
    # vertical is an arbitrary choice of viewing direction, so this costs nothing
    # in honesty -- unlike scaling the two axes independently, which would fill
    # the frame by silently distorting the geometry.
    both = np.vstack([gt, aligned])
    XZ = both[:, [0, 2]]
    c0 = XZ.mean(0)
    _, _, Vt = np.linalg.svd(XZ - c0, full_matrices=False)
    Rot = Vt                                            # rows: principal axes
    def to_axis(p):
        return (np.array([p[0], p[2]]) - c0) @ Rot.T

    A_gt = np.array([to_axis(p) for p in gt])
    A_est = np.array([to_axis(p) for p in aligned])
    A_all = np.vstack([A_gt, A_est])

    out_w = 1600
    vid_h = int(round(H * out_w / W))
    map_h = 470
    strip_h = 90
    pad = 55
    s = min((out_w - 2 * pad) / max(np.ptp(A_all[:, 0]), 1e-6),
            (map_h - 2 * pad) / max(np.ptp(A_all[:, 1]), 1e-6))
    mx, my = A_all[:, 0].mean(), A_all[:, 1].mean()

    def px(a):
        return (int(out_w / 2 + (a[0] - mx) * s), int(map_h / 2 - (a[1] - my) * s))

    GTP = np.array([px(a) for a in A_gt], np.int32)
    ETP = np.array([px(a) for a in A_est], np.int32)
    out_h = vid_h + map_h + strip_h
    orb = cv2.ORB_create(nfeatures=2000)
    vw = cv2.VideoWriter(args.out, cv2.VideoWriter_fourcc(*"mp4v"), FPS, (out_w, out_h))

    emax = float(err.max())
    i = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        k = i - offset                       # video frame -> estimate index
        k = max(0, min(k, len(est) - 1))
        live = i - offset

        left = cv2.resize(frame, (out_w, vid_h))
        g = cv2.cvtColor(left, cv2.COLOR_BGR2GRAY)
        for kp_ in orb.detect(g, None):
            cv2.circle(left, (int(kp_.pt[0]), int(kp_.pt[1])), 2, EST_C, 1, cv2.LINE_AA)
        ov = left.copy()
        cv2.rectangle(ov, (0, 0), (out_w, 62), (0, 0, 0), -1)
        cv2.rectangle(ov, (0, vid_h - 38), (out_w, vid_h), (0, 0, 0), -1)
        left = cv2.addWeighted(ov, 0.55, left, 0.45, 0)
        put(left, "KITTI 06  /  monocular RGB", (14, 26), 0.62, FG, 2)
        put(left, "scored reference sequence - this one HAS ground truth", (14, 50), 0.45, DIM)
        put(left, f"frame {i+1}/{NF}", (14, vid_h - 14), 0.48, DIM)
        put(left, "top-down view below is rotated onto the route's principal axis (equal scale on both axes)",
            (out_w - 720, vid_h - 14), 0.42, DIM)

        pan = np.full((map_h, out_w, 3), BG, np.uint8)
        for gx in range(0, out_w, 60):
            cv2.line(pan, (gx, 0), (gx, map_h), (30, 33, 38), 1)
        for gy in range(0, map_h, 60):
            cv2.line(pan, (0, gy), (out_w, gy), (30, 33, 38), 1)
        cv2.polylines(pan, [GTP], False, (60, 62, 66), 1, cv2.LINE_AA)   # full route, faint
        if 0 < live < len(GTP):
            cv2.polylines(pan, [GTP[:live + 1]], False, GT_C, 2, cv2.LINE_AA)
        if 0 < k:
            cv2.polylines(pan, [ETP[:k + 1]], False, EST_C, 2, cv2.LINE_AA)
        if 0 <= live < len(GTP):
            cv2.circle(pan, tuple(GTP[live]), 6, GT_C, -1, cv2.LINE_AA)
        cv2.circle(pan, tuple(ETP[k]), 6, CUR, -1, cv2.LINE_AA)
        if 0 <= live < len(GTP):
            cv2.line(pan, tuple(GTP[live]), tuple(ETP[k]), WARN, 1, cv2.LINE_AA)

        put(pan, "GROUND TRUTH  vs  SLAM  (top-down)", (14, 28), 0.6, FG, 2)
        put(pan, "white = ground truth      green = pySLAM estimate", (14, 50), 0.45, DIM)
        e_now = err[k]
        put(pan, f"position error now   {e_now:6.1f} m", (14, map_h - 84), 0.52, WARN)
        put(pan, f"APE RMSE, THIS RUN   {rmse:6.1f} m   = {100*rmse/path_len:.2f}% of {path_len:.0f} m",
            (14, map_h - 60), 0.48, EST_C)
        if args.note:
            put(pan, args.note, (470, map_h - 84), 0.44, DIM)
        put(pan, f"sim3 scale {scale:.3f} - monocular has no metric scale", (14, map_h - 38), 0.44, DIM)
        put(pan, "0 loop closures: nothing ever corrects this drift", (14, map_h - 16), 0.44, WARN)

        strip = np.full((strip_h, out_w, 3), (12, 13, 16), np.uint8)
        put(strip, "absolute position error", (14, 20), 0.45, DIM)
        x0, y0, ww, hh = 14, 30, out_w - 28, 46
        cv2.rectangle(strip, (x0, y0), (x0 + ww, y0 + hh), (30, 33, 38), 1)
        pts = []
        upto = max(k, 1)
        for j in range(0, upto, max(1, upto // ww + 1)):
            xx = x0 + int(ww * j / max(len(err) - 1, 1))
            yy = y0 + hh - int(hh * err[j] / (emax + 1e-9))
            pts.append((xx, yy))
        if len(pts) > 1:
            cv2.polylines(strip, [np.array(pts, np.int32)], False, WARN, 1, cv2.LINE_AA)
        put(strip, f"0", (x0 + ww + 4, y0 + hh), 0.4, DIM)
        put(strip, f"{emax:.0f} m", (x0 + ww + 4, y0 + 10), 0.4, DIM)

        vw.write(np.vstack([left, pan, strip]))
        i += 1

    cap.release(); vw.release()
    print(f"wrote {args.out}: {i} frames, {out_w}x{out_h}")


if __name__ == "__main__":
    main()
