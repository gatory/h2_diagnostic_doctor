"""FSM facts: which of the robot's state machine ids are the modes the dashboard shows as gears.

    gear_of(601)    # "walk1"
    gear_of(3)      # None: Sit is a real state, just not one of the five gears

Source: `h2-doctor discovery modes --map` on the H2, 2026-11-27: each mode set with the
remote, the FSM id read 3 times, all stable. The names are the robot's own, from
LocoClient.GetAvailableFsmIds.

Plain data: the FSM poller (telemetry) and the server read it. The dashboard gets the
gear id, never the FSM numbers.
"""

# gear id -> (FSM id, the robot's name for it). Order: the flow, Zero torque -> ... -> Walk 2.
GEARS = {
    "zero_torque": (0, "Invalid"),  # the robot calls it "Invalid"; on the remote it's zero torque
    "damp": (1, "Passive"),
    "ready": (4, "FixStand"),
    "walk1": (601, "HybridWalk"),
    "walk2": (703, "PhaseWalk"),
}

# FSM id -> gear id.
_BY_FSM_ID = {fsm_id: gear for gear, (fsm_id, _) in GEARS.items()}

# FSM ids from here up are motion clips (BeyondMimic_..., HumanMimic_...), ~250 on the H2.
MOTION_CLIP_IDS = 100000


def gear_of(fsm_id):
    """The gear id for an FSM id, or None if it isn't one of the five gears (Sit, Protection, a mimic clip...)."""
    return _BY_FSM_ID.get(fsm_id)
