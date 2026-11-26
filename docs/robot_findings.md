# Robot findings

Facts about the H2 EDU learned from the bridge's own tools. Each one says where it came from, so it can be re-checked.

## Topics with more than one message type (from discovery, 2026-11-23)

Source: `bridge/outputs/discovery/2026-11-23/snapshot_155001_eth10.json` (taken on the Thor, `eth10`, domain 0, 10 s).
See it with `h2-doctor discovery show --endpoints <topic>`.

DDS only connects a writer and a reader whose message types match. On these 4 topics, the writer uses the humanoid type (`unitree_hg`), but one reader uses the quadruped type (`unitree_go`), which has a different layout. That reader most likely **receives nothing**, and DDS gives no error. It looks like leftover quadruped (Go2) code in Unitree's shared software stack. *Unconfirmed: verifying it needs a check of which readers actually matched.*

| Topic | Writer (`unitree_hg`) | Reader using `unitree_go` (mismatch) | Readers using `unitree_hg` (match) |
|---|---|---|---|
| `rt/lowstate` | `basic_service` (PC1) | `dog_control_pub` (PC2) | `humanoid`, `state_estimator_service`, `python3` (PID 2402), all PC1 |
| `rt/lf/lowstate` | `basic_service` (PC1) | `bms_ctr` (PC2) | `motion_switcher_service`, `unitreeWebRTCClientMaster`, both PC1 |
| `rt/sportmodestate` | `humanoid` (PC1) | `dog_cmd` (PC2) | `python3` (PID 2402, PC1) |
| `rt/lf/sportmodestate` | `humanoid` (PC1) | `python3` (PID 1493, PC1) | `unitreeWebRTCClientMaster` (PC1) |

PC1 = `unitree-h2` (192.168.123.161), PC2 = `unitree-H2-pc2` (192.168.123.162).

**What this means for the bridge:**
- **Telemetry must subscribe with the `unitree_hg` type** (`unitree_hg.msg.dds_.LowState_` etc.). A `unitree_go` subscriber would silently get no data, exactly like the readers above.
- **A per-endpoint type check is a good diagnostic**: any topic whose readers use a different type than its writer is a likely silent failure. Not built yet: the `--endpoints` table shows types per topic (in the title), not per endpoint.

## Dex5 hand: the spec sheet matches the recorded data (2026-11-24)

Sources: Unitree's Dex5-1 / Dex5-1P spec sheet (unitree.com) and the MVP's test T2 (curling each finger, `../h2_diagnostics/docs/field_map.md`). Encoded in `bridge/src/h2_bridge/robot/joints.py` (`HAND_JOINTS`).

- **Each finger has 4 slots but 3 degrees of freedom.** The spec lists 4 joints per finger ("Knuckles 0-3") and says knuckle 3 is *coupled* to knuckle 2. T2 saw a finger's 3rd and 4th slots move most when curling, ~1.6 and ~1.4 rad, at a steady ratio of ~0.86. The spec's ranges, 95° (1.66 rad) and 81° (1.41 rad), give 0.85. So slots 2 and 3 of each finger are knuckles 2 and 3, and slot 3 follows slot 2.
- **Still open:** which of slots 0 and 1 is the sideways swing (±22°) and which is the base bend (0-90°). Also whether `q` uses the spec's zero, so the limits can't drive warnings yet.
- **The thumb is probably a different joint type.** The spec has "12 composite transmission joints + 4 gear transmission joints". The thumb's 4 slots report position only (no temperature, mode 0), which fits it being the 4 gear joints. *Unconfirmed.*
- **Pressure: 94 sensors on 15 pads** (palm 2x5, 5 finger pads, 5 fingertips and 4 finger roots at 2x3 each). The message has 16 pad slots of 12 cells, with 6 used per pad (= 2x3) as observed. The palm's 2x5 would need 10; unchecked.
- **`power_v` is not the supply.** The spec says 24-60 V; the robot reports ~2.4 V.
- **Rates:** the hand runs at 1 kHz over USB internally; the robot republishes it at ~100 Hz on DDS.

