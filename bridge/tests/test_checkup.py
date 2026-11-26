"""Checkup: the fake scenarios end to end, the debouncing, and the report.

Each scenario is a healthy fake robot with one fault injected (fakes.py); the
test checks that exactly the right rule reports it, and that a healthy robot
passes everything.
"""

import json

import pytest

from fakes import START, FakeSource, after
from h2_bridge.checkup import limits
from h2_bridge.checkup.engine import Checkup
from h2_bridge.checkup.models import Observation, Rule, Status
from h2_bridge.checkup.report import EXIT_FAIL, EXIT_PASS, EXIT_WARN, build_report, exit_code, save_report
from h2_bridge.telemetry.poll_loop import run
from h2_bridge.telemetry.snapshot import SnapshotBuilder
from h2_bridge.utils import output_paths


def check(seconds=10.0, **kwargs):
    """Run checkup on a FakeSource; return {rule: RuleResult}."""
    source = FakeSource(duration=seconds, **kwargs)
    builder = SnapshotBuilder(source.topics, source.dropped)
    checkup = Checkup(builder)
    run(source, [builder, checkup], poll_secs=0)
    return checkup, {r.name: r for r in checkup.results()}


def bad_rules(results):
    return {name: r.status for name, r in results.items() if r.status in (Status.WARN, Status.FAIL)}


# ---------------------------------------------------------------- Scenarios


def test_healthy_robot_passes_everything():
    checkup, results = check()
    assert bad_rules(results) == {}
    assert results["dropped"].status == Status.NO_DATA  # not a live source: drops unknown
    assert checkup.overall() == Status.PASS


def test_stalled_topic_fails_topic_flow_only():
    def stop_battery(topic, t, data):
        return False if topic == "rt/lf/bmsstate" and after(4)(t) else None
    _, results = check(tweak=stop_battery)
    assert bad_rules(results) == {"topic_flow": Status.FAIL}
    (subject, obs, first, _), = results["topic_flow"].bad
    assert subject == "rt/lf/bmsstate" and "stale" in obs.message
    assert first - START == pytest.approx(4.5, abs=0.3)  # 4 s + stale after 0.5 s


def test_silent_topic_fails_after_the_grace_period():
    def no_left_hand(topic, t, data):
        return False if topic == "rt/dex5/left/state" else None
    _, results = check(tweak=no_left_hand)
    assert bad_rules(results) == {"topic_flow": Status.FAIL}
    assert "silent" in results["topic_flow"].bad[0][1].message


def test_slow_topic_warns():
    def half_rate(topic, t, data):
        if topic == "rt/lf/secondary_imu" and round((t - START) * 20) % 2:
            return False  # every other message: 10 Hz of 20 expected
    _, results = check(tweak=half_rate)
    assert bad_rules(results) == {"topic_flow": Status.WARN}


def test_nan_joint_fails_at_once():
    def nan_knee(topic, t, data):
        if topic == "rt/lf/lowstate" and after(3)(t):
            data["motor_state"][3]["q"] = None
    _, results = check(tweak=nan_knee)
    assert bad_rules(results) == {"joint_nan": Status.FAIL}
    assert results["joint_nan"].bad[0][0] == "L_knee"


def test_frozen_joint_warns_after_the_window():
    def freeze_elbow(topic, t, data):
        if topic == "rt/lf/lowstate" and after(1)(t):
            data["motor_state"][18]["q"] = 1.0
    _, results = check(seconds=10.0, tweak=freeze_elbow)
    assert bad_rules(results) == {"joint_frozen": Status.WARN}
    subject, _, first, _ = results["joint_frozen"].bad[0]
    assert subject == "L_elbow"
    assert first - START == pytest.approx(1.0 + limits.FROZEN_S, abs=0.3)


def test_a_stopped_body_topic_is_not_reported_as_frozen_joints():
    def stop_body(topic, t, data):
        return False if topic == "rt/lf/lowstate" and after(2)(t) else None
    _, results = check(seconds=12.0, tweak=stop_body)
    assert results["joint_frozen"].status == Status.PASS
    assert results["topic_flow"].status == Status.FAIL


