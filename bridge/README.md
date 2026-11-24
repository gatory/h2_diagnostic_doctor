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

`h2-doctor discovery topics` lists every topic seen on the network, with how many writers (publishers) and readers (subscribers) it has. A topic with readers but 0 writers means something is listening for data nobody sends.

| Option                     | Default | Meaning                                  |
| -------------------------- | ------- | ---------------------------------------- |
| `-t SECS`, `--duration SECS` | `10`    | Seconds to listen for publishers         |
| `-s [NAME]`, `--save [NAME]` |         | Also save the full snapshot (participants, endpoints, QoS) to `outputs/`, optionally named NAME (default: `snapshot`) |

```bash
uv run h2-doctor discovery topics                     # listen 10s, print a table
uv run h2-doctor discovery topics --save              # also save to outputs/discovery/<date>/
uv run h2-doctor discovery topics -t 5 --save         # listen 5s, then save
uv run h2-doctor discovery topics --save [custome_file_name]  # → outputs/discovery/<date>/custome_file_name_<time>_<iface>.json
```

`h2-doctor discovery show` reads a saved snapshot from `outputs/discovery/` and prints the same table, with a line saying when, where and how long it was taken. It needs no robot or network, so it works on your laptop after copying `outputs/` over.

```bash
uv run h2-doctor discovery show                        # newest saved snapshot
uv run h2-doctor discovery show before_walk            # newest snapshot saved as `--save before_walk`
uv run h2-doctor discovery show snapshot_155001_eth10  # one exact file (name without .json)
uv run h2-doctor discovery show --list                 # table of all saved snapshots
```

### `telemetry`: the robot's live data (scaffold)

The commands exist so you can see the shape, but each one currently prints "not implemented yet" and exits with `1`.

```bash
uv run h2-doctor telemetry watch rt/lf/lowstate   # print one topic as messages arrive
uv run h2-doctor telemetry record                 # save telemetry to outputs/telemetry/<date>/
uv run h2-doctor telemetry replay FILE            # play a recording back
```

### Saved files

Saved files go in `bridge/outputs/` (ignored by git), organized by group and date:

```
outputs/<group>/<YYYY-MM-DD>/<name>_<HHMMSS>_<interface>.json
outputs/discovery/2026-11-23/snapshot_161435_eth10.json
```

The time is when the run started. The interface in the name tells robot runs (`eth10`) apart from laptop tests. Every saved file gets its path from `h2_bridge/outputs.py`. You can choose the `<name>` part (letters, digits, `-`, `_`, `.`), but never the folder, so all results end up in this one place.

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
  discovery/        # discovery logic (no argparse): models.py = Snapshot dataclasses, collect.py = collect + group + save
  dds.py            # shared DDS setup (init_dds, make_participant)
  outputs.py        # paths for saved files (outputs/<group>/<date>/...)
  model.py          # defaults (DDS_DEFAULTS)
```

To add a group, create `cli/<group>.py` with a `register(commands)` function and call it from `build_parser()` in `cli/cli.py`.

### Planned

Not built yet: the logic behind `telemetry watch|record|replay`, `discovery snapshot`, `serve`, and `--json` output.
