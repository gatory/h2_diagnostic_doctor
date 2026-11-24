"""Views of a finished Snapshot: grouping and interpreting its raw facts.

Pure functions: a Snapshot goes in, plain data comes out. No DDS and no
files, so they work on a live snapshot and a loaded one alike.

    group_by_topic(snapshot)            {topic: types, writers, readers}
    group_endpoints_by_participant(snapshot)  {participant_key: [Endpoint, ...]}
    get_participant_ips(participant)        ["192.168.123.161", ...]
"""


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


def group_endpoints_by_participant(snapshot):
    """Group a Snapshot's endpoints by the participant that owns them.

    Returns {participant_key: [Endpoint, ...]}; participants with no endpoints are left out.
    """
    owned = {}
    for e in snapshot.endpoints:
        owned.setdefault(e.participant_key, []).append(e)
    return owned


def get_participant_ips(participant):
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
