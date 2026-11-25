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

Defaults live in `DDS_DEFAULTS` in `src/h2_bridge/constants.py`. Edit that file to change them permanently.

### `discovery`: what's on the DDS network

`h2-doctor discovery topics` lists every topic seen on the network, with how many writers (publishers) and readers (subscribers) it has. A topic with readers but 0 writers means something is listening for data nobody sends.

**A snapshot lists what existed during the run, not what is alive at the end.** A program that leaves partway through (exits, crashes or restarts) stays listed with what it announced. DDS's "gone" notices are ignored on purpose: whether data is still flowing is telemetry's job. Two consequences:

- DDS only notices a program died without saying goodbye once its *lease* runs out (10 s in our tests), so even live tools see departures late.
- A program that restarts during a run can show up twice: same name, two PIDs and two Participant IDs.

| Option                     | Default | Meaning                                  |
| -------------------------- | ------- | ---------------------------------------- |
| `-t SECS`, `--duration SECS` | `10`    | Seconds to listen (longer catches programs that announce slowly) |
| `-s [NAME]`, `--save [NAME]` |         | Also save the full snapshot (participants, endpoints, QoS) to `outputs/`, optionally named NAME (default: `snapshot`) |

```bash
uv run h2-doctor discovery topics                     # listen 10s, print a table
uv run h2-doctor discovery topics --save              # also save to outputs/discovery/<date>/
uv run h2-doctor discovery topics -t 5 --save         # listen 5s, then save
uv run h2-doctor discovery topics --save before_walk  # → outputs/discovery/<date>/before_walk_<time>_<iface>.json
```

`h2-doctor discovery show` reads a snapshot saved with `--save` from `outputs/discovery/` and prints it, starting with a line saying when, where and how long it was taken. It needs no robot or network, so it works on your laptop after copying `outputs/` over (e.g. with `rsync` or `scp` from the Thor).

**Which snapshot:** give no name for the newest, a saved name (`before_walk`) for the newest with that name, or a full file name without `.json` (`snapshot_155001_eth10`) for one exact file.

**Which view:** each view is named after what one row is. Pick one at a time:

| Option | One row per | Columns |
| ------ | ----------- | ------- |
| *(none)* | topic | Topic, Message Type, Writers, Readers (the summary) |
| `-p`, `--participants` | participant (one DDS connection a program opened) | Participants (ID), Process, PID, Host, IP, Writers, Readers |
| `-e TOPIC`, `--endpoints TOPIC` | endpoint (writer or reader) of that topic | Kind, Participants (ID), Process, PID, Host, IP, Reliability, Durability, Type info |
| `-l`, `--list` | saved snapshot file, newest first | Date, Time, Name, Interface, File |

`--participants` and `--endpoints` share the same owner columns (Participants … IP), so a row in one can be matched to the other by its ID. A misspelled `--endpoints` topic suggests close matches.

```bash
uv run h2-doctor discovery show                        # newest snapshot, per-topic summary
uv run h2-doctor discovery show before_walk            # newest snapshot saved as `--save before_walk`
uv run h2-doctor discovery show snapshot_155001_eth10  # one exact file
uv run h2-doctor discovery show --participants         # who is on the network
uv run h2-doctor discovery show --endpoints rt/lowcmd  # who writes and reads rt/lowcmd
uv run h2-doctor discovery show --list                 # every saved snapshot
```

`uv run h2-doctor discovery show -h` prints the same views and examples.

### `telemetry`: the robot's live data

`watch` is built; `record` and `replay` still print "not implemented yet" and exit with `1`.

```bash
uv run h2-doctor telemetry watch                  # live overview, redrawn ~4x a second, until Ctrl-C
uv run h2-doctor telemetry watch rt/lf/lowstate   # every value of one topic, live
uv run h2-doctor telemetry watch -t 30            # stop after 30 s
```

`watch` subscribes (read-only) to a fixed list of topics, `CORE_TOPICS` in `src/h2_bridge/telemetry/layout.py`, and shows one of two views.

**Overview** (no topic given): one row per topic.

