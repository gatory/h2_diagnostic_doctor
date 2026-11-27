// Top left of Home, next to the FSM row: a battery icon filled to the robot's state of charge,
// with the % beside it. Hover (or keyboard focus) shows charge, health, volts and cell spread.
//
// Colour comes from checkup, not from the % here: the fill turns amber/red only when checkup's
// "charge" rule (SOC_WARN 20 % / SOC_FAIL 10 % in checkup/limits.py) has a finding on the battery.

import type { Finding } from '../../bridge/protocol'
import type { BridgeView } from '../../bridge/useBridge'
import { STATUS_FILL, STATUS_TEXT } from '../styles'

export function BatteryBlock({ view }: { view: BridgeView }) {
  const battery = view.latest?.snapshot.battery
  const charge = chargeFinding(view.latest?.checkup.findings ?? [])
  const soc = battery ? Math.max(0, Math.min(100, battery.soc)) : null

  return (
    // group: the details card below shows while this box is hovered or focused
    <div
      tabIndex={0}
      aria-label={soc === null ? 'Battery: no data' : `Battery ${soc} %`}
      className="group pointer-events-auto relative flex items-center gap-2.5 px-1 py-1"
    >
      <BatteryIcon soc={soc} fill={charge ? STATUS_FILL[charge.status] : 'bg-hud'} />
      <span className={`text-xl font-semibold tabular-nums ${charge ? STATUS_TEXT[charge.status] : ''}`}>
        {soc === null ? '—' : `${soc}%`}
      </span>

      {battery && (
        <div
          role="tooltip"
          className="absolute top-[calc(100%+8px)] left-0 z-10 hidden gap-0.5 rounded-xs border border-hud-border bg-panel
            px-3 py-2 text-sm whitespace-nowrap text-on-surface group-hover:grid group-focus:grid"
        >
          <span>Charge {battery.soc} % · health {battery.soh} %</span>
          <span>{battery.volts === null ? '— V' : `${battery.volts.toFixed(1)} V`}</span>
          <span>{cellSpread(battery.cells)}</span>
          {charge && <span className={STATUS_TEXT[charge.status]}>{charge.message}</span>}
        </div>
      )}
    </div>
  )
}

/**
 * A battery outline (body + the small terminal nub on the right) with a bar inside, as wide as
 * the charge. No data: an empty outline.
 */
function BatteryIcon({ soc, fill }: { soc: number | null; fill: string }) {
  return (
    <span className="flex items-center" aria-hidden>
      <span className="relative h-5 w-10 rounded-[5px] border-2 border-hud-dim p-0.5">
        <span
          className={`block h-full rounded-[2px] transition-[width] duration-500 ${fill}`}
          style={{ width: `${soc ?? 0}%` }}
        />
      </span>
      <span className="ml-0.5 h-2 w-1 rounded-r-sm bg-hud-dim" />
    </span>
  )
}

/** checkup's current finding on the charge, if any (warn or fail). */
function chargeFinding(findings: Finding[]): Finding | undefined {
  return findings.find((f) => f.rule === 'charge' && f.subject === 'battery')
}

/** "Cells 3.912–3.931 V · spread 19 mV" (cells arrive in mV). */
function cellSpread(cells: number[]): string {
  if (!cells.length) return 'No cell data'
  const lo = Math.min(...cells)
  const hi = Math.max(...cells)
  return `Cells ${(lo / 1000).toFixed(3)}–${(hi / 1000).toFixed(3)} V · spread ${hi - lo} mV`
}
