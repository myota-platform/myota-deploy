# Geodata deployment migration mirror

These files mirror the canonical migration source in
`myota-geodata-service/migrations/`. The deployment migration runner applies
them to the isolated `myota_geo` database after the core database migrations.

Do not edit this mirror independently. Update the geodata service migration
source first, synchronize the complete ordered set, and verify byte-for-byte
equality before releasing deployment changes. The location-enrichment
migration adds reverse-geocoded entity fields and must remain synchronized with
the service repository. The manual-location precedence migration also persists
which fields are administrator-controlled and exposes them through the QGIS
review views.
The unscoped-imports migration keeps programme assignment optional for
platform-wide candidate intake and adds the refresh category.
