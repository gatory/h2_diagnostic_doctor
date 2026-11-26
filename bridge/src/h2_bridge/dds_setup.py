"""Global DDS setup for the whole bridge.
    
Sets up the DDS domain and interface to establish a connection with CycloneDDS
and configure the DDS domain participant. This is done once per process.

    init_dds("eth10", 0)
    participant = make_participant()   # for discovery's built-in readers
"""

# (interface, domain_id) once init_dds() has run, else None.
_initialized = None


class DDSError(Exception):
    """DDS could not be set up."""


def init_dds(interface, domain_id):
    """Start DDS on `interface` and `domain_id`. Safe to call more than once.

    Parameters
    ----------
    interface : str
        The network interface to use for DDS. Must be a valid interface on the host.
    domain_id : int
        The DDS domain ID to use. Must be the same as the robot's domain ID.
    
    Raises
    ------
    DDSError
        If DDS is already running on a different interface or domain ID, or if the
        CycloneDDS SDK fails to initialize.
    
    Note
    ----
    This function is idempotent: calling it multiple times with the same settings does nothing.
    """

    global _initialized

    if _initialized is not None:
        if _initialized != (interface, domain_id):
            raise DDSError(
                f"DDS is already running on {_initialized[0]} (domain {_initialized[1]}); "
                f"can't switch to {interface} (domain {domain_id}) in the same process"
            )
        return

    from unitree_sdk2py.core.channel import ChannelFactoryInitialize

    try:
        ChannelFactoryInitialize(domain_id, interface)
    except Exception as e:
        raise DDSError(f"could not start DDS on {interface!r} (domain {domain_id}): {e}") from e

    _initialized = (interface, domain_id)


def make_participant():
    """Return a new DomainParticipant on the domain init_dds() set up.

    The SDK keeps its own participant private, so discovery makes its own.
    Because the domain already exists, the new participant uses the SDK's
    config (interface etc.) automatically.
    """
    if _initialized is None:
        raise DDSError("call init_dds() before make_participant()")

    from cyclonedds.domain import DomainParticipant

    return DomainParticipant(_initialized[1])
