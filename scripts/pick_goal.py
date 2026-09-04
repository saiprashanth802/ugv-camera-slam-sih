#!/usr/bin/env python3
"""
Sightline - pick a Nav2 goal that will actually plan.

WHY: sending a hand-guessed goal pose is how you get
  planner_server: "GridBased failed to generate a valid path to (x, y)"
  bt_navigator:   "Goal failed"
in front of judges. Verified 2026-09-05: the goal (-1.0, -0.3) - which looks
fine on screen - sits inside a wall of turtlebot3_house and aborts every time.

This reads the live /map occupancy grid and the map->base_footprint transform,
then returns a cell that is (a) known-free, (b) surrounded by 0.3 m of known-free
space on all sides, and (c) about 2.5 m from the robot. Goals chosen this way
planned and drove successfully on the first attempt.

RUN IT INSIDE THE CONTAINER, with the demo already up:
  python3 /ws/scripts/pick_goal.py
then feed the printed coordinates to the send_goal command in RUNBOOK section 4.
"""

import rclpy, math
from rclpy.node import Node
from nav_msgs.msg import OccupancyGrid
from rclpy.qos import QoSProfile, QoSDurabilityPolicy, QoSReliabilityPolicy
import tf2_ros

class P(Node):
    def __init__(self):
        super().__init__('pickgoal')
        q=QoSProfile(depth=1); q.durability=QoSDurabilityPolicy.TRANSIENT_LOCAL
        q.reliability=QoSReliabilityPolicy.RELIABLE
        self.m=None
        self.create_subscription(OccupancyGrid,'/map',self.cb,q)
    def cb(self,msg): self.m=msg

rclpy.init()
n=P()
buf=tf2_ros.Buffer(); li=tf2_ros.TransformListener(buf,n)
import time
t0=time.time()
while rclpy.ok() and (n.m is None or time.time()-t0<3.0):
    rclpy.spin_once(n,timeout_sec=0.2)
    if n.m is not None and time.time()-t0>3.0: break
m=n.m
assert m is not None, "no /map"
W,H,res=m.info.width,m.info.height,m.info.resolution
ox,oy=m.info.origin.position.x,m.info.origin.position.y
g=m.data
# robot pose in map
rx=ry=None
for _ in range(40):
    try:
        tr=buf.lookup_transform('map','base_footprint',rclpy.time.Time())
        rx,ry=tr.transform.translation.x,tr.transform.translation.y; break
    except Exception:
        rclpy.spin_once(n,timeout_sec=0.1)
assert rx is not None,"no tf"
print(f"MAP {W}x{H} res={res:.3f} origin=({ox:.2f},{oy:.2f})")
print(f"ROBOT map=({rx:.2f},{ry:.2f})")

def free(cx,cy,r=6):
    # every cell within r must be known-free
    for dy in range(-r,r+1):
        for dx in range(-r,r+1):
            x,y=cx+dx,cy+dy
            if x<0 or y<0 or x>=W or y>=H: return False
            v=g[y*W+x]
            if v!=0: return False
    return True

best=None
for cy in range(H):
    for cx in range(W):
        if g[cy*W+cx]!=0: continue
        wx=ox+(cx+0.5)*res; wy=oy+(cy+0.5)*res
        d=math.hypot(wx-rx,wy-ry)
        if d<1.5 or d>4.0: continue
        if not free(cx,cy): continue
        # prefer ~2.5m away
        score=abs(d-2.5)
        if best is None or score<best[0]: best=(score,wx,wy,d)
assert best,"no candidate goal found"
_,gx,gy,d=best
print(f"GOAL {gx:.2f} {gy:.2f}  (dist {d:.2f} m, 0.3m clearance all round)")
