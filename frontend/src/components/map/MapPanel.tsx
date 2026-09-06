import { useAppStore } from '../../store/useAppStore'
import { MapCanvas } from './MapCanvas'

function Legend() {
  return (
    <div className="flex items-center gap-4 text-xs font-mono text-slate-500">
      <span className="flex items-center gap-1.5">
        <span className="w-2 h-2 rounded-full bg-cyan-400 flex-shrink-0" />
        Robot
      </span>
      <span className="flex items-center gap-1.5">
        <span className="w-2 h-2 rounded bg-yellow-400 flex-shrink-0" style={{ transform: 'rotate(45deg)' }} />
        Goal
      </span>
      <span className="flex items-center gap-1.5">
        <svg width="18" height="8" viewBox="0 0 18 8" aria-hidden>
          <line x1="0" y1="4" x2="18" y2="4" stroke="#06b6d4" strokeWidth="2.5" />
        </svg>
        Traveled path
      </span>
      <span className="flex items-center gap-1.5">
        <svg width="18" height="8" viewBox="0 0 18 8" aria-hidden>
          <line x1="0" y1="4" x2="18" y2="4" stroke="#38bdf8" strokeWidth="1.5" strokeDasharray="4 4" />
        </svg>
        Planned path
      </span>
      <span className="flex items-center gap-1.5">
        <span className="w-2 h-2 flex-shrink-0" style={{ background: '#c8d5e4' }} />
        Free
      </span>
      <span className="flex items-center gap-1.5">
        <span className="w-2 h-2 flex-shrink-0" style={{ background: '#1a2639' }} />
        Wall
      </span>
    </div>
  )
}

export function MapPanel() {
  const grid          = useAppStore((s) => s.map.grid)
  const robot         = useAppStore((s) => s.robot)
  const goal          = useAppStore((s) => s.mission.goal)
  const path          = useAppStore((s) => s.map.plannedPath)
  const traveledPath  = useAppStore((s) => s.map.traveledPath)
  const missionStatus = useAppStore((s) => s.mission.status)
  const dataSource    = useAppStore((s) => s.dataSource)

  const isGoalReached = missionStatus === 'GOAL_REACHED'

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* ── Map header ── */}
      <div className="flex items-center justify-between px-3 py-1.5 flex-shrink-0 border-b border-[#1e2d3d]">
        <span className="text-xs font-mono uppercase text-slate-400 tracking-wider">
          Occupancy Map
          <span className="text-slate-600 ml-1 normal-case tracking-normal">
            — RTAB-Map / Nav2
          </span>
        </span>
        <Legend />
      </div>

      {/* ── Canvas ── */}
      <div className="flex-1 flex items-center justify-center bg-[#090e1a] overflow-hidden p-2 min-h-0">
        {grid ? (
          <MapCanvas
            grid={grid}
            robot={{ x: robot.x, y: robot.y, heading: robot.heading }}
            goal={goal}
            path={path}
            traveledPath={traveledPath}
            isGoalReached={isGoalReached}
          />
        ) : (
          <p className="text-slate-600 font-mono text-sm">
            Waiting for map data…
          </p>
        )}
      </div>

      {/* ── Map footer ── */}
      <div className="flex items-center gap-4 px-3 py-1 flex-shrink-0 border-t border-[#1e2d3d] text-xs font-mono text-slate-600">
        {grid && (
          <>
            <span>{grid.width}×{grid.height} cells</span>
            <span>{(grid.resolution * 100).toFixed(0)} cm/cell</span>
            <span>
              Origin ({grid.origin.x.toFixed(2)}, {grid.origin.y.toFixed(2)}) m
            </span>
          </>
        )}
        {dataSource === 'mock' && (
          <span className="ml-auto text-amber-600/80 uppercase tracking-wider">
            Demo data
          </span>
        )}
      </div>
    </div>
  )
}
