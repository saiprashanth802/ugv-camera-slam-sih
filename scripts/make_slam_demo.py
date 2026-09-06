#!/usr/bin/env python3
"""Sightline phone-half demo: walk footage + the map pySLAM built from it.

Left  : the clip, with the ORB features tracking actually keys off drawn on it.
Right : top-down view of the recovered camera trajectory, growing in step.

Monocular SLAM has no metric scale, so the map panel is deliberately labelled in
arbitrary units -- there is no honest metre figure to print without a calibrated
baseline or a measured ground truth.

USAGE
    ./.venv/bin/python scripts/make_slam_demo.py \\
        vendor/pyslam/data/videos/phone_walk/walkA.mp4 \\
        vendor/pyslam/results/walkA_run/trajectory_final.txt \\
        media/phone_walk_slam_demo_raw.mp4

Then transcode (mp4v out of cv2 is not broadly playable; Fedora has no libx264,
so use NVENC -- RUNBOOK 7d has the same note for the stand-in clip):

    ffmpeg -i media/phone_walk_slam_demo_raw.mp4 -c:v h264_nvenc -preset p5 -cq 23 \\
           -pix_fmt yuv420p -movflags +faststart media/phone_walk_slam_demo.mp4

Pose-to-frame alignment is a LINEAR INDEX MAPPING: the trajectory is in KITTI
12-number format, which carries no frame index, so pose k is drawn against frame
round(k * NF / len(poses)). Bounded by the unmatched-frame count. Do not use the
result to make a timing claim.
"""
import cv2, numpy as np, sys, os

CLIP  = sys.argv[1]
TRAJ  = sys.argv[2]
OUT   = sys.argv[3]
PANEL = 720                      # square map panel side

BG      = (18, 20, 24)
FG      = (235, 238, 242)
DIM     = (120, 128, 140)
ACCENT  = (200, 200, 90)         # BGR cyan-ish
TRAIL   = (150, 220, 120)
WARN    = (90, 150, 250)

M = np.loadtxt(TRAJ).reshape(-1, 3, 4)
C = M[:, :, 3]
xs, zs = C[:, 0], C[:, 2]

cap = cv2.VideoCapture(CLIP)
W  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)); H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
NF = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)); FPS = cap.get(cv2.CAP_PROP_FPS)

# scale the map into the panel with a margin
pad = 70
sx = (PANEL - 2*pad) / max(np.ptp(xs), 1e-6)
sz = (PANEL - 2*pad) / max(np.ptp(zs), 1e-6)
s  = min(sx, sz)
def to_px(x, z):
    px = int(round((x - xs.min()) * s + pad + (PANEL - 2*pad - np.ptp(xs)*s)/2))
    pz = int(round(PANEL - ((z - zs.min()) * s + pad + (PANEL - 2*pad - np.ptp(zs)*s)/2)))
    return px, pz
P = np.array([to_px(x, z) for x, z in zip(xs, zs)], dtype=np.int32)

orb = cv2.ORB_create(nfeatures=2000)
panel_h = PANEL
vid_h   = PANEL
vid_w   = int(round(W * vid_h / H))
out = cv2.VideoWriter(OUT, cv2.VideoWriter_fourcc(*'mp4v'), FPS, (vid_w + PANEL, panel_h))

def base_panel():
    p = np.full((PANEL, PANEL, 3), BG, np.uint8)
    for g in range(0, PANEL, 60):
        cv2.line(p, (g, 0), (g, PANEL), (30, 33, 38), 1)
        cv2.line(p, (0, g), (PANEL, g), (30, 33, 38), 1)
    return p

def put(img, text, org, sc=0.5, col=FG, th=1):
    cv2.putText(img, text, org, cv2.FONT_HERSHEY_SIMPLEX, sc, col, th, cv2.LINE_AA)

i = 0
while True:
    ok, frame = cap.read()
    if not ok: break
    k = min(int(i * len(P) / NF), len(P) - 1)

    # ---- left: video + features -------------------------------------------
    left = cv2.resize(frame, (vid_w, vid_h))
    g = cv2.cvtColor(left, cv2.COLOR_BGR2GRAY)
    kp = orb.detect(g, None)
    for p_ in kp:
        cv2.circle(left, (int(p_.pt[0]), int(p_.pt[1])), 2, (110, 220, 140), 1, cv2.LINE_AA)
    ov = left.copy()
    cv2.rectangle(ov, (0, 0), (vid_w, 62), (0, 0, 0), -1)
    cv2.rectangle(ov, (0, vid_h-40), (vid_w, vid_h), (0, 0, 0), -1)
    left = cv2.addWeighted(ov, 0.55, left, 0.45, 0)
    put(left, "PHONE WALK  /  monocular RGB", (14, 26), 0.62, FG, 2)
    put(left, f"ORB features this frame: {len(kp)}", (14, 50), 0.5, TRAIL)
    put(left, f"frame {i+1}/{NF}   t={i/FPS:5.1f}s", (14, vid_h-15), 0.5, DIM)

    # ---- right: map --------------------------------------------------------
    pan = base_panel()
    if k > 1:
        cv2.polylines(pan, [P[:k+1]], False, TRAIL, 2, cv2.LINE_AA)
    cv2.circle(pan, tuple(P[k]), 6, ACCENT, -1, cv2.LINE_AA)
    cv2.circle(pan, tuple(P[k]), 12, ACCENT, 1, cv2.LINE_AA)
    cv2.circle(pan, tuple(P[0]), 5, WARN, 2, cv2.LINE_AA)
    put(pan, "start", (P[0][0]+9, P[0][1]+4), 0.42, WARN)
    put(pan, "RECOVERED TRAJECTORY  (top-down)", (14, 28), 0.6, FG, 2)
    put(pan, "pySLAM mono, C++ core + GTSAM", (14, 50), 0.45, DIM)
    put(pan, f"poses {k+1}/{len(P)}", (14, PANEL-58), 0.48, TRAIL)
    put(pan, "scale is ARBITRARY - monocular", (14, PANEL-36), 0.45, WARN)
    put(pan, "0 loop closures (known-open)", (14, PANEL-16), 0.45, DIM)

    out.write(np.hstack([left, pan]))
    i += 1

cap.release(); out.release()
print(f"wrote {OUT}  ({i} frames, {vid_w+PANEL}x{panel_h})")
