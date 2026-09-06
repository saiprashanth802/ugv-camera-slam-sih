#!/usr/bin/env python3
"""Sightline — render the pySLAM map in 3D without pangolin.

WHY THIS EXISTS. pySLAM's own 3D view is pangolin, which does not build on this
box (RUNBOOK 7c, cause (2)), and upstream only saves the map from that same GUI
(`is_map_save` is set from viewer3D, and --headless sets viewer3D = None). So a
headless run built a full map and then discarded it. patches/0004 adds an
env-gated save; this script draws what that save contains.

Input is the map_lite.npz that patches/0004 writes into the run's metrics
directory: map point positions and colours plus keyframe camera centres.

Do NOT try to get this out of save_system_state()'s map.json instead. With
USE_CPP_CORE=true that file stores the whole map as ONE escaped JSON string
(~440 MB), so a streaming parser sees a single scalar and reading it costs a
multi-GB materialisation. patches/0004 dumps the three arrays straight from
memory instead, ~180 KB.

Output is an orbiting fly-around plus stills. Monocular SLAM has no metric scale,
so every axis here is in arbitrary map units -- there is no honest metre figure.

USAGE
    ./.venv/bin/python scripts/render_map_3d.py map_lite.npz -o media/phone_walk_map_3d.mp4
"""
import argparse
import numpy as np
import cv2

BG = (16, 18, 22)


def robust_mask(P, anchor, keep=0.92):
    """Monocular maps carry far-flung badly-triangulated points -- here the point
    cloud spans 37x15x42 map units while the camera path spans only 11x2x8. Left
    in, that halo sets the view scale and the actual scene collapses to a smear.

    Clip on distance from the camera path's centroid rather than per axis: the
    structure worth seeing is what the camera actually walked past."""
    d = np.linalg.norm(P - anchor, axis=1)
    return d <= np.percentile(d, 100.0 * keep)


def look_at(eye, target, up=np.array([0.0, -1.0, 0.0])):
    f = target - eye
    f /= np.linalg.norm(f) + 1e-9
    r = np.cross(f, up)
    n = np.linalg.norm(r)
    if n < 1e-6:
        up = np.array([0.0, 0.0, 1.0])
        r = np.cross(f, up)
        n = np.linalg.norm(r)
    r /= n + 1e-9
    u = np.cross(r, f)
    R = np.stack([r, u, f])          # world -> camera
    return R, -R @ eye


def project(P, R, t, f, cx, cy):
    Pc = P @ R.T + t
    z = Pc[:, 2]
    ok = z > 1e-6
    uv = np.full((len(P), 2), -1e9)
    uv[ok, 0] = f * Pc[ok, 0] / z[ok] + cx
    uv[ok, 1] = f * Pc[ok, 1] / z[ok] + cy
    return uv, z, ok


