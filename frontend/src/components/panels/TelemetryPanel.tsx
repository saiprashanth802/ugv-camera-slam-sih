import { useAppStore } from '../../store/useAppStore'

interface TelRowProps {
  label: string
  value: string
  unit?: string
  valueClass?: string
}

function TelRow({ label, value, unit, valueClass }: TelRowProps) {
  return (
    <div className="flex justify-between items-baseline py-1.5 border-b border-[#1a2535]">
      <span className="text-xs text-slate-500 uppercase tracking-wider">{label}</span>
      <span className={`text-xs font-mono tabular-nums ${valueClass ?? 'text-slate-200'}`}>
        {value}
        {unit && <span className="text-slate-500 ml-0.5">{unit}</span>}
      </span>
    </div>
  )
}

function headingStr(rad: number): string {
  const deg = ((rad * 180 / Math.PI) % 360 + 360) % 360
  return `${deg.toFixed(1)}°`
}

export function TelemetryPanel() {
  const robot = useAppStore((s) => s.robot)

  return (
    <section className="p-3">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-mono uppercase text-slate-500 tracking-wider">
          Telemetry
        </span>
        <span className="text-[10px] font-mono text-slate-600 uppercase">
          Odometry / TF
        </span>
      </div>

      <TelRow label="Lin. velocity" value={robot.linearVelocity.toFixed(2)} unit="m/s" />
      <TelRow label="Ang. velocity" value={robot.angularVelocity.toFixed(2)} unit="rad/s" />
      <TelRow label="Position X"   value={robot.x.toFixed(3)} unit="m" />
      <TelRow label="Position Y"   value={robot.y.toFixed(3)} unit="m" />
      <TelRow label="Heading"      value={headingStr(robot.heading)} />
    </section>
  )
}
