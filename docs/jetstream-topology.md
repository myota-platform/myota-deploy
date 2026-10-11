# JetStream topology provisioning

**Status:** Phase 6 is deployed and complete within its recorded evidence
bounds. Helm revision 211 uses the one-time migration flag disabled and regular
topology drift validation enabled. The MyOTA Fleet bundle is Ready=True for the latest applied Deploy main
commit. See the
[Phase 6 evidence](https://github.com/myota-platform/myota-docs/blob/main/docs/operations/messaging/evidence/phase6-fact-stream-cutover-2026-10-11.md).

`services/jetstream_topology.py` is the side-effect-free ADR-0008 topology
definition. `services/provision_jetstream.py` is the single deployment-owned
provisioner. In ordinary operation it creates missing definitions and fails
closed on drift. Its narrowly gated one-time Phase 6 migration can update only
the exact empty legacy `MYOTA_EVENTS` Interest configuration after verifying
its expected durable and zero counters. It refuses non-empty or unexpected
state. After migration the flag stays disabled; routine provisioning validates
the three streams and ten work durables without retention migration.
The registry-to-topology contract check verifies that all ten work subjects and
durables match
[the contracts registry](https://github.com/myota-platform/myota-contracts/blob/main/contracts/event-registry.json).
The topology tests verify explicit capacity requirements, the apply gate, and
consumer drift rejection. Do not manually enable the migration flag or run an ad hoc broker update. The
production cutover already removed the legacy Geodata subject capture and
converted `MYOTA_EVENTS`; any future topology change requires a separately
reviewed, bounded migration gate.

The selected policy is Limits retention for bounded facts and WorkQueue
retention for Activity and Geodata commands. Streams use file storage,
DiscardNew, one replica on the current single-server cluster, finite per-message
limits, and explicit work durable filters. The 30-day fact window and 1/1/3 GiB stream byte caps with a 3 GiB reserve on
the current 8 GiB PVC are accepted conservative limits for the single-node
deployment. Production values are Events 1 GiB/500,000 messages/1 MiB,
Activity work 1 GiB/250,000/1 MiB, and Geodata work 3 GiB/500,000/1 MiB.
The script has no implicit numeric defaults and requires explicit apply and
positive capacity values before connecting. Do not raise limits without a
representative traffic and outage-backlog review.

The deployed broker is unauthenticated and has no TLS, consistent with the
accepted cluster-internal trust decision. The NATS service is ClusterIP-only on
port 4222. The `myota` namespace has no NetworkPolicy, so any pod with network
reachability is trusted to connect. NATS auth/TLS and runtime broker credentials
are not required while this boundary holds. Do not expose NATS outside the
cluster; revisit the decision before changing service exposure or admitting
untrusted workloads.

For an isolated broker only, use the disposable Compose profile with explicit
test limits. The disposable K3s test verified creation, idempotency, drift
rejection, local PVC restore, replay, and `DiscardNew` pressure rejection. The
temporary namespace and its storage were removed afterward. Off-node recovery
is explicitly deferred; PostgreSQL remains the source for reconciliation and
work redrive. This qualification is limited to a single-node environment.

The current relay still provisions legacy durables and changes retention. The
chart now includes an opt-in `pre-upgrade` provisioner hook; Helm waits for
create-only provisioning and exact drift validation before updating workloads.
It is disabled by default and refuses to render unless the operator confirms
the documented migration gate. Do not enable it against the current mixed
Interest-retained stream. Relay mutation remains a later cutover task. The
[Phase 1 review](https://github.com/myota-platform/myota-docs/blob/main/docs/operations/messaging/evidence/phase1-joint-review-2026-10-10.md),
[recovery runbook](https://github.com/myota-platform/myota-docs/blob/main/docs/operations/messaging/jetstream-recovery.md),
and [migration plan](https://github.com/myota-platform/myota-docs/blob/main/docs/operations/messaging/nats-event-migration-plan.md)
record the remaining gates. Operations remains a metadata-only observer.
