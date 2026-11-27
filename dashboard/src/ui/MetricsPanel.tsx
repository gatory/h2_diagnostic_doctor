// Side panel (right 60% of the screen) with a few headline numbers from the bridge.
// It only shows what the bridge sent: verdicts come from checkup, never judged here.

import type { BridgeView } from '../bridge/useBridge'
import type { Status } from '../bridge/protocol'

const STATUS_TEXT: Record<Status, string> = { pass: 'Pass', warn: 'Warning', fail: 'Fail', 'no data': 'No data' }

function metrics({ state, latest }: BridgeView) {
  const snap = latest?.snapshot
  const joints = snap?.body?.joints ?? []
  const topics = Object.values(snap?.topics ?? {})
  const findings = latest?.checkup.findings.length ?? 0
  return [
    { label: 'Source', value: state !== 'open' ? '—' : latest ? (latest.source === 'live' ? 'Live robot' : 'Replay') : 'Waiting…' },
    { label: 'Checkup', value: latest ? `${STATUS_TEXT[latest.checkup.now]}${findings ? ` · ${findings}` : ''}` : '—', status: latest?.checkup.now },
    { label: 'Battery', value: snap?.battery ? `${snap.battery.soc} %` : '—' },
    { label: 'Joints', value: snap?.body ? `${joints.filter((j) => j.q !== null).length} / ${joints.length}` : '—' },
    { label: 'Topics', value: snap ? `${topics.filter((t) => t.hz).length} / ${topics.length}` : '—' },
  ]
}

export function MetricsPanel({ open, view }: { open: boolean; view: BridgeView }) {
  const findings = view.latest?.checkup.findings ?? []
  return (
    <section className={`metrics-panel ${open ? 'open' : ''}`} aria-hidden={!open}>
      <h2>Metrics</h2>
      <div className="metric-grid">
        {metrics(view).map((m) => (
          <div key={m.label} className="metric">
            <div className="metric-label">{m.label}</div>
            <div className={`metric-value ${m.status ? `status-${m.status.replace(' ', '-')}` : ''}`}>{m.value}</div>
          </div>
        ))}
      </div>
      {findings.length > 0 && (
        <ul className="findings">
          {findings.map((f) => (
            <li key={`${f.rule}/${f.subject}`} className={`status-${f.status.replace(' ', '-')}`}>
              <span className="finding-subject">{f.subject}</span> {f.message}
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
