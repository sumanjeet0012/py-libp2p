from prometheus_client import Counter, Histogram

from libp2p.pubsub.pubsub import GossipsubEvent


class GossipsubMetrics:
    publish: Counter
    subopts: Counter
    control: Counter

    received: Counter
    msg_size: Histogram

    publish_out: Counter
    publish_out_bytes: Histogram
    subscription_changes: Counter

    def __init__(self) -> None:
        self.received = Counter(
            "gossipsub_received_total",
            "Messages successfully received",
            labelnames=["peer_id"],
        )

        self.publish = Counter(
            "gossipsub_publish_total",
            "Messages to be published",
            labelnames=["peer_id"],
        )

        self.subopts = Counter(
            "gossipsub_subopts_total",
            "Messages notifying peer subscriptions",
            labelnames=["peer_id"],
        )

        self.control = Counter(
            "gossipsub_control_total",
            "Received control messages",
            labelnames=["peer_id"],
        )

        self.msg_size = Histogram(
            "gossipsub_message_bytes",
            "Message size in bytes",
            buckets=[64, 128, 256, 512, 1024, 2048, 4096],
        )

        self.publish_out = Counter(
            "gossipsub_publish_out_total",
            "Messages published by this node",
            labelnames=["peer_id"],
        )

        self.publish_out_bytes = Histogram(
            "gossipsub_publish_out_bytes",
            "Size in bytes of locally published messages",
            buckets=[64, 128, 256, 512, 1024, 2048, 4096],
        )

        self.subscription_changes = Counter(
            "gossipsub_subscription_changes_total",
            "Local subscription changes",
            labelnames=["action"],
        )

    def record(self, event: GossipsubEvent) -> None:
        if event.publish_out:
            self.publish_out.labels(peer_id=event.peer_id or "").inc()
            if event.message_size is not None:
                self.publish_out_bytes.observe(event.message_size)
            return

        if event.subscription_change:
            self.subscription_changes.labels(action=event.action or "unknown").inc()
            return

        # Inbound messages
        self.received.labels(peer_id=event.peer_id or "").inc()

        if event.publish:
            self.publish.labels(peer_id=event.peer_id or "").inc()

        if event.subopts:
            self.subopts.labels(peer_id=event.peer_id or "").inc()

        if event.control:
            self.control.labels(peer_id=event.peer_id or "").inc()

        if event.message_size is not None:
            self.msg_size.observe(event.message_size)
