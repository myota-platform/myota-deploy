# Deploy MyOTA with Rancher Fleet on K3s

The Admin UI includes **Platform health → SeaweedFS storage** at
`/object-storage`, backed by the operations service. Health/metrics endpoints
can be overridden with `services.operations.storageHealthUrl` and
`services.operations.storageMetricsUrl`; empty values use the chart's private
SeaweedFS service. `services.identity.internalUrl` supplies live session/role
checks. Core migration 003 adds sampled storage history; no new Secret is needed.
Grafana maps current GLOBAL_OPERATOR/GLOBAL_ADMIN users to Editor and other
authorized readers to Viewer. Provisioned dashboards default to the last
30 minutes with 30-second refresh; see the [storage access runbook](https://github.com/myota-platform/myota-docs/blob/main/docs/seaweedfs-admin-status.md).

This chart targets the cluster managed by Rancher at `https://rancher.spainip.es`
and uses the cluster's Traefik ingress controller. Configure the public/API
hostname with `ingress.host` and the separate administration UI hostname with
`ingress.adminHost`. Defaults (also used by the Spainip example) are
`api.myota.top` and
`admin.myota.top`, respectively. The admin web proxies same-origin `/v1`
requests to the in-cluster API gateway; the public hostname routes directly to
the gateway. The participant-facing `myota-web` is not yet packaged, so the
public hostname currently exposes the API, not a participant website.

## Before enabling Fleet

1. Point DNS `A` records for `api.myota.top` and `admin.myota.top` (and `AAAA`
   records if IPv6 is configured) to the public address of `spainip.es`. Allow
   inbound TCP 80/443 to K3s/Traefik. Confirm Traefik's `IngressRoute` CRD is
   installed and that `websecure` and the `acmeresolver` certificate resolver
   match the cluster configuration. The Spainip values use these settings;
   both hostnames are configurable.
2. The Spainip values enable three separate PostgreSQL StatefulSets with
   persistent volume claims: plain PostgreSQL for `myota_core`, plain
   PostgreSQL for `myota_activity`, and PostgreSQL/PostGIS for `myota_geo`.
   Review the PVC sizes and StorageClass in `values-spainip.yaml` against the
   disk available on the K3s node. The StatefulSets are single-instance and do
   not provide replication or automatic off-host backups. Alternatively, set
   `postgres.enabled: false` and supply externally managed database endpoints.
   This chart does not import a local Colima database; restore or import existing
   data separately before directing users to the new deployment.
3. Create namespace `myota` and the secrets below in Rancher before starting the
   Fleet bundle. Never put their values in Git or Helm values files.
4. The Spainip values render Traefik `IngressRoute` resources, matching the
   cluster's existing workloads. Both routes use `websecure` and
   `tls.certResolver: acmeresolver`, which lets the installed Traefik instance
   provision certificates. For clusters using standard Kubernetes Ingress,
   set `ingress.provider: kubernetes` and configure that controller's TLS
   mechanism. For Traefik clusters using pre-created certificates, set
   `ingress.tls.secretName` and `ingress.adminTls.secretName` to TLS secrets in
   namespace `myota` and leave their cert resolver empty.
5. If you use the chart-managed PostgreSQL StatefulSets, the database URLs in
   `myota-postgres` should use role `myota_app` and service names
   `myota-core-postgres`, `myota-activity-postgres`, and `myota-geo-postgis`,
   port 5432, and the corresponding database names. The `username` and
   `password` keys are the migration/database-owner credentials; the init script
   creates a less-privileged `myota_app` role for runtime URLs. If using external
   databases, provision equivalent migration and application roles yourself and
   update the host/port values and URLs. Credentials embedded in URLs must be
   URL-encoded.

Create these Kubernetes Secrets through Rancher's Secret UI (or an approved
secret manager); the listed keys are exact:

