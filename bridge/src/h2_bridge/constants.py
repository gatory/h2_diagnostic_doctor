"""Constants for H2 Doctor Bridge"""

from pathlib import Path

# Defaults for DDS Configuration, may override per run with --iface / --domain.
DDS_DEFAULTS = {
    "interface": "eth10",
    "domain_id": 0
}

BRIDGE_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = BRIDGE_ROOT / "outputs"