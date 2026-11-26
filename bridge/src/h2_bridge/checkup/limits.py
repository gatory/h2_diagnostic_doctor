"""Every threshold checkup uses, in one place, each with where its number came from.

Timing: rules flag at once (no waiting, like the MVP). Values that can hover at
a threshold get a *_MARGIN instead: hysteresis, so once on, a warning stays on
until the value is that far back on the good side (rules/bands.py).

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
# Once at/past a limit, it stays so until 0.01 rad back. chosen: ~10x the encoder noise.
JOINT_LIMIT_MARGIN = 0.01

# A body joint whose q is bit-identical for this long while messages keep coming
# is a stuck reading (warn). measured: at most 1.14 s on a healthy robot at rest.
FROZEN_S = 5.0

# The same for the hand motors. measured: at most 0.11 s on a healthy hand,
# except at a range end (below). Same window as the body for now.
HAND_FROZEN_S = 5.0

# ... and only with at least this many new messages seen with the same q. Live (4
# polls/s) 5 s is 20; a fast replay (high --speed) sees only a few per 5 s, and a
# quiet joint flipping between two encoder values can then repeat by chance.
FROZEN_MIN_SAMPLES = 10

# A hand motor within this distance (rad) of either end of its spec range is at
# its stop, where its q is clamped and doesn't change: not frozen. measured
# (limit_test, 2026-11-26): fully curled fingers read exactly 1.69269 / 1.39608,
# 0.035 / 0.018 from their spec ends; the right thumb_base_swing rests at -0.58676,
# 0.002 from its end. Every hand value held still for >= 2 s was within 0.035 of one.
HAND_AT_STOP = 0.05

# ---------------------------------------------------------------- Battery (rules/power.py)

# Cell spread, max - min of the cells (mV): warn, fail. 
CELL_SPREAD_WARN_MV = 50
CELL_SPREAD_FAIL_MV = 100
CELL_SPREAD_MARGIN_MV = 10  # MVP

# State of charge (%): warn at or below, fail at or below. 
SOC_WARN = 20
SOC_FAIL = 10
SOC_MARGIN = 2  # MVP

# ---------------------------------------------------------------- IMUs (rules/imus.py)

# pelvis - torso in roll and pitch should equal minus the waist joints' roll and pitch.
# The leftover (rad): warn, fail. measured: at most 0.041 on a healthy robot. Chosen
# at ~3.5x and ~7x that, to allow for the two IMUs' messages being a few ms apart.
IMU_RESIDUAL_WARN = 0.15
IMU_RESIDUAL_FAIL = 0.30
IMU_RESIDUAL_MARGIN = 0.03  # chosen: below the warn level by about the healthy maximum (0.041)
