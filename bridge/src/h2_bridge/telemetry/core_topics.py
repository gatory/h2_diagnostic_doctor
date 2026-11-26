"""CORE_TOPICS: the topics telemetry subscribes to by default (name -> TopicSpec).

Each has its SDK class and the rate measured on the Thor, so `watch` can compare
against it. Facts about the robot itself (joints, sensors) live in h2_bridge.robot.
"""

from unitree_sdk2py.idl.unitree_hg.msg.dds_ import (
    BmsState_,
    HandState_,
    IMUState_,
    LowState_,
    MainBoardState_,
)

from h2_bridge.telemetry.models import TopicSpec

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
