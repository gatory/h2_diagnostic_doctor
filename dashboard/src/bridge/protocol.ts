// The messages the bridge's WebSocket server sends (bridge/src/h2_bridge/server/messages.py).
// Hand-written to match it: the dashboard never imports from bridge/. Only the parts the
// dashboard reads are typed in detail; the rest are left loose until something uses them.
// Every number can be null: NaN/inf from the robot arrive as null.

/** Bump together with PROTOCOL in messages.py. A message with another protocol is ignored. */
export const PROTOCOL = 1

export type Status = 'pass' | 'warn' | 'fail' | 'no data'

export type Imu = {
  rpy: (number | null)[] // rad
  gyro: (number | null)[] // rad/s
  accel: (number | null)[] // m/s²
  temperature: number // unit unconfirmed
}

export type Joint = {
  slot: number
  name: string // bridge name, e.g. "L_hip_roll" (urdfJointName() maps it onto the URDF)
  q: number | null // rad
  dq: number | null
  tau: number | null
  temperatures: number[] // meaning unconfirmed
  mode: number
  motorstate: number // error bits; 0 when healthy
  lower: number // rad, robot/joints.py
  upper: number
}

export type Body = {
  joints: Joint[] // slots 0..30 in order
  imu: Imu // pelvis
  mode_machine: number
  mode_pr: number // 0 PR, 1 AB (ankle and waist q aren't angles in AB)
  tick: number
}

export type TopicStatus = {
  name: string
  expected_hz: number | null
  hz: number | null // over the last 2 s; 0 if silent
  avg_hz: number | null
  count: number
  age_s: number | null // since the newest message; null before the first
  dropped: number | null // null on a replay
}

export type Battery = {
  soc: number // %
  soh: number // %
  volts: number | null
  current: number // probably mA, unconfirmed
  cells: number[]
  temperatures: number[]
  cycle: number
  state: number[]
  version: string
}

export type Finding = {
  rule: string // e.g. "joint_limits"
  subject: string // e.g. "L_knee", "rt/lf/bmsstate"
  status: Status
  message: string
  value: number | null
  limit: number | null
  since: number | null // the source's clock
}

export type Snapshot = {
  topics: Record<string, TopicStatus>
  body: Body | null // null before the first message
  torso_imu: Imu | null
  hands: { left: unknown; right: unknown } // not used by the dashboard yet
  battery: Battery | null
  board: unknown
  bad: string[] // topics whose newest message had an unexpected shape
}

export type SnapshotMessage = {
  type: 'snapshot'
  protocol: number
  source: 'live' | 'replay'
  t: number | null
  snapshot: Snapshot
  checkup: {
    now: Status // worst finding counting right now ("pass" if none)
    worst: Status // worst of the whole run
    running_s: number | null // how long checkup has judged, on the source's clock
    preflight_s: number // how long before its verdict counts (PREFLIGHT_S in checkup/limits.py)
    preflight: boolean // still in preflight: show progress, not a verdict
    findings: Finding[] // worst first
  }
}
