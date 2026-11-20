import time

def discover_topics(domain=0, secs=10):
    """Discover available topics in the system.

    Parameters
    -----------
    domain: int
        The DDS domain to discover topics in.
    secs: int
        The number of seconds to wait for topic discovery.

    Returns
    -------
    topics: dict
        A dictionary mapping topic names to their information.

    Raises
    ------
    None
    
    """

    from cyclonedds.builtin import BuiltinDataReader, BuiltinTopicDcpsPublication
    from cyclonedds.domain import DomainParticipant

    dp = DomainParticipant(domain)
    reader = BuiltinDataReader(dp, BuiltinTopicDcpsPublication)


    topics = {}
    deadline = time.monotonic() + secs

    while time.monotonic() < deadline:
        # using take() instead of read() so that we take it out of the topic queue don't get the same data multiple times
        for topic in reader.take(256):
            name = getattr(topic, "topic_name", None)
            if not name:
                continue

            entry = topics.setdefault(name, {"type_name": topic.type_name, "writers": set(), "participants": set()})

            print(type(topic), topic)

        time.sleep(0.1)  # Sleep briefly to avoid busy waiting

    return topics

if __name__ == "__main__":
    topics = discover_topics()
    # for name, info in topics.items():
    #     print(f"Topic: {name}, Type: {info['type_name']}, Writers: {len(info['writers'])}, Participants: {len(info['participants'])}")