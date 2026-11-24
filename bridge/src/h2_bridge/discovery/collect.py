"""Collect one discovery Snapshot from the DDS network, and simple views of it.

Listens to the three DDS built-in discovery topics for a while and records
what it sees, without grouping or interpreting it (see models.py):

    DCPSParticipant   -> Participant  (one per DDS connection, with its properties)
    DCPSPublication   -> Endpoint(kind="writer")
    DCPSSubscription  -> Endpoint(kind="reader")

group_by_topic(), endpoints_by_participant(), participant_ips(), save_snapshot()
and load_snapshot() work on a finished Snapshot.
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
        for sample in participant_reader.take(256):
            p = _to_participant(sample)
            participants[p.key] = p
        for sample in writer_reader.take(256):
            e = _to_endpoint(sample, "writer")
            endpoints[e.key] = e
        for sample in reader_reader.take(256):
            e = _to_endpoint(sample, "reader")
            endpoints[e.key] = e
        time.sleep(0.1)  # don't busy-wait

    # Drop this process's own participants and everything they own.
    own = {key for key, p in participants.items() if _is_own(p)}

    return Snapshot(
        taken_at=taken_at,
        host=socket.gethostname(),
        iface=interface,
        domain=domain_id,
        duration_s=secs,
        participants=[p for key, p in participants.items() if key not in own],
        endpoints=[e for e in endpoints.values() if e.participant_key not in own],
    )


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


def group_by_topic(snapshot):
    """Group a Snapshot's endpoints by topic (the summary `discovery topics` and `show` print).

    Returns
    -------
    dict
        {topic_name: {"types": set of type names,
                      "writers": [Endpoint, ...],
                      "readers": [Endpoint, ...]}}
        A topic with readers but no writers means someone is listening
        for data nobody publishes (e.g. a command topic with no controller).
    """
    topics = {}
    for e in snapshot.endpoints:
        entry = topics.setdefault(e.topic_name, {"types": set(), "writers": [], "readers": []})
        entry["types"].add(e.type_name)
        entry[e.kind + "s"].append(e)  # "writer" -> "writers", "reader" -> "readers"
    return topics


def endpoints_by_participant(snapshot):
    """Group a Snapshot's endpoints by the participant that owns them.

    Returns {participant_key: [Endpoint, ...]}; participants with no endpoints are left out.
    """
    owned = {}
    for e in snapshot.endpoints:
        owned.setdefault(e.participant_key, []).append(e)
    return owned


def participant_ips(participant):
    """The unicast IP addresses a participant announced, e.g. ["192.168.123.161"].

    Reads CycloneDDS's __NetworkAddresses property, which looks like
    "udp/239.255.0.1:7400@3,udp/192.168.123.161:49394@3". Multicast group
    addresses (224.x to 239.x) are shared by everyone, so they're skipped.
    Empty if the property is missing (e.g. a non-CycloneDDS program).
    """
    ips = []
    for address in participant.properties.get("__NetworkAddresses", "").split(","):
        # "udp/192.168.123.161:49394@3" -> "192.168.123.161"
        if "/" not in address or ":" not in address:
            continue
        ip = address.split("/", 1)[1].rsplit(":", 1)[0]
        first_octet = ip.split(".")[0]
        if first_octet.isdigit() and 224 <= int(first_octet) <= 239:
            continue
        if ip not in ips:
            ips.append(ip)
    return ips


def save_snapshot(snapshot, name="snapshot"):
    """Write a Snapshot as JSON to the outputs folder and return the path.

    The folder is fixed; `name` only sets the start of the file name.
    The time is when the run started:
    outputs/discovery/<date>/<name>_<time>_<interface>.json
    """
    import json
    from dataclasses import asdict

    from h2_bridge.outputs import output_path

    started = datetime.fromisoformat(snapshot.taken_at)
    path = output_path("discovery", name, snapshot.iface, when=started)

    with open(path, "w") as f:
        json.dump(asdict(snapshot), f, indent=2)
    return path


def load_snapshot(path):
    """Read a Snapshot back from a JSON file written by save_snapshot().

    Raises ValueError if the file isn't a snapshot (wrong JSON shape).
    """
    import json

    with open(path) as f:
        data = json.load(f)

    try:
        return Snapshot(
            # The run info fields (taken_at, host, ...) map 1:1 onto Snapshot's fields.
            **{k: v for k, v in data.items() if k not in ("participants", "endpoints")},
            participants=[Participant(**p) for p in data["participants"]],
            endpoints=[Endpoint(**e) for e in data["endpoints"]],
        )
    except (KeyError, TypeError) as e:  # missing or unexpected fields
        raise ValueError(f"{path} is not a discovery snapshot: {e}") from None
