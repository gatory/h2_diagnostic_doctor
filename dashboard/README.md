# Dashboard

The viewer half of the project. It runs on any computer and never imports from `bridge/`.
It shows the H2 as a 3D model, posed from the bridge's WebSocket server: the live robot
(`h2-doctor server live`) or a recording (`h2-doctor server replay [FILE]`).

**Stack:** React + TypeScript + Vite, Tailwind CSS v4 (styles as classes in the components), three.js + urdf-loader for the 3D view.

## Run it

```bash
cd dashboard
npm install        # once
npm run dev        # http://localhost:5173
npm run build      # type-check (tsc) and build to dist/
```

With data, from `bridge/` in another terminal: `uv run h2-doctor server replay` (the newest
recording) or `uv run h2-doctor server live`. The page connects to port 8765 on the host that
served it (`localhost` in dev) and retries every 2 s; `?bridge=ws://<host>:8765` points it elsewhere,
e.g. at the Thor while the page runs on a laptop.

## Layout

```
src/
  main.tsx, App.tsx       page shell: tabs, theme (dark/light, remembered), the bridge client
  index.css               colour tokens (dark default; data-theme="light" on <html>), the Tailwind theme
                          that turns them into classes (bg-panel, text-ok, ...), and the robot tags' placement
  bridge/protocol.ts      types of the server's messages (match bridge/src/h2_bridge/server/messages.py by hand)
  bridge/BridgeClient.ts  the WebSocket: newest snapshot only, reconnects, receivedHz(); bridgeUrl()
  bridge/useBridge.ts     useBridgeClient(), useBridgeView() (panels: re-render at most every 250 ms)
  robot/RobotScene.ts     the 3D view: scene, camera, fly-in through fog, setPose(), setFindings(),
                          focusSubject()/unfocus(), setTheme(), fps
  robot/RobotView.tsx     React wrapper: passes pose (every message), findings, theme, panel state; Esc
  robot/findingTags.ts    checkup findings as tags on the body: findingAnchor() (subject -> joint/link)
  robot/jointNames.ts     urdfJointName(): bridge "L_hip_roll" -> URDF "left_hip_roll_joint"
  robot/backdrop.ts       studio wall + mirrored floor, dark and light palettes
  ui/home/                Home: homeState() (offline/connecting/waiting/preflight/pass/warn/fail),
                          StatusBlock, VerdictBanner (+ findings list), TopBar (clock, theme, rates)
  ui/MetricsPanel.tsx     the Telemetry tab (for now)
  ui/ComingSoon.tsx       Replays and Checkup tabs (placeholders)
  ui/BottomNav.tsx        connection, tabs
  ui/Panel.tsx            the sliding side panel the Telemetry/Replays/Checkup tabs use
  ui/styles.ts            class sets used in several places: STATUS_TEXT/EDGE/FILL, HUD_BOX
public/renders/
  h2_description/         H2.urdf + its .stl meshes (served at /renders/...); see docs/robot_models.md
```

## 3D view facts

- The URDF is Z-up, three.js is Y-up: the robot is rotated -90° about X, then lifted so its
  feet sit on the floor grid (y = 0).
- The camera looks at the robot's front (URDF +X). Drag to orbit, scroll to zoom, right-drag to pan.
- Home never judges values: pass/warn/fail and preflight come from checkup in each message
  (`checkup.now`, `checkup.preflight`); the UI only picks how to show them. "Bridge offline" greys
  the robot out and never looks like a robot fault.
- Joints are matched by name, never by slot: `urdfJointName()` turns the bridge's `L_hip_roll` into
  the URDF's `left_hip_roll_joint` (all 31 match). Poses go straight to the scene, not through React.
- Mesh loading is counted by hand, not with `LoadingManager.onLoad`: in dev, React mounts the
  view twice, three.js shares the in-flight downloads, and the second manager's `onLoad` fires
  before any mesh has arrived.
