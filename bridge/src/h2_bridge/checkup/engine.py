"""The checkup engine: runs every rule each poll and debounces them into findings.

    builder = SnapshotBuilder(source.topics, source.dropped)
    checkup = Checkup(builder)
    run(source, [builder, checkup], duration=10)   # the same poll loop as watch
    checkup.findings()      # what's wrong right now (debounced), worst first
    checkup.results()       # per rule, over the whole run: for the report
    checkup.overall()       # the worst status of the run

Debouncing (all on the source's clock, so a replay behaves like the live run):
an observation worse than a subject's current status only counts once it has
held for the rule's hold_s; a better one only once it has held for clear_s.
A value hovering at a limit therefore doesn't flicker, and a single odd message
doesn't become a finding (except for rules with hold_s 0, like NaN).
"""

from dataclasses import dataclass, field

from h2_bridge.checkup.models import Finding, Observation, Status
from h2_bridge.checkup.rules import RULES


@dataclass
class _Subject:
    """One (rule, subject) pair's debounce state and its worst moment so far."""

    current: Observation  # the status that counts right now
    since: float  # when `current` started counting
    candidate: Observation | None = None  # a different status waiting out hold_s / clear_s
    candidate_since: float = 0.0
    worst: Observation | None = None  # the worst counted observation of the run
    first_bad: float | None = None  # when it first counted as warn/fail
    last_bad: float | None = None  # the last time it counted as warn/fail


@dataclass
class RuleResult:
    """One rule over the whole run, for the report."""

    name: str
    title: str
    description: str
    status: Status  # the worst of its subjects; NO_DATA if it never had inputs
    bad: list = field(default_factory=list)  # [(subject, worst Observation, first_bad, last_bad)], warn/fail only
    checked: int = 0  # how many subjects it judged


class Checkup:
    """Poll-loop consumer: evaluates every rule on the builder's snapshot after each batch."""

    def __init__(self, builder, rules=RULES):
        self.builder = builder  # must come before this in the consumer list
        self.rules = list(rules)
        self._memory = {rule.name: {} for rule in self.rules}
        self._subjects = {rule.name: {} for rule in self.rules}  # rule -> subject -> _Subject
        self.started = None  # the source's clock at the first evaluation
        self.last = None  # ... and at the latest

    def add(self, messages, now):
        self.evaluate(self.builder.snapshot(now))

    def evaluate(self, snap):
        """Run every rule on one Snapshot and update the findings."""
        # The source's clock should never go backwards; if it does, don't let debouncing run backwards too.
        now = snap.t if self.last is None else max(snap.t, self.last)
        self.started = now if self.started is None else self.started
        self.last = now
        for rule in self.rules:
            observations = rule.check(snap, self._memory[rule.name])
            for obs in observations or ():
                self._track(rule, obs, now)

    def _track(self, rule, obs, now):
        subjects = self._subjects[rule.name]
        state = subjects.get(obs.subject)
        if state is None:  # first sight: a pass counts at once, anything worse waits out hold_s
            state = subjects[obs.subject] = _Subject(Observation(obs.subject, Status.PASS), now)
        if obs.status == state.current.status:
            state.current, state.candidate = obs, None  # same status: keep its newest message/value
        else:
            if state.candidate is None or state.candidate.status != obs.status:
                state.candidate, state.candidate_since = obs, now
            else:
                state.candidate = obs
            wait = rule.hold_s if obs.status.rank > state.current.status.rank else rule.clear_s
            if now - state.candidate_since >= wait:
                state.current, state.since, state.candidate = obs, state.candidate_since, None
        if state.current.status.rank > Status.PASS.rank:
            state.first_bad = state.since if state.first_bad is None else state.first_bad
            state.last_bad = now
        # The worst level so far, with the newest message at that level ("stale for 14.8 s", not 1.0 s).
        if state.worst is None or state.current.status.rank >= state.worst.status.rank:
            state.worst = state.current

    # ------------------------------------------------------------ Reading the results

    def findings(self):
        """What counts as wrong right now (warn/fail, debounced), worst first."""
        found = [
            Finding(rule, subject, s.current.status, s.current.message, s.current.value, s.current.limit, s.since)
            for rule, subjects in self._subjects.items()
            for subject, s in subjects.items()
            if s.current.status.rank > Status.PASS.rank
        ]
        return sorted(found, key=lambda f: (-f.status.rank, f.since))

    def status_of(self, rule, subject):
        """The status counting right now for one subject of one rule; None if it hasn't been judged."""
        state = self._subjects.get(rule, {}).get(subject)
        return None if state is None else state.current.status

    def results(self):
        """One RuleResult per rule, in rule order, over the whole run."""
        results = []
        for rule in self.rules:
            subjects = self._subjects[rule.name]
            if not subjects:
                results.append(RuleResult(rule.name, rule.title, rule.description, Status.NO_DATA))
                continue
            worst = max((s.worst.status for s in subjects.values()), key=lambda st: st.rank)
            bad = [(name, s.worst, s.first_bad, s.last_bad) for name, s in subjects.items()
                   if s.worst.status.rank > Status.PASS.rank]
            bad.sort(key=lambda item: -item[1].status.rank)
            results.append(RuleResult(rule.name, rule.title, rule.description, worst, bad, len(subjects)))
        return results

    def overall(self):
        """The worst status of the run over all rules (NO_DATA if no rule ever had inputs)."""
        statuses = [r.status for r in self.results() if r.status != Status.NO_DATA]
        return max(statuses, key=lambda st: st.rank) if statuses else Status.NO_DATA
