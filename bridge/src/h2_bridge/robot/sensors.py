"""Sensor facts: how many slots of each array carry data, and what they are.

    NUM_BMS_CELLS         battery cells in BmsState_.cell_vol
    NUM_MAINBOARD_TEMPS   temperatures in MainBoardState_.temperature

Plain data, no imports from telemetry. Details: docs/robot_findings.md.
"""

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
