"""Telemetry: rates, the recording format, the replay clock, the poll loop, and the snapshot."""

import gzip
import json

import pytest

from fakes import START, FakeSource
from h2_bridge.telemetry.core_topics import CORE_TOPICS
from h2_bridge.telemetry.models import Message
from h2_bridge.telemetry.poll_loop import run
from h2_bridge.telemetry.rate_meter import RateMeter, latest
from h2_bridge.telemetry.recording_format import RecordingReader, RecordingWriter
from h2_bridge.telemetry.snapshot import SnapshotBuilder
from h2_bridge.telemetry.sources.replay_source import ReplaySource
from h2_bridge.utils import output_paths


# ---------------------------------------------------------------- RateMeter


def _ticks(topic, hz, seconds, start=0.0):
    return [Message(start + i / hz, topic, {}) for i in range(int(seconds * hz) + 1)]


def test_rate_is_exact_from_the_gaps():
    meter = RateMeter()
    meter.add(_ticks("a", 20, 10))
    assert meter.hz("a", 10.0) == pytest.approx(20.0)  # (n - 1) / span: no 0.5 Hz steps
    assert meter.average_hz("a") == pytest.approx(20.0)


def test_rate_is_zero_when_silent_and_average_needs_two_messages():
    meter = RateMeter()
    meter.add([Message(0.0, "a", {})])
    assert meter.hz("a", 0.0) == 0.0
    assert meter.average_hz("a") is None
    assert meter.hz("never", 5.0) == 0.0


def test_average_uses_each_topics_own_span():
    meter = RateMeter()
    meter.add(_ticks("late", 10, 5, start=20.0))  # started 20 s after the run
    assert meter.average_hz("late") == pytest.approx(10.0)


def test_latest_keeps_the_newest_per_topic():
    newest = latest([Message(1.0, "a", {"n": 1}), Message(2.0, "a", {"n": 2}), Message(1.5, "b", {})])
    assert newest["a"].data == {"n": 2} and set(newest) == {"a", "b"}


# ---------------------------------------------------------------- Recording format


@pytest.fixture
def outputs(tmp_path, monkeypatch):
    """Point outputs/ at a temporary folder for the test."""
    monkeypatch.setattr(output_paths, "OUTPUT_DIR", tmp_path)
    return tmp_path


class _LiveLike:
    """Just what RecordingWriter reads from a source."""

    interface, domain_id, topics = "test0", 0, CORE_TOPICS
    dropped = dict.fromkeys(CORE_TOPICS, 0)


def _record(seconds=3.0):
    """Write a FakeSource's messages to a new recording; return its path."""
    source = FakeSource(duration=seconds)
    with RecordingWriter(_LiveLike(), "test") as writer:
        while not source.done:
            writer.add(source.poll(), source.now())
    return writer.path, writer.count


def test_recording_round_trip(outputs):
    path, count = _record()
    assert path.name.endswith("_test0.jsonl.gz")
    with RecordingReader(path) as reader:
        assert set(reader.topics) == set(CORE_TOPICS)
        messages = []
        while (m := reader.next_message()) is not None:
            messages.append(m)
        assert len(messages) == count and not reader.truncated
        assert reader.footer["messages"] == count
        assert reader.footer["avg_hz"]["rt/lf/lowstate"] == pytest.approx(20.0, abs=0.1)


