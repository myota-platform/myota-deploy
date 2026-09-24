# Geodata deployment migration mirror

These files mirror the canonical migration source in
`myota-geodata-service/migrations/`. The deployment migration runner applies
them to the isolated `myota_geo` database after the core database migrations.

Do not edit this mirror independently. Update the geodata service migration
source first, synchronize the complete ordered set, and verify byte-for-byte
equality before releasing deployment changes.
