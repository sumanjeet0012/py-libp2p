from collections.abc import AsyncIterator
import logging
import secrets
import time
from typing import Any

import trio

from libp2p.abc import (
    IHost,
    INetConn,
    INetStream,
    INetwork,
    INotifee,
)
from libp2p.custom_types import (
    TProtocol,
)
from libp2p.io.exceptions import (
    IncompleteReadError,
)
from libp2p.io.utils import (
    read_exactly,
)
from libp2p.network.stream.exceptions import (
    StreamClosed,
    StreamEOF,
    StreamReset,
)
from libp2p.peer.id import ID as PeerID
from libp2p.rcmgr import ResourceManager

ID = TProtocol("/ipfs/ping/1.0.0")
SERVICE_NAME = "libp2p.ping"
PING_LENGTH = 32
RESP_TIMEOUT = 10

logger = logging.getLogger(__name__)


class PingEvent:
    peer_id: PeerID
    rtts: list[int] | None
    failure_error: Exception | None

    def __init__(
        self, peer_id: PeerID, rtts: list[int] | None, failure_error: Exception | None
    ):
        self.peer_id = peer_id
        self.rtts = rtts
        self.failure_error = failure_error


async def _handle_ping(stream: INetStream, peer_id: PeerID) -> bool:
    """
    Return a boolean indicating if we expect more pings from the peer at ``peer_id``.
    """
    try:
        with trio.fail_after(RESP_TIMEOUT):
            # NOTE: stream.read(n) is a *short read* -- both the Mplex and
            # Yamux muxed-stream implementations document/return "up to n
            # bytes currently available", not "exactly n bytes". A 32-byte
            # ping that a peer (or the OS/transport) delivers in more than
            # one chunk would otherwise be silently truncated here. Use
            # read_exactly() (already relied on by msgio/varint/yamux's own
            # frame parsing) to block until the full PING_LENGTH is in hand.
            payload = await read_exactly(stream, PING_LENGTH)
    except trio.TooSlowError as error:
        logger.debug("Timed out waiting for ping from %s: %s", peer_id, error)
        raise
    except StreamEOF:
        logger.debug("Other side closed while waiting for ping from %s", peer_id)
        return False
    except IncompleteReadError as error:
        if error.is_clean_close:
            # Peer closed the stream cleanly between pings; same as StreamEOF.
            logger.debug("Other side closed while waiting for ping from %s", peer_id)
            return False
        logger.debug(
            "Truncated ping from %s: expected %d bytes, got %d: %s",
            peer_id,
            error.expected_bytes,
            error.received_bytes,
            error,
        )
        raise
    except (StreamReset, Exception) as error:
        logger.debug("Error while waiting for ping from %s: %s", peer_id, error)
        raise

    logger.debug("Received ping from %s with data: 0x%s", peer_id, payload.hex())

    try:
        with trio.fail_after(RESP_TIMEOUT):
            await stream.write(payload)
    except trio.TooSlowError:
        logger.debug("Timed out writing ping response to %s", peer_id)
        raise
    except StreamClosed:
        logger.debug("Fail to respond to ping from %s: stream closed", peer_id)
        raise
    return True


async def perform_ping_roundtrip(
    stream: INetStream, cancel_scope: trio.CancelScope | None = None
) -> int:
    """
    Perform a single ping round-trip and return RTT in **milliseconds**.

    Public entry point for health probes and other callers that already
    negotiated ``/ipfs/ping/1.0.0`` on a stream.

    Matches go-libp2p's Result.RTT.Milliseconds() convention.
    Raises ValueError if the pong payload does not match the sent ping.
    Raises trio.TooSlowError if the peer takes longer than RESP_TIMEOUT seconds.
    """
    return await _ping(stream, cancel_scope=cancel_scope)


