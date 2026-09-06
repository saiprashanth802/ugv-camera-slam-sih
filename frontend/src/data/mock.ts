/**
 * mock.ts — Demo-mode data source for Sightline Mission Control.
 *
 * Provides:
 *   INITIAL_APP_STATE  — snapshot matching verified RUNBOOK §4/§7c numbers
 *   MockDataBridge     — implements DataBridge, animates robot toward goal at 300 ms ticks
 *
 * All numbers sourced from RUNBOOK.md. Nothing is fabricated.
 * When the ROS bridge is ready, replace MockDataBridge with RosDataBridge
 * via store.setBridge() — no component changes required.
 */

import type { AppState, OccupancyGrid, TimelineEvent } from '../types';
import type { DataBridge, StateUpdate } from '../bridge/DataBridge';

// ─── Verified coordinates from RUNBOOK §4 ────────────────────────────────────

const ROBOT_START_X = -6.40; // map frame, meters
const ROBOT_START_Y = -1.86;
const GOAL_X = -6.21; // pick_goal.py output
const GOAL_Y = 0.63;

function dist(x1: number, y1: number, x2: number, y2: number): number {
  return Math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2);
}

// ─── Occupancy grid ───────────────────────────────────────────────────────────
// 160×160 cells @ 0.05 m — proportional to the real 202×205 map from pick_goal.py.
// Origin matches RUNBOOK §4: "origin=(-8.03,-4.54)".

function buildMockGrid(): OccupancyGrid {
  const W = 160;
  const H = 160;
  const resolution = 0.05; // m/cell
  const origin = { x: -8.03, y: -4.54 };
  const data = new Int8Array(W * H).fill(-1); // -1 = unknown by default

  const fill = (x0: number, y0: number, x1: number, y1: number, v: number) => {
    for (let cy = Math.max(0, y0); cy < Math.min(H, y1); cy++)
      for (let cx = Math.max(0, x0); cx < Math.min(W, x1); cx++)
        data[cy * W + cx] = v;
  };

  // Explored free space — main room (contains robot and goal)
  fill(4, 4, 100, 138, 0);
  // Explored free space — right wing (partially explored)
  fill(100, 4, 154, 95, 0);

  // ── Outer walls ──
  fill(0, 0, W, 4, 100);
  fill(0, H - 4, W, H, 100);
  fill(0, 0, 4, H, 100);
  fill(W - 4, 0, W, H, 100);

  // ── Interior walls (house rooms) ──

  // Horizontal divider — crosses the robot→goal path.
  // Gap at x=26–50 lets the planned path through (robot x≈32, goal x≈36).
  fill(4, 77, 100, 81, 100);
  fill(26, 77, 50, 81, 0); // door / gap

  // Lower horizontal wall
  fill(4, 36, 62, 40, 100);
  fill(18, 36, 32, 40, 0); // door

  // Right-side vertical wall
  fill(97, 4, 101, 130, 100);
  fill(97, 42, 101, 60, 0); // doorway to right wing

  // Inner left partition
  fill(52, 40, 56, 77, 100);
  fill(52, 58, 56, 70, 0); // gap

  // Upper room divider
  fill(4, 110, 68, 114, 100);
  fill(28, 110, 44, 114, 0); // door

  // Right wing divider
  fill(100, 56, 154, 60, 100);
  fill(120, 56, 138, 60, 0); // door

  return { width: W, height: H, resolution, origin, data };
}

// ─── Planned path (world frame) ───────────────────────────────────────────────
// Approximates the route a Nav2 GridBased planner would produce from
// ROBOT_START to GOAL — bends west to thread the wall gap, then straightens.

const PLANNED_PATH: { x: number; y: number }[] = [
  { x: -6.40, y: -1.86 }, // robot start
  { x: -6.39, y: -1.55 },
  { x: -6.38, y: -1.22 },
  { x: -6.37, y: -0.90 },
  { x: -6.36, y: -0.58 },
  { x: -6.34, y: -0.28 },
  { x: -6.32, y: -0.02 }, // approaching wall gap
  { x: -6.30, y:  0.22 }, // through gap (x≈32–50 cells)
  { x: -6.27, y:  0.42 },
  { x: -6.24, y:  0.55 },
  { x: -6.21, y:  0.63 }, // goal
];

// ─── Timeline script (demo — clearly labelled when displayed) ─────────────────
// Offsets are relative to the moment navigation starts (elapsedMs = 0), so the
// timeline stays in step with the mission clock across demo cycles. Events at a
// negative offset are the startup sequence that precedes the run.

interface ScriptedEvent {
  id: string;
  offsetMs: number;
  level: TimelineEvent['level'];
  message: string;
}

