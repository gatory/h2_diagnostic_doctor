"""Main entry point for the h2 doctor command line interface.

Example Usage:
    $ h2-doctor --iface eth10 --domain 0 discovery list
    
"""

import sys


def main(argv=None):
    from h2_bridge.cli import cli

    return cli(args=argv)


if __name__ == "__main__":
    sys.exit(main())
