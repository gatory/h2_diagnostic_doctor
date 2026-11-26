""" Root parser for 'h2-doctor' cli tool

Example Usage:

    h2-doctor [--iface IFACE] [--domain N] <group> <command> ...

Global options live here. Each command group registers itself from its
own module.
"""

import argparse
import sys

from h2_bridge import __version__
from h2_bridge.cli import discovery_commands, telemetry_commands
from h2_bridge.constants import DDS_DEFAULTS
from h2_bridge.dds_setup import DDSError


def build_parser():
    """Build the argparse command tree."""
    parser = argparse.ArgumentParser(prog="h2-doctor", description="H2 Diagnostic Doctor bridge")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    # Global options: shared by every command, given before the group name.
    # dest= keeps the flags short to type but stores them under the
    # DDS_DEFAULTS key names, so handlers read args.interface / args.domain_id.
    parser.add_argument(
        "--iface", dest="interface", default=DDS_DEFAULTS["interface"],
        help="Network interface for DDS (default: %(default)s)",
    )
    parser.add_argument(
        "--domain", dest="domain_id", type=int, default=DDS_DEFAULTS["domain_id"],
        help="DDS domain ID (default: %(default)s)",
    )

    commands = parser.add_subparsers(dest="command", metavar="<group>", required=True)
    discovery_commands.register(commands)
    telemetry_commands.register(commands)

    return parser


def cli(args=None):
    """Parse `args` (defaults to sys.argv[1:]) and run the selected command."""
    parser = build_parser()
    ns = parser.parse_args(args)
    try:
        return ns.func(ns)
    except KeyboardInterrupt:
        return 130  # shell convention for "stopped by Ctrl-C"
    except DDSError as e:
        # Expected failure (bad interface, etc.): one clear line, not a traceback.
        print(f"h2-doctor: error: {e}", file=sys.stderr)
        return 1
