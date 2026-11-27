# Running the live server at boot (Jetson Thor)

`bridge/deploy/h2-doctor.service` runs `h2-doctor server live` from boot, always on, and
restarts it if it exits with an error. It is read-only: it only subscribes to DDS.

## Install

On the Thor, from the repo root, with the bridge's venv already set up (`uv sync` in `bridge/`):

```bash
BRIDGE="$(pwd)/bridge"
CYCLONEDDS_HOME="/path/to/cyclonedds/install"     # the value in bridge/.envrc

sed -e "s|@USER@|$USER|g" \
    -e "s|@BRIDGE@|$BRIDGE|g" \
    -e "s|@CYCLONEDDS_HOME@|$CYCLONEDDS_HOME|g" \
    bridge/deploy/h2-doctor.service | sudo tee /etc/systemd/system/h2-doctor.service > /dev/null

sudo systemctl daemon-reload
sudo systemctl enable --now h2-doctor    # start now and at every boot
```

After changing the template, run the same commands again (the installed copy doesn't follow the repo).

## Use

```bash
systemctl status h2-doctor          # running? last lines of output
journalctl -u h2-doctor -f          # follow its output
sudo systemctl restart h2-doctor    # e.g. after pulling new code
sudo systemctl disable --now h2-doctor   # stop it and don't start at boot
```

The dashboard connects to `ws://<thor address>:8765`.

## Good to know

- **Boot order.** If `eth10` isn't up yet, DDS can't start, the command exits 1 and systemd retries
  every 5 s. If the robot's boards aren't publishing yet, the server still runs and its snapshots show
  the topics as silent until data arrives.
- **Who can connect.** It listens on every interface (`0.0.0.0`) with no login. To limit it to one
  network, add `--host <that interface's address>` to `ExecStart` (before `live`: it's a `server` option).
- **Other commands still work alongside it** (`telemetry watch`, `checkup`): DDS allows many
  subscribers. Only a second server on port 8765 would clash.
- **Cost when no browser is connected:** the poll loop and checkup keep running at 30 Hz (the JSON is
  skipped). Check with `top`; if it matters, see the socket-activation idea (start on first connection,
  exit when idle), not built.
