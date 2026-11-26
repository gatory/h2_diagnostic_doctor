"""Rules about the IMUs: the pelvis and torso IMUs agree, given the waist joints between them."""

from h2_bridge.checkup import limits
from h2_bridge.checkup.models import Observation, Rule, Status
from h2_bridge.checkup.rules.bands import band
from h2_bridge.robot.joints import MODE_PR

# Body slots of the waist joints (robot/joints.py) and rpy indices they turn.
_WAIST = {"roll": (13, 0), "pitch": (14, 1)}  # axis -> (body slot, rpy index)


def check_imu_agreement(snap, memory):
    """pelvis - torso, in roll and pitch, should equal minus the waist joints; fail/warn on the leftover.

    Yaw isn't checked: each IMU's yaw drifts on its own (docs/robot_findings.md).
    In AB mode (mode_pr 1) the waist's q is a raw motor position, not an angle,
    so there's nothing to compare against: no data.
    """
    if not (snap.body and snap.torso_imu) or snap.body.mode_pr != MODE_PR:
        return None
    pelvis, torso = snap.body.imu.rpy, snap.torso_imu.rpy
    observations = []
    for axis, (slot, i) in _WAIST.items():
        waist = snap.body.joints[slot].q
        if waist is None or pelvis[i] is None or torso[i] is None:
            continue  # joint_nan reports a NaN joint
        residual = abs(pelvis[i] - torso[i] + waist)
        subject = f"IMU {axis}"
        status = band(memory, subject, residual, limits.IMU_RESIDUAL_WARN, limits.IMU_RESIDUAL_FAIL,
                      limits.IMU_RESIDUAL_MARGIN)
        if status == Status.PASS:
            observations.append(Observation(subject, Status.PASS, value=residual))
            continue
        limit = limits.IMU_RESIDUAL_FAIL if status == Status.FAIL else limits.IMU_RESIDUAL_WARN
        observations.append(Observation(subject, status,
                                        f"pelvis and torso disagree by {residual:.3f} rad beyond the waist joint",
                                        residual, limit))
    return observations or None


IMU_AGREEMENT = Rule(
    "imu_agreement", "Body IMUs agree",
    f"pelvis - torso in roll and pitch matches the waist joints to within {limits.IMU_RESIDUAL_WARN} rad "
    f"(fail at {limits.IMU_RESIDUAL_FAIL}).",
    check_imu_agreement, hold_s=1.0, clear_s=1.0,  # kept: the two IMUs' messages are ms apart, so one snapshot can disagree in fast motion
)