| Column | Meaning |
|---|---|
| Hz | measured rate / expected rate. Green: at least 80% of expected. Yellow: slow. Red: silent. |
| Last | seconds since the topic's newest message |
| Summary | a few key fields of the newest message. A `?` marks a unit that is likely but unconfirmed (see the MVP's `docs/field_map.md`). |

**One topic** (`watch TOPIC`): subscribes to that topic only and shows every value of its newest message, the raw data with no interpretation:
- a status line: type, measured / expected Hz, time since the last message, dropped count;
- a **Field | Value** list of plain fields; nested ones are flattened with dots (`imu_state.rpy`);
- a table per list of sub-messages, one row per slot (`motor_state`, `press_sensor_state`). Joint and finger slots are named from `layout.py`; slots past the named ones show `(unused)`.

It works for any message type without knowing it. `rt/lf/lowstate` and the hands are about 55 lines tall, so make the terminal tall enough; otherwise the bottom is cut off. `TOPIC` must be one of the 6 core topics (a typo gets "Did you mean").

The 6 topics, about 280 messages/s in total, are what the dashboard draws: `rt/lf/lowstate` (body, 20 Hz), `rt/lf/secondary_imu` (torso IMU), `rt/lf/bmsstate` (battery), `rt/lf/mainboardstate` (board temperatures, fans), `rt/dex5/left/state` and `rt/dex5/right/state` (hands, 100 Hz).

**Why only these topics.** Every message costs Python time to decode, even on a background thread. Subscribing to everything, including the ~1 kHz `rt/lowstate` and `rt/lowcmd`, overloads Python and makes the rates read low (the MVP saw `rt/lf/*` at 10 Hz instead of 20). So `watch` uses the 20 Hz `rt/lf/...` copies and leaves the fast topics out. The caption shows how many messages were **dropped**; if that isn't 0, the display fell behind and its numbers can't be trusted.

**How the data flows.** A *source* hands out every message; each consumer keeps what it needs. `watch` counts every message for the rates and keeps only the newest per topic for the screen. A future recorder will keep all of them. The source is the robot today (`LiveSource`); a `ReplaySource` that reads recordings will plug into the same place.

### Saved files

Saved files go in `bridge/outputs/` (ignored by git), organized by group and date:

```
outputs/<group>/<YYYY-MM-DD>/<name>_<HHMMSS>_<interface>.json
outputs/discovery/2026-11-23/snapshot_161435_eth10.json
```

The time is when the run started. The interface in the name tells robot runs (`eth10`) apart from laptop tests. Every saved file gets its path from `h2_bridge/utils/outputs.py`. You can choose the `<name>` part (letters, digits, `-`, `_`, `.`), but never the folder, so all results end up in this one place.

### Output and exit codes

- Results (tables) go to **stdout**. Spinners and messages go to **stderr**, so `> file` or `| less` only captures the results.
- Exit codes: `0` success, `1` ran but found nothing (e.g. `watch` received no data), `2` bad arguments, `130` stopped with Ctrl-C.
- `telemetry watch` redraws a live table in a terminal. Piped or redirected, it prints only the final table.

### Code layout

The CLI only parses arguments and prints. The logic lives in the matching package:

```
src/h2_bridge/
  cli/cli.py        # root parser + global options; registers each group
  cli/discovery.py  # `discovery` commands  ->  calls h2_bridge.discovery
  cli/discovery_tables.py  # rich tables those commands print (one per kind of row)
  cli/telemetry.py  # `telemetry` commands  ->  calls h2_bridge.telemetry
  cli/telemetry_tables.py  # rich tables those commands print
  discovery/        # discovery logic (no argparse):
                    #   models.py   = Snapshot dataclasses (the raw facts)
                    #   collect.py  = DDS -> Snapshot (the only discovery module that touches DDS)
                    #   analysis.py = Snapshot -> views (group_by_topic, endpoints_by_participant, participant_ips)
                    #   persistence.py = Snapshot <-> JSON in outputs/ (save_snapshot, load_snapshot)
  telemetry/        # telemetry logic (no argparse):
                    #   models.py   = TopicSpec (a topic we read) and Message (one received message)
                    #   layout.py   = robot facts: CORE_TOPICS (SDK class, expected Hz), joint/finger slots, array sizes
                    #   sources/base.py = Source (the shared interface) and latest()
                    #   sources/live.py = LiveSource: the robot over DDS (the only telemetry module that touches DDS)
                    #   rates.py    = RateMeter: Hz per topic from message arrival times
                    #   summary.py  = one-line summary per message type, for watch
  dds.py            # shared DDS setup (init_dds, make_participant)
  utils/            # small shared helpers (no DDS, no argparse):
                    #   convert.py = SDK message -> plain dict (msg_to_dict)
                    #   outputs.py = paths for saved files (outputs/<group>/<date>/...)
  constants.py      # defaults (DDS_DEFAULTS) and paths (BRIDGE_ROOT, OUTPUT_DIR)
```

To add a group, create `cli/<group>.py` with a `register(commands)` function and call it from `build_parser()` in `cli/cli.py`.

### Planned

Not built yet: `telemetry record|replay` (and `--replay FILE` for `watch`), `serve` for the dashboard, `check` (a health sweep of every topic), and `--json` output.