| Secret | Required keys | Purpose |
| --- | --- | --- |
| `myota-postgres` | `username`, `password`, `app-password`, `core-database-url`, `activity-database-url`, `geo-database-url` | PostgreSQL initialization, migration job and service connections. Set `username` to `myota_admin`; the database init script creates the runtime role `myota_app` using `app-password`. URLs must use `myota_app` and include the correct hostname, port, database name, and URL-encoded credentials. |
| `myota-auth` | `signing-key` | Token signing. Optionally add `bootstrap-email` and `bootstrap-password` for first installation, then remove/rotate the bootstrap credentials after confirming the admin can sign in. |
| `myota-s3-auth` | `access-key`, `secret-key` | SeaweedFS and application S3-compatible access. The included Spainip values run single-node SeaweedFS with persistent storage; for an external S3/SeaweedFS service, disable `seaweedfs.enabled` and set `objectStorage.endpoint` and `objectStorage.publicEndpoint` as appropriate. |
| `myota-geodata-enrichment` | `api-key` (optional) | BigDataCloud reverse-geocoding enrichment. Add the key only in Rancher/secret manager; without it, manually managed geodata remains usable but automatic enrichment is unavailable. |

The geodata API and processing worker receive `BIGDATACLOUD_API_KEY` from that
Secret at pod startup. After creating or rotating it, increment
`geodataPipeline.locationEnrichment.rolloutRevision` in
`values-spainip.yaml` and push the change. Fleet then rolls both pods through
Helm; the key itself must never be placed in values or Git. Previous enrichment
requests that were already acknowledged as failed need a fresh request from
Entity Management after the rollout.

All three PostgreSQL databases, JetStream, and the example SeaweedFS deployment
use persistent volume claims. Uploads use resumable SeaweedFS multipart
sessions; the geodata API has no shared upload-spool volume. The databases and SeaweedFS
are each single-node deployments: they are suitable for an initial single-node
K3s rollout but are not highly available. Back up their PVCs off-host, and
review PVC sizes and StorageClass for your actual datasets before the first
upload.

The geodata service calls the activity API for entity-deletion impact checks,
including load-test cleanup safeguards. `services.activity.internalUrl`
configures this in-cluster endpoint and defaults to
`http://myota-activity:8004`; if service names or namespaces are customized,
keep this URL aligned with the Activity Service DNS name.

## Geodata API replica safety

The geodata API is stateless: its Deployment has no PVC or pod-local accepted
upload source. Durable source objects stay in SeaweedFS, authoritative state
and leases stay in PostGIS, and asynchronous work stays in JetStream. The API
can therefore have multiple pods without sharing a `ReadWriteOnce` volume.
Only the geodata API scales automatically; databases, SeaweedFS and NATS remain
single-replica stateful services on this single-node K3s installation and must
not be scaled by changing application replica settings.

The Spainip values run two API pods, with a CPU HPA from two to at most three
pods at 70% of the 250m CPU request. Scale-up adds at most one pod per minute;
scale-down observes a five-minute stabilization window. A PDB preserves one
available API pod during voluntary eviction, the Deployment rolls with zero
unavailable and one surge pod, and hostname topology spreading is best-effort
so a one-node cluster can still schedule all replicas. This protects pod-level
replica changes and rolling updates; it does not provide node, database,
SeaweedFS, or JetStream high availability.

Connection use is bounded independently of HTTP concurrency. The chart caps
each API pool at eight connections and each geodata worker pool at four. At
the configured maxima (three API pods, two worker pods, one geo outbox pool of
ten), plus the reserved forty connections, the computed budget is 82 of the
live geo database's 100 `max_connections`. Helm rendering fails if a worker
replica cap or the configured connection budget is exceeded. Adjust the
documented database maximum and reserve together if the Postgres setting
changes; do not simply raise the HPA maximum.

Geodata API and worker containers request 250m CPU/256 MiB memory and are
limited to one CPU/1 GiB. The API has startup, readiness, and liveness probes;
SIGTERM grace is 60 seconds. Worker bounds remain independent and manual: one
to two replicas, using the queue-depth/oldest-message Grafana signals and the
JetStream durable pull consumer's shared acknowledgement limit. Worker SIGTERM
stops new pulls and drains active work before lease recovery. A tested maximum
throughput for two workers is not implied by this configuration.

