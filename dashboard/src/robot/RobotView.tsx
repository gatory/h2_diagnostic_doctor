// React wrapper for RobotScene: mounts it in a div, shows loading/error over it, and
// passes the metrics panel's state on so the camera can reframe.

import { useEffect, useRef, useState } from 'react'
import { RobotScene, type SceneStatus } from './RobotScene'

export function RobotView({ panelOpen }: { panelOpen: boolean }) {
  const container = useRef<HTMLDivElement>(null)
  const scene = useRef<RobotScene | null>(null)
  const [status, setStatus] = useState<SceneStatus>({ state: 'loading' })

  useEffect(() => {
    const created = new RobotScene(container.current!, setStatus)
    scene.current = created
    return () => created.dispose() // StrictMode mounts twice in dev: the first scene is disposed
  }, [])

  useEffect(() => scene.current?.setPanelOpen(panelOpen), [panelOpen])

  return (
    <div className="robot-view" ref={container}>
      {status.state === 'loading' && <div className="overlay">Loading H2 model…</div>}
      {status.state === 'error' && <div className="overlay error">{status.message}</div>}
    </div>
  )
}
