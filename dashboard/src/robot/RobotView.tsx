// React wrapper for RobotScene: mounts it in a div and shows loading/error over it.

import { useEffect, useRef, useState } from 'react'
import { RobotScene, type SceneStatus } from './RobotScene'

export function RobotView() {
  const container = useRef<HTMLDivElement>(null)
  const [status, setStatus] = useState<SceneStatus>({ state: 'loading' })

  useEffect(() => {
    const scene = new RobotScene(container.current!, setStatus)
    return () => scene.dispose() // StrictMode mounts twice in dev: the first scene is disposed
  }, [])

  return (
    <div className="robot-view" ref={container}>
      {status.state === 'loading' && <div className="overlay">Loading H2 model…</div>}
      {status.state === 'error' && <div className="overlay error">{status.message}</div>}
    </div>
  )
}
