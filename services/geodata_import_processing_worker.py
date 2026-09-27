"""NATS worker for the administrator-confirmed geodata import queue."""
from __future__ import annotations

import asyncio
import os
import sys

from event_consumer import consume_forever
from geodata import GeoHandler


async def main() -> None:
    if not GeoHandler.store.durable:
        raise RuntimeError("GEO_DATABASE_URL is required for the geodata import processor")
    GeoHandler.store.hydrate()

    async def handle(event: dict) -> None:
        queue_id = event.get("aggregate", {}).get("id") or (event.get("payload") or {}).get("queueId")
        if queue_id:
            await asyncio.to_thread(GeoHandler._process_import_queue, str(queue_id))

    await consume_forever("geodata-import-processing", "myota.geodata.import.process.v1",
                          GeoHandler.store.dsn, handle)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)
