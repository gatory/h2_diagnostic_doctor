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
        Example:
        {
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

    from cyclonedds.builtin import BuiltinDataReader, BuiltinTopicDcpsPublication

    from h2_bridge.dds import init_dds, make_participant

    init_dds(iface, domain)
    dp = make_participant()
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

    return topics

def get_topics_table(topics, title="Discovered DDS Topics"):
    """Build a rich Table from the dict returned by discover_publishers().
    
    Parameters
    ----------
    topics: dict
        The dictionary returned by discover_publishers().
    title: str

    Returns
    -------
    table: rich.table.Table
        A rich Table object representing the discovered topics.
    """
    from rich.table import Table

    table = Table(title=title, show_lines=False, header_style="bold cyan")
    table.add_column("Topic", style="bold")
    table.add_column("Message Type", style="magenta")
    table.add_column("Writers", justify="right", style="green")
    table.add_column("Participants", justify="right", style="yellow")

    for name in sorted(topics):
        info = topics[name]
        table.add_row(
            name,
            info["msg_type"],
            str(len(info["writers"])),
            str(len(info["participants"])),
        )

    table.caption = f"{len(topics)} topic(s)"
    return table

def save_topics_to_file(topics, filename=None):
    """Save the discovered topics to a JSON file.

    Parameters
    ----------
    topics: dict
        The dictionary returned by discover_publishers().
    filename: str
        The name of the file to save the topics to.

    Returns
    -------
    filename: str
        The path the topics were written to.
    """
    import json

    if not filename:
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = f"discovered_topics_{timestamp}.json"


    # sets aren't JSON serializable, so convert them to sorted lists
    serializable = {
        name: {k: sorted(v) if isinstance(v, set) else v for k, v in info.items()}
        for name, info in topics.items()
    }

    with open(filename, "w") as f:
        json.dump(serializable, f, indent=4)

    return filename


if __name__ == "__main__":
    from rich.console import Console

    console = Console()
    with console.status("Discovering publishers..."):
        topics = discover_publishers()

    if topics:
        console.print(get_topics_table(topics))
    else:
        console.print("[bold red]No publishers discovered.[/] Check the interface and domain ID.")