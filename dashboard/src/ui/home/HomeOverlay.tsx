// The Home screen's layer over the 3D robot: FSM gear row + battery, then status (top left), clock + theme switch and verdict banner (top centre),
// rates (top right), and a centre message while there's no robot data to show.

import type { BridgeView } from '../../bridge/useBridge'
import type { Theme } from '../../robot/backdrop'
import { HUD_BOX } from '../styles'
import { BatteryBlock } from './BatteryBlock'
import { Clock } from './Clock'
import { FSMStateBlock, previewGear } from './FSMStateBlock'
import { homeState, type HomeState } from './homeState'
// import { StatusBlock } from './StatusBlock' // TODO: re-enable with <StatusBlock /> below
import { RatesHud } from './RatesHud'
import { ThemeToggle } from './ThemeToggle'
import { VerdictBanner } from './VerdictBanner'

type Props = {
  view: BridgeView
  fps: number
  theme: Theme
  focused: string | null
  onToggleTheme: () => void
  onFocus: (subject: string) => boolean
}

export function HomeOverlay({ view, fps, theme, focused, onToggleTheme, onFocus }: Props) {
  const state = homeState(view)
  return (
    // pointer-events-none: drags pass through to the 3D view; the boxes opt back in (pointer-events-auto)
    <div className="pointer-events-none absolute inset-0 text-hud">
      {/* Top-left column: the gear row, then the status lines under it. items-start: each box only as wide as it needs. */}
      <div className="absolute top-5 left-5 flex flex-col items-start gap-3">
        {/* The bridge doesn't send the FSM state yet (robot_queries.py, not streamed): null shows "FSM unknown".
            previewGear() reads ?fsm=... from the URL so the row can be tried out meanwhile. */}
        {/* items-stretch: the battery box is as tall as the FSM box beside it */}
        <div className="flex items-stretch gap-3">
          <FSMStateBlock current={previewGear()} />
          <BatteryBlock view={view} />
        </div>
        {/* TODO: re-enable this later */}
        {/* <StatusBlock view={view} /> */}
      </div>
      {/* Top-centre column: the clock with the dark/light switch beside it, then checkup's verdict under
          them. left-1/2 puts the column's left edge in the middle of the screen; -translate-x-1/2 pulls
          it back by half its own width. */}
      <div className="absolute top-5 left-1/2 flex -translate-x-1/2 flex-col items-center gap-3">
        <div className="flex items-center gap-2">
          <Clock />
          <ThemeToggle theme={theme} onToggle={onToggleTheme} />
        </div>
        <VerdictBanner view={view} onFocus={onFocus} />
      </div>
      <RatesHud view={view} fps={fps} />
      <CentreMessage state={state} url={view.url} />
      {focused && (
        <div className="absolute bottom-5 left-1/2 -translate-x-1/2 rounded-xs bg-hud-chip px-3.5 py-1.5 text-hud-dim">
          {focused} · Esc to go back
        </div>
      )}
    </div>
  )
}

function CentreMessage({ state, url }: { state: HomeState; url: string }) {
  const box = `absolute top-[45%] left-1/2 grid -translate-1/2 justify-items-center gap-1 px-6 py-4 text-center ${HUD_BOX}`
  if (state === 'offline') {
    return (
      <div className={box}>
        <strong>Bridge offline</strong>
        <span className="text-hud-dim">Retrying {url} every 2 s. Is `h2-doctor server` running?</span>
      </div>
    )
  }
  if (state === 'connecting') return <div className={box}>Connecting to {url}…</div>
  if (state === 'waiting') {
    return (
      <div className={box}>
        <strong>Connected · waiting for robot data</strong>
        <span className="text-hud-dim">No body data yet (rt/lf/lowstate).</span>
      </div>
    )
  }
  return null
}
