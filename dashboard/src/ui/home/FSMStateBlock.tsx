// Top left of Home: the robot's state machine (FSM) as a gear row, like a car's P R N D.
//
//   Z › D › R › [ W1  W2 ]
//
// The flow: Zero torque -> Damp -> Ready -> Walk 1 or Walk 2. Walk 1/2 can drop back to Damp, and
// Damp back to Zero torque. Ready is as far as it goes on its own: once the robot is in Ready, the
// Walk pair flashes to say "ready to enter walk mode".
//
// An indicator, not a selector: the dashboard (and the bridge) never change the robot's mode. The
// current gear comes from the bridge's FSM queries (robot_queries.py, not streamed yet: until then
// `current` is null and the row shows "FSM unknown"). To preview a gear now: add ?fsm=ready (or
// zero_torque, damp, walk1, walk2) to the page's URL.

import { CaretRight } from '@phosphor-icons/react'
import { HUD_BOX } from '../styles'

export const GEARS = [
  { id: 'zero_torque', short: 'Z', label: 'Zero torque' },
  { id: 'damp', short: 'D', label: 'Damp' },
  { id: 'ready', short: 'R', label: 'Ready' },
  { id: 'walk1', short: 'W1', label: 'Walk 1' },
  { id: 'walk2', short: 'W2', label: 'Walk 2' },
] as const
export type Gear = (typeof GEARS)[number]['id']

const isGear = (value: string | null): value is Gear => GEARS.some((g) => g.id === value)

/** ?fsm=<gear> in the URL, for previewing the row before the bridge sends the FSM state. */
export function previewGear(): Gear | null {
  const value = new URLSearchParams(window.location.search).get('fsm')
  return isGear(value) ? value : null
}

const LINEAR = GEARS.slice(0, 3) // Z, D, R: one after another
const WALKS = GEARS.slice(3) // W1, W2: either one, from Ready

export function FSMStateBlock({ current }: { current: Gear | null }) {
  const ready = current === 'ready'
  const label = current ? GEARS.find((g) => g.id === current)!.label : 'FSM unknown'

  return (
    <div className={`pointer-events-auto grid gap-1.5 px-4 py-3 ${HUD_BOX}`} aria-label={`Robot mode: ${label}`}>
      <div className="flex items-center gap-1">
        {LINEAR.map((g) => (
          <span key={g.id} className="flex items-center gap-1">
            <GearLetter gear={g} current={current} />
            <CaretRight className="size-3.5 text-hud-dim" weight="bold" aria-hidden />
          </span>
        ))}
        {/* The Walk pair, boxed together: either one can follow Ready. While in Ready the box flashes
            (motion-safe: not for people who've asked their system for reduced motion). */}
        <span
          className={`flex items-center gap-0.5 rounded-xs border px-1 transition-colors
            ${ready ? 'border-sky-400 bg-sky-400/15 motion-safe:animate-pulse' : 'border-hud-border'}`}
        >
          {WALKS.map((g) => (
            <GearLetter key={g.id} gear={g} current={current} highlight={ready} />
          ))}
        </span>
      </div>
      <div className="flex items-center justify-between gap-3 text-xs">
        <span className={current ? 'font-medium text-hud' : 'text-hud-dim'}>{label}</span>
        {ready && <span className="font-medium text-sky-400 motion-safe:animate-pulse">Ready to walk</span>}
      </div>
    </div>
  )
}

type GearProps = { gear: (typeof GEARS)[number]; current: Gear | null; highlight?: boolean }

/** One gear: bright and bold when it's the current one, dim otherwise (like a car's gear readout). */
function GearLetter({ gear, current, highlight = false }: GearProps) {
  const on = gear.id === current
  const tone = on ? 'text-hud font-semibold' : highlight ? 'text-sky-400 font-medium' : 'text-hud-dim/50 font-medium'
  return (
    <span
      title={gear.label}
      aria-current={on ? 'true' : undefined}
      className={`grid min-w-7 place-items-center rounded-xs px-1 py-0.5 text-xl tabular-nums transition-colors
        ${tone} ${on ? 'bg-white/10 light:bg-black/8' : ''}`}
    >
      {gear.short}
    </span>
  )
}
