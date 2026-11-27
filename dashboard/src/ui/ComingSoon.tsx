// Placeholder panel for tabs that aren't built yet (Replays, Checkup).

import type { ReactNode } from 'react'
import { Panel } from './Panel'

export function ComingSoon({ open, title, children }: { open: boolean; title: string; children: ReactNode }) {
  return (
    <Panel open={open} title={title}>
      <p className="max-w-[560px] text-placeholder">{children}</p>
    </Panel>
  )
}
