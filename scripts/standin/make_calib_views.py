"""Stand-in rehearsal scaffolding (see scripts/standin/README.md).

Synthetic chessboard stills from a KNOWN camera, so calibrate_camera.py can be
exercised end to end without a printed board. Same validation trick RUNBOOK 7a
records for 2026-09-01, retargeted at the stand-in clip's intrinsics."""
import cv2, numpy as np, os

W, H = 1280, 720
sx, sy = 1280/1226, 720/370
FX, FY = 707.0912*sx, 707.0912*sy
CX, CY = 601.8873*sx, 183.1104*sy
K = np.array([[FX,0,CX],[0,FY,CY],[0,0,1]], float)
print(f"TRUE fx={FX:.4f} fy={FY:.4f} cx={CX:.4f} cy={CY:.4f}")

COLS, ROWS, SQ = 9, 6, 60
board = np.zeros(((ROWS+1)*SQ, (COLS+1)*SQ), np.uint8)
for r in range(ROWS+1):
    for c in range(COLS+1):
        if (r+c) % 2 == 0:
            board[r*SQ:(r+1)*SQ, c*SQ:(c+1)*SQ] = 255
board = cv2.cvtColor(board, cv2.COLOR_GRAY2BGR)
A = np.array([[SQ,0,SQ],[0,SQ,SQ],[0,0,1]], float)
Ainv = np.linalg.inv(A)
obj = np.array([[x, y, 0.0] for y in range(ROWS) for x in range(COLS)])
centroid = np.array([(COLS-1)/2, (ROWS-1)/2, 0.0])

rng = np.random.default_rng(11)
out = "media/calib_standin"; os.makedirs(out, exist_ok=True)
# spread the board across the frame: corners get covered, which is what fixes cx/cy
targets = [(u, v) for v in (0.28, 0.5, 0.72) for u in (0.25, 0.4, 0.55, 0.7)]
n = 0
for i, (fu, fv) in enumerate(targets * 3):
    rvec = np.array([rng.uniform(-0.5,0.5), rng.uniform(-0.5,0.5), rng.uniform(-0.4,0.4)])
    R, _ = cv2.Rodrigues(rvec)
    z = rng.uniform(17.0, 27.0)
    u, v = fu*W + rng.uniform(-30,30), fv*H + rng.uniform(-30,30)
    c = R @ centroid
    Pz = z
    P = np.array([(u-CX)/FX*Pz, (v-CY)/FY*Pz, Pz])
    t = P - c
    proj, _ = cv2.projectPoints(obj, rvec, t, K, np.zeros(5))
    p = proj.reshape(-1,2)
    if p[:,0].min() < 15 or p[:,0].max() > W-15 or p[:,1].min() < 15 or p[:,1].max() > H-15:
        continue
    Hmat = K @ np.column_stack([R[:,0], R[:,1], t]) @ Ainv
    frame = np.full((H, W, 3), 235, np.uint8)
    cv2.warpPerspective(board, Hmat, (W, H), flags=cv2.INTER_LINEAR,
                        borderMode=cv2.BORDER_TRANSPARENT, dst=frame)
    cv2.imwrite(f"{out}/view{n:02d}.png", frame)
    n += 1
    if n >= 22:
        break
print("wrote", n, "views to", out)
