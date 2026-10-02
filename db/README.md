# Postgres/PostGIS storage layout

The deployment uses three service-owned database targets:

- `myota_core` on plain PostgreSQL: identity, programme configuration, permissions, and core audit/outbox data.
- `myota_activity` on plain PostgreSQL: activations, QSOs, aggregates, awards, activity jobs, and notifications.
- `myota_geo` on PostgreSQL with PostGIS: geodata entities, geometries, source snapshots, import runs, conflation candidates, review records, and relational entity-to-category assignments.

Local development uses three database containers; Helm can deploy three
persistent StatefulSets or use externally managed database endpoints. Only
`myota_geo` requires PostGIS. Keep backups, migrations, and capacity planning
independent for each database target. Cross-service references use opaque IDs
and events, never foreign keys across databases.

The migration SQL is intentionally compatible with a later move to separate
PostgreSQL clusters. See the
[three-database migration ADR](https://github.com/myota-platform/myota-docs/blob/main/docs/adr/0007-three-database-migration.md)
for ownership and migration details.
