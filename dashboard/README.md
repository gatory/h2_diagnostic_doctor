# Dashboard

The viewer half of the project. It runs on any computer and never imports from `bridge/`.
Today it shows the H2 as a 3D model; next it will play recordings (`.jsonl.gz` from
`h2-doctor telemetry watch --record`) to pose that model. A live feed from the bridge comes later.

**Stack:** React + TypeScript + Vite, three.js + urdf-loader for the 3D view.

## Run it

```bash
cd dashboard
npm install        # once
npm run dev        # http://localhost:5173
npm run build      # type-check (tsc) and build to dist/
```

## Layout

```
src/
  main.tsx, App.tsx      page shell
  index.css              styles
  robot/RobotScene.ts    the 3D view: three.js scene, camera, orbit controls, loads the H2 URDF
  robot/RobotView.tsx    React wrapper: mounts RobotScene, shows loading/errors over it
public/renders/
  h2_description/        H2.urdf + its .stl meshes (served at /renders/...); see docs/robot_models.md
```

## 3D view facts

- The URDF is Z-up, three.js is Y-up: the robot is rotated -90° about X, then lifted so its
  feet sit on the floor grid (y = 0).
- The camera looks at the robot's front (URDF +X). Drag to orbit, scroll to zoom, right-drag to pan.
- Mesh loading is counted by hand, not with `LoadingManager.onLoad`: in dev, React mounts the
  view twice, three.js shares the in-flight downloads, and the second manager's `onLoad` fires
  before any mesh has arrived.
