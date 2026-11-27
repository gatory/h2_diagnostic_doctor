// Dark/light switch as an icon (28px, in a 44px round button), next to the clock (top centre of Home). Shows the mode you'd switch
// TO: a sun while dark ("go light"), a moon while light ("go dark").

import { Moon, Sun } from '@phosphor-icons/react'
import type { Theme } from '../../robot/backdrop'

export function ThemeToggle({ theme, onToggle }: { theme: Theme; onToggle: () => void }) {
  const next = theme === 'dark' ? 'light' : 'dark'
  const Icon = theme === 'dark' ? Sun : Moon
  return (
    <button
      onClick={onToggle}
      title={`Switch to ${next} mode`}
      aria-label={`Switch to ${next} mode`}
      className="pointer-events-auto grid size-11 cursor-pointer place-items-center rounded-full border-0 bg-transparent
        text-hud-dim transition-colors hover:bg-white/10 hover:text-hud light:hover:bg-black/8"
    >
      <Icon className="size-7" weight="fill" aria-hidden />
    </button>
  )
}
