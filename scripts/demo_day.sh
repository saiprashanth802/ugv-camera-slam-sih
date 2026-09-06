#!/usr/bin/env bash
# Sightline — the whole demonstration, one command.
#
# Five segments, fullscreen, pausing between each so you can narrate. Segment 4
# attempts the real Nav2 run in Gazebo and falls back to the recording on any
# failure or timeout, so the demo cannot stall in front of judges.
#
#   ./scripts/demo_day.sh              run everything
#   ./scripts/demo_day.sh --check      preflight only, then exit  <- rehearsal gate
#   ./scripts/demo_day.sh --no-live    skip the live attempt, use the recording
#   ./scripts/demo_day.sh --from 4     start at segment 4
#   ./scripts/demo_day.sh --live-timeout 300
#   ./scripts/demo_day.sh --no-play    print what would play instead of playing it
#
# --no-play exists to rehearse the FALLBACK, not the demo: it lets you prove the
# live Nav2 segment degrades to the recording inside its deadline without sitting
# through six minutes of video to find out.
#
# Deliberately NOT set -e: a failing live segment must fall back, not abort the
# demo. Every step that can fail is checked explicitly.
set -uo pipefail

WS="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$WS"

LIVE=1
FROM=1
CHECK_ONLY=0
LIVE_TIMEOUT=240
NO_PLAY=0
UI_PORT="${UI_PORT:-8777}"
CONTAINER="${NAME:-sightline}"
IMAGE="${IMAGE:-ugv-slam:demo}"

while [ $# -gt 0 ]; do
  case "$1" in
    --check)         CHECK_ONLY=1 ;;
    --no-live)       LIVE=0 ;;
    --no-play)       NO_PLAY=1 ;;
    --from)          FROM="${2:-1}"; shift ;;
    --live-timeout)  LIVE_TIMEOUT="${2:-240}"; shift ;;
    -h|--help)       sed -n '2,20p' "$0"; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
  shift
done

B=$'\033[1m'; G=$'\033[32m'; R=$'\033[31m'; Y=$'\033[33m'; D=$'\033[2m'; N=$'\033[0m'

S1=media/phone_walk_slam_demo.mp4
S2=media/kitti06_gt_demo_3x.mp4
S3=media/map_building.mp4
S4=media/nav2_goal_run.mp4

HTTP_PID=""
cleanup() {
  [ -n "$HTTP_PID" ] && kill "$HTTP_PID" 2>/dev/null
  docker rm -f "$CONTAINER" >/dev/null 2>&1
}
trap cleanup EXIT INT TERM

# ---------------------------------------------------------------- preflight --

PLAYER=""
pick_player() {
  if command -v mpv >/dev/null;   then PLAYER=mpv;   return 0; fi
  if command -v ffplay >/dev/null; then PLAYER=ffplay; return 0; fi
  return 1
}

row() { # row <PASS|FAIL|WARN> <label> <detail>
  local s="$1"; shift; local label="$1"; shift
  local c="$G"; [ "$s" = FAIL ] && c="$R"; [ "$s" = WARN ] && c="$Y"
  printf "  %b%-4s%b  %-34s %s\n" "$c" "$s" "$N" "$label" "${1:-}"
}

preflight() {
  local fail=0
  echo
  echo "${B}Sightline preflight${N}   $(date '+%Y-%m-%d %H:%M')"
  echo

  if pick_player; then row PASS "video player" "$PLAYER"
  else row FAIL "video player" "install mpv  -> no video segment can play"; fail=1; fi

  local f
  for f in "$S1" "$S2" "$S3" "$S4"; do
    if [ ! -f "$f" ]; then
      row FAIL "$(basename "$f")" "MISSING"
      fail=1
    elif ffprobe -v error -show_entries format=duration -of csv=p=0 "$f" >/dev/null 2>&1; then
      row PASS "$(basename "$f")" "$(printf '%.0fs' "$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$f")")"
    else
      row FAIL "$(basename "$f")" "will not decode"
      fail=1
    fi
  done

  if [ -f frontend/dist/index.html ]; then row PASS "mission-control UI" "frontend/dist built"
  else row WARN "mission-control UI" "not built -> segment 5 skipped (npm run build in frontend/)"; fi

  if [ "$LIVE" -eq 1 ]; then
    if docker image inspect "$IMAGE" >/dev/null 2>&1; then row PASS "sim image" "$IMAGE"
    else row WARN "sim image" "$IMAGE absent -> segment 4 uses the recording"; fi
    if xhost >/dev/null 2>&1; then row PASS "X / XWayland" "reachable"
    else row WARN "X / XWayland" "no display -> segment 4 uses the recording"; fi
  else
    row PASS "live Nav2" "disabled (--no-live), using the recording"
  fi

  echo
  if [ "$fail" -ne 0 ]; then
    echo "  ${R}Preflight FAILED.${N} Fix the FAIL rows; WARN rows fall back on their own."
    return 1
  fi
  echo "  ${G}Ready.${N} WARN rows degrade gracefully; FAIL rows do not."
  echo
  return 0
}

