// Bottom bar in the style of Tesla's in-car UI. Left: the bridge connection. Tabs only
// highlight for now; the right-hand button shows and hides the metrics panel.

import { useState } from 'react'
import type { BridgeView } from '../bridge/useBridge'

const TABS = ['Overview', 'Telemetry', 'Recordings', 'Health'] as const

type Props = { view: BridgeView; panelOpen: boolean; onTogglePanel: () => void }

function connectionText({ state, latest }: BridgeView): { text: string; dot: string } {
  if (state === 'open') return latest ? { text: latest.source === 'live' ? 'Live' : 'Replay', dot: 'ok' } : { text: 'Connected', dot: 'ok' }
  if (state === 'closed') return { text: 'Bridge offline · retrying', dot: 'off' }
  return { text: 'Connecting…', dot: '' }
}

export function BottomNav({ view, panelOpen, onTogglePanel }: Props) {
  const [active, setActive] = useState<(typeof TABS)[number]>('Overview')
  const connection = connectionText(view)

  return (
    <nav className="bottom-nav">
      <span className="bottom-nav-status">
        <span className={`status-dot ${connection.dot}`} /> {connection.text}
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
