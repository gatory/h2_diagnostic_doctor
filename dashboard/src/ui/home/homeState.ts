// Which situation the Home screen is in, from the bridge's view. Every Home component reads this,
// so "bridge offline" can never look like "robot fault". No judging here: pass/warn/fail and
// preflight are checkup's; this only picks which of them to show.

import type { BridgeView } from '../../bridge/useBridge'

export type HomeState =
  | 'offline' // the bridge's server can't be reached (it retries)
  | 'connecting' // first connection attempt
  | 'waiting' // connected, but no snapshot yet, or the robot's body topic hasn't sent anything
  | 'preflight' // checkup is still in its first PREFLIGHT_S: no verdict yet
  | 'pass'
  | 'warn'
  | 'fail'

export function homeState({ state, latest }: BridgeView): HomeState {
  if (state === 'closed') return 'offline'
  if (state === 'connecting') return 'connecting'
  if (!latest || !latest.snapshot.body) return 'waiting'
  if (latest.checkup.preflight) return 'preflight'
  const now = latest.checkup.now
  return now === 'warn' || now === 'fail' ? now : 'pass'
}

/** "2 warnings · 1 failing" from checkup's findings. */
export function findingCounts(view: BridgeView): string {
  const findings = view.latest?.checkup.findings ?? []
  const fails = findings.filter((f) => f.status === 'fail').length
  const warns = findings.filter((f) => f.status === 'warn').length
  const parts = []
  if (fails) parts.push(`${fails} failing`)
  if (warns) parts.push(`${warns} warning${warns === 1 ? '' : 's'}`)
  return parts.join(' · ')
}
