import { useState, useEffect } from 'react'
import { useAppStore } from '../store/useAppStore'
import { MissionBadge } from './common/MissionBadge'

function SightlineIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" className="w-5 h-5 flex-shrink-0" aria-hidden>
      <circle cx="12" cy="12" r="3.5"  stroke="#06b6d4" strokeWidth="1.5" />
      <circle cx="12" cy="12" r="8"    stroke="#06b6d4" strokeWidth="0.75" strokeDasharray="2.5 2" opacity="0.6" />
      <line x1="12" y1="2"  x2="12" y2="6"  stroke="#06b6d4" strokeWidth="1.5" strokeLinecap="round" />
      <line x1="12" y1="18" x2="12" y2="22" stroke="#06b6d4" strokeWidth="1.5" strokeLinecap="round" />
      <line x1="2"  y1="12" x2="6"  y2="12" stroke="#06b6d4" strokeWidth="1.5" strokeLinecap="round" />
      <line x1="18" y1="12" x2="22" y2="12" stroke="#06b6d4" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  )
}

export function Header() {
  const missionStatus = useAppStore((s) => s.mission.status)
  const dataSource    = useAppStore((s) => s.dataSource)

  const [time, setTime] = useState(() => new Date())
  useEffect(() => {
    const t = setInterval(() => setTime(new Date()), 1_000)
    return () => clearInterval(t)
  }, [])

  const timeStr = time.toLocaleTimeString('en-IN', {
    hour12: false,
    hour:   '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })

  return (
    <header className="
      flex items-center justify-between
      px-4 h-12 flex-shrink-0
      border-b border-[#1e2d3d] bg-[#090e1a]
    ">
      {/* ── Brand ── */}
      <div className="flex items-center gap-2.5">
        <SightlineIcon />
        <div className="flex items-baseline gap-2">
          <span className="text-cyan-400 font-mono font-bold text-sm tracking-[0.2em] uppercase">
            SIGHTLINE
          </span>
          <span className="text-slate-500 font-mono text-xs tracking-wider uppercase hidden sm:inline">
            Mission Control
          </span>
        </div>
      </div>

      {/* ── Mission status ── */}
      <div className="flex items-center gap-3">
        <MissionBadge status={missionStatus} />
      </div>

      {/* ── Right: data source + clock ── */}
      <div className="flex items-center gap-5 text-xs font-mono">
        {dataSource === 'mock' ? (
          <span className="flex items-center gap-1.5 text-amber-400/90 uppercase tracking-wider">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse-slow" />
            DEMO DATA
          </span>
        ) : (
          <span className="flex items-center gap-1.5 text-green-400 uppercase tracking-wider">
            <span className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />
            LIVE ROS
          </span>
        )}
        <span className="text-slate-500 tabular-nums">{timeStr}</span>
      </div>
    </header>
  )
}
