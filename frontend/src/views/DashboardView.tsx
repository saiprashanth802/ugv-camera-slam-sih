import { MapPanel } from '../components/map/MapPanel'
import { MissionStatePanel } from '../components/panels/MissionStatePanel'
import { TelemetryPanel } from '../components/panels/TelemetryPanel'
import { SystemHealthPanel } from '../components/panels/SystemHealthPanel'
import { VisualSlamPanel } from '../components/panels/VisualSlamPanel'
import { ControlsPanel } from '../components/panels/ControlsPanel'
import { MissionTimeline } from '../components/timeline/MissionTimeline'

export function DashboardView() {
  return (
    <main className="flex-1 flex flex-col md:flex-row overflow-hidden min-h-0">
      {/* Main Area: Map View (Left/Center) */}
      <section className="flex-1 flex flex-col min-w-0 border-r border-[#1e2d3d] overflow-hidden">
        <div className="flex-1 min-h-0">
          <MapPanel />
        </div>
      </section>

      {/* Side Panel: Mission State, Telemetry, System Health, Visual SLAM, Controls & Timeline */}
      <aside className="w-full md:w-80 lg:w-[420px] flex flex-col flex-shrink-0 bg-[#0c1322] overflow-hidden">
        <div className="flex-1 overflow-y-auto divide-y divide-[#1e2d3d]">
          <MissionStatePanel />
          {/* Visual SLAM sits above System Health: on a 768px-tall laptop only
              two panels clear the fold, and the verified KITTI numbers are the
              ones worth showing. System Health is six green pills. */}
          <VisualSlamPanel />
          <SystemHealthPanel />
          <TelemetryPanel />
          <ControlsPanel />
        </div>
        
        {/* Timeline embedded at bottom of side panel */}
        <div className="h-52 flex-shrink-0 border-t border-[#1e2d3d] bg-[#090e1a]">
          <MissionTimeline />
        </div>
      </aside>
    </main>
  )
}
