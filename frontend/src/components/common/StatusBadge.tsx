import type { HealthStatus } from '../../types'

const CFG: Record<HealthStatus, { text: string; dot: string; label: string }> = {
  OPERATIONAL: { text: 'text-green-400',  dot: 'bg-green-400',  label: 'OPERATIONAL' },
  DEGRADED:    { text: 'text-amber-400',  dot: 'bg-amber-400',  label: 'DEGRADED'    },
  OFFLINE:     { text: 'text-red-400',    dot: 'bg-red-400',    label: 'OFFLINE'     },
  UNKNOWN:     { text: 'text-slate-500',  dot: 'bg-slate-600',  label: 'UNKNOWN'     },
}

interface Props {
  status: HealthStatus
  label?: string  // override display text
  pulse?: boolean // animated pulse dot for OPERATIONAL
}

export function StatusBadge({ status, label, pulse }: Props) {
  const { text, dot } = CFG[status]
  const displayLabel = label ?? CFG[status].label

  return (
    <span className={`inline-flex items-center gap-1.5 text-xs font-mono uppercase tracking-wide ${text}`}>
      <span
        className={`
          w-1.5 h-1.5 rounded-full flex-shrink-0 ${dot}
          ${pulse && status === 'OPERATIONAL' ? 'animate-pulse' : ''}
        `}
      />
      {displayLabel}
    </span>
  )
}
