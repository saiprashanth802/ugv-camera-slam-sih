import type { AppState } from '../types';

/**
 * A partial snapshot of AppState — only the fields that changed.
 * Bridges call onUpdate() with a StateUpdate whenever new data arrives.
 * The store merges these patches shallowly.
 */
export type StateUpdate = Partial<AppState>;

/**
 * DataBridge — the single interface that separates UI from data sources.
 *
 * Implementations:
 *   MockDataBridge  — src/data/mock.ts         (current)
 *   RosDataBridge   — src/bridge/RosBridge.ts  (P4: after ROS topic inspection)
 *
 * To swap data sources, pass a new bridge to store.setBridge().
 * No React component ever imports a concrete bridge class.
 */
export interface DataBridge {
  /**
   * Start delivering state updates.
   * @returns unsubscribe function — call it to stop updates and clean up.
   */
  subscribe(onUpdate: (update: StateUpdate) => void): () => void;

  /**
   * Send a navigation goal in map-frame world coordinates (meters).
   * Optional: not all bridge implementations support this yet.
   */
  sendGoal?(x: number, y: number): void;

  /**
   * Cancel the current navigation action.
   * Optional: not all bridge implementations support this yet.
   */
  cancelNavigation?(): void;
}
