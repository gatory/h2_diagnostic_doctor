"""The WebSocket server: the message contract, newest-wins delivery, and the whole pipeline. No robot."""

import json
import math

import pytest
from websockets.sync.client import connect

from fakes import FakeSource, after
from h2_bridge.checkup.engine import Checkup
from h2_bridge.server.messages import PROTOCOL, _clean, snapshot_message
from h2_bridge.server.publisher import SnapshotPublisher
from h2_bridge.server.ws_server import WebSocketServer
from h2_bridge.telemetry.poll_loop import run
from h2_bridge.telemetry.snapshot import SnapshotBuilder


def _judged(seconds=3.0, **kwargs):
    """A FakeSource run through the builder and checkup: (source, builder, checkup)."""
    source = FakeSource(duration=seconds, **kwargs)
    builder = SnapshotBuilder(source.topics, source.dropped)
    checkup = Checkup(builder)
    run(source, [builder, checkup], poll_secs=0)
    return source, builder, checkup


@pytest.fixture
def server():
    with WebSocketServer("127.0.0.1", 0) as s:  # port 0: any free port
        yield s


# ---------------------------------------------------------------- The message


def test_message_has_named_joints_and_checkups_verdict():
    source, builder, checkup = _judged()
    msg = snapshot_message(builder.snapshot(source.now()), checkup, live=False)
    assert msg["type"] == "snapshot" and msg["protocol"] == PROTOCOL and msg["source"] == "replay"
    joints = msg["snapshot"]["body"]["joints"]
    assert len(joints) == 31 and joints[1]["name"] == "L_hip_roll" and joints[1]["slot"] == 1
    assert msg["snapshot"]["hands"]["left"]["motors"][0]["name"] == "index_knuckle_swing"
    assert msg["checkup"]["now"] == "pass" and msg["checkup"]["findings"] == []
    assert "t" not in msg["snapshot"]  # only at the top level


def test_message_is_strict_json():
    source, builder, checkup = _judged()
    msg = snapshot_message(builder.snapshot(source.now()), checkup, live=True)
    text = json.dumps(msg, allow_nan=False)  # raises on NaN/inf or anything not JSON
    assert json.loads(text) == msg


def test_findings_are_sent_with_their_status_as_text():
    def stop_battery(topic, t, data):
        return False if topic == "rt/lf/bmsstate" and after(2)(t) else None

    source, builder, checkup = _judged(seconds=5.0, tweak=stop_battery)
    msg = snapshot_message(builder.snapshot(source.now()), checkup, live=False)
    assert msg["checkup"]["now"] == "fail" and msg["checkup"]["worst"] == "fail"
    finding = msg["checkup"]["findings"][0]
    assert finding["rule"] == "topic_flow" and finding["subject"] == "rt/lf/bmsstate"
    assert isinstance(finding["status"], str)


def test_parts_without_data_are_null():
    def only_lowstate(topic, t, data):
        return None if topic == "rt/lf/lowstate" else False

    source, builder, checkup = _judged(tweak=only_lowstate)
    snap = snapshot_message(builder.snapshot(source.now()), checkup, live=False)["snapshot"]
    assert snap["body"] is not None
    assert snap["battery"] is None and snap["hands"] == {"left": None, "right": None}


def test_clean_turns_non_finite_numbers_into_null():
    assert _clean({"a": (1.0, math.nan), "b": frozenset({math.inf}), "c": -math.inf}) == \
        {"a": [1.0, None], "b": [None], "c": None}


# ---------------------------------------------------------------- The server


def test_late_joiner_gets_the_newest_message_at_once(server):
    with connect(f"ws://127.0.0.1:{server.port}") as client:
        server.publish("a")
        assert client.recv(timeout=2) == "a"
        # Join later: the second client gets the newest message without waiting for the next one.
        with connect(f"ws://127.0.0.1:{server.port}") as late:
            assert late.recv(timeout=2) == "a"
            server.publish("b")
            assert late.recv(timeout=2) == "b"
            assert client.recv(timeout=2) == "b"


def test_a_client_that_falls_behind_skips_to_the_newest(server):
    with connect(f"ws://127.0.0.1:{server.port}") as client:
        server.publish("first")
        assert client.recv(timeout=2) == "first"
        for i in range(500):  # far more than the client reads
            server.publish(f"m{i}")
        received = []
        while (text := client.recv(timeout=2)) != "m499":
            received.append(text)
        assert len(received) < 499  # it skipped some: no queue builds up


def test_clients_are_counted(server):
    assert server.clients == 0
    with connect(f"ws://127.0.0.1:{server.port}") as client:
        server.publish("x")
        client.recv(timeout=2)
        assert server.clients == 1


def test_port_in_use_raises_at_start(server):
    with pytest.raises(OSError):
        WebSocketServer("127.0.0.1", server.port).start()


# ---------------------------------------------------------------- The whole pipeline


def test_poll_loop_to_browser(server):
    source = FakeSource(duration=2.0)
    builder = SnapshotBuilder(source.topics, source.dropped)
    checkup = Checkup(builder)
    publisher = SnapshotPublisher(builder, checkup, server, source.live)
    with connect(f"ws://127.0.0.1:{server.port}") as client:
        _wait_for_client(server)
        run(source, [builder, checkup, publisher], poll_secs=0)
        msg = json.loads(client.recv(timeout=2))
    assert publisher.sent == 8  # one per poll: 2 s at 0.25 s a step
    assert msg["type"] == "snapshot"
    assert msg["snapshot"]["body"]["joints"][1]["name"] == "L_hip_roll"
    assert msg["checkup"]["now"] == "pass"


def test_publisher_skips_work_with_no_clients(server):
    source = FakeSource(duration=1.0)
    builder = SnapshotBuilder(source.topics, source.dropped)
    checkup = Checkup(builder)
    publisher = SnapshotPublisher(builder, checkup, server, source.live)
    run(source, [builder, checkup, publisher], poll_secs=0)
    assert publisher.sent == 0


def _wait_for_client(server, timeout=2.0):
    """The handshake finishes on the server's thread a moment after connect() returns."""
    import time

    end = time.monotonic() + timeout
    while not server.clients:
        assert time.monotonic() < end, "client never registered"
        time.sleep(0.005)
