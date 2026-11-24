"""Turn a decoded SDK message into plain, JSON-safe Python data.

SDK messages are dataclasses (LowState_, MotorState_, ...) that can nest
each other and hold lists. Plain dicts and lists are what a recording can
store and what replay can give back, so both sources hand out this form.

    to_dict(LowState_(...))   # {"tick": 123, "motor_state": [{"q": 0.1, ...}, ...], ...}
"""

import dataclasses
import math


def to_dict(obj):
    """Convert a decoded message (or any part of one) into plain Python data.

    - dataclass (a message or sub-message)  -> dict of its fields, converted recursively
    - list / tuple                          -> list, items converted recursively
    - bytes                                 -> list of ints
    - NaN / infinity                        -> None (JSON has no NaN)
    - anything else (int, str, ...)         -> unchanged
    """
    if dataclasses.is_dataclass(obj):
        return {f.name: to_dict(getattr(obj, f.name)) for f in dataclasses.fields(obj)}
    if isinstance(obj, (list, tuple)):
        return [to_dict(x) for x in obj]
    if isinstance(obj, (bytes, bytearray)):
        return list(obj)
    if isinstance(obj, float) and not math.isfinite(obj):
        return None
    return obj