The server also bounds active HTTP handlers (64 per API pod), database pool
connections (8 per API pod), resumable upload parts (16 MiB), and request bodies
(1 GiB hard limit); the gateway uses the configured long upload timeout. These
are per-deployment maxima, not a global requests-per-second limiter. Follow
`docs/geodata/horizontal-scaling-roadmap.md` and its Phase 4 evidence before
raising any replica or concurrency ceiling.

The chart schedules separate object-retention jobs. Geodata import sources and
their import history use the configurable 30-day policy under
`geodataImportRetention`; completed ADIF source files are deleted after 15 days
by `activityAdifRetention`, while the activity import result remains in
PostgreSQL. Both completed and failed imports qualify; queued and processing
imports are excluded. Award assets, signatures, and issued certificates are
not covered by either policy.

Prometheus, Alertmanager, Grafana, and Tempo are enabled by default in the
chart and use separate persistent claims (10 GiB, 1 GiB, 1 GiB, and 10 GiB by
default, respectively). Set `observability.storageClassName` to use a specific
StorageClass, or leave it empty to use the cluster default. Their Services are
cluster-internal and none has a public IngressRoute. Grafana is available at
`https://admin.myota.top/observability/` by default (the host follows
`ingress.adminHost`) through the Admin UI web server. That
server validates the MyOTA access token against the identity API on every
request, then Grafana assigns a read-only Viewer session. Anonymous access,
Grafana's login form, and basic authentication are disabled. Users must sign in
to the Admin UI first; expired tokens are refreshed before opening Grafana.
Prometheus, Alertmanager, and Tempo stay private, and Grafana accesses them
through internal data sources. Alertmanager receives configured alerts and is
available through Grafana's Alertmanager data source, but no email or paging
destination is enabled by default. Configure an approved Alertmanager receiver
before expecting external notifications.

The gateway receives the same `MYOTA_ENV` value as the domain services so its
OpenTelemetry resource is correctly labelled. Gateway API route metrics use
the route templates registered by the service (for example,
`/v1/geodata/entities/{entityId}`), not raw URL paths containing entity or
import UUIDs. The Collector scrapes SeaweedFS's built-in master and S3 metrics
listener on the internal-only port 9324 by default. That endpoint exposes both
master and S3 request metrics. The **MyOTA Object Storage** dashboard shows S3
request rate, server-side p50/p95/p99 processing time, non-2xx responses, and
in-flight uploads. The port is configurable under `seaweedfs.metricsPort`; do
not expose it through an Ingress or public Service.
The Collector pod template includes a checksum of its scrape configuration,
so Fleet changes to the ConfigMap automatically roll the Collector and activate
new scrape targets.

The migration runner is a normal release Job, not a `post-install` hook. Helm
waits for Deployments before running post-install hooks, while these services
need their tables before they can become ready; using that hook ordering can
leave clean databases empty and trigger an atomic rollback. The runner waits
for all three database endpoints, marks the current release revision as not
ready, applies migrations, and marks it ready only after all schemas (and the
optional one-time data copy) succeed. Database-backed pods wait for that exact
revision before starting. If migration fails, the gate stays closed and the
Job remains available for inspection/retry; Fleet no longer uninstalls the
release on failure. This does not delete or reinitialize PVC data.

Wait for Fleet to report the bundle ready before sending public traffic.

The role-creation script runs only when a PostgreSQL volume is initialized for
the first time. If you restore a database volume or attach a pre-existing
database, make sure the `myota_app` role, database grants, and matching URL
credentials already exist; the initializer will not rerun against a populated
data directory.

## Fleet setup

The `Roll out newly published service images` GitHub Actions workflow checks
the public GHCR `:latest` tags every five minutes and on demand. When any
digest changes, it commits the new digests to `values-image-digests.yaml`.
Fleet reconciles that commit; the digest annotation changes the pod template
and Kubernetes performs a rolling update. This avoids relying on mutable image
tags alone, which do not restart already-running pods. Keep Fleet pointed at
the deployment repository's intended branch and allow it to reconcile commits.

The identity access-token lifetime is configurable as
`auth.accessTokenSeconds`; the Spainip values set it to 1800 seconds (30
minutes). Refresh-token policy is unchanged.