def draw(pts, cols, kf, R, t, W, H, fpx):
    img = np.full((H, W, 3), BG, np.uint8)
    cx, cy = W / 2, H / 2

    uv, z, ok = project(pts, R, t, fpx, cx, cy)
    vis = ok & (uv[:, 0] > -50) & (uv[:, 0] < W + 50) & (uv[:, 1] > -50) & (uv[:, 1] < H + 50)
    idx = np.where(vis)[0]
    idx = idx[np.argsort(-z[idx])]                      # painter's algorithm
    if len(idx):
        zz = z[idx]
        near, far = np.percentile(zz, [2, 98])
        shade = np.clip(1.0 - (zz - near) / (far - near + 1e-9), 0.25, 1.0)
        U = uv[idx].astype(np.int32)
        C = (cols[idx] * shade[:, None]).astype(np.int32)
        for (u, v), c, s in zip(U, C, shade):
            if 0 <= u < W and 0 <= v < H:
                cv2.circle(img, (u, v), 2 if s < 0.6 else 3,
                           (int(c[0]), int(c[1]), int(c[2])), -1, cv2.LINE_AA)

    kuv, kz, kok = project(kf, R, t, fpx, cx, cy)
    good = np.where(kok)[0]
    if len(good) > 1:
        poly = kuv[good].astype(np.int32).reshape(-1, 1, 2)
        cv2.polylines(img, [poly], False, (150, 220, 120), 2, cv2.LINE_AA)
        for g in good[::6]:
            u, v = kuv[g].astype(int)
            if 0 <= u < W and 0 <= v < H:
                cv2.circle(img, (u, v), 3, (200, 200, 90), -1, cv2.LINE_AA)
        u, v = kuv[good[0]].astype(int)
        cv2.circle(img, (u, v), 7, (90, 150, 250), 2, cv2.LINE_AA)
    return img


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("npz")
    ap.add_argument("-o", "--out", default="media/phone_walk_map_3d.mp4")
    ap.add_argument("--frames", type=int, default=420)
    ap.add_argument("--width", type=int, default=1280)
    ap.add_argument("--height", type=int, default=720)
    ap.add_argument("--fps", type=int, default=30)
    args = ap.parse_args()

    d = np.load(args.npz)
    pts, cols, kf = d["points"], d["colors"], d["kf_centers"]
    n0 = len(pts)
    m = robust_mask(pts, np.median(kf, axis=0))
    pts, cols = pts[m], cols[m]
    if cols.max() <= 1.001:
        cols = cols * 255.0
    # The walk was shot before sunrise; the sampled colours are correspondingly
    # dark and the cloud reads as mud at default gain. Lift it for legibility and
    # say so -- this is a display gain, not a change to the map.
    cols = np.clip(cols.astype(np.float32) * 1.55 + 26.0, 0, 255)

    centre = np.median(np.vstack([pts, kf]), axis=0)
    fpx = 1.05 * args.width

    # Auto-fit the orbit radius by MEASURING the projection rather than guessing a
    # multiplier: hand-picked multipliers were wrong in both directions here (2.6x
    # left the map a band across the middle, 1.9x overflowed the frame), because
    # the right value depends on the cloud shape, not just its extent.
    def fit_radius(target_frac=0.44, iters=3):
        r = 3.0 * np.percentile(np.linalg.norm(pts - centre, axis=1), 88)
        target = target_frac * min(args.width, args.height)
        for _ in range(iters):
            a, elev = 0.0, np.deg2rad(42)
            eye = centre + r * np.array([np.cos(a) * np.cos(elev), -np.sin(elev),
                                         np.sin(a) * np.cos(elev)])
            R, t = look_at(eye, centre)
            uv, z, ok = project(np.vstack([pts, kf]), R, t, fpx,
                                args.width / 2, args.height / 2)
            if ok.sum() < 10:
                break
            rad = np.linalg.norm(uv[ok] - np.array([args.width / 2, args.height / 2]), axis=1)
            r95 = np.percentile(rad, 95)
            if r95 <= 1e-6:
                break
            r *= float(r95 / target)
        return r

    radius = fit_radius()

    W, H = args.width, args.height
    vw = cv2.VideoWriter(args.out, cv2.VideoWriter_fourcc(*"mp4v"), args.fps, (W, H))
    for i in range(args.frames):
        a = 2 * np.pi * i / args.frames
        elev = np.deg2rad(42 + 14 * np.sin(2 * a))
        eye = centre + radius * np.array([np.cos(a) * np.cos(elev),
                                          -np.sin(elev),
                                          np.sin(a) * np.cos(elev)])
        R, t = look_at(eye, centre)
        img = draw(pts, cols, kf, R, t, W, H, fpx)

        cv2.putText(img, "SPARSE MAP  /  monocular SLAM", (18, 34),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.68, (235, 238, 242), 2, cv2.LINE_AA)
        cv2.putText(img, f"{len(pts):,} map points   {len(kf)} keyframes", (18, 58),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.48, (150, 220, 120), 1, cv2.LINE_AA)
        cv2.putText(img, "green = camera path   |   point colour sampled from frames (display gain 1.55x)",
                    (18, H - 58),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (150, 220, 120), 1, cv2.LINE_AA)
        cv2.putText(img, "axes in ARBITRARY units - monocular has no scale", (18, H - 36),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (90, 150, 250), 1, cv2.LINE_AA)
        cv2.putText(img, "0 loop closures (known-open, RUNBOOK 7c)", (18, H - 14),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (120, 128, 140), 1, cv2.LINE_AA)
        vw.write(img)
    vw.release()
    print(f"wrote {args.out}: {args.frames} frames, {len(pts):,}/{n0:,} points kept, {len(kf)} keyframes")


if __name__ == "__main__":
    main()
