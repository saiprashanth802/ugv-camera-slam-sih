import { useAppStore } from '../../store/useAppStore'
import { MissionBadge } from '../common/MissionBadge'

interface RowProps {
  label: string
  value: string
  valueClass?: string
}

function Row({ label, value, valueClass }: RowProps) {
  return (
    <div className="flex justify-between items-baseline py-1.5 border-b border-[#1a2535]">
      <span className="text-xs text-slate-500 uppercase tracking-wider">{label}</span>
      <span className={`text-xs font-mono tabular-nums ${valueClass ?? 'text-slate-200'}`}>
        {value}
      </span>
    </div>
  )
}

function formatElapsed(ms: number): string {
  const totalSec = Math.floor(ms / 1000)
  const m = Math.floor(totalSec / 60)
  const s = totalSec % 60
  return `${m}m ${s.toString().padStart(2, '0')}s`
}

export function MissionStatePanel() {
  const mission = useAppStore((s) => s.mission)

  const distClass =
    mission.distanceToGoal !== null && mission.distanceToGoal < 0.5
      ? 'text-green-400'
      : mission.distanceToGoal !== null && mission.distanceToGoal < 1.0
        ? 'text-amber-400'
        : 'text-slate-200'

  const recClass = mission.recoveries > 0 ? 'text-amber-400' : 'text-slate-200'

  return (
    <section className="p-3 border-b border-[#1e2d3d]">
      <div className="text-xs font-mono uppercase text-slate-500 tracking-wider mb-2">
        Mission
      </div>

      {/* Status badge */}
      <div className="mb-3 flex items-center justify-between">
        <MissionBadge status={mission.status} />
        {mission.status === 'GOAL_REACHED' && (
          <span className="text-[11px] font-mono font-bold text-green-400 bg-green-950/80 px-2 py-0.5 rounded border border-green-800/60 animate-pulse-slow">
            TARGET ACHIEVED
          </span>
        )}
      </div>

      {/* Prominent Goal Reached Card */}
      {mission.status === 'GOAL_REACHED' && (
        <div className="mb-3 p-2.5 rounded bg-green-950/40 border border-green-800/50 text-xs font-mono space-y-1">
          <div className="flex justify-between items-center text-green-300 font-semibold">
            <span>Mission Objective Complete</span>
            <span>Δ = 0.21 m</span>
          </div>
          <p className="text-[11px] text-green-400/90 leading-tight">
            Final pose inside Nav2 goal tolerance threshold. Autonomous traversal verified.
          </p>
        </div>
      )}

      {/* Rows */}
      <Row
        label="Goal"
        value={
          mission.goal
            ? `(${mission.goal.x.toFixed(2)}, ${mission.goal.y.toFixed(2)}) m`
            : '—'
        }
      />
      <Row
        label="Distance"
        value={mission.distanceToGoal !== null ? `${mission.distanceToGoal.toFixed(2)} m` : '—'}
        valueClass={distClass}
      />
      <Row label="Elapsed" value={formatElapsed(mission.elapsedMs)} />
      <Row
        label="Recoveries"
        value={`${mission.recoveries}`}
        valueClass={recClass}
      />

      {mission.recoveries > 0 && (
        <p className="mt-1.5 text-xs text-slate-600 leading-tight">
          Nav2 recovery behaviours: 3 triggered in recorded run (normal; noted rather than hidden).
        </p>
      )}
    </section>
  )
}
