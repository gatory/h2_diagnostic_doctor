// React wrapper for RobotScene: mounts it in a div, shows loading/error over it, passes the
// metrics panel's state on so the camera can reframe, and poses the model from the bridge.

import { useEffect, useRef, useState } from 'react'
import type { BridgeClient } from '../bridge/BridgeClient'
import { RobotScene, type SceneStatus } from './RobotScene'

type Props = { panelOpen: boolean; client: BridgeClient | null }

export function RobotView({ panelOpen, client }: Props) {
  const container = useRef<HTMLDivElement>(null)
  const scene = useRef<RobotScene | null>(null)
  const [status, setStatus] = useState<SceneStatus>({ state: 'loading' })

  useEffect(() => {
    const created = new RobotScene(container.current!, setStatus)
    scene.current = created
    return () => created.dispose() // StrictMode mounts twice in dev: the first scene is disposed
  }, [])

  useEffect(() => scene.current?.setPanelOpen(panelOpen), [panelOpen])

  // Every message goes straight to the scene, not through React state: 30 poses a second
  // shouldn't re-render the page.
  useEffect(() => {
    if (!client) return
    return client.subscribe(() => {
      const joints = client.latest?.snapshot.body?.joints
      if (joints) scene.current?.setPose(joints)
    })
  }, [client])

  return (
    <div className="robot-view" ref={container}>
      {status.state === 'loading' && <div className="overlay">Loading H2 model…</div>}
      {status.state === 'error' && <div className="overlay error">{status.message}</div>}
    </div>
  )
}
