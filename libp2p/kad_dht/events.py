"""Event definitions for the Kademlia DHT module.

Held in a dedicated module (rather than in ``kad_dht.py``) so that
``peer_routing``, ``provider_store`` and ``value_store`` can import the
event type without creating a circular import with ``kad_dht.py``.
"""


class KadDhtEvent:
    """A Kad-DHT event, emitted on the host's event bus.

    One event object carries a single occurrence; boolean flags mark which
    kind of event it is and the remaining fields carry its payload.
    """

    peer_id: str | None = None

    # Inbound (server-side request handling)
    inbound: bool = False
    find_node: bool = False
    get_value: bool = False
    put_value: bool = False
    get_providers: bool = False
    add_provider: bool = False

    # Outbound (client-side operations)
    lookup: bool = False
    provide: bool = False
    find_providers: bool = False
    put_value_out: bool = False
    get_value_out: bool = False
    find_peer: bool = False
    refresh: bool = False
    republish: bool = False

    # Operational / defensive events
    rate_limited: bool = False
    stream_reset: bool = False
    routing_table: bool = False

    # Fields
    key: str | None = None
    target: str | None = None
    duration_ms: float | None = None
    peers_queried: int | None = None
    peers_found: int | None = None
    peers_announced: int | None = None
    providers_found: int | None = None
    peers_stored: int | None = None
    value_found: bool | None = None
    success: bool | None = None
    record_type: str | None = None
    count: int | None = None
    errors: int | None = None
    reason: str | None = None
