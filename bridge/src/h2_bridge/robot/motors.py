"""Motor facts: what the bits of MotorState_.motorstate mean.

    decode_motorstate(0x204)   # ["Sustained Overvoltage", "Winding Overheating"]

Source: Unitree's H2 SDK docs, "Basic Services Interface" (last updated
2026-11-24), "Motor Error Codes". They describe the body's MotorState_
(rt/lowstate, LowState_.motor_state). The Dex5 hands send the same MotorState_
type, so the same bits most likely apply there; unconfirmed.

Plain data: telemetry, checkup and the dashboard read it.
"""

# bit -> description, as in the docs (0 means no error).
MOTOR_ERROR_BITS = {
    0x00001: "Overcurrent",
    0x00002: "Transient Overvoltage",
    0x00004: "Sustained Overvoltage",
    0x00008: "Transient Undervoltage",
    0x00010: "Chip Overheating",
    0x00020: "MOS Overheating/Overcooling",
    0x00040: "MOS Temperature Anomaly",
    0x00080: "Housing Overheating/Overcooling",
    0x00100: "Housing Temperature Anomaly",
    0x00200: "Winding Overheating",
    0x00400: "Rotor Encoder 1 Error",
    0x00800: "Rotor Encoder 2 Error",
    0x01000: "Output Encoder Error",
    0x02000: "Calibration/BOOT Data Error",
    0x04000: "Abnormal Reset",
    0x08000: "Motor Lock, Master Control Authentication Error",
    0x10000: "Chip Verification Error",
    0x20000: "Calibration Mode Warning",
    0x40000: "Communication Check Error",
    0x80000: "Driver Version Too Low",
    0x40000000: "Disconnection timeout (motor side)",
    0x80000000: "Disconnection timeout (PC side)",
}


def decode_motorstate(value):
    """The descriptions of every bit set in `value`, lowest bit first; unknown bits as hex."""
    names = [name for bit, name in MOTOR_ERROR_BITS.items() if value & bit]
    unknown = value & ~sum(MOTOR_ERROR_BITS)
    if unknown:
        names.append(f"unknown bits 0x{unknown:X}")
    return names
