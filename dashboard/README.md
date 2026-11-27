# Dashboard

The viewer half of the project. It runs on any computer and never imports from `bridge/`.
It shows the H2 as a 3D model, posed from the bridge's WebSocket server: the live robot
(`h2-doctor server live`) or a recording (`h2-doctor server replay [FILE]`).

**Stack:** React + TypeScript + Vite, three.js + urdf-loader for the 3D view.

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
  main.tsx, App.tsx      page shell
  index.css              styles
  robot/RobotScene.ts    the 3D view: three.js scene, camera, orbit controls, loads the H2 URDF
  robot/RobotView.tsx    React wrapper: mounts RobotScene, shows loading/errors over it, poses it from the bridge
  bridge/protocol.ts     types of the server's messages (match bridge/src/h2_bridge/server/messages.py by hand)
  bridge/BridgeClient.ts the WebSocket: newest snapshot only, reconnects; bridgeUrl()
  bridge/useBridge.ts    useBridgeClient(), useBridgeView() (panels: re-render at most every 250 ms)
public/renders/
  h2_description/        H2.urdf + its .stl meshes (served at /renders/...); see docs/robot_models.md
```

## 3D view facts

- The URDF is Z-up, three.js is Y-up: the robot is rotated -90° about X, then lifted so its
  feet sit on the floor grid (y = 0).
- The camera looks at the robot's front (URDF +X). Drag to orbit, scroll to zoom, right-drag to pan.
- Joints are matched by name, never by slot: `urdfJointName()` turns the bridge's `L_hip_roll` into
  the URDF's `left_hip_roll_joint` (all 31 match). Poses go straight to the scene, not through React.
- Mesh loading is counted by hand, not with `LoadingManager.onLoad`: in dev, React mounts the
  view twice, three.js shares the in-flight downloads, and the second manager's `onLoad` fires
  before any mesh has arrived.
