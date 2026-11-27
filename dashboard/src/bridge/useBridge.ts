// React hooks around BridgeClient. The 3D view subscribes to the client directly (every
// message, no React render); panels use useBridgeView(), which re-renders a few times a second.

import { useEffect, useState } from 'react'
import { BridgeClient, bridgeUrl, type ConnectionState } from './BridgeClient'
import type { SnapshotMessage } from './protocol'

/** One BridgeClient for the component's lifetime (closed on unmount; StrictMode's double mount is fine). */
export function useBridgeClient(url: string = bridgeUrl()): BridgeClient | null {
  const [client, setClient] = useState<BridgeClient | null>(null)
  useEffect(() => {
    const created = new BridgeClient(url)
    setClient(created)
    return () => created.close()
  }, [url])
  return client
}

export type BridgeView = {
  state: ConnectionState
  latest: SnapshotMessage | null
  url: string // where it connects, for "Connecting to ..."
  receivedHz: number // snapshots per second actually arriving
}

/** The client's state and newest snapshot, updated at most every `everyMs` (text doesn't need 30 Hz). */
export function useBridgeView(client: BridgeClient | null, everyMs = 250): BridgeView {
  const [view, setView] = useState<BridgeView>({ state: 'connecting', latest: null, url: '', receivedHz: 0 })
  useEffect(() => {
    if (!client) return
    let timer = 0
    const update = () =>
      setView({ state: client.state, latest: client.latest, url: client.url, receivedHz: client.receivedHz() })
    update()
    const tick = window.setInterval(update, 1000) // so the rate falls to 0 when messages stop
    const unsubscribe = client.subscribe(() => {
      if (!timer) timer = window.setTimeout(() => ((timer = 0), update()), everyMs)
    })
    return () => {
      unsubscribe()
      window.clearTimeout(timer)
      window.clearInterval(tick)
    }
  }, [client, everyMs])
  return view
}
