// Bottom bar in the style of Tesla's in-car UI. Left: the bridge connection (on every tab).
// Centre: the tabs, each a white icon on its own coloured tile (Phosphor icons); hovering (or
// keyboard focus) shows the name above. Right: the app's name.
//
// Layout: one flex row, items spread out with justify-between (no wrapping):
//   [ status: may shrink ] ......... [ tabs: never grow or shrink ] ......... [ name: may shrink ]
// None of them grow; justify-between puts the free space between them. On a narrow screen the side
// texts shrink and end in "…" (min-w-0 + truncate) instead of pushing the tabs out of the bar.

import { ClockCounterClockwise, GearSix, House, Pulse, Stethoscope, type Icon } from '@phosphor-icons/react'
import type { BridgeView } from '../bridge/useBridge'

// Each tab's tile colour. Green, amber and red are left out on purpose: on this dashboard they
// only ever mean checkup's pass / warn / fail.
export const TABS = [
  { id: 'home', label: 'Home', Icon: House, colour: 'bg-sky-500' },
  { id: 'telemetry', label: 'Telemetry', Icon: Pulse, colour: 'bg-violet-500' },
  { id: 'replays', label: 'Replays', Icon: ClockCounterClockwise, colour: 'bg-pink-500' },
  { id: 'checkup', label: 'Checkup', Icon: Stethoscope, colour: 'bg-cyan-600' },
  // Settings: a placeholder for now (its panel says "coming soon"); it makes five, so Replays sits in the middle.
  { id: 'settings', label: 'Settings', Icon: GearSix, colour: 'bg-indigo-500' },
] as const satisfies readonly { id: string; label: string; Icon: Icon; colour: string }[]
export type Tab = (typeof TABS)[number]['id']

type Props = { view: BridgeView; tab: Tab; onTab: (tab: Tab) => void }

// dot: the dot's colour, plus a soft glow of the same colour (shadow-ok = a shadow in --ok).
function connection({ state, latest }: BridgeView): { text: string; dot: string } {
  if (state === 'open') {
    return { text: latest ? (latest.source === 'live' ? 'Live' : 'Replay') : 'Connected', dot: 'bg-ok shadow-ok' }
  }
  if (state === 'closed') return { text: 'Bridge offline · retrying', dot: 'bg-fail shadow-fail' }
  return { text: 'Connecting…', dot: 'bg-placeholder shadow-placeholder' }
}

export function BottomNav({ view, tab, onTab }: Props) {
  const { text, dot } = connection(view)

  return (
    // relative isolate: the glow below can sit behind the bar's contents (-z-10) but in front of its background
    <nav className="relative isolate flex h-20 items-center justify-between gap-8 border-t border-divider bg-bar px-8 text-placeholder">
      {/* White glow along the whole bottom edge: a gradient from 14% white at the bottom (from-white/14)
          up to clear at the top (to-transparent). bg-linear-to-t = linear gradient towards the top. */}
      <span aria-hidden className="pointer-events-none absolute inset-0 -z-10 bg-linear-to-t from-white/12 to-transparent" />
      {/* shrink + min-w-0: may get narrower than its text (flex items won't go below their content
          width without min-w-0); truncate cuts the text with "…" */}
      {/* Bright on purpose: the connection is the first thing to check when the screen looks wrong. */}
      <span className="flex min-w-0 shrink items-center gap-2.5 text-base font-medium text-on-surface">
        <span className={`size-2.5 flex-none rounded-full shadow-[0_0_8px] ${dot}`} />
        <span className="truncate">{text}</span>
      </span>

      <div className="flex flex-none gap-20">
        {TABS.map(({ id, label, Icon, colour }) => (
          // group: the label below reacts to this button's hover/focus (group-hover, group-focus-visible)
          <button
            key={id}
            onClick={() => onTab(id)}
            aria-label={label}
            aria-current={id === tab ? 'page' : undefined}
            // The tile: coloured box, white icon. The current tab gets a white ring around it (ring-offset
            // leaves a gap in the bar's colour between tile and ring); the others are dimmed until hovered.
            className={`group relative grid size-11 cursor-pointer place-items-center rounded-xs border-0 text-white
              transition duration-300 ${colour}
              ${id === tab
                ? 'ring-2 ring-white/80 ring-offset-2 ring-offset-bar light:ring-black/60'
                : 'opacity-55 hover:opacity-100'}`}
          >
            {/* fill: a solid white icon, which reads best on a coloured tile */}
            <Icon className="size-6" weight="fill" aria-hidden />
            {/* The name, above the icon: hidden (and slightly lower) until hovered, then fades up into place. */}
            <span
              className="pointer-events-none absolute bottom-full mb-2 translate-y-1 rounded-xs bg-panel px-2 py-1
                text-xs font-medium whitespace-nowrap text-on-surface opacity-0 shadow-sm transition
                group-hover:translate-y-0 group-hover:opacity-100 group-focus-visible:translate-y-0
                group-focus-visible:opacity-100"
            >
              {label}
            </span>
          </button>
        ))}
      </div>

      <div className="min-w-0 shrink truncate text-base font-medium">The H2 Doctor</div>
    </nav>
  )
}