def test_frozen_hand_motor_warns_after_the_window():
    def freeze_finger(topic, t, data):
        if topic == "rt/dex5/left/state" and after(1)(t):
            data["motor_state"][6]["q"] = 0.5  # left middle_mid_bend
    _, results = check(seconds=10.0, tweak=freeze_finger)
    assert bad_rules(results) == {"hand_frozen": Status.WARN}
    subject, _, first, _ = results["hand_frozen"].bad[0]
    assert subject == "left:middle_mid_bend"
    assert first - START == pytest.approx(1.0 + limits.HAND_FROZEN_S, abs=0.3)


def test_a_stopped_hand_topic_is_not_reported_as_frozen_motors():
    def stop_right_hand(topic, t, data):
        return False if topic == "rt/dex5/right/state" and after(2)(t) else None
    _, results = check(seconds=12.0, tweak=stop_right_hand)
    assert results["hand_frozen"].status == Status.PASS
    assert results["topic_flow"].status == Status.FAIL


def test_a_hand_motor_resting_on_its_stop_is_not_frozen():
    def at_stops(topic, t, data):  # values read off the real robot (limit_test, 2026-11-26)
        if topic == "rt/dex5/right/state":
            data["motor_state"][16]["q"] = -0.58676  # right thumb_base_swing on its stop
        if topic == "rt/dex5/left/state":
            data["motor_state"][2]["q"] = 1.69269  # left index_mid_bend fully curled
            data["motor_state"][3]["q"] = 1.39608  # left index_tip_bend fully curled
    assert bad_rules(check(seconds=10.0, tweak=at_stops)[1]) == {}


def test_joint_at_its_limit_warns_and_forced_past_it_fails():
    upper = 2.53025  # L_knee's upper limit (robot/joints.py)
    def knee(offset):
        def tweak(topic, t, data):
            if topic == "rt/lf/lowstate":  # offset from the limit, with noise so it isn't also "frozen"
                data["motor_state"][3]["q"] = upper + offset + 0.001 * ((t - START) * 20 % 3)
        return tweak
    assert bad_rules(check(tweak=knee(-0.05))[1]) == {}  # 0.05 inside: fine (the closest a healthy joint came)
    assert bad_rules(check(tweak=knee(-0.01))[1]) == {"joint_limits": Status.WARN}  # at the limit
    assert bad_rules(check(tweak=knee(0.005))[1]) == {"joint_limits": Status.WARN}  # on the stop, within the noise
    _, results = check(tweak=knee(0.1))  # forced 0.1 rad past it
    assert bad_rules(results) == {"joint_limits": Status.FAIL}
    assert "forced past its upper limit" in results["joint_limits"].bad[0][1].message


def test_a_joint_reaching_its_limit_shows_within_half_a_second():
    def push_elbow(topic, t, data):
        if topic == "rt/lf/lowstate" and after(3)(t):
            data["motor_state"][18]["q"] = 3.0717795 + 0.05 + 0.001 * ((t - START) * 20 % 3)  # L_elbow past its limit
    _, results = check(tweak=push_elbow)
    _, _, first, _ = results["joint_limits"].bad[0]
    assert first - START == pytest.approx(3.0, abs=0.3)  # counted from when it started


def test_motor_error_bits_warn():
    def error_bits(topic, t, data):
        if topic == "rt/dex5/right/state":
            data["motor_state"][5]["motorstate"] = 0x4
    _, results = check(tweak=error_bits)
    assert bad_rules(results) == {"motor_errors": Status.WARN}
    assert results["motor_errors"].bad[0][0] == "right:middle_knuckle_bend"


def test_motor_error_bits_are_named_from_the_docs():
    def overheat(topic, t, data):
        if topic == "rt/lf/lowstate":
            data["motor_state"][18]["motorstate"] = 0x204  # Sustained Overvoltage + Winding Overheating
    _, results = check(tweak=overheat)
    subject, obs, *_ = results["motor_errors"].bad[0]
    assert subject == "L_elbow"
    assert obs.message == "motorstate 0x204: Sustained Overvoltage, Winding Overheating"