def test_recording_cut_off_ends_early_and_says_so(outputs):
    path, count = _record()
    data = path.read_bytes()
    path.write_bytes(data[: len(data) // 2])
    with RecordingReader(path) as reader:
        n = 0
        while reader.next_message() is not None:
            n += 1
    assert 0 < n < count and reader.truncated and reader.footer is None


def test_reader_refuses_anything_but_jsonl_gz(tmp_path):
    plain = tmp_path / "old.jsonl"
    plain.write_text(json.dumps({"recording": 1, "topics": {}}) + "\n")
    with pytest.raises(ValueError):
        RecordingReader(plain)
    fake = tmp_path / "fake.jsonl.gz"
    fake.write_text("not gzip")
    with pytest.raises(ValueError):
        RecordingReader(fake)


def test_find_outputs_handles_dotted_extensions(outputs):
    path, _ = _record()
    found = output_paths.find_outputs("telemetry", ext="jsonl.gz")
    assert [f.path for f in found] == [path]
    assert found[0].interface == "test0" and found[0].name == "test"


# ---------------------------------------------------------------- Replay clock


def test_stepped_replay_moves_the_clock_exactly_per_poll(outputs):
    path, count = _record(seconds=3.0)
    with ReplaySource(path, step_s=0.25) as source:
        first = source.now()
        batch = source.poll()
        assert source.now() == pytest.approx(first + 0.25)
        assert all(m.t <= source.now() for m in batch)  # now() matches the batch handed out
        total = len(batch)
        while not source.done:
            total += len(source.poll())
    assert total == count


def test_replay_clock_never_runs_ahead_of_its_batch_or_backwards(outputs):
    path, _ = _record(seconds=3.0)
    times = []
    with ReplaySource(path, speed=1000) as source:  # far faster than the wall clock allows
        while not source.done:
            batch = source.poll()
            now = source.now()
            assert all(m.t <= now for m in batch)
            times.append(now)
    assert times == sorted(times)


# ---------------------------------------------------------------- Poll loop


class _Recorder:
    def __init__(self):
        self.calls = []

    def add(self, messages, now):
        self.calls.append((len(messages), now))


def test_loop_hands_every_message_to_every_consumer_in_order():
    source = FakeSource(duration=2.0)
    a, b = _Recorder(), _Recorder()
    run(source, [a, b], poll_secs=0)
    assert a.calls == b.calls and len(a.calls) == 8
    assert sum(n for n, _ in a.calls) == 4 * (2 * 20 + 1) + 2 * (2 * 100 + 1)  # both ends included


def test_loop_duration_is_on_the_sources_clock():
    source = FakeSource(duration=60.0)
    seen = _Recorder()
    run(source, [seen], duration=5.0, poll_secs=0)
    assert seen.calls[-1][1] - START == pytest.approx(5.0)


# ---------------------------------------------------------------- Snapshot


def _snapshot(seconds=1.0, **kwargs):
    source = FakeSource(duration=seconds, **kwargs)
    builder = SnapshotBuilder(source.topics, source.dropped)
    run(source, [builder], poll_secs=0)
    return builder.snapshot(source.now())


def test_snapshot_names_joints_and_hands():
    snap = _snapshot()
    assert snap.body.joints[18].name == "L_elbow"
    assert len(snap.body.joints) == 31 and len(snap.hands["left"].motors) == 20
    assert snap.hands["left"].motors[16].temperature is None  # the thumb reports none
    assert snap.battery.cell_spread == 2 and len(snap.battery.cells) == 18
    assert snap.topics["rt/lf/lowstate"].hz == pytest.approx(20.0, abs=0.5)
    assert not snap.bad and snap.any_data


def test_snapshot_parts_are_none_before_data_and_bad_shapes_are_flagged():
    builder = SnapshotBuilder(CORE_TOPICS)
    empty = builder.snapshot(START)
    assert empty.body is None and empty.battery is None and not empty.any_data
    builder.add([Message(START, "rt/lf/bmsstate", {"soc": 5})], START)
    snap = builder.snapshot(START)
    assert snap.battery is None and snap.bad == {"rt/lf/bmsstate"}


def test_snapshot_passes_nan_through_as_none():
    def nan_elbow(topic, t, data):
        if topic == "rt/lf/lowstate":
            data["motor_state"][18]["q"] = None
    assert _snapshot(tweak=nan_elbow).body.joints[18].q is None


def test_recordings_are_gzip_json_lines(outputs):
    path, _ = _record(seconds=1.0)
    with gzip.open(path, "rt") as f:
        header = json.loads(f.readline())
    assert header["recording"] == 1 and header["interface"] == "test0"
