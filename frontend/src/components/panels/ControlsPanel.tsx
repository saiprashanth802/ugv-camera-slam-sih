import { useAppStore } from '../../store/useAppStore'

interface BtnProps {
  onClick?: () => void
  disabled: boolean
  variant: 'primary' | 'danger'
  children: React.ReactNode
}

function Btn({ onClick, disabled, variant, children }: BtnProps) {
  const base = 'w-full px-3 py-1.5 rounded text-xs font-mono uppercase tracking-wider transition-colors'
  const styles =
    disabled
      ? 'bg-[#111d2e] text-slate-600 cursor-not-allowed'
      : variant === 'primary'
        ? 'bg-cyan-800 hover:bg-cyan-700 text-cyan-100 cursor-pointer'
        : 'bg-red-900/70 hover:bg-red-800 text-red-200 cursor-pointer'

  return (
    <button
      className={`${base} ${styles}`}
      disabled={disabled}
      onClick={onClick}
    >
      {children}
    </button>
  )
}

export function ControlsPanel() {
  const dataSource    = useAppStore((s) => s.dataSource)
  const missionStatus = useAppStore((s) => s.mission.status)

  const rosReady   = dataSource === 'ros'
  const navigating = missionStatus === 'NAVIGATING' || missionStatus === 'REPLANNING'

  return (
    <section className="p-3">
      <div className="text-xs font-mono uppercase text-slate-500 tracking-wider mb-2">
        Controls
      </div>

      {!rosReady && (
        <div className="mb-3 px-2 py-2 rounded bg-[#1a1400] border border-amber-900/50 text-xs font-mono text-amber-500/90 leading-relaxed">
          Demo mode — controls unavailable.
          <br />
          <span className="text-slate-600">
            Connect ROS bridge (P4) to enable goal sending and cancel.
          </span>
        </div>
      )}

      <div className="flex flex-col gap-2">
        <Btn variant="primary" disabled={!rosReady}>
          Set Navigation Goal
        </Btn>
        <Btn variant="danger" disabled={!rosReady || !navigating}>
          Cancel Navigation
        </Btn>
      </div>

      {/* Context info */}
      <div className="mt-3 space-y-0.5">
        <div className="flex justify-between text-xs font-mono">
          <span className="text-slate-600">ROS action</span>
          <span className="text-slate-500">/navigate_to_pose</span>
        </div>
        <div className="flex justify-between text-xs font-mono">
          <span className="text-slate-600">Frame</span>
          <span className="text-slate-500">map</span>
        </div>
      </div>
    </section>
  )
}
