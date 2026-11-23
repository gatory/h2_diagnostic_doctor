"""h2 doctor command line. Only parses arguments and wires the layers together;
the actual logic is in the h2_bridge packages."""

import sys


def main(argv=None):
    """Main entry point for the h2 doctor command line interface."""
    from h2_bridge.cli import cli

    return cli(args=argv)


if __name__ == "__main__":
    sys.exit(main())
