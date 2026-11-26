"""Every threshold checkup uses, in one place, each with where its number came from.

Facts about the robot (joint limits, which slots are real) live in h2_bridge.robot;
this file holds judgements: how far is too far. "measured" values come from the
healthy-robot baselines in docs/robot_findings.md (2026-11-26 recordings); Will correct 
as we collect more data
"""

# ---------------------------------------------------------------- Topics (rules/topics.py)

# A topic that has sent nothing this long after the start is silent (fail).
# chosen: > 2 s of rate window, so a slow start isn't called silent.
TOPIC_STARTUP_GRACE_S = 3.0

# A topic is slow (warn) below this fraction of its expected rate.
RATE_OK = 0.8

# A topic is stale (fail) once its newest message is older than this many expected
# periods, and at least STALE_MIN_S.
STALE_PERIODS = 5
STALE_MIN_S = 0.5

# ---------------------------------------------------------------- Body joints (rules/joints.py)

# A body joint (robot/joints.py) is AT its limit (warn) once q is within this
# distance of it (rad), and PAST it (fail, being forced beyond) once q is further
# past it than this. Both 0.02 (~1.1°): the MVP's allowance for encoder noise and
# rounded limits. measured on the healthy robot: the closest any joint came to a
# limit at rest was 0.054 inside (L_wrist_roll); head_pitch rests 0.003 past its
# limit (on its stop), so it reads as AT the limit whenever the head is fully down.
JOINT_AT_LIMIT = 0.02
JOINT_PAST_LIMIT = 0.02

# A body joint whose q is bit-identical for this long while messages keep coming
# is a stuck reading (warn). measured: at most 1.14 s on a healthy robot at rest.
FROZEN_S = 5.0

# The same for the hand motors. measured: at most 0.11 s on a healthy hand at rest,
# apart from the slots below. Same window as the body for now.
HAND_FROZEN_S = 5.0

# Hand slots left out of the frozen rule, as "side:joint". measured: the right
# thumb_base_swing was bit-identical for 42-60 s in all three healthy recordings
# (docs/robot_findings.md, open question: stuck sensor, or a joint without noise?).
# Delete it from here once that's known; a stuck sensor should then be reported.
HAND_FROZEN_IGNORE = frozenset({"right:thumb_base_swing"})

# ---------------------------------------------------------------- Battery (rules/power.py)

# Cell spread, max - min of the cells (mV): warn, fail. 
CELL_SPREAD_WARN_MV = 50
CELL_SPREAD_FAIL_MV = 100

# State of charge (%): warn at or below, fail at or below. 
SOC_WARN = 20
SOC_FAIL = 10

# ---------------------------------------------------------------- IMUs (rules/imus.py)

# pelvis - torso in roll and pitch should equal minus the waist joints' roll and pitch.
# The leftover (rad): warn, fail. measured: at most 0.041 on a healthy robot. Chosen
# at ~3.5x and ~7x that, to allow for the two IMUs' messages being a few ms apart.
IMU_RESIDUAL_WARN = 0.15
IMU_RESIDUAL_FAIL = 0.30
