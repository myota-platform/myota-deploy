# MyOTA Helm chart

See [DEPLOYMENT.md](DEPLOYMENT.md) for the Rancher Fleet/K3s installation
guide. The chart includes optional persistent PostgreSQL/PostGIS StatefulSets,
the application workloads, and configurable routing via Traefik `IngressRoute`
resources or a standard Kubernetes `Ingress`.

The Spainip Fleet bundle uses [fleet.yaml](fleet.yaml) and
[values-spainip.yaml](values-spainip.yaml). Create the required Kubernetes
Secrets before enabling Fleet reconciliation; never commit credential values.
