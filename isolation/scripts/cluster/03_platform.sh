#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
source "$SCRIPT_DIR/common.sh"
load_env

step "Platform chart (Postgres + GoTrue)"

info "Installing platform chart"
helm upgrade --install platform "$ROOT_DIR/helm/charts/platform" \
  --namespace platform \
  --kube-context "$KUBE_CTX" \
  --values "$ROOT_DIR/helm/charts/platform/values.yaml" \
  --values "$ROOT_DIR/helm/charts/platform/values-dev.yaml" \
  --timeout 10m

info "Waiting for postgres to become Available..."
kubectl wait deployment/postgres \
  --namespace platform \
  --context "$KUBE_CTX" \
  --for=condition=Available \
  --timeout=600s

info "Waiting for gotrue to become Available..."
kubectl wait deployment/gotrue \
  --namespace platform \
  --context "$KUBE_CTX" \
  --for=condition=Available \
  --timeout=180s

info "Verify:"
info "  kubectl exec -n platform deploy/postgres -- pg_isready -U supabase_admin"
info "  kubectl logs -n platform -l app=gotrue | grep 'GoTrue API started'"

step "03_platform - Done"
