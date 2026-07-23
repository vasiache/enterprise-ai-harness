#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
source "$SCRIPT_DIR/common.sh"
load_env

step "Database migrations"

POSTGRES_POD=$(kubectl get pod -n platform --context "$KUBE_CTX" \
  -l app=postgres -o jsonpath='{.items[0].metadata.name}')
info "Postgres pod: $POSTGRES_POD"

for migration in "$ROOT_DIR"/supabase/migrations/*.sql; do
  fname=$(basename "$migration")
  info "Applying migration: $fname"
  kubectl exec -i "$POSTGRES_POD" -n platform --context "$KUBE_CTX" \
    -- env PGPASSWORD="$POSTGRES_PASSWORD" \
    psql -U supabase_admin -h localhost -d postgres \
    -f "/dev/stdin" < "$migration"
done

KAGENT_PW="${KAGENT_DB_PASSWORD:-kagent}"
info "Setting password for kagent role"
kubectl exec "$POSTGRES_POD" -n platform --context "$KUBE_CTX" \
  -- env PGPASSWORD="$POSTGRES_PASSWORD" \
  psql -U supabase_admin -h localhost -d postgres \
  -c "ALTER ROLE kagent WITH LOGIN PASSWORD '$KAGENT_PW';"

info "Creating kagent database (if not exists)"
DB_EXISTS=$(kubectl exec "$POSTGRES_POD" -n platform --context "$KUBE_CTX" \
  -- env PGPASSWORD="$POSTGRES_PASSWORD" \
  psql -U supabase_admin -h localhost -d postgres -tAc \
  "SELECT 1 FROM pg_database WHERE datname='kagent'")
if [[ "$DB_EXISTS" != "1" ]]; then
  kubectl exec "$POSTGRES_POD" -n platform --context "$KUBE_CTX" \
    -- env PGPASSWORD="$POSTGRES_PASSWORD" \
    psql -U supabase_admin -h localhost -d postgres \
    -c "CREATE DATABASE kagent OWNER kagent;"
  info "kagent database created"
else
  info "kagent database already exists - skipping"
fi


step "04_migrations - Done"
