// The side panel used by the Telemetry, Replays and Checkup tabs: a card over the right 60% of
// the screen that slides in from the right edge (0.7 s, matching the camera's REFRAME_MS).

import type { ReactNode } from 'react'

export function Panel({ open, title, children }: { open: boolean; title: string; children: ReactNode }) {
  return (
    <section
      aria-hidden={!open}
      className={`absolute top-5 right-5 bottom-6 box-border w-[60vw] overflow-y-auto rounded-xs bg-panel p-8
        transition-[transform,opacity] duration-700 ease-[cubic-bezier(0.33,1,0.68,1)]
        ${open ? 'translate-x-0' : 'pointer-events-none translate-x-[calc(100%+20px)] opacity-0'}`}
    >
      <h2 className="mt-0 mb-4 text-[17px] font-medium text-on-surface">{title}</h2>
      {children}
    </section>
  )
}
