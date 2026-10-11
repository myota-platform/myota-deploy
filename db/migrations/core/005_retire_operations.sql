-- Retire Operations-owned sampled history after OpenTelemetry replaces it.
DROP TABLE IF EXISTS operations_storage_snapshot;
DROP TABLE IF EXISTS operations_jetstream_snapshot;