- **Temperature:** the spec's -20-60 °C is the *ambient* range. Finger motors already read 42-66 °C at rest (MVP), and Unitree publishes no motor limit.
- **Mechanical (spec):** 1100 g; 217.3 x 127.5 x 72.1 mm flat; fingertip force 10 N; repeatability ±1 mm; smallest grip 10 mm; holds 3.5 kg palm down, 4.5 kg palm sideways (5 cm hard ball).

### Joint names in `robot/joints.py`

| Spec name | Ours | Motion |
|---|---|---|
| Knuckles 0 | `<finger>_knuckle_swing` | side to side at the knuckle (±22°) |
| Knuckles 1 | `<finger>_knuckle_bend` | curl where the finger meets the hand (0-90°) |
| Knuckles 2 | `<finger>_mid_bend` | curl at the middle joint (0-95°) |
| Knuckles 3 | `<finger>_tip_bend` | curl nearest the fingertip (0-81°), follows `mid_bend` |
| Thumb Joint 0-3 | `thumb_base_swing`, `_base_bend`, `_mid_bend`, `_tip_bend` | assumes the spec counts from the base, like the fingers (unconfirmed) |

`<finger>` is `index`, `middle`, `ring`, `pinky` (the spec's "little finger"). `knuckle_swing` and `knuckle_bend` may be swapped until tested: spread the fingers while recording and see which slot moves.

**Useful for diagnostics:** a coupled pair whose ratio drifts far from ~0.86 hints at a slipping or broken linkage (`HAND_COUPLED`, `HAND_COUPLING_RATIO`).

## Healthy-robot baselines for checkup (2026-11-26)

From the three 60 s recordings of 2026-11-26 (`outputs/telemetry/2026-11-26/`, robot standing, nothing moving on purpose). These set checkup's limits (`bridge/src/h2_bridge/checkup/limits.py`).

- **`head_pitch` rests past its limit.** It sat at q = 0.8411 for a whole recording; the limit is 0.8377 (`robot/joints.py`), so 0.003 rad past. Probably the head lying on its hard stop, with a limit that's slightly off or rounded. Checkup only counts a joint as past its limit when it's more than 0.02 rad past (the MVP's allowance for encoder noise and rounded limits).
- **Body joints never hold a bit-identical `q` for long.** At rest, the longest run of an unchanged `q` was 1.14 s (R_hip_roll); encoder noise changes the value. So a joint whose `q` doesn't change for 5 s is a real sign of a stuck reading.
- **The right hand's `thumb_base_swing` `q` never changes.** It was bit-identical for 42-60 s in all three recordings, while every other hand slot (the left thumb included) changed within 0.11 s. *Open:* is that slot stuck, or does that joint just not report noise? Checkup's hand frozen rule leaves out only that slot (`HAND_FROZEN_IGNORE` in `checkup/limits.py`) until that's known; without the exception it warns on it in every recording.
- **The two body IMUs agree in roll and pitch, not yaw.** pelvis - torso in roll and pitch equals minus the waist joints' roll and pitch (`waist_roll`, `waist_pitch`) to within 0.04 rad. Yaw differs by up to 0.48 rad while the waist yaw moves less than 0.08 rad: each IMU's yaw drifts on its own (no absolute heading), so yaw can't be compared.
- **The hand IMUs' `temperature` reads 6489-6509** (the body IMUs: 78-81). *Open:* a different unit or scale; 6500 as centi-degrees would be 65.00 °C, close to the finger motors' 39-62 °C. Not used by checkup until confirmed.
- **Battery cell spread** (max - min of the 18 cells): 11-30 mV. **`motorstate`** was 0 on every body and hand motor, and the hands' **`error`** was always `[0, 0]`. No NaN values anywhere.
