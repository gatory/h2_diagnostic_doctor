"""Constants for H2 Doctor Bridge"""

from pathlib import Path

# Defaults for DDS Configuration, may override per run with --iface / --domain.
DDS_DEFAULTS = {
    "interface": "eth10",
    "domain_id": 0
}

# Defaults for `h2-doctor server`. 0.0.0.0: every interface, since the dashboard runs on another machine.
SERVER_DEFAULTS = {
    "host": "0.0.0.0",
    "port": 8765,
    "rate_hz": 30.0,
}

BRIDGE_ROOT =Path(__file__).resolve().parents[2]
OUTPUT_DIR = BRIDGE_ROOT / "outputs"
CACHE_DIR = BRIDGE_ROOT / "cache"  # the program's own state (vs. results in OUTPUT_DIR)
