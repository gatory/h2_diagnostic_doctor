import { useEffect, useRef, useState } from 'react'
import { useBridgeClient, useBridgeView } from './bridge/useBridge'
import type { Theme } from './robot/backdrop'
import type { RobotScene } from './robot/RobotScene'
import { RobotView } from './robot/RobotView'
import { BottomNav, type Tab } from './ui/BottomNav'
import { ComingSoon } from './ui/ComingSoon'
import { HomeOverlay } from './ui/home/HomeOverlay'
import { MetricsPanel } from './ui/MetricsPanel'

const THEME_KEY = 'h2-doctor.theme'

export default function App() {
  const [tab, setTab] = useState<Tab>('home')
  const [theme, setTheme] = useTheme()
  const [fps, setFps] = useState(0)
  const [focused, setFocused] = useState<string | null>(null)
  const sceneRef = useRef<RobotScene | null>(null)
  const client = useBridgeClient()
  const view = useBridgeView(client)
  const findings = view.latest?.checkup.findings ?? NO_FINDINGS

  return (
    <div className="grid h-full grid-rows-[1fr_auto]">
      {/* min-h-0: let the 3D view shrink to the row; overflow-hidden: closed panels hide past the right edge */}
      <main className="relative min-h-0 overflow-hidden">
        <RobotView
          panelOpen={tab !== 'home'}
          client={client}
          theme={theme}
          findings={findings}
          dimmed={view.state === 'closed'}
          sceneRef={sceneRef}
          onFps={setFps}
          onFocus={setFocused}
        />
        {tab === 'home' && (
          <HomeOverlay
            view={view}
            fps={fps}
            theme={theme}
            focused={focused}
            onToggleTheme={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
            onFocus={(subject) => sceneRef.current?.focusSubject(subject) ?? false}
          />
        )}
        <MetricsPanel open={tab === 'telemetry'} view={view} />
        <ComingSoon open={tab === 'replays'} title="Replays">
          Browsing and playing recordings from here needs a server command that lists them. For now, run
          `h2-doctor server replay [FILE]` and watch it on Home.
        </ComingSoon>
        <ComingSoon open={tab === 'checkup'} title="Checkup">
          Every rule with its status and history. For now, Home's verdict banner lists the current findings.
        </ComingSoon>
      </main>
      <BottomNav view={view} tab={tab} onTab={setTab} />
    </div>
  )
}

const NO_FINDINGS: never[] = [] // one array, so "no findings" doesn't re-tag the robot every render

/** Dark or light, remembered in this browser; sets data-theme on <html> for the CSS. */
function useTheme(): [Theme, (theme: Theme) => void] {
  const [theme, setTheme] = useState<Theme>(() => {
    try {
      return localStorage.getItem(THEME_KEY) === 'light' ? 'light' : 'dark'
    } catch {
      return 'dark' // storage blocked: still works, just not remembered
    }
  })
  useEffect(() => {
    document.documentElement.dataset.theme = theme
    try {
      localStorage.setItem(THEME_KEY, theme)
    } catch {
      // not remembered; fine
    }
  }, [theme])
  return [theme, setTheme]
}
