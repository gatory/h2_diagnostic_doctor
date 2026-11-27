"""Query-only service calls: ask Unitree's services what the robot is doing, change nothing.

    init_dds("eth10", 0)
    queries = RobotQueries()
    queries.ask("fsm_id")        # Answer(name="fsm_id", code=0, value=4, seconds=0.012)
    queries.ask_all()            # every query in QUERIES, in order

The SDK's MotionSwitcherClient and LocoClient carry both getters and commands
(SelectMode, ReleaseMode, SetFsmId, Move...). This module is the only place
h2_bridge creates them, and it never hands them out: the only calls reachable
through it are the getters in QUERIES, each checked in the SDK to only read
(the allowlist in CLAUDE.md). Add one only after reading its SDK code.

A call sends one request on rt/api/<service>/request and waits for the answer
on .../response (up to `timeout_s`). Ask about once a second at most, never per poll.
Needs init_dds() first (it uses the SDK's DDS setup).
"""

import time
from dataclasses import dataclass

# name -> (service, SDK method, what it tells). All checked in unitree_sdk2py to be getters.
# GetPhase is on the allowlist too, but the SDK marks it deprecated, so it isn't asked.
QUERIES = {
    "motion_mode": ("motion_switcher", "CheckMode", "which controller has the robot (Unitree's mode name)"),
    "fsm_id": ("loco", "GetFsmId", "the locomotion state machine's current state id"),
    "fsm_mode": ("loco", "GetFsmMode", "the state machine's mode"),
    "available_fsms": ("loco", "GetAvailableFsmIds", "every FSM id with its name"),
    "balance_mode": ("loco", "GetBalanceMode", "balance mode"),
    "stand_height": ("loco", "GetStandHeight", "stand height"),
    "swing_height": ("loco", "GetSwingHeight", "foot swing height"),
    "arm_sdk": ("loco", "GetArmSdkStatus", "whether arm_sdk control is enabled"),
}

# The SDK's RPC error codes (unitree_sdk2py/rpc/internal.py), for messages.
ERROR_NAMES = {
    3001: "unknown error",
    3102: "couldn't send the request",
    3103: "API not registered",
    3104: "no answer (timeout)",
    3105: "answer to another API",
    3106: "bad answer data",
    3107: "invalid lease",
    3201: "service couldn't send",
    3202: "service internal error",
    3203: "service doesn't implement this API",
    3204: "bad parameter",
    3205: "lease denied",
    3206: "lease doesn't exist",
    3207: "lease already exists",
}


@dataclass(frozen=True)
class Answer:
    """One query's answer. `value` is None unless code is 0."""

    name: str
    code: int  # 0: answered; otherwise an RPC error (ERROR_NAMES)
    value: object  # whatever the SDK returned: an int, a dict, ([ids], [names]) for available_fsms
    seconds: float  # how long the call took

    @property
    def ok(self):
        return self.code == 0

    @property
    def error(self):
        """The error in words; "" when it answered."""
        return "" if self.ok else ERROR_NAMES.get(self.code, f"error {self.code}")


class RobotQueries:
    """The allowlisted getters, and nothing else. Create it after init_dds()."""

    def __init__(self, timeout_s=1.0, clients=None):
        """clients: {service: client}, for tests; by default the SDK's own clients."""
        if clients is None:
            from unitree_sdk2py.comm.motion_switcher.motion_switcher_client import MotionSwitcherClient
            from unitree_sdk2py.h2.loco.h2_loco_client import LocoClient

            clients = {"motion_switcher": MotionSwitcherClient(), "loco": LocoClient()}
            for client in clients.values():
                client.SetTimeout(timeout_s)
                client.Init()
        self.__clients = clients  # name-mangled: not meant to be reached from outside

    def ask(self, name):
        """Run query `name` (a key of QUERIES; anything else raises KeyError) and return its Answer."""
        service, method, _ = QUERIES[name]
        start = time.monotonic()
        try:
            result = getattr(self.__clients[service], method)()
        except Exception:  # the SDK raises on bad JSON in an answer
            return Answer(name, 3106, None, time.monotonic() - start)
        seconds = time.monotonic() - start
        code, rest = result[0], result[1:]
        if code != 0:
            return Answer(name, code, None, seconds)
        return Answer(name, code, rest[0] if len(rest) == 1 else tuple(rest), seconds)

    def ask_all(self):
        """Every query in QUERIES, in order."""
        return [self.ask(name) for name in QUERIES]
