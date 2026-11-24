"""The one place storing robot facts.

    CORE_TOPICS    the topics telemetry subscribes to (SDK class, expected Hz)
    BODY_JOINTS    LowState_.motor_state slot -> joint name and limits
    HAND_JOINTS    HandState_.motor_state slot -> finger joint
    HAND_*, BMS_*, MAINBOARD_*   how many slots of each array carry data
"""

from unitree_sdk2py.idl.unitree_hg.msg.dds_ import (
    BmsState_,
    HandState_,
    IMUState_,
    LowState_,
    MainBoardState_,
)

from h2_bridge.telemetry.models import TopicSpec

# ---------------------------------------------------------------- Topics
# The `rt/lf/...` ("low frequency") copies, not `rt/lowstate` (~1 kHz): same
# data, a fiftieth of the load. ~280 messages/s in total. Rates measured on the Thor.
# Left out on purpose: rt/lowstate and rt/lowcmd (~1 kHz, too much for Python
# alongside the rest), rt/lf/sportmodestate (the SDK has no unitree_hg class for it),
# quadruped leftovers (rt/dog_*, unitree_go types), services (rt/api/*).
CORE_TOPICS = {
    "rt/lf/lowstate": TopicSpec(LowState_, 20.0, "body: 31 joints, pelvis IMU"),
    "rt/lf/secondary_imu": TopicSpec(IMUState_, 20.0, "torso IMU (above the waist)"),
    "rt/lf/bmsstate": TopicSpec(BmsState_, 20.0, "battery"),
    "rt/lf/mainboardstate": TopicSpec(MainBoardState_, 20.0, "main board temperatures, fans"),
    "rt/dex5/left/state": TopicSpec(HandState_, 100.0, "left hand: motors, pressure pads"),
    "rt/dex5/right/state": TopicSpec(HandState_, 100.0, "right hand: motors, pressure pads"),
}

# ---------------------------------------------------------------- Body (rt/lf/lowstate)
# Row i is LowState_.motor_state[i]. LowState_ has 35 slots; only 0..30 are used.
BODY_JOINTS = [
    # name               min (rad)        max (rad)        slot
    ("L_hip_pitch",      -2.4525975,      2.7754225),      # 0
    ("L_hip_roll",       -0.467441,       2.1688605),      # 1
    ("L_hip_yaw",        -2.827,          2.827),          # 2
    ("L_knee",           -0.08725,        2.53025),        # 3
    ("L_ankle_roll",     -0.3490658503,   0.296705972783), # 4
    ("L_ankle_pitch",    -1.13446401358,  0.61086523808),  # 5

    ("R_hip_pitch",      -2.4525975,      2.7754225),      # 6
    ("R_hip_roll",       -2.1688605,      0.467441),       # 7
    ("R_hip_yaw",        -2.827,          2.827),          # 8
    ("R_knee",           -0.08725,        2.53025),        # 9
    ("R_ankle_roll",     -0.296705972783, 0.3490658503),   # 10
    ("R_ankle_pitch",    -1.13446401358,  0.61086523808),  # 11

    ("waist_yaw",        -1.7453,         1.7453),         # 12
    ("waist_roll",       -0.5236,         0.5236),         # 13
    ("waist_pitch",      -0.43633,        0.5236),         # 14

    ("L_shoulder_pitch", -2.6179939,      1.8325957),      # 15
    ("L_shoulder_roll",  -0.517,          2.494),          # 16
    ("L_shoulder_yaw",   -2.6179939,      2.6179939),      # 17
    ("L_elbow",          -0.986111,       3.0717795),      # 18
    ("L_wrist_roll",     -2.6179939,      2.6179939),      # 19
    ("L_wrist_pitch",    -0.576,          0.576),          # 20
    ("L_wrist_yaw",      -1.2217305,      1.2217305),      # 21

    ("R_shoulder_pitch", -2.6179939,      1.8325957),      # 22
    ("R_shoulder_roll",  -2.494,          0.517),          # 23
    ("R_shoulder_yaw",   -2.6179939,      2.6179939),      # 24
    ("R_elbow",          -0.986111,       3.0717795),      # 25
    ("R_wrist_roll",     -2.6179939,      2.6179939),      # 26
    ("R_wrist_pitch",    -0.576,          0.576),          # 27
    ("R_wrist_yaw",      -1.2217305,      1.2217305),      # 28

    ("head_pitch",       -0.5236,         0.83775),        # 29
    ("head_yaw",         -1.7453,         1.7453),         # 30
]
NUM_BODY_JOINTS = len(BODY_JOINTS)  # 31

# TODO: not sure about this will need to look into it further
# PR_LINKAGE_JOINTS = frozenset({4, 5, 10, 11, 13, 14})

# ---------------------------------------------------------------- Hands (rt/dex5/*/state)
# Row i is HandState_.motor_state[i] (20 slots), same order on both hands (T2).
# Four slots per finger. Within a finger, which slot is the base bend and which
# is the sideways spread isn't known yet, so they're numbered 1-4, not named.
# The thumb (16..19) reports position (q) only: no temperature, mode 0.
HAND_JOINTS = [
    # name        position only?   slot
    ("index_1",   False),          # 0
    ("index_2",   False),          # 1
    ("index_3",   False),          # 2
    ("index_4",   False),          # 3

    ("middle_1",  False),          # 4
    ("middle_2",  False),          # 5
    ("middle_3",  False),          # 6
    ("middle_4",  False),          # 7

    ("ring_1",    False),          # 8
    ("ring_2",    False),          # 9
    ("ring_3",    False),          # 10
    ("ring_4",    False),          # 11

    ("pinky_1",   False),          # 12
    ("pinky_2",   False),          # 13
    ("pinky_3",   False),          # 14
    ("pinky_4",   False),          # 15

    ("thumb_1",   True),           # 16  (right thumb not yet confirmed)
    ("thumb_2",   True),           # 17
    ("thumb_3",   True),           # 18
    ("thumb_4",   True),           # 19
]
NUM_HAND_JOINTS = len(HAND_JOINTS)  # 20
NUM_HAND_ACTIVE_MOTORS = sum(1 for _, position_only in HAND_JOINTS if not position_only)  # 16: report temperature

# HandState_.press_sensor_state: 16 pads, each with 12 cells, of which only the
# first 6 carry data. Raw values, noisy around 0, units unknown. Which pad sits
# where on the hand isn't known yet (test T5), so pads stay numbered.
NUM_HAND_PADS = 16
NUM_HAND_PAD_CELLS = 6  # used cells per pad (of 12)

# ---------------------------------------------------------------- Battery (rt/lf/bmsstate)
# cell_vol[0..17] are the 18 cells in mV (they sum to bmsvoltage[0]); [18..39] unused.
NUM_BMS_CELLS = 18

# ---------------------------------------------------------------- Main board (rt/lf/mainboardstate)
# temperature[0..3] are °C (probably); which board parts they are is unknown. [4..5] unused.
NUM_MAINBOARD_TEMPS = 4

# ---------------------------------------------------------------- IMUs
# Two IMUs (T1): the main one in the PELVIS rides inside LowState_.imu_state
# (rt/lf/lowstate); the second, in the TORSO above the waist, is rt/lf/secondary_imu.
# Their difference is the waist's rotation.
