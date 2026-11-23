# h2-doctor: the bridge (runs on the Thor)

- Network Interface: eth10
- Domain: 0

Topics I need to subscribe to to read the data:


- LowState_             (unitree_hg::msg::dds_::LowState_)
    - MotorState_       (unitree_hg::msg::dds_::MotorState_)
    - IMUState_         (unitree_hg::msg::dds_::IMUState)
- BmsState_             (unitree_hg::msg::dds_::BmsState_)
- HandState_            (unitree_hg::msg::dds_::HandState_)
- MainBoardState_       (unitree_hg::msg::dds_::MainBoardState_)
- PressSensorState_     (unitree_hg::msg::dds_::PressSensorState_)

## CLI

The bridge is run through one command, `h2-doctor`, from the `bridge/` directory:

```bash
uv run h2-doctor --help
```

Commands are grouped: `h2-doctor [global options] <group> <command> [options]`.

### Global options

These go **before** the group name, e.g. `h2-doctor --iface eth0 discovery topics`.

| Option          | Default | Meaning                    |
| --------------- | ------- | -------------------------- |
| `--iface IFACE` | `eth10` | Network interface for DDS  |
| `--domain N`    | `0`     | DDS domain ID              |
| `--version`     |         | Print the version and exit |

Defaults live in `DDS_DEFAULTS` in `src/h2_bridge/model.py`. Edit that file to change them permanently.

### `discovery`: what's on the DDS network

`h2-doctor discovery topics` lists every topic that has an active publisher.

| Option                     | Default | Meaning                                  |
| -------------------------- | ------- | ---------------------------------------- |
| `-t SECS`, `--duration SECS` | `10`    | Seconds to listen for publishers         |
| `-o FILE`, `--output FILE`   |         | Also save the topics to this JSON file   |

```bash
uv run h2-doctor discovery topics                     # listen 10s, print a table
uv run h2-doctor discovery topics -t 5 -o topics.json # listen 5s, also save JSON
```

### `telemetry`: the robot's live data (scaffold)

The commands exist so you can see the shape, but each one currently prints "not implemented yet" and exits with `1`.

```bash
uv run h2-doctor telemetry watch rt/lf/lowstate   # print one topic as messages arrive
uv run h2-doctor telemetry record -o FILE         # save telemetry to a file
uv run h2-doctor telemetry replay FILE            # play a recording back
```

### Output and exit codes

- Results (tables) go to **stdout**. Spinners and messages go to **stderr**, so `> file` or `| less` only captures the results.
- Exit codes: `0` success, `1` ran but found nothing, `2` bad arguments, `130` stopped with Ctrl-C.

### Code layout

The CLI only parses arguments and prints. The logic lives in the matching package:

```
src/h2_bridge/
  cli/cli.py        # root parser + global options; registers each group
  cli/discovery.py  # `discovery` commands  ->  calls h2_bridge.discovery
  cli/telemetry.py  # `telemetry` commands (scaffold, will call h2_bridge.telemetry)
  discovery/        # discovery logic (no argparse)
  model.py          # defaults (DDS_DEFAULTS)
```

To add a group, create `cli/<group>.py` with a `register(commands)` function and call it from `build_parser()` in `cli/cli.py`.

### Planned

Not built yet: the logic behind `telemetry watch|record|replay`, `discovery snapshot`, `serve`, and `--json` output.
