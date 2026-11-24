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
