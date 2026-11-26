"""The remote controller: decoding LowState_.wireless_remote (40 raw bytes).

    remote = decode_remote(lowstate["wireless_remote"])
    remote.connected        # True once the controller sends (first bytes 0x55 0x51)
    remote.buttons          # ("L2", "B") while L2 + B are held
    remote.ly               # left stick y, -1.0 .. 1.0

Source: Unitree's H2 SDK docs, "Remote Control Data" (last updated 2026-05-29):
xRockerBtnDataStruct, read from rt/lowstate's 40-byte wireless_remote. Checked
against our 2026-11-26 recordings: see docs/robot_findings.md.

Layout (little-endian):
    bytes 0-1    head: 0x55 0x51 while a controller is connected; all zeros otherwise (observed)
    bytes 2-3    buttons, uint16: one bit each, in BUTTONS order (bit 0 = R1 ... bit 15 = left)
    bytes 4-23   five float32: lx, rx, ry, L2, ly (that order, as in the docs), -1.0 .. 1.0
    bytes 24-39  "idle" in the docs, but bytes 38-39 aren't always 0 (meaning unknown)

Plain data, no telemetry imports.
"""

import struct
from dataclasses import dataclass

# Bit i of the uint16 button field (xKeySwitchUnion), in the docs' order.
BUTTONS = ("R1", "L1", "start", "select", "R2", "L2", "F1", "F2",
           "A", "B", "X", "Y", "up", "right", "down", "left")

_HEAD = b"\x55\x51"


@dataclass(frozen=True)
class Remote:
    connected: bool  # head bytes are 0x55 0x51
    buttons: tuple  # names of the buttons held, in BUTTONS order
    lx: float  # left stick x
    rx: float  # right stick x
    ry: float  # right stick y
    l2: float  # L2 as an axis (reads 0.0 on our robot even with L2 held: the L2 button bit is set)
    ly: float  # left stick y


def decode_remote(raw):
    """40 bytes (a list of ints, as msg_to_dict gives them) -> Remote. ValueError if not 40 bytes."""
    data = bytes(raw)
    if len(data) != 40:
        raise ValueError(f"wireless_remote has {len(data)} bytes, expected 40")
    (bits,) = struct.unpack_from("<H", data, 2)
    lx, rx, ry, l2, ly = struct.unpack_from("<5f", data, 4)
    held = tuple(name for i, name in enumerate(BUTTONS) if bits >> i & 1)
    return Remote(data[:2] == _HEAD, held, lx, rx, ry, l2, ly)
