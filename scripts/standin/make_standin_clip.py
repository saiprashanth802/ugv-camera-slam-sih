import cv2, sys
src = "vendor/pyslam/data/videos/kitti06/video_color.mp4"
dst = "vendor/pyslam/data/videos/phone_walk/walk.mp4"
W, H, FPS = 1280, 720, 30.0
cap = cv2.VideoCapture(src)
if not cap.isOpened():
    sys.exit("cannot open source")
print("src:", int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), "x", int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
      "@", cap.get(cv2.CAP_PROP_FPS), "frames", int(cap.get(cv2.CAP_PROP_FRAME_COUNT)))
out = cv2.VideoWriter(dst, cv2.VideoWriter_fourcc(*"mp4v"), FPS, (W, H))
n = 0
while True:
    ok, f = cap.read()
    if not ok:
        break
    out.write(cv2.resize(f, (W, H), interpolation=cv2.INTER_AREA))
    n += 1
cap.release(); out.release()
print("wrote", n, "frames ->", dst)