async def _ping(
    stream: INetStream, cancel_scope: trio.CancelScope | None = None
) -> int:
    """
    Perform a single ping and return the RTT in **milliseconds**.

    Matches go-libp2p's Result.RTT.Milliseconds() convention.
    Raises ValueError if the pong payload does not match the sent ping.
    Raises trio.TooSlowError if the peer takes longer than RESP_TIMEOUT seconds.
    """
    ping_bytes = secrets.token_bytes(PING_LENGTH)

    start = time.monotonic()

    with cancel_scope or trio.CancelScope():
        with trio.fail_after(RESP_TIMEOUT):
            await stream.write(ping_bytes)
            # See the matching note in _handle_ping: stream.read(n) may return
            # fewer than n bytes even on a healthy connection, so a naive
            # single read() here can misreport a short-but-correct pong as a
            # payload mismatch. read_exactly() blocks until PING_LENGTH bytes
            # are collected (or the connection genuinely closes/resets).
            try:
                pong_bytes = await read_exactly(stream, PING_LENGTH)
            except IncompleteReadError as error:
                if error.is_clean_close:
                    raise StreamEOF() from error
                raise

    rtt = int((time.monotonic() - start) * 1000)  # in milliseconds

    if ping_bytes != pong_bytes:
        logger.debug("invalid pong response")
        await stream.reset()
        raise ValueError(
            f"Ping payload mismatch: sent {ping_bytes.hex()!r}, "
            f"got {pong_bytes.hex()!r}"
        )

    return rtt


