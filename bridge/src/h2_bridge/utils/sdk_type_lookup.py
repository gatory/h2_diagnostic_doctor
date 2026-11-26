"""DDS type name -> SDK message class.

    lookup_type("unitree_hg::msg::dds_::LowState_")   # -> LowState_, or None

Accepts discovery's "::" form and the SDK's "." form.
"""

import importlib


def lookup_type(type_name):
    """SDK class for a DDS type name, or None if this SDK doesn't define it."""
    dotted = type_name.replace("::", ".")
    module_name, _, class_name = dotted.rpartition(".")
    if not module_name:
        return None
    try:
        cls = getattr(importlib.import_module(f"unitree_sdk2py.idl.{module_name}"), class_name)
    except (ImportError, AttributeError):
        return None
    # Only a real message class for exactly this type (not a submodule or another name).
    return cls if getattr(cls, "__idl_typename__", None) == dotted else None
