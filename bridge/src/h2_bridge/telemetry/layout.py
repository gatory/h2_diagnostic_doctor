"""The one place storing robot facts.

    CORE_TOPICS    the topics telemetry subscribes to (SDK class, expected Hz)
    BODY_JOINTS    LowState_.motor_state slot -> joint name and limits
    HAND_JOINTS    HandState_.motor_state slot -> finger joint and limits
    HAND_*         hand spec: coupling, electrical, temperature, pressure pads
    NUM_*          how many slots of each array carry data

Details and sources: docs/robot_findings.md.
"""

from math import radians

from unitree_sdk2py.idl.unitree_hg.msg.dds_ import (
    BmsState_,
    HandState_,
    IMUState_,
    LowState_,
    MainBoardState_,
)

from h2_bridge.telemetry.models import TopicSpec

# ---------------------------------------------------------------- Topics
# Note uses low frequency copy for better computation optimization
_CORE = [
    TopicSpec("rt/lf/lowstate", LowState_, 20.0),  # body: 31 joints, pelvis IMU
    TopicSpec("rt/lf/secondary_imu", IMUState_, 20.0),  # torso IMU (above the waist)
    TopicSpec("rt/lf/bmsstate", BmsState_, 20.0),  # battery
    TopicSpec("rt/lf/mainboardstate", MainBoardState_, 20.0),  # main board temperatures, fans
    TopicSpec("rt/dex5/left/state", HandState_, 100.0),  # left hand: motors, pressure pads
    TopicSpec("rt/dex5/right/state", HandState_, 100.0),  # right hand: motors, pressure pads
]
CORE_TOPICS = {spec.name: spec for spec in _CORE}  # name -> TopicSpec

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
# Dex5-1P: spec sheet, details can be found in docs/robot_findings.md.
# 4 slots per finger, then the thumb. Limits are the spec's, in rad (q's zero unchecked).
HAND_JOINTS = [
    # name                    min (rad)         max (rad)        position only?   slot
    ("index_knuckle_swing",   radians(-22),     radians(22),     False),          # 0   0/1 may be swapped
    ("index_knuckle_bend",    radians(0),       radians(90),     False),          # 1
    ("index_mid_bend",        radians(0),       radians(95),     False),          # 2
    ("index_tip_bend",        radians(0),       radians(81),     False),          # 3   follows mid_bend

    ("middle_knuckle_swing",  radians(-22),     radians(22),     False),          # 4
    ("middle_knuckle_bend",   radians(0),       radians(90),     False),          # 5
    ("middle_mid_bend",       radians(0),       radians(95),     False),          # 6
    ("middle_tip_bend",       radians(0),       radians(81),     False),          # 7

    ("ring_knuckle_swing",    radians(-22),     radians(22),     False),          # 8
    ("ring_knuckle_bend",     radians(0),       radians(90),     False),          # 9
    ("ring_mid_bend",         radians(0),       radians(95),     False),          # 10
    ("ring_tip_bend",         radians(0),       radians(81),     False),          # 11

    ("pinky_knuckle_swing",   radians(-22),     radians(22),     False),          # 12
    ("pinky_knuckle_bend",    radians(0),       radians(90),     False),          # 13
    ("pinky_mid_bend",        radians(0),       radians(95),     False),          # 14
    ("pinky_tip_bend",        radians(0),       radians(81),     False),          # 15

    ("thumb_base_swing",      radians(-33.5),   radians(39),     True),           # 16
    ("thumb_base_bend",       radians(0),       radians(100),    True),           # 17
    ("thumb_mid_bend",        radians(0),       radians(110),    True),           # 18
    ("thumb_tip_bend",        radians(0),       radians(92),     True),           # 19
]

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
