import { useState } from 'react'
import { RobotView } from './robot/RobotView'
import { BottomNav } from './ui/BottomNav'
import { MetricsPanel } from './ui/MetricsPanel'

export default function App() {
  const [panelOpen, setPanelOpen] = useState(true)

  return (
    <div className="app">
      <main className="stage">
        <RobotView panelOpen={panelOpen} />
        <MetricsPanel open={panelOpen} />
      </main>
      <BottomNav panelOpen={panelOpen} onTogglePanel={() => setPanelOpen((open) => !open)} />
    </div>
  )
}
