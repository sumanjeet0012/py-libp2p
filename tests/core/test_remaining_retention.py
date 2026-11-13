"""High-churn regressions for histories, waiters and optional resource APIs."""

from types import SimpleNamespace
from typing import Any

import pytest
import trio
from trio.testing import wait_all_tasks_blocked

from libp2p.peer.id import ID
from libp2p.peer.peerdata import PeerData
from libp2p.pubsub.gossipsub import GossipSub
from libp2p.pubsub.pubsub import Pubsub, ValidationCache, ValidationResult
from libp2p.rcmgr import Direction, ResourceManager
from libp2p.rcmgr.rate_limiter import (
    RateLimitConfig,
    RateLimiter,
    RateLimitScope,
    RateLimitStrategy,
)


def make_pubsub():
    host: Any = SimpleNamespace(
        get_network=lambda: SimpleNamespace(register_notifee=lambda *args: None),
        get_id=lambda: ID(b"local"),
        set_stream_handler=lambda *args: None,
    )
    router = GossipSub([], 6, 4, 12)
    return Pubsub(host, router, strict_signing=False), router


def waiter(kind):
    pubsub, router = make_pubsub()
    if kind == "peer":
        return pubsub._peer_added_events, lambda pid, timeout: pubsub.wait_for_peer(
            pid, timeout
        )
    if kind == "subscription":
        return (
            pubsub._subscription_events,
            lambda pid, timeout: pubsub.wait_for_subscription(pid, "topic", timeout),
        )
    return router._mesh_peer_events, lambda pid, timeout: router.wait_for_mesh(
        pid, "topic", timeout
    )


@pytest.mark.trio
@pytest.mark.parametrize("kind", ["peer", "subscription", "mesh"])
async def test_timed_out_waiters_release_registry_entries(kind):
    registry, wait = waiter(kind)
    for i in range(1000):
        with pytest.raises(trio.TooSlowError):
            await wait(ID(i.to_bytes(32, "big")), 0)
        assert not registry


@pytest.mark.trio
@pytest.mark.parametrize("kind", ["peer", "subscription", "mesh"])
async def test_one_cancelled_waiter_does_not_orphan_another(kind):
    registry, wait = waiter(kind)
    done = trio.Event()
    peer = ID(b"peer")

    async def remaining():
        await wait(peer, 5)
        done.set()

    async with trio.open_nursery() as nursery:
        nursery.start_soon(remaining)
        await wait_all_tasks_blocked()
        event = next(iter(registry.values()))
        with trio.move_on_after(0) as scope:
            await wait(peer, 5)
        assert scope.cancelled_caught
        assert next(iter(registry.values())) is event
        event.set()
    assert done.is_set()
    assert not registry


def test_validation_overwrites_do_not_accumulate_lru_entries():
    cache = ValidationCache(max_size=4)
    for i in range(1000):
        cache.put(b"same", ValidationResult(True, float(i)))
    assert len(cache.cache) == len(cache.access_order) == 1


def test_protocol_updates_are_idempotent_and_keep_order():
    data = PeerData()
    for _ in range(1000):
        data.add_protocols(["/a", "/b", "/a"])
    assert data.get_protocols() == ["/a", "/b"]
    data.set_protocols(["/b", "/a", "/b"])
    assert data.get_protocols() == ["/b", "/a"]


@pytest.mark.parametrize(
    "strategy",
    [
        RateLimitStrategy.TOKEN_BUCKET,
        RateLimitStrategy.ADAPTIVE,
        RateLimitStrategy.FIXED_WINDOW,
        RateLimitStrategy.SLIDING_WINDOW,
    ],
)
def test_every_rate_strategy_bounds_entity_state(strategy):
    limiter = RateLimiter(
        RateLimitConfig(
            strategy=strategy,
            scope=RateLimitScope.PER_PEER,
            max_peers=4,
        )
    )
    for i in range(1000):
        limiter.try_allow(peer_id=ID(i.to_bytes(32, "big")), current_time=1000 + i)
    assert len(limiter._last_request_times) <= 4
    assert len(limiter._window_counts) <= 4
    assert len(limiter._token_buckets) <= 4


@pytest.mark.parametrize("limits", [(0, 1, 1), (1, 0, 1), (1, 1, 0)])
def test_entity_tracking_limits_must_be_positive(limits):
    with pytest.raises(ValueError, match="tracking limits"):
        RateLimitConfig(
            max_peers=limits[0], max_connections=limits[1], max_protocols=limits[2]
        )


def manager():
    return ResourceManager(
        enable_metrics=False,
        enable_connection_tracking=False,
        enable_rate_limiting=False,
        enable_circuit_breaker=False,
        enable_graceful_degradation=False,
    )


def test_scoped_resources_release_zero_counters_after_churn():
    rm = manager()
    rm.set_service_stream_limit("service", 2)
    rm.set_service_peer_stream_limit("service", 2)
    rm.set_protocol_stream_limit("protocol", 2)
    rm.set_protocol_peer_stream_limit("protocol", 2)
    for i in range(1000):
        assert rm.acquire_scoped_stream(
            str(i), Direction.OUTBOUND, "service", "protocol"
        )
        rm.release_scoped_stream(str(i), Direction.OUTBOUND, "service", "protocol")
    assert not rm._service_stream_counts
    assert not rm._service_peer_stream_counts
    assert not rm._protocol_stream_counts
    assert not rm._protocol_peer_stream_counts
    assert rm._current_streams == 0


@pytest.mark.parametrize(
    "denied_scope", ["service", "service-peer", "protocol", "protocol-peer"]
)
def test_failed_scoped_acquisition_rolls_back_without_zero_entries(denied_scope):
    rm = manager()
    rm.set_service_stream_limit("service", 0 if denied_scope == "service" else 2)
    rm.set_service_peer_stream_limit(
        "service", 0 if denied_scope == "service-peer" else 2
    )
    rm.set_protocol_stream_limit("protocol", 0 if denied_scope == "protocol" else 2)
    rm.set_protocol_peer_stream_limit(
        "protocol", 0 if denied_scope == "protocol-peer" else 2
    )
    assert not rm.acquire_scoped_stream(
        "peer", Direction.OUTBOUND, "service", "protocol"
    )
    assert not rm._service_stream_counts
    assert not rm._service_peer_stream_counts
    assert not rm._protocol_stream_counts
    assert not rm._protocol_peer_stream_counts
    assert rm._current_streams == 0


def test_releasing_one_scope_preserves_another_active_owner():
    rm = manager()
    rm.set_service_stream_limit("service", 2)
    rm.set_service_peer_stream_limit("service", 2)
    rm.set_protocol_stream_limit("protocol", 2)
    rm.set_protocol_peer_stream_limit("protocol", 2)
    for peer in ["one", "two"]:
        assert rm.acquire_scoped_stream(peer, Direction.OUTBOUND, "service", "protocol")
    rm.release_scoped_stream("one", Direction.OUTBOUND, "service", "protocol")
    assert rm._service_stream_counts == {"service": 1}
    assert rm._service_peer_stream_counts == {("service", "two"): 1}
    assert rm._protocol_stream_counts == {"protocol": 1}
    assert rm._protocol_peer_stream_counts == {("protocol", "two"): 1}
    rm.release_scoped_stream("two", Direction.OUTBOUND, "service", "protocol")
    assert rm._current_streams == 0
