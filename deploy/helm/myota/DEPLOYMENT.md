# Deploy MyOTA with Rancher Fleet on K3s

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

All three PostgreSQL databases, the upload spool, JetStream, and the example
SeaweedFS deployment use persistent volume claims. The databases and SeaweedFS
are each single-node deployments: they are suitable for an initial single-node
K3s rollout but are not highly available. Back up their PVCs off-host, and
review PVC sizes and StorageClass for your actual datasets before the first
upload. The first-install migration hook runs after these database pods have
started; on upgrades it runs before the new application rollout. Wait for Fleet
to report the bundle ready before sending public traffic.

The role-creation script runs only when a PostgreSQL volume is initialized for
the first time. If you restore a database volume or attach a pre-existing
database, make sure the `myota_app` role, database grants, and matching URL
credentials already exist; the initializer will not rerun against a populated
data directory.

## Fleet setup

Commit the prepared, non-secret `values-spainip.yaml` to the deployment repo.
Then in Rancher open **Continuous Delivery → Git Repos → Create** and configure:

- Repository URL: `https://github.com/myota-platform/myota-deploy.git`
- Branch: `main` (prefer a reviewed release branch/tag once releases are cut)
- Paths: `deploy/helm/myota`
- Target: the K3s cluster managed by this Rancher installation

Fleet reads `fleet.yaml` at that path, installs release `myota` into namespace
`myota`, and waits for the migration hook. Follow the GitRepo/Bundle status in
Rancher; do not treat a created Ingress as proof that the application is ready.
Check the `myota-migrations-*` Job, then confirm all service Deployments are
Ready and the TLS URL responds.

The chart renders in the repository's GitHub Actions workflow. Do not render or
apply it from a developer workstation; submit chart changes through Git and
review the workflow result before Fleet reconciles them.

## Rollouts and operational checks

- Update the image tags in `values-spainip.yaml` to the reviewed build for each
  service. `latest` is only a bring-up default; use immutable tags for repeatable
  production rollbacks. Each API service has its own image repository and can
  override the shared `image.tag` with `services.<name>.imageTag`.
- Confirm `/healthz` through `https://api.myota.top/healthz`; open the admin UI at
  `https://admin.myota.top` and test login, entity reads, geodata import, and
  one activity/QSO workflow before announcing the service.
- Keep the database and S3 credentials out of Git. Rotate the signing key only
  with a coordinated token/session plan.
- The current chart deploys the administration web; the `myota-web` participant
  client is not yet packaged as a container or included in this chart.
- The optional observability stack is disabled in the Spainip values until a
  private Grafana access path and persistent storage are configured. The app
  services still expose health and metrics endpoints for your existing
  monitoring.
