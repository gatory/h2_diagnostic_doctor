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

```bash
uv run h2-doctor telemetry watch                             # live overview of the core topics until Ctrl-C
uv run h2-doctor telemetry watch rt/lf/lowstate              # every value of one topic, live
uv run h2-doctor telemetry watch --record first_try -t 30    # also record 30 s, as first_try_<time>_<iface>.jsonl.gz
uv run h2-doctor telemetry watch -q --record                 # record without the table (long runs)
uv run h2-doctor telemetry watch rt/odommodestate            # any topic: looked up in the cache, else by discovery (~2 s)
uv run h2-doctor telemetry replay FILE                       # play a recording back in the same table (no robot needed)
uv run h2-doctor telemetry replay FILE rt/lf/bmsstate -s 4   # one recorded topic, 4x faster
```

`watch` subscribes (read-only) to the core topics, `CORE_TOPICS` in `src/h2_bridge/telemetry/core_topics.py`, or to the `TOPIC`s given. A name that isn't core is looked up in the **topic cache** (`bridge/cache/topics.json`, filled by every `discovery topics` run), and only if it isn't cached either, by a 2 s discovery run (which also fills the cache). Put `TOPIC`s before `--record`, or `--record` reads the first one as its name. Ctrl-C stops cleanly (it never cuts a line in half); a second Ctrl-C stops at once. At the end it prints the messages received (and dropped) per topic and where the recording went.

**Recordings** are gzipped JSON Lines (`.jsonl.gz`, about 10x smaller than plain: ~300 MB/hour for the core topics) in `outputs/telemetry/<date>/`:
- a header line: start time, host, interface, domain, and each topic's DDS type and expected Hz;
- one line per message: `t` (arrival time), `topic`, `data`;
- a footer line when the recording closes: end time, duration, message count, and `dropped` per topic. **No footer** means the recorder died (power loss, `kill -9`).

Only the watched topics are recorded. The file is flushed about 4 times a second, so a crash loses at most the last ~0.25 s, and a recording is never overwritten. Read one with `zcat FILE | head`. `replay` also reads older plain `.jsonl` recordings.

**`replay`** plays a recording at its recorded pace (`-s/--speed` to change it) in the same table as `watch`. Rates and ages run on the recording's clock, so they match the live run at any speed; the clock stops at the last message. At the end it says whether the recording closed cleanly (footer) or was cut off.

**The live table.** Two views:

*Overview* (no topic given): one row per topic.

