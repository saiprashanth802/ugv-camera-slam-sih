import { useAppStore } from '../../store/useAppStore'
import { StatusBadge } from '../common/StatusBadge'

export function SystemHealthPanel() {
  const health = useAppStore((s) => s.health)
  const dataSource = useAppStore((s) => s.dataSource)

  const items = [
    { name: 'ROS 2 Core', status: health.ros, desc: 'Humble Desktop Full' },
    { name: 'Gazebo Sim', status: health.gazebo, desc: 'Classic 11 (GPU Offload)' },
    { name: 'RTAB-Map', status: health.rtabmap, desc: 'RGB-D SLAM & Grid' },
    { name: 'Nav2 Stack', status: health.nav2, desc: 'Planner & Controller' },
    { name: 'Camera Sensor', status: health.camera, desc: 'Patched RGB-D @ 30 Hz' },
    { name: 'pySLAM Core', status: health.slam, desc: 'GTSAM Backend' },
  ]

  return (
    <section className="p-3 border-b border-[#1e2d3d]">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-mono uppercase text-slate-500 tracking-wider">
          System Health
        </span>
        <span className="text-[10px] font-mono text-amber-500/80 uppercase px-1.5 py-0.5 rounded bg-amber-950/40 border border-amber-900/40">
          {dataSource === 'mock' ? 'Demo / Recorded State' : 'Live ROS'}
        </span>
      </div>

      <div className="grid grid-cols-2 gap-2">
        {items.map((item) => (
          <div
            key={item.name}
            className="p-2 rounded bg-[#090e1a] border border-[#1a2638] flex flex-col justify-between min-h-[46px]"
          >
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-mono text-slate-300 font-medium">
                {item.name}
              </span>
              <StatusBadge status={item.status} pulse={item.status === 'OPERATIONAL'} />
            </div>
            <span className="text-[10px] font-mono text-slate-500 truncate mt-0.5">
              {item.desc}
            </span>
          </div>
        ))}
      </div>

      {health.slam === 'DEGRADED' && (
        <p className="mt-2 text-[10px] font-mono text-slate-500 leading-tight">
          Note: Visual SLAM is marked Degraded due to open loop closure RANSAC verification.
        </p>
      )}
    </section>
  )
}
