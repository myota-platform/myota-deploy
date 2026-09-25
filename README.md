# MyOTA Outdoor Activation Platform

MyOTA is a programme-agnostic platform for outdoor activation programmes. MPOTA is represented as a configured programme, not as the platform itself. No rules or charter text are copied from POTA or any other programme: every programme supplies its own configuration, policy, eligibility, awards and public charter.

This repository is a runnable vertical-slice bootstrap for the service repositories described in [`docs/repository-map.md`](docs/repository-map.md). It contains four independently runnable Python services, an API-first contract, a universal browser UI, PostGIS migrations, and Kubernetes/Helm deployment assets.

## What works now

- Amateur-radio-aware identity: operator/SWL participation, multiple callsigns, one primary callsign, lifecycle and verification fields.
- Programme configuration: programme-owned entity types, rules, minimum QSOs, awards, theme and optional OIDC settings.
- Geodata lifecycle: imported candidate → community proposal → approver review → approved entity.
- Provenance-aware imports with adapter metadata for ParkServe, OSM, government GIS and manual proposals.
- Activation and QSO primitives with idempotency keys and audit events.
- Programme-owned hunter/activator awards, nested conditions, achievement levels, asset metadata and issuance requests are served by the activity service on the same port (8004).
- Universal themed frontend with verified/candidate map distinction.
- OpenAPI and event contracts, ADRs, migration notes, health endpoints and local deployment manifests.

The default test/runtime adapter is in-memory so the slice can be exercised without third-party Python packages. PostgreSQL/PostGIS is the production storage target and is defined in `db/migrations/`.

## Run the vertical slice

```bash
python3 -m unittest discover -s tests -v
python3 services/dev_server.py
```

Open <http://127.0.0.1:8080>. The dev server starts the four services on ports 8001–8004 and proxies the browser API calls. Activations and awards intentionally share the activity service on port 8004; there is no standalone awards port. It is intentionally dependency-free.

For a containerized PostGIS environment, start Colima and run
`docker-compose up -d --build`. The gateway is available on
`http://localhost:8080`; the authenticated administration web is available on
`http://localhost:8090`; MinIO is available on `http://localhost:9001` for
local asset administration. Activity and awards share port 8004, while
`activity-worker` and `activity-notifications` run asynchronously and can be
scaled independently. The activity migration is applied by
`db/migrations/run.sh`; its canonical source is maintained in
`myota-activity-service/migrations/` and reviewed into this deployment copy.
Helm rendering and linting run in the GitHub workflow rather than being a
local prerequisite.

The admin web's Geodata imports page sends pasted GeoJSON/KML/GPX/WFS/ArcGIS
documents to the geodata service and uploads binary/text files through the
MinIO-backed intake endpoint. The category selector reads the complete shared
Master data catalogue from the programme service database; imports are not
assigned to a programme and enter as `CANDIDATE`. The geodata outbox publishes the queued import event
to NATS. Global entity deletion is a two-step API workflow: activity impact and
QSO cascade/award recalculation first, then geodata entity/audit cleanup.

## Architecture

Read [`docs/architecture.md`](docs/architecture.md), [`docs/adr/0001-storage-topology.md`](docs/adr/0001-storage-topology.md), and [`docs/repository-map.md`](docs/repository-map.md). The current bootstrap is kept together to make the vertical slice easy to run; the repository map defines the justified GitHub split once the MyOTA organization is available.

## Source project

The original `ea7klk/mpota` repository remains untouched. Its charter and planned flows are treated as the migration source; see [`docs/migration-from-mpota.md`](docs/migration-from-mpota.md).