| Column | Meaning |
|---|---|
| Hz | measured rate / expected rate. Green: at least 80% of expected. Yellow: slow. Red: silent, or stale (newest message older than 5 periods, at least 0.5 s). |
| Last | seconds since the topic's newest message (red when stale) |
| Summary | a few key fields of the newest message. A `?` marks a unit that is likely but unconfirmed (see the MVP's `docs/field_map.md`). |

*One topic* (`watch TOPIC`): subscribes to that topic only and shows every value of its newest message, the raw data with no interpretation:
- a status line: type, measured / expected Hz, time since the last message, dropped count (live only);
- a **Field | Value** list of plain fields; nested ones are flattened with dots (`imu_state.rpy`);
- a table per list of sub-messages, one row per slot (`motor_state`, `press_sensor_state`). Joint and finger slots are named from `robot/joints.py`; slots past the named ones show `(unused)`.

It works for any message type without knowing it. `rt/lf/lowstate` and the hands are about 55 lines tall, so make the terminal tall enough; otherwise the bottom is cut off.

The 6 topics, about 280 messages/s in total, are what the dashboard draws: `rt/lf/lowstate` (body, 20 Hz), `rt/lf/secondary_imu` (torso IMU), `rt/lf/bmsstate` (battery), `rt/lf/mainboardstate` (board temperatures, fans), `rt/dex5/left/state` and `rt/dex5/right/state` (hands, 100 Hz).

**Why only these topics.** Every message costs Python time to decode, even on a background thread. Subscribing to everything, including the ~1 kHz `rt/lowstate` and `rt/lowcmd`, overloads Python and makes the rates read low (the MVP saw `rt/lf/*` at 10 Hz instead of 20). So `watch` uses the 20 Hz `rt/lf/...` copies and leaves the fast topics out. The caption shows how many messages were **dropped** (live only); if that isn't 0, the loop fell behind and its numbers can't be trusted.

**How the data flows.** A *source* hands out every message; each consumer keeps what it needs. The recorder writes all of them; the table counts every message for the rates and keeps only the newest per topic for the screen. The source is the robot (`LiveSource`) or, for `replay`, a recording (`ReplaySource`), behind the same interface.

### Saved files

Saved files go in `bridge/outputs/` (ignored by git), organized by group and date:

```
outputs/<group>/<YYYY-MM-DD>/<name>_<HHMMSS>_<interface>.json
outputs/discovery/2026-11-23/snapshot_161435_eth10.json
```

The time is when the run started. The interface in the name tells robot runs (`eth10`) apart from laptop tests. Every saved file gets its path from `h2_bridge/utils/output_paths.py`. You can choose the `<name>` part (letters, digits, `-`, `_`, `.`), but never the folder, so all results end up in this one place.

The program's own state goes in `bridge/cache/` (also ignored by git), through `h2_bridge/utils/state_files.py`. Today that's `topics.json`, the topic cache: which DDS type each topic carries, learned from discovery runs. It's safe to delete; the next `discovery topics` rebuilds it.

### Output and exit codes

- Results (tables) go to **stdout**. Spinners and messages go to **stderr**, so `> file` or `| less` only captures the results.
- Exit codes: `0` success, `1` ran but found nothing (e.g. `watch` received no data, a topic can't be found, or `replay` can't read the file), `2` bad arguments, `130` stopped with Ctrl-C (`telemetry watch` and `replay` instead stop cleanly and exit `0`/`1`).
- `telemetry watch`/`replay` redraw a live table in a terminal. Piped or redirected, they print only the final table.

### Code layout

The CLI only parses arguments and prints. The logic lives in the matching package:

```
src/h2_bridge/
  cli/root_parser.py         # root parser + global options; registers each group
  cli/discovery_commands.py  # `discovery` commands  ->  calls h2_bridge.discovery
  cli/discovery_tables.py    # rich tables those commands print (one per kind of row)
  cli/telemetry_commands.py  # `telemetry` commands  ->  calls h2_bridge.telemetry
  cli/telemetry_tables.py    # rich tables those commands print
  cli/telemetry_summaries.py # the Summary column: one line per message type (the core 6)
  discovery/        # discovery logic (no argparse):
                    #   models.py   = Snapshot dataclasses (the raw facts)
                    #   collect.py  = DDS -> Snapshot (the only discovery module that touches DDS)
                    #   snapshot_views.py = Snapshot -> views (group_by_topic, endpoints_by_participant, participant_ips)
                    #   snapshot_files.py = Snapshot <-> JSON in outputs/ (save_snapshot, load_snapshot)
                    #   topic_cache.py = topic -> type, learned from snapshots (bridge/cache/topics.json)
  telemetry/        # telemetry logic (no argparse):
                    #   models.py   = TopicSpec (a topic we read) and Message (one received message)
                    #   core_topics.py = CORE_TOPICS (SDK class, expected Hz)
                    #   sources/base_source.py = Source (the shared interface) and TopicError
                    #   sources/live_source.py = LiveSource: the robot over DDS (the only telemetry module that touches DDS)
                    #   sources/replay_source.py = ReplaySource: a recording, played back at its original pace
                    #   recording_format.py = the .jsonl.gz format: RecordingWriter, open_recording, read_header, read_line
                    #   topic_lookup.py = topic names -> TopicSpecs (core, then the topic cache, then a short discovery run)
                    #   rate_meter.py = RateMeter, latest()
  robot/            # robot facts, plain data (no telemetry imports):
                    #   joints.py  = body and hand slots -> joint names and limits
                    #   sensors.py = battery cell and main board temperature counts, IMU notes
  dds_setup.py      # shared DDS setup (init_dds, make_participant)
  utils/            # small shared helpers (no DDS, no argparse):
                    #   msg_to_dict.py = SDK message -> plain dict (msg_to_dict)
                    #   output_paths.py = paths for saved files (outputs/<group>/<date>/...)
                    #   sdk_type_lookup.py = DDS type name -> SDK class (lookup_type)
                    #   state_files.py = the program's own state in bridge/cache/ (cache_path, read_json, atomic write_json)
  constants.py      # defaults (DDS_DEFAULTS) and paths (BRIDGE_ROOT, OUTPUT_DIR, CACHE_DIR)
```

To add a group, create `cli/<group>_commands.py` with a `register(commands)` function and call it from `build_parser()` in `cli/root_parser.py`.

### Planned

Not built yet: `serve` for the dashboard, `check` (a health sweep of every topic), and `--json` output.
