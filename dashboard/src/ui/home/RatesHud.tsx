// Top right of Home: the rates, one per line, straight on the 3D view (no box). Snapshots arriving from the bridge, the robot's
// lowstate rate (as the bridge measured it), and the 3D view's frames per second.

import type { BridgeView } from '../../bridge/useBridge'

export function RatesHud({ view, fps }: { view: BridgeView; fps: number }) {
  const lowstate = view.latest?.snapshot.topics['rt/lf/lowstate']?.hz

  return (
    // flex-col items-start: a column, each line starting at the same left edge.
    // tabular-nums: digits all the same width, so the numbers don't jiggle as they change.
    <div className="pointer-events-auto absolute top-5 right-5 flex flex-col items-start gap-0.5 text-base font-medium text-hud-dim tabular-nums">
      <span title="snapshots per second arriving from the bridge">Bridge: {view.receivedHz.toFixed(0)} Hz</span>
      {/* 0 Hz until the bridge has measured rt/lf/lowstate (no snapshot yet, or the topic is silent) */}
      <span title="rt/lf/lowstate, as measured by the bridge">LowState: {(lowstate ?? 0).toFixed(0)} Hz</span>
      <span title="3D view frames per second">FPS: {fps}</span>
    </div>
  )
}
