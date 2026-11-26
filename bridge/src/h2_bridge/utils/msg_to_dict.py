"""Conversions shared across the bridge.

    to_dict(sdk_message)   # -> plain JSON-safe dicts/lists/numbers
"""

import dataclasses
import math


def msg_to_dict(obj):
    """SDK message -> plain JSON-safe data (dicts, lists, numbers; NaN/inf -> None)."""
    if dataclasses.is_dataclass(obj):
        return {f.name: msg_to_dict(getattr(obj, f.name)) for f in dataclasses.fields(obj)}
    if isinstance(obj, (list, tuple)):
        return [msg_to_dict(x) for x in obj]
    if isinstance(obj, (bytes, bytearray)):
        return list(obj)
    if isinstance(obj, float) and not math.isfinite(obj):
        return None
    return obj