def test_ab_mode_skips_the_ankle_and_waist_angles():
    """In AB mode (mode_pr 1) the ankles' and waist's q is a raw motor position: no limit or IMU check on them."""
    def ab_mode(topic, t, data):
        if topic == "rt/lf/lowstate":
            data["mode_pr"] = 1
            data["motor_state"][4]["q"] = 5.0 + 0.001 * ((t - START) * 20 % 3)   # L_ankle_roll: far outside its "limits"
            data["motor_state"][13]["q"] = 2.0 + 0.001 * ((t - START) * 20 % 3)  # waist_roll: would break the IMU check
    _, results = check(tweak=ab_mode)
    assert bad_rules(results) == {}
    assert results["imu_agreement"].status == Status.NO_DATA

    def ab_mode_elbow_past(topic, t, data):  # ... but every other joint is still checked
        ab_mode(topic, t, data)
        if topic == "rt/lf/lowstate":
            data["motor_state"][18]["q"] = 3.2 + 0.001 * ((t - START) * 20 % 3)
    assert bad_rules(check(tweak=ab_mode_elbow_past)[1]) == {"joint_limits": Status.FAIL}


def test_hand_error_warns():
    def hand_error(topic, t, data):
        if topic == "rt/dex5/left/state":
            data["error"] = [3, 0]
    assert bad_rules(check(tweak=hand_error)[1]) == {"hand_errors": Status.WARN}


def test_bad_cell_spread_warns_then_fails():
    def spread(mv):
        def tweak(topic, t, data):
            if topic == "rt/lf/bmsstate":
                data["cell_vol"][0] -= mv
        return tweak
    assert bad_rules(check(tweak=spread(60))[1]) == {"cell_spread": Status.WARN}
    assert bad_rules(check(tweak=spread(150))[1]) == {"cell_spread": Status.FAIL}


def test_low_battery_warns_then_fails():
    def soc(value):
        def tweak(topic, t, data):
            if topic == "rt/lf/bmsstate":
                data["soc"] = value
        return tweak
    assert bad_rules(check(tweak=soc(15))[1]) == {"charge": Status.WARN}
    assert bad_rules(check(tweak=soc(5))[1]) == {"charge": Status.FAIL}


def test_imus_disagreeing_beyond_the_waist_fails():
    def tilt_torso(topic, t, data):
        if topic == "rt/lf/secondary_imu":
            data["rpy"][1] += 0.4  # pitch off by 0.4 rad with the waist not moving
    _, results = check(tweak=tilt_torso)
    assert bad_rules(results) == {"imu_agreement": Status.FAIL}
    assert results["imu_agreement"].bad[0][0] == "IMU pitch"


def test_yaw_drift_between_the_imus_is_ignored():
    def drift(topic, t, data):
        if topic == "rt/lf/secondary_imu":
            data["rpy"][2] += 1.0
    assert bad_rules(check(tweak=drift)[1]) == {}


def test_dropped_messages_warn_on_a_live_source():
    dropped = {name: 0 for name in ("rt/lf/lowstate", "rt/lf/secondary_imu", "rt/lf/bmsstate",
                                    "rt/lf/mainboardstate", "rt/dex5/left/state", "rt/dex5/right/state")}
    dropped["rt/dex5/left/state"] = 12
    _, results = check(dropped=dropped)
    assert bad_rules(results) == {"dropped": Status.WARN}


# ---------------------------------------------------------------- Flagging fast, without flicker


def test_faults_are_flagged_on_the_first_poll_after_they_start():
    """No waiting: a fault starting at 3.0 s counts from the poll that first sees it (polls every 0.25 s)."""
    cases = {
        "joint_limits": lambda topic, t, data: data["motor_state"][18].update(q=3.0717795 + 0.05 + 0.001 * ((t - START) * 20 % 3))
        if topic == "rt/lf/lowstate" and after(3)(t) else None,
        "cell_spread": lambda topic, t, data: data["cell_vol"].__setitem__(0, data["cell_vol"][0] - 60)
        if topic == "rt/lf/bmsstate" and after(3)(t) else None,
        "motor_errors": lambda topic, t, data: data["motor_state"][0].update(motorstate=1)
        if topic == "rt/lf/lowstate" and after(3)(t) else None,
    }
    for rule, tweak in cases.items():
        _, results = check(tweak=tweak)
        _, _, first, _ = results[rule].bad[0]
        assert 3.0 <= first - START <= 3.25, rule


