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
- **A hand motor at an end of its range reads a clamped, unchanging value.** The right `thumb_base_swing` was bit-identical for 42-60 s in all three recordings: it rests at -0.58676, on its spec stop (-33.5° = -0.585). Fully curled fingers (`limit_test` recording) read exactly 1.69269 (`*_mid_bend`, spec end 1.658) and 1.39608 (`*_tip_bend`, spec end 1.414). Every hand value held still for 2 s or more, in all four recordings, was within 0.035 rad of a spec range end. So it's not a stuck sensor: checkup's hand frozen rule skips a motor within 0.05 rad of a range end (`HAND_AT_STOP`).
- **The hand's `q` seems to use the spec's zero.** Full curl reads within 0.035 rad of the spec's range end on the bend joints. That's evidence (not yet proof) that `q = 0` is the spec's zero; still open for `knuckle_swing`/`knuckle_bend`, which weren't driven to their ends.
- **The two body IMUs agree in roll and pitch, not yaw.** pelvis - torso in roll and pitch equals minus the waist joints' roll and pitch (`waist_roll`, `waist_pitch`) to within 0.04 rad. Yaw differs by up to 0.48 rad while the waist yaw moves less than 0.08 rad: each IMU's yaw drifts on its own (no absolute heading), so yaw can't be compared.
- **The hand IMUs' `temperature` reads 6489-6509** (the body IMUs: 78-81). *Open:* a different unit or scale; 6500 as centi-degrees would be 65.00 °C, close to the finger motors' 39-62 °C. Not used by checkup until confirmed.
- **Battery cell spread** (max - min of the 18 cells): 11-30 mV. **`motorstate`** was 0 on every body and hand motor, and the hands' **`error`** was always `[0, 0]`. No NaN values anywhere.

## Official LowState_ field meanings (Unitree H2 SDK docs)

From Unitree's H2 SDK Development Guide, "Basic Services Interface" (last updated 2026-11-24). It covers the body only: `rt/lowstate` / `LowState_` and its `MotorState_` and `IMUState_` (`rt/lf/lowstate` is the 20 Hz copy). Hands, battery and main board aren't in it.

| Field | Meaning (docs) | Used in |
|---|---|---|
| `mode_pr` | parallel mechanism (ankles and waist) control mode: **0 PR** (default), **1 AB** | dashboard title; checkup skips the ankle/waist angles in AB |
| `mode_machine` | H2 model | dashboard title ("model") |
| `tick` | increments every 1 ms | dashboard title ("up N s") |
| `MotorState_.q`, `dq`, `ddq` | joint feedback position (rad), speed (rad/s), acceleration (rad/s²) | everywhere |
| `MotorState_.tau_est` | joint feedback torque (no unit given) | dashboard "tau N·m?" |
| `MotorState_.temperature[2]` | motor temperature: **surface and winding** | dashboard "T surface/winding" |
| `MotorState_.vol` | terminal voltage of the motor | not shown: reads 0.0 on our robot |
| `MotorState_.motorstate` | **error bits** (table below, in `robot/motors.py`) | dashboard "m/err"; checkup's motor_errors names them |
| `MotorState_.mode` | current motor mode (the command side says 0 disable, 1 enable; the state reads 1 or 10 on our robot) | dashboard, still "?" |
| `IMUState_.rpy`, `temperature` | Euler angles; IMU temperature (no unit given) | dashboard |

- **AB mode changes what `q` means.** In AB mode the parallel-linkage slots (ankle roll/pitch 4, 5, 10, 11 and waist roll/pitch 13, 14: `PR_LINKAGE_JOINTS` in `robot/joints.py`) report raw motor positions, not joint angles. Checkup's joint-limit rule skips them and its IMU-agreement rule reports no data in AB mode. All our recordings so far are in PR mode.
- **The docs' `MotorState_` has fields our SDK's message doesn't**: `q_raw`, `dq_raw`, `ddq_raw` ("reserve"). The Python SDK in use is a different version of the message; nothing reads them.
- **Motor error codes** (`motorstate` bits): 0x1 Overcurrent, 0x2 Transient Overvoltage, 0x4 Sustained Overvoltage, 0x8 Transient Undervoltage, 0x10 Chip Overheating, 0x20 MOS Overheating/Overcooling, 0x40 MOS Temperature Anomaly, 0x80 Housing Overheating/Overcooling, 0x100 Housing Temperature Anomaly, 0x200 Winding Overheating, 0x400 Rotor Encoder 1 Error, 0x800 Rotor Encoder 2 Error, 0x1000 Output Encoder Error, 0x2000 Calibration/BOOT Data Error, 0x4000 Abnormal Reset, 0x8000 Motor Lock / Master Control Authentication Error, 0x10000 Chip Verification Error, 0x20000 Calibration Mode Warning, 0x40000 Communication Check Error, 0x80000 Driver Version Too Low, 0x40000000 Disconnection timeout (motor side), 0x80000000 Disconnection timeout (PC side). The hands send the same `MotorState_` type, so the same bits most likely apply there (unconfirmed).
