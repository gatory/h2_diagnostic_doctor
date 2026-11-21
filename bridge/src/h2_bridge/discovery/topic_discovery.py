import time


def discover_publishers(iface="eth10", domain=0, secs=10):
    """Discover available publishers and their topics in the system.

    Parameters
    -----------
    iface: str
        The network interface to use for discovery.
    domain: int
        The DDS domain to discover topics in.
    secs: int
        The number of seconds to wait for topic discovery.

    Returns
    -------
    topics: dict
        A dictionary mapping topic names to their information.    
    """

    from cyclonedds.builtin import BuiltinDataReader, BuiltinTopicDcpsPublication
    from cyclonedds.domain import Domain, DomainParticipant

    # Chose to setup CycloneDDS configuration instead using the unitree_sdkpy for independent configuration.
    config_xml = f"""
    <?xml version="1.0" encoding="UTF-8" ?>
    <CycloneDDS>
        <Domain Id="any">
            <General>
                <Interfaces>
                    <NetworkInterface name="{iface}" priority="default" multicast="default"/>
                </Interfaces>
            </General>
            <Tracing>
                <Verbosity>config</Verbosity>
                <OutputFile>/tmp/cdds.LOG</OutputFile>
            </Tracing>
        </Domain>
    </CycloneDDS>
    """

    dds_domain = Domain(domain_id=domain, config=config_xml)
    dp = DomainParticipant(domain)
    reader = BuiltinDataReader(dp, BuiltinTopicDcpsPublication)


    topics = {}
    deadline = time.monotonic() + secs

    while time.monotonic() < deadline:
        # using take() instead of read() so that we take it out of the topic queue don't get the same data multiple times
        for endpoint in reader.take(256):
            name = getattr(endpoint, "topic_name", None)
            if not name:
                continue

            entry = topics.setdefault(name, {"msg_type": endpoint.type_name, "writers": set(), "participants": set()})
            entry["writers"].add(str(endpoint.key))
            entry["participants"].add(str(endpoint.participant_key))
        
        time.sleep(0.1)  # Sleep briefly to avoid busy waiting

        """ Example of the returned topics dictionary:
            topics = {
                "rt/lowstate": {                                        # key: the topic name (a string)
                    "msg_type": "unitree_hg::msg::dds_::LowState_",     # a string
                    "writers": {"3f2a...", "9c1b..."},                  # a set of writer IDs
                    "participants": {"a7e0..."},                        # a set of participant IDs
                },
                "rt/lf/bmsstate": {
                    "msg_type": "...",
                    "writers": {...},
                    "participants": {...},
                },
            }
        """
    return topics

if __name__ == "__main__":
    topics = discover_publishers()
    for name, info in topics.items():
        print(f"Topic: {name}, Type: {info['msg_type']}, Writers: {len(info['writers'])}, Participants: {len(info['participants'])}")