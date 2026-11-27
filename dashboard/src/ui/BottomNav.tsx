// Bottom bar in the style of Tesla's in-car UI. Tabs only highlight for now; the right-hand
// button shows and hides the metrics panel.

import { useState } from 'react'

const TABS = ['Overview', 'Telemetry', 'Recordings', 'Health'] as const

type Props = { panelOpen: boolean; onTogglePanel: () => void }

export function BottomNav({ panelOpen, onTogglePanel }: Props) {
  const [active, setActive] = useState<(typeof TABS)[number]>('Overview')

  return (
    <nav className="bottom-nav">
      <span className="bottom-nav-status">
        <span className="status-dot" /> Sample data
      </span>
      <div className="bottom-nav-tabs">
        {TABS.map((tab) => (
          <button key={tab} className={tab === active ? 'active' : ''} onClick={() => setActive(tab)}>
            {tab}
          </button>
        ))}
      </div>
      <div className="bottom-nav-right">
        <button className={`panel-toggle ${panelOpen ? 'active' : ''}`} onClick={onTogglePanel} aria-pressed={panelOpen}>
          Metrics {panelOpen ? '▸' : '◂'}
        </button>
      </div>
    </nav>
  )
}
