// The Home screen's layer over the 3D robot: FSM gear row and status (top left), verdict banner (top centre),
// clock and rates (top right), and a centre message while there's no robot data to show.

import type { BridgeView } from '../../bridge/useBridge'
import type { Theme } from '../../robot/backdrop'
import { HUD_BOX } from '../styles'
import { FSMStateBlock, previewGear } from './FSMStateBlock'
import { homeState, type HomeState } from './homeState'
import { StatusBlock } from './StatusBlock'
import { TopBar } from './TopBar'
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
        <FSMStateBlock current={previewGear()} />
        {/* TODO: re-enable this later */}
        {/* <StatusBlock view={view} /> */}
      </div>
      <VerdictBanner view={view} onFocus={onFocus} />
      <TopBar view={view} fps={fps} theme={theme} onToggleTheme={onToggleTheme} />
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
