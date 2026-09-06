#!/usr/bin/env python3
"""Swap the active VIDEO_DATASET block in vendor/pyslam/config.yaml.
KITTI 06 stays present, commented, so RUNBOOK 7c's reference run is one edit away."""
import re, sys, os
cfg = os.path.expanduser("~/claude_code_projects/sih_sightline/vendor/pyslam/config.yaml")
which = sys.argv[1]                       # A | B | C | kitti
blocks = {
 "A": ("./data/videos/phone_walk", "settings/SIGHTLINE_WALK_A.yaml", "walkA.mp4"),
 "B": ("./data/videos/phone_walk", "settings/SIGHTLINE_WALK_B.yaml", "walkB.mp4"),
 "C": ("./data/videos/phone_walk", "settings/SIGHTLINE_WALK_C.yaml", "walkC.mp4"),
}
s = open(cfg).read()
if which == "kitti":
    body = ("  base_path: ./data/videos/kitti06\n"
            "  settings: settings/KITTI04-12.yaml\n"
            "  name: video_color.mp4\n"
            "  groundtruth_file: groundtruth.txt\n"
            "  timestamps: times.txt\n")
else:
    bp, st, nm = blocks[which]
    body = (f"  base_path: {bp}\n  settings: {st}\n  name: {nm}\n"
            "  # groundtruth_file / timestamps deliberately ABSENT (RUNBOOK 7d)\n")
new = ("VIDEO_DATASET:\n  type: video\n  sensor_type: mono\n"
       f"  # --- ACTIVE: {which} ---\n{body}"
       "  # --- KITTI 06 reference run, swap back for RUNBOOK 7c ---\n"
       "  #base_path: ./data/videos/kitti06\n"
       "  #settings: settings/KITTI04-12.yaml\n"
       "  #name: video_color.mp4\n"
       "  #groundtruth_file: groundtruth.txt\n"
       "  #timestamps: times.txt\n")
s2 = re.sub(r"VIDEO_DATASET:\n(?:.*?\n)*?\n\nFOLDER_DATASET:", new + "\n\nFOLDER_DATASET:", s, count=1)
assert s2 != s, "VIDEO_DATASET block not replaced"
open(cfg, "w").write(s2)
print(f"config.yaml -> {which}")
print(new)
