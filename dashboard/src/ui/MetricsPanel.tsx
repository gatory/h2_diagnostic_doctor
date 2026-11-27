// The Telemetry tab (for now): a few headline numbers from the bridge, and checkup's findings.
// It only shows what the bridge sent: verdicts come from checkup, never judged here.

import type { Status } from '../bridge/protocol'
import type { BridgeView } from '../bridge/useBridge'
import { Panel } from './Panel'
import { STATUS_EDGE, STATUS_TEXT } from './styles'

const STATUS_WORD: Record<Status, string> = { pass: 'Pass', warn: 'Warning', fail: 'Fail', 'no data': 'No data' }

function metrics({ state, latest }: BridgeView): { label: string; value: string; status?: Status }[] {
  const snap = latest?.snapshot
  const joints = snap?.body?.joints ?? []
  const topics = Object.values(snap?.topics ?? {})
  const findings = latest?.checkup.findings.length ?? 0
  return [
    { label: 'Source', value: state !== 'open' ? '—' : latest ? (latest.source === 'live' ? 'Live robot' : 'Replay') : 'Waiting…' },
    { label: 'Checkup', value: latest ? `${STATUS_WORD[latest.checkup.now]}${findings ? ` · ${findings}` : ''}` : '—', status: latest?.checkup.now },
    { label: 'Battery', value: snap?.battery ? `${snap.battery.soc} %` : '—' },
    { label: 'Joints', value: snap?.body ? `${joints.filter((j) => j.q !== null).length} / ${joints.length}` : '—' },
    { label: 'Topics', value: snap ? `${topics.filter((t) => t.hz).length} / ${topics.length}` : '—' },
  ]
}

export function MetricsPanel({ open, view }: { open: boolean; view: BridgeView }) {
  const findings = view.latest?.checkup.findings ?? []
  return (
    <Panel open={open} title="Metrics">
      {/* auto-fill: as many 160px+ columns as fit */}
      <div className="grid grid-cols-[repeat(auto-fill,minmax(160px,1fr))] gap-2">
        {metrics(view).map((m) => (
          <div key={m.label} className="rounded-xs bg-tint p-4">
            <div className="text-placeholder">{m.label}</div>
            <div className={`mt-1 text-[22px] leading-tight ${m.status ? STATUS_TEXT[m.status] : 'text-on-surface'}`}>
              {m.value}
            </div>
          </div>
        ))}
      </div>
      {findings.length > 0 && (
        <ul className="mt-4 grid list-none gap-1 p-0">
          {findings.map((f) => (
            <li
              key={`${f.rule}/${f.subject}`}
              className={`rounded-xs border-l-[3px] bg-tint px-3 py-2 text-on-surface ${STATUS_EDGE[f.status]}`}
            >
              <span className="mr-1.5 text-placeholder">{f.subject}</span> {f.message}
            </li>
          ))}
        </ul>
      )}
    </Panel>
  )
}
