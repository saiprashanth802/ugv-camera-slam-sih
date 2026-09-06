// ─── Mission state machine ────────────────────────────────────────────────────

export type MissionStatus =
  | 'IDLE'
  | 'LOCALIZING'
  | 'READY'
  | 'GOAL_SELECTED'
  | 'PLANNING'
  | 'NAVIGATING'
  | 'OBSTACLE_DETECTED'
  | 'REPLANNING'
  | 'GOAL_REACHED'
  | 'CANCELLED'
  | 'ERROR';

export type HealthStatus = 'OPERATIONAL' | 'DEGRADED' | 'OFFLINE' | 'UNKNOWN';

// ─── Robot ────────────────────────────────────────────────────────────────────

export interface RobotState {
  /** Map-frame position (meters). */
  x: number;
  y: number;
  /** Heading in radians — ROS convention: 0 = +X axis, π/2 = +Y (north). */
  heading: number;
  linearVelocity: number;  // m/s
  angularVelocity: number; // rad/s
}

// ─── Mission ──────────────────────────────────────────────────────────────────

export interface MissionState {
  status: MissionStatus;
  goal: { x: number; y: number } | null;
  distanceToGoal: number | null; // meters
  recoveries: number;
  elapsedMs: number;
}

// ─── Map ──────────────────────────────────────────────────────────────────────

export interface OccupancyGrid {
  width: number;
  height: number;
  resolution: number;          // meters per cell
  origin: { x: number; y: number }; // world-frame coordinates of cell (0, 0)
  data: Int8Array;             // −1 = unknown, 0 = free, 100 = occupied
}

export interface MapState {
  grid: OccupancyGrid | null;
  plannedPath: { x: number; y: number }[];  // world-frame full route
  traveledPath?: { x: number; y: number }[]; // trail of traversed positions
}

// ─── Perception ───────────────────────────────────────────────────────────────

export interface PerceptionState {
  trackingStatus: 'HEALTHY' | 'LOST' | 'DEMO' | 'UNKNOWN';
  framesTracked: number;
  totalFrames: number;
  keyframes: number;
  mapPoints: number;
  /**
   * Loop closures from pySLAM KITTI 06 run.
   * NOTE: RUNBOOK §7c confirms loop closure does NOT fire — value is 0.
   * Do not present as "1 loop closure" despite README typo.
   */
  loopClosures: number;
  resets: number;
  /**
   * APE RMSE vs ground truth after Umeyama sim3 alignment.
   * Monocular SLAM provides no metric scale — this is a relative, not absolute, figure.
   */
  apeRmse: number | null;
  pathPercentage: number | null;
  isLive: boolean;
}

// ─── System health ────────────────────────────────────────────────────────────

export interface SystemHealth {
  ros: HealthStatus;
  gazebo: HealthStatus;
  rtabmap: HealthStatus;
  nav2: HealthStatus;
  camera: HealthStatus;
  slam: HealthStatus;
  bridge: HealthStatus;
}

// ─── Timeline ─────────────────────────────────────────────────────────────────

export interface TimelineEvent {
  id: string;
  timestampMs: number;
  level: 'info' | 'warn' | 'success' | 'error';
  message: string;
}

// ─── Top-level application state ─────────────────────────────────────────────

export interface AppState {
  robot: RobotState;
  mission: MissionState;
  map: MapState;
  perception: PerceptionState;
  health: SystemHealth;
  timeline: TimelineEvent[];
  /** 'mock' | 'ros' — controls whether UI labels warn about demo data. */
  dataSource: 'mock' | 'ros';
}
