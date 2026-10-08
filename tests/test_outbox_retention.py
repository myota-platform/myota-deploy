"""JetStream retention setup must preserve pending delivery semantics."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault(
    "OUTBOX_DATABASE_URL", "postgresql://test:test@127.0.0.1/test"
)
sys.path.insert(0, str(Path(__file__).parents[1] / "services"))

from nats.js.api import AckPolicy, RetentionPolicy
from outbox_routing import event_subject
from outbox_worker import STREAM_NAME, ensure_stream, required_consumers


class FakeJetStream:
    def __init__(self, stream=None, consumers=None):
        self.stream = stream
        self.consumers = consumers or {}
        self.calls = []

    async def stream_info(self, name):
        if name != STREAM_NAME or self.stream is None:
            raise LookupError("stream not found")
        return self.stream

    async def add_stream(self, config):
        self.calls.append(("add_stream", config.retention))
        self.stream = SimpleNamespace(config=config)
        return self.stream

    async def update_stream(self, config):
        self.calls.append(("update_stream", config.retention))
        self.stream.config = config
        return self.stream

    async def consumer_info(self, stream, durable):
        if stream != STREAM_NAME or durable not in self.consumers:
            raise LookupError("consumer not found")
        return self.consumers[durable]

    async def add_consumer(self, stream, config):
        self.calls.append(("add_consumer", config.durable_name))
        self.consumers[config.durable_name] = SimpleNamespace(config=config)


class FakeNats:
    def __init__(self, jetstream):
        self._jetstream = jetstream

    def jetstream(self):
        return self._jetstream


class OutboxRetentionTests(unittest.IsolatedAsyncioTestCase):
    def test_geodata_work_requires_a_provisioned_queue(self):
        with self.assertRaisesRegex(ValueError, "unsupported explicit"):
            event_subject(
                {
                    "eventType": "geodata.other-work.queued.v1",
                    "payload": {"natsSubject": "myota.geodata.unhandled.v1"},
                }
            )

    async def test_durables_exist_before_interest_retention_is_enabled(self):
        js = FakeJetStream()

        await ensure_stream(FakeNats(js))

        self.assertEqual(js.stream.config.retention, RetentionPolicy.INTEREST)
        self.assertEqual(len(js.consumers), len(required_consumers()))
        self.assertEqual(
            js.calls[-1], ("update_stream", RetentionPolicy.INTEREST)
        )
        self.assertTrue(
            all(
                consumer.config.ack_policy == AckPolicy.EXPLICIT
                for consumer in js.consumers.values()
            )
        )

    async def test_existing_interest_stream_remains_interest_and_is_repaired(
        self,
    ):
        js = FakeJetStream(
            SimpleNamespace(
                config=SimpleNamespace(
                    name=STREAM_NAME,
                    subjects=["myota.events.>", "myota.geodata.>"],
                    retention=RetentionPolicy.INTEREST,
                )
            )
        )

        await ensure_stream(FakeNats(js))

        self.assertEqual(js.stream.config.retention, RetentionPolicy.INTEREST)
        self.assertEqual(len(js.consumers), len(required_consumers()))
        self.assertFalse(any(call[0] == "update_stream" for call in js.calls))


if __name__ == "__main__":
    unittest.main()
