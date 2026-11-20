from time import time


def discover_topics(domain=0, secs=10):
    """
    Discover available topics in the system.

    Returns:
        list: A list of discovered topics.
    """

    from cyclonedds.builtin import BuiltinDataReader, BuiltinTopicDcpsPublication
    from cyclonedds.domain import DomainParticipant

    dp = DomainParticipant()
    reader = BuiltinDataReader(dp, BuiltinTopicDcpsPublication)


    topics = {}
    deadline = time.monotonic() + secs

    while time.monotonic() < deadline:
        for topic in reader.read(256):
            name = getattr(topic, "topic_name", None)
            if not name:
                continue

            entry = topics.setdefault(name, {"type_name": topic.type_name, "writers": set(), "participants": set()})

            entry["writers"].add(topic.key.value)
            entry["participants"].add(topic.participant_key.value)
            time.sleep(0.1)

    return topics

if __name__ == "__main__":
    topics = discover_topics()
    for name, info in topics.items():
        print(f"Topic: {name}, Type: {info['type_name']}, Writers: {len(info['writers'])}, Participants: {len(info['participants'])}")