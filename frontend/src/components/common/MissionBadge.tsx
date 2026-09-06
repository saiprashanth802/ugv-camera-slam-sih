import type { MissionStatus } from '../../types'

const CFG: Record<MissionStatus, { text: string; bg: string }> = {
  IDLE:              { text: 'text-slate-400', bg: 'bg-slate-800'      },
  LOCALIZING:        { text: 'text-amber-300', bg: 'bg-amber-950/60'   },
  READY:             { text: 'text-green-400', bg: 'bg-green-950/60'   },
  GOAL_SELECTED:     { text: 'text-cyan-300',  bg: 'bg-cyan-950/60'    },
  PLANNING:          { text: 'text-cyan-300',  bg: 'bg-cyan-950/60'    },
  NAVIGATING:        { text: 'text-blue-300',  bg: 'bg-blue-950/60'    },
  OBSTACLE_DETECTED: { text: 'text-amber-300', bg: 'bg-amber-950/60'   },
  REPLANNING:        { text: 'text-amber-300', bg: 'bg-amber-950/60'   },
  GOAL_REACHED:      { text: 'text-green-300', bg: 'bg-green-950/60'   },
  CANCELLED:         { text: 'text-red-400',   bg: 'bg-red-950/60'     },
  ERROR:             { text: 'text-red-400',   bg: 'bg-red-950/60'     },
}

interface Props {
  status: MissionStatus
}

export function MissionBadge({ status }: Props) {
  const { text, bg } = CFG[status]
  return (
    <span
      className={`
        px-2 py-0.5 rounded text-xs font-mono font-bold
        uppercase tracking-widest ${text} ${bg}
      `}
    >
      {status.replace(/_/g, '\u00a0')}
    </span>
  )
}
