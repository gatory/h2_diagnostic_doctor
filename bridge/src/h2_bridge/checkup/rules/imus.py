"""Rules about the IMUs: the pelvis and torso IMUs agree, given the waist joints between them."""

from h2_bridge.checkup import limits
from h2_bridge.checkup.models import Observation, Rule, Status

# Body slots of the waist joints (robot/joints.py) and rpy indices they turn.
_WAIST = {"roll": (13, 0), "pitch": (14, 1)}  # axis -> (body slot, rpy index)


def check_imu_agreement(snap, memory):
    """pelvis - torso, in roll and pitch, should equal minus the waist joints; fail/warn on the leftover.

    Yaw isn't checked: each IMU's yaw drifts on its own (docs/robot_findings.md).
    """
    if not (snap.body and snap.torso_imu):
        return None
    pelvis, torso = snap.body.imu.rpy, snap.torso_imu.rpy
    observations = []
    for axis, (slot, i) in _WAIST.items():
        waist = snap.body.joints[slot].q
        if waist is None or pelvis[i] is None or torso[i] is None:
            continue  # joint_nan reports a NaN joint
        residual = abs(pelvis[i] - torso[i] + waist)
        subject = f"IMU {axis}"
        if residual > limits.IMU_RESIDUAL_FAIL:
            status, limit = Status.FAIL, limits.IMU_RESIDUAL_FAIL
        elif residual > limits.IMU_RESIDUAL_WARN:
            status, limit = Status.WARN, limits.IMU_RESIDUAL_WARN
        else:
            observations.append(Observation(subject, Status.PASS, value=residual))
            continue
        observations.append(Observation(subject, status,
                                        f"pelvis and torso disagree by {residual:.3f} rad beyond the waist joint",
                                        residual, limit))
    return observations or None


IMU_AGREEMENT = Rule(
    "imu_agreement", "Body IMUs agree",
    f"pelvis - torso in roll and pitch matches the waist joints to within {limits.IMU_RESIDUAL_WARN} rad "
    f"(fail at {limits.IMU_RESIDUAL_FAIL}).",
    check_imu_agreement, hold_s=1.0, clear_s=2.0,
)
