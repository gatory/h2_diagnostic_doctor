// The connection to the bridge's WebSocket server: keeps only the newest snapshot, and
// reconnects on its own (the server may start after the page, or restart).
//
//   const client = new BridgeClient(bridgeUrl())
//   const stop = client.subscribe(() => draw(client.latest))   // after every message / state change
//   client.close()

import { PROTOCOL, type SnapshotMessage } from './protocol'

export type ConnectionState = 'connecting' | 'open' | 'closed'

const RETRY_MS = 2000
const RATE_WINDOW_MS = 2000 // receivedHz() averages over this
const DEFAULT_PORT = 8765 // SERVER_DEFAULTS in bridge/src/h2_bridge/constants.py

/** Where the bridge is: ?bridge=ws://host:port, else port 8765 on the host that served this page. */
export function bridgeUrl(): string {
  const fromQuery = new URLSearchParams(window.location.search).get('bridge')
  return fromQuery ?? `ws://${window.location.hostname || 'localhost'}:${DEFAULT_PORT}`
}

export class BridgeClient {
  readonly url: string
  state: ConnectionState = 'connecting'
  /** The newest snapshot; kept after a disconnect (the last thing the bridge said). */
  latest: SnapshotMessage | null = null

  private socket: WebSocket | null = null
  private listeners = new Set<() => void>()
  private retryTimer = 0
  private closed = false
  private warnedProtocol = false
  private arrivals: number[] = [] // performance.now() of each message in the last RATE_WINDOW_MS

  constructor(url: string) {
    this.url = url
    this.connect()
  }

  /** Call `listener` after every message and connection change. Returns the unsubscribe function. */
  subscribe(listener: () => void): () => void {
    this.listeners.add(listener)
    return () => this.listeners.delete(listener)
  }

  /** Snapshots received per second, over the last 2 s (0 when nothing is arriving). */
  receivedHz(): number {
    this.dropOldArrivals(performance.now())
    return this.arrivals.length / (RATE_WINDOW_MS / 1000)
  }

  private dropOldArrivals(now: number) {
    const cutoff = now - RATE_WINDOW_MS
    let i = 0
    while (i < this.arrivals.length && this.arrivals[i] < cutoff) i++
    if (i) this.arrivals.splice(0, i)
  }

  /** Disconnect for good (no more retries). Safe to call twice. */
  close() {
    this.closed = true
    window.clearTimeout(this.retryTimer)
    this.socket?.close()
    this.socket = null
  }

  private connect() {
    if (this.closed) return
    this.setState('connecting')
    const socket = new WebSocket(this.url)
    this.socket = socket
    socket.onopen = () => this.setState('open')
    socket.onmessage = (event) => this.receive(event.data)
    socket.onclose = () => {
      if (this.socket !== socket) return // replaced or closed on purpose
      this.socket = null
      this.setState('closed')
      this.retryTimer = window.setTimeout(() => this.connect(), RETRY_MS)
    }
    // onerror is always followed by onclose, which does the retry.
  }

  private receive(data: unknown) {
    if (typeof data !== 'string') return
    let message: SnapshotMessage
    try {
      message = JSON.parse(data)
    } catch {
      return // not JSON: ignore it rather than drop the connection
    }
    if (message.type !== 'snapshot') return
    if (message.protocol !== PROTOCOL) {
      if (!this.warnedProtocol) console.warn(`bridge speaks protocol ${message.protocol}, dashboard ${PROTOCOL}`)
      this.warnedProtocol = true
      return
    }
    this.latest = message
    const now = performance.now()
    this.arrivals.push(now)
    this.dropOldArrivals(now)
    this.notify()
  }

  private setState(state: ConnectionState) {
    this.state = state
    this.notify()
  }

  private notify() {
    for (const listener of this.listeners) listener()
  }
}
