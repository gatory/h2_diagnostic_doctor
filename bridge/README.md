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
uv run h2-doctor telemetry watch                             # live view of the core topics until Ctrl-C
uv run h2-doctor telemetry watch --record first_try -t 30    # also record 30 s, as first_try_<time>_<iface>.jsonl.gz
uv run h2-doctor telemetry watch -q --record                 # record without the live view (long runs)
uv run h2-doctor telemetry replay                            # play the newest recording back (no robot needed)
uv run h2-doctor telemetry replay FILE -s 4                  # a given recording, 4x faster
```

`watch` subscribes (read-only) to the core topics, `CORE_TOPICS` in `src/h2_bridge/telemetry/core_topics.py`, and nothing else. Ctrl-C stops cleanly (it never cuts a line in half); a second Ctrl-C stops at once. At the end it prints, per topic, the messages received, the average rate (against the expected rate for core topics) and any dropped, then where the recording went.

**Recordings** are gzipped JSON Lines (`.jsonl.gz`, about 10x smaller than plain: ~300 MB/hour for the core topics) in `outputs/telemetry/<date>/`:
- a header line: start time, host, interface, domain, and each topic's DDS type and expected Hz;
- one line per message: `t` (arrival time), `topic`, `data`;
- a footer line when the recording closes: end time, duration, message count, `dropped` per topic, and `avg_hz` (each topic's average rate over the recording; footers from before it was added don't have it). **No footer** means the recorder died (power loss, `kill -9`).

The core topics are recorded. The file is flushed about 4 times a second, so a crash loses at most the last ~0.25 s, and a recording is never overwritten. Read one with `zcat FILE | head`. Only `.jsonl.gz` is read: `replay` refuses any other file.

**`replay`** plays the newest `.jsonl.gz` in `outputs/telemetry/` (or `FILE`, if given) at its recorded pace (`-s/--speed` to change it) in the same dashboard as `watch`. Rates and ages run on the recording's clock, so they match the live run at any speed; the clock stops at the last message. At the end it prints each topic's average rate in the replay next to the one saved when it was recorded (they should match), and says whether the recording closed cleanly (footer) or was cut off.

**The live dashboard** (`cli/telemetry_tables.py`) shows every core topic on one screen: topics, battery and main board across the top, then the body joints, the hands over the IMUs, and checkup's **Warnings** on the right. Each panel is as wide as its content; the Warnings panel takes what's left. It needs a terminal of about **190 x 46** to show the warnings' full messages; at ~175 they're shortened (status and subject always stay), and below ~160 there's no room for them. The topic colors and the **Warnings** panel come from checkup's rules, run live on the same data (see `checkup` below). In a fast replay (high `--speed`) the warnings are coarse: few polls cover a lot of recording, so short problems can be missed. `h2-doctor checkup --replay` is the full check.

| Panel | What it shows |
|---|---|
| Topics | per topic: Hz over the last 2 s / expected, colored by checkup's verdict (green: on rate, yellow: slow, red: silent or stale), Avg since the start, Last (age of the newest message), Dropped (live only) |
| Warnings | checkup's current findings, worst first (at most 10, then "and N more"); "none" when every rule passes |
| Body joints | the 31 joints by name (`robot/joints.py`): q, dq, tau, both temperatures, mode/motorstate; `mode_machine`, `mode_pr`, `tick` in the title |
| Hands | one row per finger joint, left hand (orange) then right (blue): q, dq, tau, temperature (none for the position-only thumb), mode/motorstate; per hand: error, power, and the highest reading of each of the 16 pressure pads |
| IMUs | pelvis (inside `rt/lf/lowstate`), torso (`rt/lf/secondary_imu`) and both hands: rpy, gyro, accel, temperature |
| Battery | charge, health, voltage, current, cell min-max and spread, temperatures, cycles, raw state |
| Main board | the 4 temperatures, fans, state, value |

Apart from the topic colors and the Warnings panel (both from checkup), it shows numbers only, never judgements. A `?` marks a unit or meaning that isn't confirmed (see `docs/robot_findings.md`). A panel says "waiting for data..." until its topic's first message, and "(unexpected message shape)" instead of crashing on odd data.

The 6 topics, about 280 messages/s in total, are what the dashboard draws: `rt/lf/lowstate` (body, 20 Hz), `rt/lf/secondary_imu` (torso IMU), `rt/lf/bmsstate` (battery), `rt/lf/mainboardstate` (board temperatures, fans), `rt/dex5/left/state` and `rt/dex5/right/state` (hands, 100 Hz).

**Why only these topics.** Every message costs Python time to decode, even on a background thread. Subscribing to everything, including the ~1 kHz `rt/lowstate` and `rt/lowcmd`, overloads Python and makes the rates read low (the MVP saw `rt/lf/*` at 10 Hz instead of 20). So `watch` uses the 20 Hz `rt/lf/...` copies and leaves the fast topics out. The caption shows how many messages were **dropped** (live only); if that isn't 0, the loop fell behind and its numbers can't be trusted.

**How the data flows.** One poll loop (`telemetry/poll_loop.py`) polls a *source* about 4 times a second and hands every batch, in order, to each *consumer*: anything with `add(messages, now)`. The source is the robot (`LiveSource`) or a recording (`ReplaySource`), behind the same interface. The consumers: the snapshot builder (keeps the newest message per topic and every rate, and turns them into a `Snapshot` of named values), the recorder (writes every message), checkup's engine (judges each snapshot) and the dashboard (draws it). `watch`, `replay` and `checkup` differ only in their source and consumers.

### `checkup`: is the robot healthy?

```bash
uv run h2-doctor checkup                       # listen 10 s, then a pass/warn/fail report
uv run h2-doctor checkup -t 30 --name pre_walk # 30 s, saved as pre_walk_<time>_<iface>.json
uv run h2-doctor checkup --replay              # check the newest recording (no robot needed)
uv run h2-doctor checkup --replay FILE -t 20   # the first 20 s of a given recording
```

It listens to the core topics (or replays a recording), runs every rule on each poll, prints one row per rule, and **always saves the report** as JSON to `outputs/checkup/<date>/` (`checkup_<time>_<iface>.json`, or `replay_...` for a recording). A replay steps its clock 0.25 s per poll, like a live run, but as fast as the rules go: 60 s of recording takes about 2 s.

| Rule | What it checks | Status |
|---|---|---|
| Topics arriving | each topic: not silent 3 s after the start, not stale (no message for 5 periods, at least 0.5 s), not below 80% of its expected rate | fail / fail / warn |
| No dropped messages | the live source kept up (no data for a replay) | warn |
| No NaN joint readings | q, dq, tau of every body and hand motor are real numbers | fail |
| Joints within limits | body q **at** a limit in `robot/joints.py` (within 0.02 rad of it): warn; **forced past** it (more than 0.02 rad beyond): fail. Shows within one poll. `head_pitch` rests on its stop, so it warns whenever the head is fully down. Hands: not checked, their zero is unconfirmed | warn / fail |
| Joint readings change | no body q bit-identical for 5 s while messages arrive | warn |
| Hand readings change | no hand motor q bit-identical for 5 s while that hand's messages arrive, except at an end of its range (within 0.05 rad), where the reading is clamped (a curled finger, the right thumb on its stop) | warn |
| No motor error bits | `motorstate` is 0 on every motor (what each bit means is unknown) | warn |
| No hand errors | each hand's `error` is all 0 | warn |
| Battery cells balanced | cell spread under 50 mV (warn), 100 mV (fail) | warn / fail |
| Battery charged | charge above 20% (warn), 10% (fail) | warn / fail |
| Body IMUs agree | pelvis - torso in roll and pitch matches the waist joints within 0.15 rad (warn), 0.30 (fail). Yaw drifts, so it isn't compared | warn / fail |

Every limit, and where its number came from, is in `src/h2_bridge/checkup/limits.py`; the healthy-robot measurements behind them are in `docs/robot_findings.md`. Temperatures and fields of unknown meaning (`fan_state`, `bmsstate`, `mode`, the hand IMU temperature) are never judged. **Timing:** problems are flagged **at once**, on the first poll that sees them (like the MVP). A value that can hover at a threshold (joint limits, cell spread, charge, the IMU leftover) has **hysteresis** instead: once on, it stays on until the value is a margin back on the good side (`*_MARGIN` in `limits.py`, `checkup/rules/bands.py`), so it doesn't flicker. Only `imu_agreement` still waits 1 s, because the two IMUs' messages are a few ms apart and one snapshot can disagree during fast motion.

### Saved files

Saved files go in `bridge/outputs/` (ignored by git), organized by group and date:

```
outputs/<group>/<YYYY-MM-DD>/<name>_<HHMMSS>_<interface>.json
outputs/discovery/2026-11-23/snapshot_161435_eth10.json
```

The time is when the run started. The interface in the name tells robot runs (`eth10`) apart from laptop tests. Every saved file gets its path from `h2_bridge/utils/output_paths.py`. You can choose the `<name>` part (letters, digits, `-`, `_`, `.`), but never the folder, so all results end up in this one place.

The program's own state goes in `bridge/cache/` (also ignored by git), through `h2_bridge/utils/state_files.py`. Today that's `topics.json`, the topic cache: which DDS type each topic carries, learned from discovery runs. It's safe to delete; the next `discovery topics` rebuilds it. **Nothing reads it right now:** it fed `telemetry watch TOPIC` (watching any topic by name), which was removed because many topics use types the Python SDK lacks. It's kept, and still updated, for when that feature comes back (`telemetry/topic_lookup.py` in git history).

### Output and exit codes

- Results (tables) go to **stdout**. Spinners and messages go to **stderr**, so `> file` or `| less` only captures the results.
- Exit codes: `0` success, `1` ran but found nothing (e.g. `watch` received no data, a topic can't be found, or `replay` can't read the file), `2` bad arguments, `130` stopped with Ctrl-C (`telemetry watch` and `replay` instead stop cleanly and exit `0`/`1`).
- `checkup`'s exit codes say how the robot is, so scripts can act on them: `0` every check passed, `1` couldn't run (no data, DDS error, unreadable recording; no report saved), `3` warnings but no failures, `4` at least one failure (`2` is still bad arguments).
- `telemetry watch`/`replay` redraw a live dashboard in a terminal. Piped or redirected, they print only the final screen.

### Code layout

The CLI only parses arguments and prints. The logic lives in the matching package:

```
src/h2_bridge/
  cli/root_parser.py         # root parser + global options; registers each group
  cli/discovery_commands.py  # `discovery` commands  ->  calls h2_bridge.discovery
  cli/discovery_tables.py    # rich tables those commands print (one per kind of row)
  cli/telemetry_commands.py  # `telemetry` commands  ->  calls h2_bridge.telemetry
  cli/telemetry_tables.py    # the live dashboard those commands draw (from a Snapshot + checkup's verdicts)
  cli/checkup_commands.py    # `checkup`  ->  calls h2_bridge.checkup
  cli/checkup_tables.py      # the report table it prints
  discovery/        # discovery logic (no argparse):
                    #   models.py   = Snapshot dataclasses (the raw facts)
                    #   collect.py  = DDS -> Snapshot (the only discovery module that touches DDS)
                    #   snapshot_views.py = Snapshot -> views (group_by_topic, endpoints_by_participant, participant_ips)
                    #   snapshot_files.py = Snapshot <-> JSON in outputs/ (save_snapshot, load_snapshot)
                    #   topic_cache.py = topic -> type, learned from snapshots (bridge/cache/topics.json); unused for now, kept for watching topics by name later
  telemetry/        # telemetry logic (no argparse):
                    #   models.py   = TopicSpec (a topic we read) and Message (one received message)
                    #   core_topics.py = CORE_TOPICS (SDK class, expected Hz)
                    #   sources/base_source.py = Source (the shared interface) and TopicError
                    #   sources/live_source.py = LiveSource: the robot over DDS (the only telemetry module that touches DDS)
                    #   sources/replay_source.py = ReplaySource: a recording, at its original pace or stepped (step_s per poll)
                    #   recording_format.py = the .jsonl.gz format: RecordingWriter, RecordingReader
                    #   rate_meter.py = RateMeter (recent and average rates), latest()
                    #   poll_loop.py = run(source, consumers): the one poll loop (Ctrl-C flag, duration on the source's clock)
                    #   snapshot.py = SnapshotBuilder (a consumer) -> Snapshot: named joints, hands, IMUs, battery, board, topic rates
  checkup/          # health checks (no argparse, no rich, no DDS):
                    #   models.py  = Status, Observation, Rule, Finding
                    #   rules/     = the rules, by area (topics, joints, power, imus); RULES in rules/__init__.py
                    #   limits.py  = every threshold, with where its number came from
                    #   engine.py  = Checkup (a consumer): runs the rules each poll, debounces them into findings
                    #   report.py  = the report as data, saving it to outputs/checkup/, exit codes
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

To add a checkup rule: write a `check(snapshot, memory)` function returning `Observation`s (or None when its inputs aren't there), wrap it in a `Rule` with its hold/clear times, put its thresholds in `checkup/limits.py`, add it to `RULES`, and add a scenario test in `tests/test_checkup.py`.

### Tests

```bash
uv run pytest            # from bridge/: ~35 tests, a few seconds, no robot needed
```

`tests/fakes.py` makes healthy fake core-topic messages and a `FakeSource` that steps its clock; each scenario in `tests/test_checkup.py` injects one fault (a topic stopping, a NaN joint, a frozen joint, a bad cell...) and checks that exactly the right rule reports it. `tests/test_telemetry.py` covers the rate meter, the recording format, the replay clock, the poll loop and the snapshot.

### Planned

Not built yet: `serve` for the dashboard and `--json` output.
