# MyOTA Outdoor Activation Platform

MyOTA is a programme-agnostic platform for outdoor activation programmes. MPOTA is represented as a configured programme, not as the platform itself. No rules or charter text are copied from POTA or any other programme: every programme supplies its own configuration, policy, eligibility, awards and public charter.

The platform’s purpose and accessibility motivation are documented in the
[project charter](https://github.com/myota-platform/myota-docs/blob/main/docs/project-charter.md).
This repository supplies the durable local/production topology; it is not the
owner of programme rules or the participant product. Remaining launch gates
are tracked in the [charter gap analysis](https://github.com/myota-platform/myota-docs/blob/main/docs/charter-gap-analysis.md).

This repository is a runnable vertical-slice bootstrap for the service repositories described in [`docs/repository-map.md`](docs/repository-map.md). It contains four independently runnable Python services, an API-first contract, a universal browser UI, PostGIS migrations, and Kubernetes/Helm deployment assets.

## What works now

- Amateur-radio-aware identity: operator/SWL participation, multiple callsigns, one primary callsign, lifecycle and verification fields.
- Shared entity-category catalogue used by imports and review, with programme assignment and programme-owned rules handled separately.
- Geodata lifecycle: adapter/import run or community proposal → pre-processing → administrator validation → CANDIDATE or APPROVED; normal review then permits CANDIDATE → APPROVED or REJECTED, and approved entities may only be RETIRED.
- Provenance-aware imports with adapter metadata for ParkServe, OSM, government GIS and manual proposals.
- Activation and QSO primitives with idempotency keys and audit events.
- Programme-owned hunter/activator awards, nested conditions, achievement levels, asset metadata and issuance requests are served by the activity service on the same port (8004).
- Universal themed frontend with verified/candidate map distinction.
- OpenAPI and event contracts, ADRs, migration notes, health endpoints and local deployment manifests.
- Phase 2 geodata resource aliases are deployed alongside the legacy routes:
  consolidated imports, proposals, metadata, categories, geometry, reviews,
  bbox-filtered entity collections, and confirmation-based deletion jobs. See
  the [Phase 2 resource model](https://github.com/myota-platform/myota-docs/blob/main/docs/api-phase2-geodata-resource-model.md).
- Phase 3 activity and award job resources are deployed on the shared activity
  API port 8004. The worker handles QSO ingestion, ADIF, statistics, award
  evaluation/recalculation, certificate rendering, notifications, and bounded
  retries. Participant mutations are owner-authorized, recalculation is rule-
  version scoped, and statistics rebuilds replace the current deterministic
  snapshot set. See the [Phase 3 job record](https://github.com/myota-platform/myota-docs/blob/main/docs/api-phase3-activity-award-jobs.md).

Unit tests may use a small in-memory adapter when they explicitly omit a
database URL. The local Compose runtime is different: every database-backed
service has a PostgreSQL/PostGIS URL and `MYOTA_REQUIRE_DURABILITY=1`. A
missing URL therefore stops that service during startup instead of silently
accepting writes in process memory. PostgreSQL/PostGIS is defined in
`db/migrations/` and the named Compose volumes preserve it between restarts.

## Run the vertical slice

```bash
python3 -m unittest discover -s tests -v
docker-compose up -d --build
```

Open <http://127.0.0.1:8080>. The Compose stack starts the four services on
ports 8001–8004 and proxies the browser API calls. Activations and awards
intentionally share the activity service on port 8004; there is no standalone
awards port. Use `python3 services/dev_server.py` only as the dependency-free
unit-test harness; it is not a durable runtime unless database URLs and
`MYOTA_REQUIRE_DURABILITY=1` are supplied explicitly.

For a containerized PostGIS environment, start Colima and run
`docker-compose up -d --build`. The gateway is available on
`http://localhost:8080`; the authenticated administration web is available on
`http://localhost:8090`; SeaweedFS exposes its S3 endpoint on
`http://localhost:8333` and filer UI on `http://localhost:8888` for local
object administration. Container and Kubernetes health probes use the S3
`/status` endpoint rather than the filer HTML root; the latter is a streaming
directory page and can log harmless broken-pipe messages when a probe closes
early. Activity and awards share port 8004, while
`activity-worker`, `activity-notifications`, and `geodata-import-processing`
run asynchronously and can be scaled independently. The geodata processing
worker consumes `myota.geodata.import.process.v1` after an administrator
confirms a selection. The activity migration is applied by
`db/migrations/run.sh`; its canonical source is maintained in
`myota-activity-service/migrations/` and reviewed into this deployment copy.
The Helm chart exposes the same processor as
`geodataImportProcessing`, so production Kubernetes deployments keep the
promotion worker separate from the HTTP geodata pods. Helm rendering and
linting run in the GitHub workflow rather than being a local prerequisite.

The Vue administration image listens on port `8080` inside its container and
is exposed on port `8090` by Compose and the Helm Service. Nginx proxies the
same-origin `/v1` and `/healthz` requests to the gateway, so the browser does
not need a separate API origin or CORS configuration. Local Vite development
uses port `8090` and proxies to the gateway on `8080`.

### Migrating filesystem-adapter objects

Before removing a development `MYOTA_OBJECT_STORAGE_LOCAL_DIR`, copy its
bucket/key tree into SeaweedFS with:

```bash
MYOTA_OBJECT_STORAGE_ENDPOINT=http://localhost:8333 \
MYOTA_OBJECT_STORAGE_ACCESS_KEY=myota-s3 \
MYOTA_OBJECT_STORAGE_SECRET_KEY=myota-s3-dev-only \
python3 scripts/migrate-local-object-store.py --source /path/to/object-store
```

The tool preserves bucket names and object keys. It is safe to run with
`--dry-run` first and is idempotent for the same source tree. The current
checkout was inventoried during the migration; no filesystem-adapter object
directory was present, and the old development object-store volume was empty.

The admin web's Geodata imports page sends pasted GeoJSON/KML/GPX/WFS/ArcGIS
documents to the geodata service and uploads binary/text files through the
SeaweedFS-backed intake endpoint. Imports stop at `PREPROCESSED`; normalized
records are duplicate-checked against existing geometry and can carry a
non-blocking `POSSIBLE_DUPLICATE` warning with comparison geometry. The admin
page shows active runs in a dedicated pre-processing queue, separate from
Geodata Review, with pending/confirmed counts. Its modal provides compact
paging, select-all, duplicate map comparison, validation, and explicit
promotion to `CANDIDATE` or `APPROVED`. The multi-select category control reads the
complete shared Master data catalogue from the programme service database;
imports may carry several categories, are not assigned to a programme, and
enter as `CANDIDATE`. The first category remains the compatibility primary
`entityType`; all assignments are persisted in `geodata_entity_category`. The
geodata outbox publishes the processing request to NATS. Global entity deletion
is a two-step API workflow: activity impact and
QSO cascade/award recalculation first, then geodata entity/audit cleanup.

## Architecture

Read [`docs/architecture.md`](docs/architecture.md), [`docs/adr/0001-storage-topology.md`](docs/adr/0001-storage-topology.md), and [`docs/repository-map.md`](docs/repository-map.md). The current bootstrap is kept together to make the vertical slice easy to run; the repository map defines the justified GitHub split once the MyOTA organization is available.

## Source project

The original `ea7klk/mpota` repository remains untouched. Its charter and planned flows are treated as the migration source; see [`docs/migration-from-mpota.md`](docs/migration-from-mpota.md).
