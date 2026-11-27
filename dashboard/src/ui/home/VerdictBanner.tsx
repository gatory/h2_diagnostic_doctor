// Top centre of Home, under the clock: checkup's verdict at a glance. Green "All checks passing", amber/red with
// the counts, or "Preflight…" with progress. Click it to list every finding, including those
// with no place on the body (battery, topics); a row with a place zooms the camera to it.
// Hidden while offline/connecting/waiting: the centre message says what's going on instead.

import { useEffect, useState } from 'react'
import type { BridgeView } from '../../bridge/useBridge'
import { HUD_BOX, STATUS_EDGE, STATUS_TEXT } from '../styles'
import { findingCounts, homeState } from './homeState'

type Props = { view: BridgeView; onFocus: (subject: string) => boolean }

const PILL = `flex min-w-[240px] items-center justify-center gap-2.5 px-5 py-2.5 text-[15px] font-medium ${HUD_BOX}`

export function VerdictBanner({ view, onFocus }: Props) {
  const [open, setOpen] = useState(false)
  const state = homeState(view)
  const checkup = view.latest?.checkup
  const findings = checkup?.findings ?? []

  useEffect(() => {
    if (!findings.length) setOpen(false) // nothing left to list
  }, [findings.length])

  if (state === 'offline' || state === 'connecting' || state === 'waiting' || !checkup) return null

  if (state === 'preflight') {
    const running = checkup.running_s ?? 0
    const progress = Math.min(1, running / checkup.preflight_s)
    return (
      <div role="status" className={`${PILL} flex-col gap-1.5 text-hud`}>
        <span>Preflight… {Math.floor(running)} / {checkup.preflight_s} s</span>
        <span className="block h-[3px] w-full overflow-hidden rounded-sm bg-hud-border">
          <span className="block h-full bg-hud transition-[width] duration-250 ease-linear" style={{ width: `${progress * 100}%` }} />
        </span>
      </div>
    )
  }

  const text = state === 'pass' ? 'All checks passing' : findingCounts(view)
  return (
    <div className="pointer-events-auto grid justify-items-center gap-1.5">
      <button
        onClick={() => findings.length && setOpen((o) => !o)}
        aria-expanded={open}
        disabled={!findings.length}
        // border-current: the border takes the text colour, so the pill is outlined in the verdict's colour
        className={`${PILL} border-current enabled:cursor-pointer ${STATUS_TEXT[state]}`}
      >
        {text}
        {findings.length > 0 && <span className="text-xs">{open ? '▴' : '▾'}</span>}
      </button>
      {open && (
        <ul className="m-0 grid max-h-[50vh] w-[min(520px,90vw)] list-none gap-1 overflow-y-auto rounded-xs border border-hud-border bg-panel p-1.5">
          {findings.map((f) => (
            <li key={`${f.rule}/${f.subject}`}>
              <button
                onClick={() => onFocus(f.subject) && setOpen(false)}
                className={`w-full cursor-pointer rounded-xs border-0 border-l-[3px] bg-tint px-3 py-2 text-left
                  text-on-surface ${STATUS_EDGE[f.status]}`}
              >
                <span className="mr-1.5 text-placeholder">{f.subject}</span>
                {f.message}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
