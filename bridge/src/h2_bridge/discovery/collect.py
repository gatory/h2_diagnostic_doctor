"""Collect one discovery Snapshot from the DDS network.

Listens to the three DDS built-in discovery topics for a while and records
what it sees, without grouping or interpreting it (see models.py):

    DCPSParticipant   -> Participant  (one per DDS connection, with its properties)
    DCPSPublication   -> Endpoint(kind="writer")
    DCPSSubscription  -> Endpoint(kind="reader")

This is the only discovery module that touches DDS. 
Work with finished Snapshot lives in analysis.py (views of it) and persistence.py (save/load).
"""

import os
import socket
import time
from datetime import datetime

from h2_bridge.discovery.models import Endpoint, Participant, Snapshot


def collect_snapshot(interface, domain_id, secs=10):
    """Listen for `secs` seconds and return everything seen as a Snapshot.

    Parameters
    ----------
    interface : str
        Network interface to listen on.
    domain_id : int
        DDS domain ID to listen on.
    secs : float
        How long to listen. Longer catches programs that announce themselves slowly.

    Returns
    -------
    Snapshot
        Participants and endpoints of every *other* program; this process's
        own participants (the SDK's and discovery's) are left out.
    """
    from cyclonedds.builtin import (
        BuiltinDataReader,
        BuiltinTopicDcpsParticipant,
        BuiltinTopicDcpsPublication,
        BuiltinTopicDcpsSubscription,
    )

    from h2_bridge.dds import init_dds, make_participant

    taken_at = datetime.now().astimezone().isoformat(timespec="seconds")

    init_dds(interface, domain_id)
    dp = make_participant()
    participant_reader = BuiltinDataReader(dp, BuiltinTopicDcpsParticipant)
    writer_reader = BuiltinDataReader(dp, BuiltinTopicDcpsPublication)
    reader_reader = BuiltinDataReader(dp, BuiltinTopicDcpsSubscription)

    # Keyed by DDS key: the same entity can be announced more than once
    # (e.g. when its QoS changes); the latest announcement wins.
    participants = {}
    endpoints = {}

    deadline = time.monotonic() + secs
    while time.monotonic() < deadline:
        # take() removes samples from the reader's queue, so each is handled once.
        # Only real announcements count; "gone" notices are skipped (see _is_announcement).
        for sample in participant_reader.take(256):
            if _is_announcement(sample):
                p = _to_participant(sample)
                participants[p.key] = p
        for sample in writer_reader.take(256):
            if _is_announcement(sample):
                e = _to_endpoint(sample, "writer")
                endpoints[e.key] = e
        for sample in reader_reader.take(256):
            if _is_announcement(sample):
                e = _to_endpoint(sample, "reader")
                endpoints[e.key] = e
        time.sleep(0.1)  # don't busy-wait

    # Drop this process's own participants and everything they own.
    own = {key for key, p in participants.items() if _is_own(p)}

    return Snapshot(
        taken_at=taken_at,
        host=socket.gethostname(),
        interface=interface,
        domain_id=domain_id,
        duration_s=secs,
        participants=[p for key, p in participants.items() if key not in own],
        endpoints=[e for e in endpoints.values() if e.participant_key not in own],
    )


def _is_announcement(sample):
    """True for a real announcement, False for a "gone" notice.

    When a program leaves (or its lease runs out, ~10 s after it dies without
    saying goodbye), DDS sends a notice with only the key: valid_data is False,
    and qos is None. Discovery records what *existed* during the run, so a
    program that left stays listed with its last real announcement; noticing
    that something went quiet is telemetry's job.
    """
    return sample.sample_info.valid_data


def _to_participant(sample):
    """Turn a DCPSParticipant sample into a Participant."""
    from cyclonedds.qos import Policy

    # CycloneDDS programs announce __Hostname, __Pid, __ProcessName and
    # __NetworkAddresses as Property policies; other DDS vendors may send none.
    properties = {p.key: p.value for p in sample.qos if isinstance(p, Policy.Property)}
    return Participant(key=str(sample.key), properties=properties)


def _to_endpoint(sample, kind):
    """Turn a DCPSPublication / DCPSSubscription sample into an Endpoint."""
    return Endpoint(
        key=str(sample.key),
        participant_key=str(sample.participant_key),
        kind=kind,
        topic_name=sample.topic_name,
        type_name=sample.type_name,
        qos=sample.qos.asdict(),
        has_type_info=sample.type_id is not None,
    )


def _is_own(participant):
    """True if this participant belongs to this very process (same host and PID)."""
    props = participant.properties
    return props.get("__Pid") == str(os.getpid()) and props.get("__Hostname") == socket.gethostname()
