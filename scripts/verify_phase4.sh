#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONTRACTS_DIR="${MYOTA_CONTRACTS_DIR:-${ROOT_DIR}/../myota-contracts}"

echo "Running dependency-free regression tests"
(cd "${ROOT_DIR}" && python3 -m unittest discover -s tests -v)

echo "Checking the frozen contract and typed clients"
(cd "${CONTRACTS_DIR}" && python3 scripts/check_generated_clients.py)

for endpoint in \
  http://127.0.0.1:8080/healthz \
  http://127.0.0.1:8080/metrics \
  http://127.0.0.1:8001/metrics \
  http://127.0.0.1:8002/metrics \
  http://127.0.0.1:8003/metrics \
  http://127.0.0.1:8004/metrics; do
  echo "Probing ${endpoint}"
  curl --fail --silent --show-error "${endpoint}" >/dev/null
done

echo "Phase 4 contract, authorization, idempotency, audit, and telemetry probes passed"