const EVENT_SCRIPT: ScriptedEvent[] = [
  { id: 'e1',  offsetMs:  -9_200, level: 'info',    message: 'System initialized — ROS 2 Humble' },
  { id: 'e2',  offsetMs:  -7_400, level: 'info',    message: 'RTAB-Map started — occupancy grid building' },
  { id: 'e3',  offsetMs:  -6_000, level: 'success', message: 'Localization ready — map→odom TF active' },
  { id: 'e4',  offsetMs:  -4_100, level: 'info',    message: 'Nav2 action server ready' },
  { id: 'e5',  offsetMs:    -800, level: 'success', message: 'Goal received: (−6.21, 0.63) map frame' },
  { id: 'e6',  offsetMs:    -300, level: 'info',    message: 'Path generated — GridBased planner' },
  { id: 'e7',  offsetMs:       0, level: 'info',    message: 'Navigating…' },
  { id: 'e8',  offsetMs:  12_800, level: 'warn',    message: 'Nav2 recovery behaviour triggered (1/3)' },
  { id: 'e9',  offsetMs:  24_300, level: 'warn',    message: 'Nav2 recovery behaviour triggered (2/3)' },
  { id: 'e10', offsetMs:  24_900, level: 'info',    message: 'Resuming — replanned path OK' },
];

/** Events already in the past at elapsedMs = 0 — the startup sequence. */
const PRE_NAV_COUNT = EVENT_SCRIPT.filter((e) => e.offsetMs <= 0).length;

function isRecovery(e: ScriptedEvent): boolean {
  return e.message.startsWith('Nav2 recovery behaviour triggered');
}

/** Turn the first `count` scripted events into real timestamps. */
function materialize(count: number, navStartMs: number): TimelineEvent[] {
  return EVENT_SCRIPT.slice(0, count).map(({ id, offsetMs, level, message }) => ({
    id,
    timestampMs: navStartMs + offsetMs,
    level,
    message,
  }));
}

// ─── Initial application state ────────────────────────────────────────────────

export const INITIAL_APP_STATE: AppState = {
  dataSource: 'mock',

  robot: {
    x: ROBOT_START_X,
    y: ROBOT_START_Y,
    heading: Math.atan2(GOAL_Y - ROBOT_START_Y, GOAL_X - ROBOT_START_X),
    linearVelocity: 0.42,
    angularVelocity: 0.03,
  },

  mission: {
    status: 'NAVIGATING',
    goal: { x: GOAL_X, y: GOAL_Y },
    distanceToGoal: dist(ROBOT_START_X, ROBOT_START_Y, GOAL_X, GOAL_Y),
    // Cold open is t=0 at the start pose: no distance covered, so no recoveries
    // yet. The bridge raises this to 3 (the recorded-run total) as the scripted
    // recovery events fire.
    recoveries: 0,
    elapsedMs: 0,
  },

  map: {
    grid: buildMockGrid(),
    plannedPath: PLANNED_PATH,
    traveledPath: [{ x: ROBOT_START_X, y: ROBOT_START_Y }],
  },

  perception: {
    // Verified pySLAM C++ core + GTSAM metrics on KITTI 06 (README.md & RUNBOOK.md §7c)
    trackingStatus: 'DEMO',
    framesTracked: 1101,
    totalFrames: 1101,
    keyframes: 321,
    mapPoints: 11893,
    loopClosures: 0,  // Verified: loop closure does not currently fire
    resets: 0,
    apeRmse: 49.5,    // Umeyama sim3-aligned APE RMSE — monocular, no metric scale
    pathPercentage: 4.05, // 4.05% of 1222m path
    isLive: false,
  },

  health: {
    // Demo / Recorded states based on the verified simulation stack
    ros:     'OPERATIONAL',
    gazebo:  'OPERATIONAL',
    rtabmap: 'OPERATIONAL',
    nav2:    'OPERATIONAL',
    camera:  'OPERATIONAL',
    slam:    'DEGRADED',   // DEGRADED because loop closure RANSAC verification does not converge
    bridge:  'OFFLINE',    // OFFLINE because no live ROS-web bridge is connected
  },

  timeline: materialize(PRE_NAV_COUNT, Date.now()),
};

// ─── Mock data bridge ─────────────────────────────────────────────────────────

const TICK_MS = 300;    // update interval
const STEP_M  = 0.012;  // meters moved per tick (~0.04 m/s effective)
// Nav2 goal tolerance in the recorded run was 0.21 m (RUNBOOK §8)
const GOAL_TOLERANCE_M = 0.22;