class PingService(INotifee):
    """
    PingService executes pings and returns RTT in milliseconds (ms).

    Matches go-libp2p convention: Result.RTT.Milliseconds().
    """

    def __init__(self, host: IHost, rcmgr: ResourceManager | None = None):
        self._host = host
        self._rcmgr = rcmgr
        self._outbound_streams: dict[PeerID, INetStream] = {}
        self._inbound_streams: dict[PeerID, set[INetStream]] = {}
        try:
            network = self._host.get_network()
            if hasattr(network, "register_notifee"):
                network.register_notifee(self)
        except Exception:
            pass

    async def aclose(self) -> None:
        """Unregister this service and terminate streams owned by it."""
        try:
            network = self._host.get_network()
            if hasattr(network, "remove_notifee"):
                network.remove_notifee(self)
        except Exception:
            logger.debug("Failed to unregister ping service", exc_info=True)
        finally:
            streams = set(self._outbound_streams.values())
            for inbound in self._inbound_streams.values():
                streams.update(inbound)
            self._outbound_streams.clear()
            self._inbound_streams.clear()

            # A cancelled probe must not leave its streams behind. Bound the
            # shield so a broken transport cannot stall DHT maintenance.
            with trio.move_on_after(5) as cleanup_scope:
                cleanup_scope.shield = True
                for stream in streams:
                    try:
                        await stream.reset()
                    except Exception:
                        logger.debug("Failed to reset ping stream", exc_info=True)

    async def opened_stream(self, network: "INetwork", stream: INetStream) -> None:
        pass

    async def closed_stream(self, network: "INetwork", stream: INetStream) -> None:
        for pid, s in list(self._outbound_streams.items()):
            if s is stream:
                self._outbound_streams.pop(pid, None)

    async def connected(self, network: "INetwork", conn: "INetConn") -> None:
        pass

    async def disconnected(self, network: "INetwork", conn: "INetConn") -> None:
        peer_id = getattr(getattr(conn, "muxed_conn", None), "peer_id", None)
        if peer_id is not None:
            cached = self._outbound_streams.get(peer_id)
            if cached is not None:
                cached_conn = getattr(cached, "swarm_conn", None)
                cached_muxed = getattr(cached, "muxed_conn", None)
                conn_muxed = getattr(conn, "muxed_conn", None)
                if (
                    cached_conn is None
                    or cached_conn == conn
                    or cached_muxed is None
                    or conn_muxed is None
                    or cached_muxed == conn_muxed
                    or getattr(cached, "is_closed", False)
                ):
                    self._outbound_streams.pop(peer_id, None)
            self._inbound_streams.pop(peer_id, None)

    async def listen(self, network: "INetwork", multiaddr: Any) -> None:
        pass

    async def listen_close(self, network: "INetwork", multiaddr: Any) -> None:
        pass

    async def handle_ping(self, stream: INetStream) -> None:
        """
        Respond to incoming ping requests until one side errors
        or closes the ``stream``.
        """
        peer_id = stream.muxed_conn.peer_id

        peer_streams = self._inbound_streams.setdefault(peer_id, set())
        if len(peer_streams) >= 2:
            logger.debug("Rejecting ping stream from %s: max 2 reached", peer_id)
            await stream.reset()
            return
        peer_streams.add(stream)

        try:
            while True:
                try:
                    should_continue = await _handle_ping(stream, peer_id)
                    if not should_continue:
                        await stream.close()
                        return
                except trio.TooSlowError:
                    # The peer simply stopped pinging within RESP_TIMEOUT -- this is
                    # not a protocol violation. go-libp2p's handler closes the
                    # stream when its own idle timer fires (rather than resetting),
                    # so match that: Reset signals an abnormal/error termination to
                    # the remote peer, which an idle timeout is not.
                    logger.debug(
                        "Idle timeout waiting for ping from %s, closing stream", peer_id
                    )
                    try:
                        await stream.close()
                    except Exception as close_error:
                        logger.debug(
                            "Error closing idle ping stream to %s: %s",
                            peer_id,
                            close_error,
                        )
                    return
                except Exception:
                    await stream.reset()
                    return
        finally:
            if peer_id in self._inbound_streams:
                self._inbound_streams[peer_id].discard(stream)
                if not self._inbound_streams[peer_id]:
                    self._inbound_streams.pop(peer_id, None)

    async def ping_iter(
        self,
        peer_id: PeerID,
        ping_amt: int = 1,
        cancel_scope: trio.CancelScope | None = None,
    ) -> AsyncIterator[int]:
        if ping_amt < 1:
            raise ValueError(f"ping_amt must be >= 1, got {ping_amt!r}")

        stream = self._outbound_streams.get(peer_id)
        # Check if cached stream is still usable. A stream may be closed
        # (connection dropped) or in reset state (protocol error). In both
        # cases we must create a fresh stream.
        needs_new = stream is None
        if stream is not None:
            is_closed = getattr(stream, "is_closed", False)
            if callable(is_closed):
                is_closed = is_closed()
            if is_closed:
                needs_new = True
            elif hasattr(stream, "_state"):
                if getattr(stream._state, "value", None) == "RESET":
                    needs_new = True
        if needs_new:
            stream = await self._host.new_stream(peer_id, [ID])
            self._outbound_streams[peer_id] = stream

        assert stream is not None
        event: PingEvent | None = None
        rtts: list[int] = []

        try:
            for _ in range(ping_amt):
                rtt = await _ping(stream, cancel_scope=cancel_scope)
                rtts.append(rtt)
                yield rtt
            # Keep the stream open for reuse across ping cycles.
            # Closing and reopening a QUIC stream per ping causes massive
            # C-level memory fragmentation (OpenSSL encrypt/decrypt buffers,
            # glibc malloc pools) that manifests as unbounded RSS growth.
            # The remote handle_ping() handler loops forever reading pings,
            # so the stream stays alive. QUIC idle timeout handles cleanup
            # if the connection dies.
            event = PingEvent(peer_id=peer_id, rtts=rtts, failure_error=None)
        except BaseException as error:
            # An outer fail_after delivers Cancelled here, not TooSlowError.
            # Drop ownership before any await, and shield transport cleanup.
            if self._outbound_streams.get(peer_id) is stream:
                self._outbound_streams.pop(peer_id, None)
            with trio.move_on_after(5) as cleanup_scope:
                cleanup_scope.shield = True
                try:
                    await stream.reset()
                except Exception:
                    logger.debug("Failed to reset ping stream", exc_info=True)
            if isinstance(error, Exception):
                event = PingEvent(peer_id=peer_id, rtts=None, failure_error=error)
            raise
        finally:
            if event is not None:
                self._host.get_event_bus().emit(event)

    async def ping(self, peer_id: PeerID, ping_amt: int = 1) -> list[int]:
        """
        Legacy support for callers expecting a list of RTTs.
        """
        rtts = []
        async for rtt in self.ping_iter(peer_id, ping_amt=ping_amt):
            rtts.append(rtt)
        return rtts


async def handle_ping(stream: INetStream) -> None:
    """
    Standalone ping stream handler (no shared state).

    Suitable for use as a ``StreamHandlerFn`` without creating a
    :class:`PingService` instance — e.g. in simple examples and tests.
    """
    peer_id = stream.muxed_conn.peer_id
    try:
        while True:
            should_continue = await _handle_ping(stream, peer_id)
            if not should_continue:
                await stream.close()
                return
    except StreamEOF:
        try:
            await stream.close()
        except Exception:
            pass
    except StreamReset:
        pass
    except Exception:
        try:
            await stream.reset()
        except Exception:
            pass
