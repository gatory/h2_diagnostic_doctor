// Top centre of Home: the local time (this computer's clock and time zone), like a car's dash clock.

import { useEffect, useState } from 'react'

export function Clock() {
  const time = useClock()
  // tabular-nums: digits all the same width, so the time doesn't shift sideways as it changes
  return <time className="text-xl font-medium tabular-nums">{time}</time>
}

/** "2:41 PM" in the browser's locale, checked every few seconds (so it's never more than 5 s late). */
function useClock(): string {
  const format = () => new Date().toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })
  const [text, setText] = useState(format)
  useEffect(() => {
    const timer = window.setInterval(() => setText(format()), 5000)
    return () => window.clearInterval(timer)
  }, [])
  return text
}
