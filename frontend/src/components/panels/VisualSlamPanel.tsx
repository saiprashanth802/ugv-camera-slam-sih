import { useAppStore } from '../../store/useAppStore'

interface MetricProps {
  label: string
  value: string | number
  sub?: string
  highlight?: string
}

function MetricBox({ label, value, sub, highlight }: MetricProps) {
  return (
    <div className="p-2 rounded bg-[#090e1a] border border-[#1a2638] flex flex-col justify-between">
      <span className="text-[10px] font-mono text-slate-500 uppercase tracking-wider truncate">
        {label}
      </span>
      <div className="flex items-baseline gap-1 mt-1">
        <span className={`text-sm font-mono font-semibold tabular-nums ${highlight ?? 'text-slate-200'}`}>
          {value}
        </span>
        {sub && <span className="text-[10px] font-mono text-slate-500">{sub}</span>}
      </div>
    </div>
  )
}

export function VisualSlamPanel() {
  const perception = useAppStore((s) => s.perception)

  return (
    <section className="p-3 border-b border-[#1e2d3d]">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-1.5">
          <span className="text-xs font-mono uppercase text-slate-400 tracking-wider">
            Visual SLAM
          </span>
          <span className="text-[10px] font-mono text-slate-500">
            (pySLAM + GTSAM)
          </span>
        </div>
        <span className="text-[10px] font-mono text-cyan-400/90 uppercase px-1.5 py-0.5 rounded bg-cyan-950/40 border border-cyan-900/40">
          Recorded / KITTI 06
        </span>
      </div>

      <div className="grid grid-cols-3 gap-2">
        <MetricBox
          label="Tracked Frames"
          value={`${perception.framesTracked} / ${perception.totalFrames}`}
          sub="(1 lost)"
        />
        <MetricBox
          label="Keyframes"
          value={perception.keyframes}
        />
        <MetricBox
          label="Map Points"
          value={perception.mapPoints.toLocaleString()}
        />
        <MetricBox
          label="APE RMSE"
          value={perception.apeRmse !== null ? `${perception.apeRmse.toFixed(1)} m` : '—'}
          sub="Sim3 aligned"
          highlight="text-amber-300"
        />
        <MetricBox
          label="Path Error"
          value={perception.pathPercentage !== null ? `${perception.pathPercentage.toFixed(2)} %` : '—'}
          sub="of 1222 m"
        />
        <MetricBox
          label="SLAM Resets"
          value={perception.resets}
          highlight="text-green-400"
        />
      </div>

      {/* Loop Closure & Monocular Disclaimer status */}
      <div className="mt-2.5 p-2 rounded bg-[#0e1626] border border-[#1a293e] space-y-1.5 text-[11px] font-mono">
        <div className="flex items-center justify-between">
          <span className="text-slate-400">Loop Closures:</span>
          <div className="flex items-center gap-1.5">
            <span className="text-slate-300 font-bold">{perception.loopClosures}</span>
            <span className="px-1.5 py-0.5 rounded text-[10px] bg-amber-950/60 border border-amber-900/40 text-amber-400 font-medium">
              STATUS: OPEN WORK
            </span>
          </div>
        </div>
        <p className="text-[10px] text-slate-500 leading-tight">
          Monocular SLAM recovers no metric scale (evaluated via Umeyama Sim3 alignment). Offline benchmark from KITTI sequence 06.
        </p>
      </div>
    </section>
  )
}
