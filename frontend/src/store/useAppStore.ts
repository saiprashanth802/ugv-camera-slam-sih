/**
 * Zustand application store.
 *
 * Architecture contract:
 *  - All state lives here; components read via selectors.
 *  - setBridge() is the single entry point for swapping data sources.
 *    Call it once with MockDataBridge; later call it with RosDataBridge.
 *  - The bridge interface (DataBridge) is the only ROS-aware seam.
 *    No component file ever imports a concrete bridge class.
 */

import { create } from 'zustand';
import type { AppState } from '../types';
import type { DataBridge, StateUpdate } from '../bridge/DataBridge';
import { INITIAL_APP_STATE } from '../data/mock';

interface AppStore extends AppState {
  setBridge(bridge: DataBridge): void;
}

// Module-level ref for cleanup — only one bridge active at a time
let _currentUnsub: (() => void) | null = null;

export const useAppStore = create<AppStore>((set) => ({
  ...INITIAL_APP_STATE,

  setBridge(bridge: DataBridge) {
    // Clean up previous subscription before starting new one
    if (_currentUnsub) {
      _currentUnsub();
      _currentUnsub = null;
    }

    _currentUnsub = bridge.subscribe((update: StateUpdate) => {
      set((state) => {
        // Shallow-merge each top-level key individually so sibling keys
        // that the bridge didn't touch are preserved untouched.
        const next: Partial<AppStore> = {};

        if (update.robot !== undefined)
          next.robot = { ...state.robot, ...update.robot };

        if (update.mission !== undefined)
          next.mission = { ...state.mission, ...update.mission };

        if (update.map !== undefined)
          next.map = { ...state.map, ...update.map };

        if (update.perception !== undefined)
          next.perception = { ...state.perception, ...update.perception };

        if (update.health !== undefined)
          next.health = { ...state.health, ...update.health };

        if (update.timeline !== undefined)
          next.timeline = update.timeline;

        if (update.dataSource !== undefined)
          next.dataSource = update.dataSource;

        return next;
      });
    });
  },
}));