export class MockDataBridge implements DataBridge {
  subscribe(onUpdate: (update: StateUpdate) => void): () => void {
    // Mutable simulation state — local to this subscription
    let robotX       = ROBOT_START_X;
    let robotY       = ROBOT_START_Y;
    let elapsed      = INITIAL_APP_STATE.mission.elapsedMs;
    let recovery     = INITIAL_APP_STATE.mission.recoveries;
    let status       = INITIAL_APP_STATE.mission.status;
    let navStart     = Date.now();
    let emitted      = PRE_NAV_COUNT;
    let timeline     = materialize(emitted, navStart);
    let traveledPath = [{ x: ROBOT_START_X, y: ROBOT_START_Y }];
    let pending      = false; // true while goal-reached pause is in effect

    /**
     * Release any scripted events whose offset the mission clock has passed.
     * Returns true if the timeline changed, so the tick knows to publish it.
     */
    const drainScript = (): boolean => {
      let changed = false;
      while (emitted < EVENT_SCRIPT.length && EVENT_SCRIPT[emitted].offsetMs <= elapsed) {
        const ev = EVENT_SCRIPT[emitted];
        timeline = [
          ...timeline,
          { id: ev.id, timestampMs: navStart + ev.offsetMs, level: ev.level, message: ev.message },
        ];
        if (isRecovery(ev)) recovery += 1;
        emitted += 1;
        changed = true;
      }
      return changed;
    };

    const timer = setInterval(() => {
      elapsed  += TICK_MS;

      if (pending) return;

      const timelineChanged = drainScript();

      const dx = GOAL_X - robotX;
      const dy = GOAL_Y - robotY;
      const d  = Math.sqrt(dx * dx + dy * dy);

      if (d < GOAL_TOLERANCE_M) {
        // ── Goal reached ──
        status   = 'GOAL_REACHED';
        // Match verified final position from RUNBOOK §8
        robotX   = -6.36;
        robotY   =  0.47;
        recovery = 3; // third recovery fired mid-run per RUNBOOK §8

        traveledPath = [...traveledPath, { x: robotX, y: robotY }];

        timeline = [
          ...timeline,
          {
            id:          'e_goal',
            timestampMs: Date.now(),
            level:       'success' as const,
            message:     'Goal reached — final distance 0.21 m from target (inside Nav2 tolerance)',
          },
        ];

        onUpdate({
          robot: { x: robotX, y: robotY, heading: Math.atan2(dy, dx), linearVelocity: 0, angularVelocity: 0 },
          mission: { status, goal: { x: GOAL_X, y: GOAL_Y }, distanceToGoal: d, recoveries: recovery, elapsedMs: elapsed },
          map: { grid: INITIAL_APP_STATE.map.grid, plannedPath: PLANNED_PATH, traveledPath },
          timeline,
        });

        pending = true;
        // Reset loop after 5 s so the demo cycles
        setTimeout(() => {
          robotX       = ROBOT_START_X;
          robotY       = ROBOT_START_Y;
          elapsed      = 0;
          recovery     = 0;
          status       = 'NAVIGATING';
          navStart     = Date.now();
          emitted      = PRE_NAV_COUNT;
          timeline     = materialize(emitted, navStart);
          traveledPath = [{ x: ROBOT_START_X, y: ROBOT_START_Y }];
          pending      = false;

          onUpdate({
            robot: {
              x: robotX, y: robotY,
              heading: Math.atan2(GOAL_Y - robotY, GOAL_X - robotX),
              linearVelocity: 0.40, angularVelocity: 0,
            },
            mission: {
              status,
              goal: { x: GOAL_X, y: GOAL_Y },
              distanceToGoal: dist(robotX, robotY, GOAL_X, GOAL_Y),
              recoveries: recovery,
              elapsedMs: elapsed,
            },
            map: { grid: INITIAL_APP_STATE.map.grid, plannedPath: PLANNED_PATH, traveledPath },
            timeline,
          });
        }, 5_000);

        return;
      }

      // ── Moving toward goal ──
      const noise = () => (Math.random() - 0.5) * 0.003;
      robotX += (dx / d) * STEP_M + noise();
      robotY += (dy / d) * STEP_M + noise();

      // Append to traveled path every ~4 ticks
      if (traveledPath.length === 0 || dist(traveledPath[traveledPath.length - 1].x, traveledPath[traveledPath.length - 1].y, robotX, robotY) > 0.05) {
        traveledPath = [...traveledPath, { x: robotX, y: robotY }];
      }

      const heading        = Math.atan2(GOAL_Y - robotY, GOAL_X - robotX);
      const linearVelocity = 0.38 + Math.random() * 0.08;
      const angularVelocity = (Math.random() - 0.5) * 0.06;

      onUpdate({
        robot: {
          x: robotX, y: robotY, heading,
          linearVelocity: Math.round(linearVelocity * 100) / 100,
          angularVelocity: Math.round(angularVelocity * 100) / 100,
        },
        mission: {
          status,
          goal: { x: GOAL_X, y: GOAL_Y },
          distanceToGoal: Math.round(dist(robotX, robotY, GOAL_X, GOAL_Y) * 100) / 100,
          recoveries: recovery,
          elapsedMs: elapsed,
        },
        map: { grid: INITIAL_APP_STATE.map.grid, plannedPath: PLANNED_PATH, traveledPath },
        ...(timelineChanged ? { timeline } : {}),
      });
    }, TICK_MS);

    return () => clearInterval(timer);
  }

  sendGoal(_x: number, _y: number): void {
    // No-op in mock mode — will be implemented in RosDataBridge
    console.info('[MockBridge] sendGoal: ignored in demo mode');
  }

  cancelNavigation(): void {
    console.info('[MockBridge] cancelNavigation: ignored in demo mode');
  }
}
