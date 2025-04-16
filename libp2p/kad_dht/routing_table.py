import heapq
from typing import (
    Optional,
)

from libp2p.peer.id import ID as PeerID

KBUCKET_SIZE = 20


def xor_distance(a: bytes, b: bytes) -> int:
    """Calculate XOR distance between two peer IDs."""
    return int.from_bytes(a, "big") ^ int.from_bytes(b, "big")


class RoutingTable:
    def __init__(self, local_peer_id: PeerID, kbucket_size: int = KBUCKET_SIZE):
        self.local_peer_id = local_peer_id
        self.kbucket_size = kbucket_size
        self.peers: list[PeerID] = []

    def add(self, peer_id: PeerID) -> None:
        """Add a peer to the routing table if not already present and not self."""
        if peer_id == self.local_peer_id:
            return
        if peer_id in self.peers:
            return
        if len(self.peers) < self.kbucket_size:
            self.peers.append(peer_id)
        else:
            pass

    def remove(self, peer_id: PeerID) -> None:
        """Remove a peer from the routing table."""
        try:
            self.peers.remove(peer_id)
        except ValueError:
            pass

    def find(self, peer_id: PeerID) -> Optional[PeerID]:
        """Find a peer by ID."""
        for p in self.peers:
            if p == peer_id:
                return p
        return None

    def closest_peers(
        self, target_id: PeerID, count: Optional[int] = None
    ) -> list[PeerID]:
        """
        Return up to `count` peers closest to the target_id (by XOR distance).
        If count is None, return up to kbucket_size.
        """
        count = count or self.kbucket_size
        distances = [
            (xor_distance(target_id.to_bytes(), p.to_bytes()), p) for p in self.peers
        ]
        closest = heapq.nsmallest(count, distances, key=lambda x: x[0])
        return [p for _, p in closest]

    @property
    def size(self) -> int:
        return len(self.peers)

    def all_peers(self) -> list[PeerID]:
        """Return all peers in the routing table."""
        return list(self.peers)


# Only for testing, will be removed in production
if __name__ == "__main__":
    from libp2p.peer.id import ID as PeerID

    local_id = PeerID.from_base58("QmTzQ1Nj5xw5gQb7Y7Fv6X3tL2J9FJg7v5v9wW9uT1p1zF")
    rt = RoutingTable(local_id)

    import random

    base58_alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    # Add some peers
    for _ in range(25):
        # Generate a random valid base58 PeerID (length 46, like a real Qm... ID)
        rand_peer_id = "Qm" + "".join(random.choices(base58_alphabet, k=44))
        pid = PeerID.from_base58(rand_peer_id)
        rt.add(pid)

    print("Routing table size:", rt.size)
    print("All peers:", [str(p) for p in rt.all_peers()])
    target = PeerID.from_base58("QmTargetPeer")
    closest = rt.closest_peers(target, 5)
    print("Closest peers to target:", [str(p) for p in closest])
