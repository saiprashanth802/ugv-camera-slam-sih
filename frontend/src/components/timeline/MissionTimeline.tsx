import { useRef, useEffect } from 'react'
import { useAppStore } from '../../store/useAppStore'
import type { TimelineEvent } from '../../types'

const LEVEL_CFG: Record<
  TimelineEvent['level'],
  { dot: string; text: string; badge: string }
> = {
  info:    { dot: 'bg-slate-400',  text: 'text-slate-300', badge: 'text-slate-400 bg-slate-800'     },
  warn:    { dot: 'bg-amber-400',  text: 'text-amber-300', badge: 'text-amber-400 bg-amber-950/60'  },
  success: { dot: 'bg-green-400',  text: 'text-green-300', badge: 'text-green-400 bg-green-950/60'  },
  error:   { dot: 'bg-red-400',    text: 'text-red-300',   badge: 'text-red-400 bg-red-950/60'      },
}

function formatTime(ms: number): string {
  const d = new Date(ms)
  return d.toLocaleTimeString('en-IN', {
    hour12: false,
    hour:   '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

export function MissionTimeline() {
  const timeline   = useAppStore((s) => s.timeline)
  const dataSource = useAppStore((s) => s.dataSource)
  const listRef    = useRef<HTMLDivElement>(null)

  // Auto-scroll to bottom on new events
  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight
    }
  }, [timeline])

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* ── Header ── */}
      <div className="flex items-center justify-between px-3 py-1.5 flex-shrink-0 border-b border-[#1e2d3d]">
        <span className="text-xs font-mono uppercase text-slate-400 tracking-wider">
          Event Timeline
        </span>
        <div className="flex items-center gap-2">
          {dataSource === 'mock' && (
            <span className="text-[10px] font-mono text-amber-500/80 uppercase tracking-wider">
              Recorded sequence
            </span>
          )}
          <span className="text-xs font-mono text-slate-600">
            {timeline.length} events
          </span>
        </div>
      </div>

      {/* ── Event list ── */}
      <div ref={listRef} className="flex-1 overflow-y-auto p-2 space-y-1.5 min-h-0">
        {timeline.map((event) => {
          const cfg = LEVEL_CFG[event.level]
          return (
            <div
              key={event.id}
              className="flex items-baseline gap-2 text-xs font-mono py-0.5 leading-snug"
            >
              <span className="text-slate-600 tabular-nums flex-shrink-0 text-[11px]">
                {formatTime(event.timestampMs)}
              </span>
              <span
                className={`w-1.5 h-1.5 rounded-full flex-shrink-0 self-center ${cfg.dot}`}
              />
              <span className={`flex-1 ${cfg.text}`}>
                {event.message}
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}
