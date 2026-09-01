#!/usr/bin/env python3
"""
Give the TurtleBot3 waffle a working DEPTH camera.

WHY THIS EXISTS
  SPEC.md picked the waffle because it "has a depth camera (needed for RTAB-Map RGB-D)".
  Verified 2026-09-01 against ros-humble-turtlebot3-gazebo 2.3.8: NOT true out of the box.
  waffle and waffle_pi each carry three sensors -- imu, ray (lidar), and a MONOCULAR RGB
  camera. Only leftover camera_depth_* TF frames in the URDF make it look otherwise.
  Without depth, RTAB-Map has no RGB-D input and the sim half of the demo does not exist.

WHAT IT DOES
  Applies the modifications the RTAB-Map maintainer documents at the top of
  /opt/ros/humble/share/rtabmap_demos/launch/turtlebot3/turtlebot3_sim_rgbd_demo.launch.py
  (the "Requirements" block), for ROS 2 Humble. Following that recipe verbatim rather than
  improvising is deliberate: an earlier hand-rolled version of this patch changed the far
  clip and stripped the <noise> block, and produced a camera that published at the right
  rate but rendered BLANK frames -- rtabmap then reported features=0, lost=true while the
  robot was visibly moving. The upstream recipe is the supported path.

  1. <sensor name="camera" type="camera">  ->  type="depth"
  2. image 1920x1080 -> 640x480
  3. rename <link name="camera_rgb_frame"> -> <link name="camera_rgb_optical_frame">
  4. add an empty <link name="camera_rgb_frame"/>
  5. add camera_rgb_optical_joint with the optical-frame rotation

  Steps 3-5 matter because ROS image topics are published in the optical convention
  (z forward, x right). Without that frame, RTAB-Map's TF lookup resolves against a
  body-convention frame and the map comes out rotated 90 degrees.
"""
import re
import sys

SDF = "/opt/ros/humble/share/turtlebot3_gazebo/models/turtlebot3_waffle/model.sdf"
src = open(SDF).read()
orig = src
applied = []

# 1. camera sensor -> depth sensor
src, n = re.subn(r'<sensor name="camera" type="camera">',
                 '<sensor name="camera" type="depth">', src)
applied.append(("sensor type -> depth", n))

# 2. 1920x1080 -> 640x480, scoped to the camera block
cam = re.search(r'<camera name="intel_realsense_r200">.*?</camera>', src, re.S)
if not cam:
    sys.exit("FAIL: camera block not found -- package layout changed, re-inspect the SDF")
blk = cam.group(0)
new = blk.replace("<width>1920</width>", "<width>640</width>") \
         .replace("<height>1080</height>", "<height>480</height>")
src = src.replace(blk, new)
applied.append(("image -> 640x480", int(blk != new)))

# 3 + 4. rename the rgb link to the optical frame, and re-add the body frame
src, n = re.subn(r'<link name="camera_rgb_frame">',
                 '<link name="camera_rgb_frame"/>\n    <link name="camera_rgb_optical_frame">',
                 src)
applied.append(("rgb link -> optical + body link", n))

# 5. joint linking the body frame to the optical frame
joint = """
    <joint name="camera_rgb_optical_joint" type="fixed">
      <parent>camera_rgb_frame</parent>
      <child>camera_rgb_optical_frame</child>
      <pose>0 0 0 -1.57079632679 0 -1.57079632679</pose>
      <axis>
        <xyz>0 0 1</xyz>
      </axis>
    </joint>
"""
m = re.search(r'<joint name="camera_rgb_joint" type="fixed">.*?</joint>', src, re.S)
if not m:
    sys.exit("FAIL: camera_rgb_joint not found")
src = src.replace(m.group(0), m.group(0) + "\n" + joint)
applied.append(("camera_rgb_optical_joint", 1))

for name, count in applied:
    print(f"  {'OK  ' if count == 1 else 'FAIL'} {name}")
if any(c != 1 for _, c in applied) or src == orig:
    sys.exit("FAIL: patch did not apply cleanly")

open(SDF, "w").write(src)
print(f"patched {SDF}")
