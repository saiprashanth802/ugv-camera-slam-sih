#!/usr/bin/env python3
"""Estimate focal length from orthogonal vanishing points.

No checkerboard was shot, so intrinsics have to come from somewhere. These are
corridors: floor joints, wall edges and handrails give two mutually orthogonal
world directions. With the principal point assumed at the image centre and
square pixels, orthogonality of two vanishing points v1,v2 gives
    f^2 = -(v1-c) . (v2-c)
which is a measurement, not a guess. Median over many frames.
"""
import sys, os
import cv2, numpy as np

def segments(gray):
    lsd = cv2.createLineSegmentDetector(cv2.LSD_REFINE_STD)
    lines = lsd.detect(gray)[0]
    if lines is None: return np.empty((0,4))
    L = lines.reshape(-1,4)
    ln = np.linalg.norm(L[:,2:]-L[:,:2], axis=1)
    return L[ln > 40]

def vp_ransac(L, iters=600, tol_deg=2.0):
    """Return (vp, inlier_mask) for the dominant vanishing point."""
    if len(L) < 8: return None, None
    p1 = np.c_[L[:,0], L[:,1], np.ones(len(L))]
    p2 = np.c_[L[:,2], L[:,3], np.ones(len(L))]
    lines = np.cross(p1, p2)
    mid   = (L[:,:2] + L[:,2:]) / 2.0
    d     = L[:,2:] - L[:,:2]
    d    /= (np.linalg.norm(d, axis=1, keepdims=True) + 1e-9)
    best, bestm = None, None
    rng = np.random.default_rng(0)
    tol = np.deg2rad(tol_deg)
    for _ in range(iters):
        i, j = rng.choice(len(L), 2, replace=False)
        v = np.cross(lines[i], lines[j])
        if abs(v[2]) < 1e-6: continue
        v = v[:2] / v[2]
        r = v - mid
        n = np.linalg.norm(r, axis=1, keepdims=True)
        ok = (n[:,0] > 1e-6)
        r = r / (n + 1e-9)
        ang = np.arccos(np.clip(np.abs((r*d).sum(1)), 0, 1))
        m = ok & (ang < tol)
        if best is None or m.sum() > bestm.sum():
            best, bestm = v, m
    return best, bestm

def focal_from_frame(gray, cx, cy):
    L = segments(gray)
    v1, m1 = vp_ransac(L)
    if v1 is None or m1.sum() < 12: return None
    L2 = L[~m1]
    v2, m2 = vp_ransac(L2)
    if v2 is None or m2.sum() < 12: return None
    a = np.array([v1[0]-cx, v1[1]-cy]); b = np.array([v2[0]-cx, v2[1]-cy])
    # reject near-parallel VP pairs: they carry almost no focal information
    if np.linalg.norm(a) < 50 or np.linalg.norm(b) < 50: return None
    f2 = -float(a @ b)
    if f2 <= 0: return None
    f = np.sqrt(f2)
    return f if 200 < f < 6000 else None

def run(path, n_samples=140):
    cap = cv2.VideoCapture(path)
    W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)); H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    N = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cx, cy = W/2.0, H/2.0
    idx = np.linspace(0, N-1, n_samples).astype(int)
    fs = []
    for k in idx:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(k))
        ok, fr = cap.read()
        if not ok: continue
        g = cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY)
        if cv2.Laplacian(g, cv2.CV_64F).var() < 60:   # skip blurred frames
            continue
        f = focal_from_frame(g, cx, cy)
        if f: fs.append(f)
    cap.release()
    fs = np.array(fs)
    if fs.size < 10:
        return dict(clip=os.path.basename(path), n=int(fs.size), note="too few VP pairs")
    return dict(clip=os.path.basename(path)[:40], wh=f"{W}x{H}", n=int(fs.size),
                f_med=round(float(np.median(fs)),1),
                f_p25=round(float(np.percentile(fs,25)),1),
                f_p75=round(float(np.percentile(fs,75)),1),
                hfov_deg=round(float(np.rad2deg(2*np.arctan(W/(2*np.median(fs))))),1),
                f_over_width=round(float(np.median(fs))/W, 4))

d = os.path.expanduser("~/Downloads")
for f in ["WhatsApp Video 2026-09-06 at 5.43.59 AM.mp4",
          "WhatsApp Video 2026-09-06 at 5.33.42 AM.mp4"]:
    print(run(os.path.join(d, f)))
