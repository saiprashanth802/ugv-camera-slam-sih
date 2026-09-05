#!/usr/bin/env python3
"""Score a pySLAM trajectory against ground truth (Umeyama-aligned APE).

pySLAM writes results/<run>/trajectory_final.txt as KITTI 12-column rows (a
flattened 3x4 pose, no timestamps). The kitti06 clip that ships with the repo
writes groundtruth.txt as 9 columns: TUM (t x y z qx qy qz qw) plus a trailing
scale column. Neither evo importer accepts that pair directly, which is why
earlier attempts here produced plots but never a number.

Monocular SLAM has no metric scale, so a raw position diff is meaningless. The
only honest comparison is a similarity (sim3) alignment -- rotation, translation
AND a single global scale -- after which the residual is real trajectory error.
That is what evo's --correct_scale does; this reimplements it so the check has
no format-conversion step to get wrong.

The estimate is usually shorter than the ground truth (initialisation frames
carry no pose). Rather than assume where the missing rows sit, both alignments
are scored and the better one is reported, with the offset stated.

Usage:
  eval_trajectory.py results/<run>/trajectory_final.txt data/videos/kitti06/groundtruth.txt
"""
import sys
import numpy as np


def load_est(path):
    a = np.loadtxt(path)
    if a.ndim != 2 or a.shape[1] != 12:
        raise SystemExit(f"{path}: expected 12 columns (KITTI), got {a.shape}")
    return a.reshape(-1, 3, 4)[:, :, 3]          # translation column only


def load_gt(path):
    a = np.loadtxt(path)
    if a.ndim != 2 or a.shape[1] not in (8, 9):
        raise SystemExit(f"{path}: expected 8 or 9 columns (TUM[+scale]), got {a.shape}")
    return a[:, 1:4]                              # x y z


def umeyama_sim3(src, dst):
    """Least-squares similarity transform mapping src onto dst (Umeyama 1991)."""
    mu_s, mu_d = src.mean(0), dst.mean(0)
    s0, d0 = src - mu_s, dst - mu_d
    cov = d0.T @ s0 / len(src)
    U, D, Vt = np.linalg.svd(cov)
    S = np.eye(3)
    if np.linalg.det(U) * np.linalg.det(Vt) < 0:   # reflection guard
        S[2, 2] = -1
    R = U @ S @ Vt
    scale = float(np.trace(np.diag(D) @ S) / s0.var(0).sum())
    t = mu_d - scale * R @ mu_s
    return scale, R, t


def ape(est, gt):
    scale, R, t = umeyama_sim3(est, gt)
    aligned = (scale * (R @ est.T)).T + t
    err = np.linalg.norm(aligned - gt, axis=1)
    return err, scale


def main():
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    est, gt = load_est(sys.argv[1]), load_gt(sys.argv[2])
    n = min(len(est), len(gt))
    print(f"estimate {len(est)} poses, groundtruth {len(gt)} poses -> comparing {n}")

    best = None
    for label, g in (("head-aligned (est[0] == gt[0])", gt[:n]),
                     ("tail-aligned (est[-1] == gt[-1])", gt[len(gt) - n:])):
        err, scale = ape(est[:n], g)
        rmse = float(np.sqrt((err ** 2).mean()))
        print(f"  {label:34s} RMSE {rmse:7.3f} m   scale {scale:.4f}")
        if best is None or rmse < best[1]:
            best = (label, rmse, err, scale)

    label, rmse, err, scale = best
    length = float(np.linalg.norm(np.diff(gt[:n], axis=0), axis=1).sum())
    print(f"\nbest alignment: {label}")
    print(f"  APE RMSE   {rmse:.3f} m")
    print(f"  APE mean   {err.mean():.3f} m   median {np.median(err):.3f} m   max {err.max():.3f} m")
    print(f"  sim3 scale {scale:.4f}  (monocular has no metric scale; this is the fitted factor)")
    print(f"  path length {length:.1f} m  ->  RMSE is {100 * rmse / length:.2f}% of trajectory length")


if __name__ == "__main__":
    main()
