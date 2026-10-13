#!/usr/bin/env bash
set -euo pipefail

source_namespace="${MYOTA_LIVE_NAMESPACE:-myota}"
target_namespace="${MYOTA_TEST_NAMESPACE:-myota-test}"
seed_marker="myota.dev/live-data-seed"

kubectl get namespace "$source_namespace" >/dev/null
kubectl get namespace "$target_namespace" >/dev/null

if [[ -n "$(kubectl get namespace "$target_namespace" -o json | jq -r --arg key "$seed_marker" '.metadata.annotations[$key] // ""')" ]]; then
  echo "Relational seed already completed for this namespace." >&2
  exit 1
fi

if kubectl get ingress,ingressroute -n "$target_namespace" -o name 2>/dev/null | grep -q .; then
  echo "Refusing to seed while test ingress is enabled." >&2
  exit 1
fi

for statefulset in myota-core-postgres myota-activity-postgres myota-geo-postgis; do
  kubectl wait --namespace "$source_namespace" --for=condition=ready "statefulset/$statefulset" --timeout=180s
  kubectl wait --namespace "$target_namespace" --for=condition=ready "statefulset/$statefulset" --timeout=180s
done

# The live Core database currently has no user accounts. Refuse to copy stored
# credentials into the public test environment if that changes; add an explicit
# anonymization step before any future seed containing account rows.
account_count="$(kubectl exec -n "$source_namespace" statefulset/myota-core-postgres -- \
  sh -ec 'psql -U "$POSTGRES_USER" -d myota_core -Atc "SELECT count(*) FROM public.account"')"
if [[ "$account_count" != "0" ]]; then
  echo "Live Core contains $account_count accounts; sanitize identity data before seeding test." >&2
  exit 1
fi

common_excludes=(
  --exclude-table-data=public.myota_schema_migration
  --exclude-table-data=public.myota_deployment_schema_state
  --exclude-table-data=public.outbox_event
  --exclude-table-data=public.outbox_redrive_audit
  --exclude-table-data=public.consumer_checkpoint
  --exclude-table-data=public.consumer_processed_event
  --exclude-table-data=public.dead_letter_event
  --exclude-table-data=public.idempotency_record
  --exclude-table-data=public.service_state
  --exclude-table-data=public.auth_session
  --exclude-table-data=public.auth_revocation
  --exclude-table-data=public.account_recovery_token
  --exclude-table-data=public.oidc_provider_mapping
  --exclude-table-data=public.security_event
)
geo_excludes=(
  "${common_excludes[@]}"
  --exclude-table-data=public.entity_type
  --exclude-table-data=public.spatial_ref_sys
)

copy_database() {
  local database="$1"
  local source_statefulset="$2"
  local target_statefulset="$3"
  shift 3
  local database_marker="myota.dev/live-data-seed-$database"
  local completed
  completed="$(kubectl get namespace "$target_namespace" -o json \
    | jq -r --arg key "$database_marker" '.metadata.annotations[$key] // ""')"
  if [[ "$completed" == "complete" ]]; then
    echo "Skipping already copied database $database"
    return
  fi

  echo "Copying relational domain rows for $database"
  kubectl exec -n "$source_namespace" "statefulset/$source_statefulset" -- \
    sh -ec 'database="$1"; shift; pg_dump -U "$POSTGRES_USER" -d "$database" -Fc --data-only "$@"' sh "$database" "$@" \
    | kubectl exec -i -n "$target_namespace" "statefulset/$target_statefulset" -- \
      sh -ec 'pg_restore -U "$POSTGRES_USER" -d "$1" --data-only --disable-triggers --single-transaction --no-owner -' sh "$database"
  kubectl annotate namespace "$target_namespace" "$database_marker=complete" --overwrite=false
}

copy_database myota_core myota-core-postgres myota-core-postgres "${common_excludes[@]}"
copy_database myota_activity myota-activity-postgres myota-activity-postgres "${common_excludes[@]}"
copy_database myota_geo myota-geo-postgis myota-geo-postgis "${geo_excludes[@]}"

kubectl annotate namespace "$target_namespace" "$seed_marker=$(date -u +%Y-%m-%dT%H:%M:%SZ)" --overwrite=false
echo "Relational seed completed. Copy application S3 objects before enabling ingress."
