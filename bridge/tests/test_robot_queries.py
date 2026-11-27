"""robot_queries: only the allowlisted getters are reachable, and answers unpack the SDK's shapes.
fsm_map: reading and saving which FSM id each mode is (discovery modes --watch / --map). No robot."""

import json

import pytest

from h2_bridge.discovery.fsm_map import WALKTHROUGH, fsm_names, read_fsm, save_fsm_map
from h2_bridge.robot_queries import QUERIES, Answer, RobotQueries
from h2_bridge.utils import output_paths


class _FakeClient:
    """Answers every getter; records every call, and has the SDK's commands too (which must never run)."""

    def __init__(self, fail=None):
        self.calls = []
        self.fail = fail or set()

    def __getattr__(self, method):
        def call():
            self.calls.append(method)
            if method in self.fail:
                return 3104, None
            if method == "GetAvailableFsmIds":
                return 0, [0, 1, 4], ["zero torque", "damping", "stand"]
            if method == "CheckMode":
                return 0, {"name": "ai", "form": "0"}
            return 0, 4
        return call


def _queries(**fake):
    clients = {"motion_switcher": _FakeClient(**fake), "loco": _FakeClient(**fake)}
    return RobotQueries(clients=clients), clients


def test_only_allowlisted_getters_are_called():
    queries, clients = _queries()
    queries.ask_all()
    called = clients["motion_switcher"].calls + clients["loco"].calls
    assert sorted(called) == sorted(method for _, method, _ in QUERIES.values())
    assert all(m.startswith(("Get", "Check")) for m in called)


def test_anything_off_the_allowlist_is_refused():
    queries, clients = _queries()
    with pytest.raises(KeyError):
        queries.ask("SetFsmId")
    with pytest.raises(KeyError):
        queries.ask("ReleaseMode")
    assert not hasattr(queries, "clients") and not hasattr(queries, "_clients")  # the SDK clients aren't handed out
    assert clients["loco"].calls == []


def test_answers_unpack_the_sdks_shapes():
    queries, _ = _queries()
    answers = {a.name: a for a in queries.ask_all()}
    assert answers["fsm_id"].value == 4 and answers["fsm_id"].ok and answers["fsm_id"].error == ""
    assert answers["motion_mode"].value == {"name": "ai", "form": "0"}
    assert answers["available_fsms"].value == ([0, 1, 4], ["zero torque", "damping", "stand"])


def test_an_unanswered_query_has_no_value_and_says_why():
    queries, _ = _queries(fail={"GetFsmId"})
    answer = queries.ask("fsm_id")
    assert not answer.ok and answer.value is None and answer.error == "no answer (timeout)"


# ---------------------------------------------------------------- FSM mapping (discovery modes --watch / --map)


class _ChangingRobot:
    """Answers fsm_id from a list, one per call (the robot switching modes between readings)."""

    def __init__(self, fsm_ids):
        self.fsm_ids = list(fsm_ids)

    def ask(self, name):
        if name == "fsm_id":
            value = self.fsm_ids.pop(0)
            return Answer(name, 0, value, 0.001) if value is not None else Answer(name, 3104, None, 1.0)
        if name == "motion_mode":
            return Answer(name, 0, {"name": "ai", "form": "0"}, 0.001)
        raise AssertionError(name)


def test_fsm_names_come_from_the_available_list():
    queries, _ = _queries()
    assert fsm_names(queries.ask("available_fsms")) == {0: "zero torque", 1: "damping", 4: "stand"}
    unanswered, _ = _queries(fail={"GetAvailableFsmIds"})
    assert fsm_names(unanswered.ask("available_fsms")) == {}


def test_a_settled_mode_reads_stable():
    reading = read_fsm(_ChangingRobot([601, 601, 601]), gap_s=0)
    assert reading.fsm_id == 601 and reading.stable and reading.motion_mode == "ai"


def test_a_mode_still_switching_or_unanswered_is_not_stable():
    switching = read_fsm(_ChangingRobot([4, 4, 601]), gap_s=0)
    assert switching.fsm_id == 601 and not switching.stable and switching.seen == [4, 4, 601]
    silent = read_fsm(_ChangingRobot([None, None, None]), gap_s=0)
    assert silent.fsm_id is None and not silent.stable


def test_the_map_is_saved_with_names_and_skips(tmp_path, monkeypatch):
    monkeypatch.setattr(output_paths, "OUTPUT_DIR", tmp_path)
    ready = read_fsm(_ChangingRobot([4, 4, 4]), gap_s=0)
    steps = [(gear, label, ready if gear == "ready" else None) for gear, label in WALKTHROUGH]
    path = save_fsm_map(steps, {4: "FixStand"}, "eth10")
    data = json.loads(path.read_text())
    assert path.parent.parent.name == "discovery" and path.name.startswith("fsm_map_")
    assert data["gears"]["ready"]["fsm_id"] == 4 and data["gears"]["ready"]["fsm_name"] == "FixStand"
    assert data["gears"]["damp"] is None and data["available_fsms"] == {"4": "FixStand"}
