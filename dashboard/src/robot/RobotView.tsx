// React wrapper for RobotScene: mounts it in a div, shows loading/error over it, and passes on
// what React knows: panel state (camera framing), theme, checkup's findings (tags), and every
// bridge message (pose). Esc flies back from a focused joint.

import { useEffect, useRef, useState, type RefObject } from 'react'
import type { BridgeClient } from '../bridge/BridgeClient'
import type { Finding } from '../bridge/protocol'
import type { Theme } from './backdrop'
import { RobotScene, type SceneStatus } from './RobotScene'

const OVERLAY = 'pointer-events-none absolute inset-0 grid place-items-center text-placeholder'

type Props = {
  panelOpen: boolean
  client: BridgeClient | null
  theme: Theme
  findings: Finding[]
  dimmed: boolean // bridge offline: grey the robot out, so a stale pose doesn't look live
  sceneRef: RefObject<RobotScene | null> // for the overlay: focusSubject() from the banner's list
  onFps: (fps: number) => void
  onFocus: (subject: string | null) => void
}

export function RobotView({ panelOpen, client, theme, findings, dimmed, sceneRef, onFps, onFocus }: Props) {
  const container = useRef<HTMLDivElement>(null)
  const [status, setStatus] = useState<SceneStatus>({ state: 'loading' })
  // The callbacks can change every render; the scene keeps calling the newest ones.
  const callbacks = useRef({ onFps, onFocus })
  callbacks.current = { onFps, onFocus }

  useEffect(() => {
    const created = new RobotScene(container.current!, setStatus, {
      theme,
      onFps: (fps) => callbacks.current.onFps(fps),
      onFocus: (subject) => callbacks.current.onFocus(subject),
    })
    sceneRef.current = created
    return () => {
      created.dispose() // StrictMode mounts twice in dev: the first scene is disposed
      if (sceneRef.current === created) sceneRef.current = null
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- created once; theme changes go through setTheme
  }, [])

  useEffect(() => sceneRef.current?.setPanelOpen(panelOpen), [panelOpen, sceneRef])
  useEffect(() => sceneRef.current?.setTheme(theme), [theme, sceneRef])
  useEffect(() => sceneRef.current?.setFindings(findings), [findings, sceneRef])

  // Every message goes straight to the scene, not through React state: 30 poses a second
  // shouldn't re-render the page.
  useEffect(() => {
    if (!client) return
    return client.subscribe(() => {
      const joints = client.latest?.snapshot.body?.joints
      if (joints) sceneRef.current?.setPose(joints)
    })
  }, [client, sceneRef])

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') sceneRef.current?.unfocus()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [sceneRef])

  return (
    // [&_canvas]: style the <canvas> three.js adds inside this div. Offline: grey and dim it,
    // so a stale pose doesn't look live.
    <div
      ref={container}
      className={`absolute inset-0 overflow-hidden [&_canvas]:transition-[filter] [&_canvas]:duration-500
        ${dimmed ? '[&_canvas]:brightness-55 [&_canvas]:grayscale' : ''}`}
    >
      {status.state === 'loading' && <div className={OVERLAY}>Loading H2 model…</div>}
      {status.state === 'error' && <div className={`${OVERLAY} text-on-surface`}>{status.message}</div>}
    </div>
  )
}
