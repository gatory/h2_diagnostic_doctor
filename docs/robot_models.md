# Robot models (URDF + meshes)

The dashboard's 3D view uses the H2's URDF and meshes in
`dashboard/public/renders/h2_description/`.

- **Copied from** the MVP (`../h2_diagnostics/dashboard/public/renders/h2_description/`)
  on 2026-11-25. Only `H2.urdf` and the 35 `.stl` meshes (13 MB) it refers to; the MVP's
  `.dae` copies (30 MB) aren't used.
- **Original source: unconfirmed.** The MVP has no README or license for these files. They
  look like Unitree's published H2 description. Record the source and license here once known.
- **Joints:** 31 revolute joints named like `left_knee_joint`, `waist_yaw_joint`,
  `head_pitch_joint`, matching the 31 body slots in `bridge/.../telemetry/layout.py`
  (`BODY_JOINTS`, e.g. `L_knee`). Map them by name, never by order in the file.
- **Dex5 hands:** the MVP also has `dex5_hands/` (Dex5-URDF-L/R, 14 MB). Not copied yet.