def test_band_flags_at_once_and_clears_only_past_its_margin():
    from h2_bridge.checkup.rules.bands import band
    memory, grade = {}, lambda v: band(memory, "x", v, warn=50, fail=100, margin=10).value
    assert [grade(v) for v in (49, 50, 45, 41, 39)] == ["pass", "warn", "warn", "warn", "pass"]
    assert [grade(v) for v in (100, 95, 89, 39)] == ["fail", "fail", "warn", "pass"]


def test_band_works_when_lower_is_worse():
    from h2_bridge.checkup.rules.bands import band
    memory, grade = {}, lambda v: band(memory, "soc", v, warn=20, fail=10, margin=2, higher_is_bad=False).value
    assert [grade(v) for v in (21, 20, 21, 22, 23, 10, 11, 13)] == ["pass", "warn", "warn", "warn", "pass", "fail", "fail", "warn"]


def test_a_value_hovering_at_its_threshold_is_one_steady_warning():
    def hover(topic, t, data):  # the spread alternates 49 / 52 mV every message
        if topic == "rt/lf/bmsstate":
            data["cell_vol"][0] -= 47 if round((t - START) * 20) % 2 else 50
    checkup, results = check(tweak=hover)
    assert results["cell_spread"].status == Status.WARN
    assert len(checkup.findings()) == 1  # still on at the end: never flickered off


# ---------------------------------------------------------------- Debouncing


class _Script:
    """A fake builder whose snapshot is just a time: drives one scripted rule."""

    def __init__(self):
        self.t = START

    def snapshot(self, now):
        return type("Snap", (), {"t": now})()


def _scripted(statuses, hold_s=1.0, clear_s=2.0, step=0.25):
    """Run a rule that reports `statuses[i]` on poll i; return the engine."""
    calls = iter(statuses)
    rule = Rule("scripted", "Scripted", "", lambda snap, memory: [Observation("x", next(calls))],
                hold_s=hold_s, clear_s=clear_s)
    checkup = Checkup(_Script(), rules=[rule])
    for i in range(len(statuses)):
        checkup.add([], START + i * step)
    return checkup


def test_a_short_blip_never_counts():
    checkup = _scripted([Status.PASS] * 4 + [Status.WARN] * 3 + [Status.PASS] * 4)  # 0.75 s < hold 1 s
    assert checkup.overall() == Status.PASS


def test_a_held_problem_counts_from_when_it_started_and_clears_late():
    checkup = _scripted([Status.PASS] * 4 + [Status.WARN] * 8 + [Status.PASS] * 4)  # 2 s of warn
    assert checkup.overall() == Status.WARN
    (_, _, first, _), = checkup.results()[0].bad
    assert first - START == pytest.approx(1.0)  # when the warn began, not when it had held
    assert checkup.findings()  # 1 s of pass < clear 2 s: still counting


def test_a_flickering_value_does_not_flicker_the_finding():
    flicker = [Status.WARN, Status.PASS] * 10
    checkup = _scripted([Status.WARN] * 8 + flicker)  # warn held, then hovering at the limit
    assert len(checkup.findings()) == 1


# ---------------------------------------------------------------- Report and exit codes


def test_report_and_exit_codes(tmp_path, monkeypatch):
    from datetime import datetime

    monkeypatch.setattr(output_paths, "OUTPUT_DIR", tmp_path)
    started = datetime(2026, 11, 26, 14, 0, 0).astimezone()

    checkup, _ = check()
    report = build_report(checkup, started, {"kind": "replay", "file": "x.jsonl.gz"})
    assert report["overall"] == "pass" and exit_code(report) == EXIT_PASS

    def low(topic, t, data):
        if topic == "rt/lf/bmsstate":
            data["soc"] = 15
    report = build_report(check(tweak=low)[0], started, {"kind": "live", "interface": "test0", "domain_id": 0})
    assert exit_code(report) == EXIT_WARN
    finding = next(r for r in report["rules"] if r["rule"] == "charge")["findings"][0]
    assert finding["value"] == 15 and finding["limit"] == limits.SOC_WARN

    path = save_report(report, "checkup", "test0", started)
    assert path.parent == tmp_path / "checkup" / "2026-11-26"
    assert json.loads(path.read_text())["overall"] == "warn"

    def nan(topic, t, data):
        if topic == "rt/lf/lowstate":
            data["motor_state"][0]["q"] = None
    assert exit_code(build_report(check(tweak=nan)[0], started, {"kind": "replay", "file": "x"})) == EXIT_FAIL