Commit the prepared, non-secret `values-spainip.yaml` to the deployment repo.
Then in Rancher open **Continuous Delivery → Git Repos → Create** and configure:

- Repository URL: `https://github.com/myota-platform/myota-deploy.git`
- Branch: `main` (prefer a reviewed release branch/tag once releases are cut)
- Paths: `deploy/helm/myota`
- Target: the K3s cluster managed by this Rancher installation

Fleet reads `fleet.yaml` at that path, installs release `myota` into namespace
`myota`, and waits for the migration Job and gated Deployments. Follow the
GitRepo/Bundle status in Rancher; do not treat a created IngressRoute as proof
that the application is ready. Check the `myota-migrations-*` Job and its pod
logs first, then confirm all service Deployments are Ready and the TLS URL
responds. A failed migration is intentionally retained; correct its reported
cause and reconcile the bundle again rather than deleting database PVCs.

The chart renders in the repository's GitHub Actions workflow. Do not render or
apply it from a developer workstation; submit chart changes through Git and
review the workflow result before Fleet reconciles them.

## Rollouts and operational checks

- Production currently follows the published `latest` tags. The digest-sync
  workflow records those exact image digests and triggers a rolling update;
  for controlled releases, set an immutable `services.<name>.imageTag` and
  update its corresponding digest deliberately.
- Confirm `/healthz` through `https://api.myota.top/healthz`; open the admin UI at
  `https://admin.myota.top` and test login, entity reads, geodata import, and
  one activity/QSO workflow before announcing the service.
- Keep the database and S3 credentials out of Git. Rotate the signing key only
  with a coordinated token/session plan.
- API gateway liveness and readiness probes use `/healthz`; the root path is
  not a health endpoint. When diagnosing an unready gateway, check the
  Deployment probe configuration and pod events before changing ingress.
- The geodata import worker uses a durable JetStream pull consumer and can be
  scaled independently through `geodataImportProcessing.replicas`. Atomic
  PostgreSQL leases and stable candidate/entity identities protect concurrent
  delivery. The conservative rolling strategy (`maxSurge: 0`,
  `maxUnavailable: 1`) allows a brief worker-capacity pause during upgrades;
  unacknowledged messages remain durable and are redelivered. SIGTERM stops
  pulls, drains the active delivery, and then closes the NATS connection.
- `geodataImportProcessing.batchSize` controls the default 100-feature
  preprocessing checkpoint window. Streaming decoders cover GeoJSON, KML,
  GPX, zipped Shapefile/ParkServe, and OSM PBF. Current bounded qualification
  uses a 16 MiB decoded-feature cap, 250,000-vertex cap, 5,000-feature import
  cap, and checkpoints bounded by 100 features or 32 MiB serialized source
  data. The recorded parser RSS and worker recovery evidence is in the
  [Phase 3 report](https://github.com/myota-platform/myota-docs/blob/main/docs/geodata/evidence/phase3-bounded-preprocessing-2026-10-09.md).
  Source objects are staged in worker-local scratch, so ensure node ephemeral
  storage can accommodate the configured upload limit. These correctness bounds
  do not qualify larger replica counts or throughput; Phase 4/5 scaling gates
  remain open.
- Fleet's GitRepo polling interval controls when a pushed commit is fetched.
  A bundle re-sync only reapplies the revision Fleet has already fetched; it
  does not necessarily fetch a newer Git commit immediately. Check the
  GitRepo's observed revision and polling interval, then inspect Bundle and
  Helm release status before retrying. The chart migration Job is named for
  its Helm release revision, so each upgrade runs the migration gate for that
  revision before database-backed pods start.
- A readiness or migration failure is not a reason to delete database PVCs.
  The migration gate preserves existing data and remains inspectable; diagnose
  the failed Job and pod events, correct the cause, and let Fleet reconcile.
- The current chart deploys the administration web; the `myota-web` participant
  client is not yet packaged as a container or included in this chart.
- Observability dashboards are at `/observability/` on the authenticated Admin
  UI host. The stack is enabled by the Spainip values; no separate public
  Grafana, Prometheus, Alertmanager, or Tempo hostname is created.
