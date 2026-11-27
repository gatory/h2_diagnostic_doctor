// Bridge joint names -> URDF joint names. A naming rule, not a slot table: the dashboard never
// needs slot numbers (those live only in bridge/.../robot/joints.py).

/** "L_hip_roll" -> "left_hip_roll_joint", "waist_yaw" -> "waist_yaw_joint". */
export function urdfJointName(bridgeName: string): string {
  return bridgeName.replace(/^L_/, 'left_').replace(/^R_/, 'right_') + '_joint'
}
