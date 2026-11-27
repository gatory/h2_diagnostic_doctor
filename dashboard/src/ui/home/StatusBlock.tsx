// Top left of Home, under the FSM row and battery: connection, mode and checkup, one line each.
// Numbers only: the verdicts come from checkup.

import type { ReactNode } from 'react'
import type { BridgeView } from '../../bridge/useBridge'
import { HUD_BOX, STATUS_TEXT } from '../styles'
import { findingCounts, homeState } from './homeState'

const CHECKUP_TEXT = {
  offline: '—',
  connecting: '—',
  waiting: 'Waiting for data',
  preflight: 'Preflight…',
  pass: 'All checks passing',
} as const

export function StatusBlock({ view }: { view: BridgeView }) {
  const state = homeState(view)
  const latest = view.latest
  const body = latest?.snapshot.body
  const live = view.state === 'open' && latest

  return (
    <div className={`pointer-events-auto grid min-w-[220px] gap-1 px-4 py-3 ${HUD_BOX}`}>
      <Row label="Bridge">
        {view.state === 'closed' && <span className="text-fail">Offline · retrying</span>}
        {view.state === 'connecting' && 'Connecting…'}
        {view.state === 'open' && !latest && 'Connected'}
        {live && latest.source === 'live' && 'Live'}
        {live && latest.source === 'replay' && (
          <span className="rounded-xs bg-warn px-2 py-px text-xs font-semibold tracking-wider text-white uppercase">
            Replay
          </span>
        )}
      </Row>
      <Row label="Mode">
        {/* mode_pr is the only mode the bridge reads so far; the FSM comes with the robot-queries poller. */}
        {body ? (body.mode_pr === 0 ? 'PR' : body.mode_pr === 1 ? 'AB · ankle/waist q raw' : `mode_pr ${body.mode_pr}`) : '—'}
      </Row>
      <Row label="Checkup">
        {state === 'warn' || state === 'fail' ? (
          <span className={STATUS_TEXT[state]}>{findingCounts(view)}</span>
        ) : (
          <span className={state === 'pass' ? STATUS_TEXT.pass : ''}>{CHECKUP_TEXT[state]}</span>
        )}
      </Row>
    </div>
  )
}

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="grid grid-cols-[72px_1fr] gap-2">
      <span className="text-hud-dim">{label}</span>
      <span className="font-medium">{children}</span>
    </div>
  )
}
