import { useEffect } from 'react'
import { useAppStore } from './store/useAppStore'
import { MockDataBridge } from './data/mock'
import { Header } from './components/Header'
import { DashboardView } from './views/DashboardView'

// Single bridge instance — lives for the app lifetime.
// Swap this import for RosDataBridge at P4 integration without touching any component.
const bridge = new MockDataBridge()

export default function App() {
  const setBridge = useAppStore((s) => s.setBridge)

  useEffect(() => {
    setBridge(bridge)
    // setBridge stores its own cleanup; unsubscribe on next call.
    // For strict-mode double-mount safety we rely on the _currentUnsub in the store.
  }, [setBridge])

  return (
    <div className="flex flex-col h-full overflow-hidden bg-[#0b1120] text-slate-200">
      <Header />
      <DashboardView />
    </div>
  )
}