# ----------------------------------------------------------------- helpers --

pause() {
  [ -t 0 ] || return 0
  echo
  read -rsn1 -p "  ${D}press any key for the next segment...${N}" _ || true
  echo; echo
}

say() { # the RUNBOOK section 10 talking points, printed for the presenter
  echo "  ${Y}SAY:${N} $1"
}

banner() { echo; echo "${B}── $1 ──${N}"; echo; }

play() { # play <file> ; returns non-zero if it could not play
  local f="$1"
  [ -f "$f" ] || { echo "  ${R}missing:${N} $f"; return 1; }
  if [ "$NO_PLAY" -eq 1 ]; then
    echo "  ${D}[--no-play] would play $f ($(printf '%.0fs' "$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$f")"))${N}"
    return 0
  fi
  case "$PLAYER" in
    mpv)    mpv --fullscreen --really-quiet --no-terminal --osd-level=0 "$f" ;;
    ffplay) ffplay -fs -autoexit -loglevel error "$f" ;;
    *)      return 1 ;;
  esac
}

# ------------------------------------------------------------ live segment --

ROS_PRELUDE='source /opt/ros/humble/setup.bash 2>/dev/null || true;
for w in /root/*_ws /opt/*_ws; do [ -f "$w/install/setup.bash" ] && source "$w/install/setup.bash" 2>/dev/null; done; true;'

dexec() { docker exec "$CONTAINER" bash -c "$ROS_PRELUDE $1"; }

live_nav2() {
  local t0=$(date +%s)
  local deadline=$(( t0 + LIVE_TIMEOUT ))
  step() { printf '  [%3ds] %s\n' "$(( $(date +%s) - t0 ))" "$1"; }
  # seconds left on the single hard deadline for the whole live attempt; never
  # returns <=0, because `timeout 0` means "no timeout" and would hang the demo.
  left() { local r=$(( deadline - $(date +%s) )); [ "$r" -gt 0 ] && echo "$r" || echo 0; }

  docker image inspect "$IMAGE" >/dev/null 2>&1 || { echo "  image $IMAGE absent"; return 1; }

  step "starting container..."
  "$WS/scripts/run_demo.sh" --detach >/dev/null 2>&1 || { echo "  container failed to start"; return 1; }

  step "checking the GPU..."
  if ! dexec 'bash /ws/scripts/check_gpu.sh' 2>/dev/null | grep -q '^PASS'; then
    echo "  ${Y}GPU check did not PASS${N} — Gazebo would render on the iGPU"
    return 1
  fi

  step "launching Gazebo + RTAB-Map + Nav2 (this is the slow part)..."
  docker exec -d "$CONTAINER" bash -c \
    "$ROS_PRELUDE export TURTLEBOT3_MODEL=waffle;
     ros2 launch rtabmap_demos turtlebot3_sim_rgbd_demo.launch.py > /tmp/nav2.log 2>&1" \
    || { echo "  launch failed"; return 1; }

  step "waiting for /map"; echo -n "  "
  while [ "$(left)" -gt 0 ]; do
    if dexec 'ros2 topic list 2>/dev/null' | grep -qx '/map'; then
      if timeout 20 docker exec "$CONTAINER" bash -c \
           "$ROS_PRELUDE ros2 topic echo /map --once" >/dev/null 2>&1; then
        echo " ok"; break
      fi
    fi
    echo -n "."; sleep 5
  done
  [ "$(left)" -gt 0 ] || { echo; echo "  ${Y}timed out waiting for /map${N}"; return 1; }

  # planner_server comes up with use_sim_time FALSE while every other Nav2 node
  # and rtabmap have it TRUE (measured 2026-09-06; /clock publishes fine at 10 Hz).
  # The planner then stamps its path with wall-clock time, controller_server reads
  # it as sim time, calls the data "too old" when converting map->odom, never
  # follows the path, and the goal ABORTs with "Failed to make progress" -- which
  # reads like an unreachable goal but is not: the planner produced a path fine.
  step "normalising use_sim_time across Nav2..."
  local n
  for n in /planner_server /controller_server /bt_navigator /behavior_server \
           /smoother_server /velocity_smoother; do
    dexec "ros2 param set $n use_sim_time true" >/dev/null 2>&1
  done

  # Never hand-guess a goal: RUNBOOK section 4 records (-1.0, -0.3) looking like
  # open floor, sitting inside a wall, and aborting every single time.
  step "choosing a reachable goal..."
  local goal x y
  goal="$(timeout 60 docker exec "$CONTAINER" bash -c \
            "$ROS_PRELUDE python3 /ws/scripts/pick_goal.py" 2>/dev/null \
          | awk '/^GOAL/{print $2, $3; exit}')"
  x="$(echo "$goal" | awk '{print $1}')"; y="$(echo "$goal" | awk '{print $2}')"
  [ -n "$x" ] && [ -n "$y" ] || { echo "  ${Y}pick_goal.py returned no goal${N}"; return 1; }
  echo "  goal: ($x, $y)"

  step "sending it ($(left)s left on the deadline)"
  local out
  [ "$(left)" -gt 0 ] || { echo "  ${Y}out of time before sending the goal${N}"; return 1; }
  out="$(timeout "$(left)" docker exec "$CONTAINER" bash -c \
    "$ROS_PRELUDE ros2 action send_goal /navigate_to_pose nav2_msgs/action/NavigateToPose \
     \"{pose: {header: {frame_id: map}, pose: {position: {x: $x, y: $y}, orientation: {w: 1.0}}}}\"" 2>&1)"

  if echo "$out" | grep -qiE 'result.*succeeded|Goal finished with status: SUCCEEDED'; then
    step "${G}goal reached — that was live${N}"
    return 0
  fi
  if echo "$out" | grep -qi 'Goal accepted'; then
    step "${Y}goal accepted but did not succeed${N}"
    diagnose_live "$out"
    return 1
  fi
  step "${Y}goal was rejected${N}"
  diagnose_live "$out"
  return 1
}

# Why the live run failed, printed before the container is torn down. Without
# this the fallback is silent and the same failure gets rediagnosed from scratch
# next time -- at a venue, with no time.
diagnose_live() {
  echo "  ${D}--- why it failed ---${N}"
  echo "$1" | grep -aiE 'status|result|aborted|canceled' | tail -4 | sed 's/^/    /'
  docker exec "$CONTAINER" bash -c \
    'grep -aiE "GridBased failed|Goal failed|aborted|no valid path|Failed to make progress|collision" /tmp/nav2.log | tail -6' \
    2>/dev/null | sed 's/^/    /'
  docker exec "$CONTAINER" bash -c \
    "source /opt/ros/humble/setup.bash 2>/dev/null; timeout 8 ros2 topic echo --once --field info /map 2>/dev/null | grep -E '^(width|height|resolution)'" \
    2>/dev/null | sed 's/^/    map /'
}

# -------------------------------------------------------------- segments ---

seg1() {
  banner "1/5  Real phone footage -> visual SLAM map -> 3D map"
  say "Monocular gives no metric scale. This map is qualitative — never quote distances off it."
  say "Shot pre-dawn on a covered walkway, not the outdoor daylight our spec claims. That is disclosed."
  play "$S1"
}

seg2() {
  banner "2/5  How accurate is it? Ground truth vs SLAM"
  say "The walk has no ground truth, so this is KITTI 06, the scored reference sequence."
  say "APE is a distribution, not a point: four runs today spanned 12.2-14.4 m over a 1223 m path."
  say "Loop closure fires zero times — nothing corrects this drift. Known and open."
  play "$S2"
}

seg3() {
  banner "3/5  Simulated robot builds its own map"
  say "The simulated depth sensor is noise-free, so this looks cleaner than real hardware would."
  say "Frame it as 'what a real depth camera gives us', not as a field result."
  play "$S3"
}

seg4() {
  banner "4/5  Autonomous navigation to a goal, GPS-free"
  say "Phone map and sim map are different coordinate frames. The halves connect by narrative, not a shared map."
  local ok=1
  if [ "$LIVE" -eq 1 ]; then
    echo "  ${D}attempting the live run (deadline ${LIVE_TIMEOUT}s; falls back automatically)${N}"
    echo
    live_nav2 && ok=0
    echo
    if [ "$ok" -ne 0 ]; then
      echo "  ${Y}falling back to the recorded run — rung 1 of the ladder.${N}"
      docker rm -f "$CONTAINER" >/dev/null 2>&1
    fi
  fi
  [ "$ok" -ne 0 ] && play "$S4"
  say "Proves: vision -> map -> autonomous navigation works. Does NOT prove: robustness to real terrain, noise or lighting."
}

seg5() {
  banner "5/5  Mission-control UI"
  if [ ! -f frontend/dist/index.html ]; then
    echo "  ${Y}frontend/dist not built — skipping.${N}  (cd frontend && npm run build)"
    return 0
  fi
  python3 -m http.server "$UI_PORT" --directory frontend/dist >/dev/null 2>&1 &
  HTTP_PID=$!
  sleep 1
  say "This is demo-fed, not ROS-fed, and the DEMO DATA markers on screen say so."
  say "The SLAM metrics shown are the 2026-09-05 run; today's runs scored better. Do not defend the exact number."
  echo "  serving http://localhost:${UI_PORT}"
  command -v xdg-open >/dev/null && xdg-open "http://localhost:${UI_PORT}" >/dev/null 2>&1
  pause
  kill "$HTTP_PID" 2>/dev/null; HTTP_PID=""
}

# ------------------------------------------------------------------- main ---

preflight || exit 1
[ "$CHECK_ONLY" -eq 1 ] && exit 0

pick_player || { echo "no video player"; exit 1; }

for n in 1 2 3 4 5; do
  [ "$n" -lt "$FROM" ] && continue
  "seg$n"
  [ "$n" -lt 5 ] && pause
done

banner "Done"
echo "  Fallback ladder if anything above failed live: RUNBOOK section 9."
echo
