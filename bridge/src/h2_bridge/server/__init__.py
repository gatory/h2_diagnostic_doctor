"""The WebSocket server: streams Snapshots and checkup's verdicts to the dashboard.

    messages.py    Snapshot + Checkup -> one JSON-safe message (the API contract)
    ws_server.py   WebSocketServer: the asyncio server, in its own thread; publish() from any thread
    publisher.py   SnapshotPublisher: the poll-loop consumer that feeds the server

No argparse, rich or DDS here (the command is cli/server_commands.py). One way
only for now: bridge -> browser. Read-only like the rest of h2_bridge.
"""
