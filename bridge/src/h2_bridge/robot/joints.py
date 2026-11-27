"""Joint facts: which motor_state slot is which joint, and its limits.

    BODY_JOINTS       LowState_.motor_state slot -> (name, min rad, max rad)
    NUM_BODY_JOINTS   how many body slots carry data (31 of 35)
    HAND_JOINTS       HandState_.motor_state slot -> (name, min rad, max rad, position only?)

Plain data, no imports from telemetry: telemetry, checkup and server all read it.
Details and sources: docs/robot_findings.md.
"""

from math import radians

# ---------------------------------------------------------------- Body (rt/lf/lowstate)
# Row i is LowState_.motor_state[i]. LowState_ has 35 slots; only 0..30 are used.
#
# HIP_ROLL note: both hip roll limits are measured, not the spec's. Each leg was pushed
# by hand to each hard stop and held ~5 s, in damping mode
# (outputs/telemetry/2026-11-27/LR_hips_091601_eth10):
#   inner (L min, R max): L -0.5898, R +0.5905; spec 0.467441, ~0.12 rad short of the real stop.
#   outer (L max, R min): L +2.081,  R -2.076;  spec 2.1688605, ~0.09 rad past the real stop.
# The two sides mirror each other, so both use the farther of the pair (0.5905, 2.081).
BODY_JOINTS = [
    # name               min (rad)        max (rad)        slot
    ("L_hip_pitch",      -2.4525975,      2.7754225),      # 0
    ("L_hip_roll",       -0.5905,         2.081),          # 1   measured, see HIP_ROLL note
    ("L_hip_yaw",        -2.827,          2.827),          # 2
    ("L_knee",           -0.08725,        2.53025),        # 3
    ("L_ankle_roll",     -0.3490658503,   0.296705972783), # 4
    ("L_ankle_pitch",    -1.13446401358,  0.61086523808),  # 5

    ("R_hip_pitch",      -2.4525975,      2.7754225),      # 6
    ("R_hip_roll",       -2.081,          0.5905),         # 7   measured, see HIP_ROLL note
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

# Body slots driven by a parallel mechanism (two motors via rods): the ankles' roll
# and pitch, and the waist's roll and pitch. Unitree's H2 SDK docs ("Basic Services
# Interface", LowState_.mode_pr): "Parallel mechanism (Ankles and waist) Control Mode,
# 0: PR, 1: AB". In PR mode their q is the joint angle; in AB mode it's a raw motor
# position, not an angle, so limits and angle-based checks don't apply to them.
PR_LINKAGE_JOINTS = frozenset({4, 5, 10, 11, 13, 14})
MODE_PR = 0  # LowState_.mode_pr: joint angles (the default)
MODE_AB = 1  # LowState_.mode_pr: raw motor positions for PR_LINKAGE_JOINTS

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
