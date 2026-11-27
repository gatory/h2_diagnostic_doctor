// Tailwind class sets used by more than one component. Kept as whole class names (not built from
// pieces like `text-${x}`): Tailwind only generates classes it can find written out in the source.

import type { Status } from '../bridge/protocol'

/** Text in checkup's colour for a status. */
export const STATUS_TEXT: Record<Status, string> = {
  pass: 'text-ok',
  warn: 'text-warn',
  fail: 'text-fail',
  'no data': 'text-placeholder',
}

/** A coloured bar on the left edge, for list rows and cards. */
export const STATUS_EDGE: Record<Status, string> = {
  pass: 'border-l-ok',
  warn: 'border-l-warn',
  fail: 'border-l-fail',
  'no data': 'border-l-placeholder',
}

/** A dot or leader line filled with the status colour. */
export const STATUS_FILL: Record<Status, string> = {
  pass: 'bg-ok',
  warn: 'bg-warn',
  fail: 'bg-fail',
  'no data': 'bg-placeholder',
}

/** The frosted box used for everything drawn over the 3D view. */
export const HUD_BOX = 'rounded-xs border border-hud-border bg-hud-chip backdrop-blur-md'
