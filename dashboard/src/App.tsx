import { useState } from 'react'
import { useBridgeClient, useBridgeView } from './bridge/useBridge'
import { RobotView } from './robot/RobotView'
import { BottomNav } from './ui/BottomNav'
import { MetricsPanel } from './ui/MetricsPanel'

export default function App() {
  const [panelOpen, setPanelOpen] = useState(true)
  const client = useBridgeClient()
  const view = useBridgeView(client)

  return (
    <div className="app">
      <main className="stage">
        <RobotView panelOpen={panelOpen} client={client} />
        <MetricsPanel open={panelOpen} view={view} />
      </main>
      <BottomNav view={view} panelOpen={panelOpen} onTogglePanel={() => setPanelOpen((open) => !open)} />
    </div>
  )
}
