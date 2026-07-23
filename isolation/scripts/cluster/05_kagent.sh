#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
source "$SCRIPT_DIR/common.sh"
load_env

step "kagent ${KAGENT_VERSION}"

if helm status kagent-crds -n kagent --kube-context "$KUBE_CTX" &>/dev/null; then
  warn "kagent-crds already installed - skipping"
else
  info "Installing kagent-crds"
  helm upgrade --install kagent-crds \
    oci://ghcr.io/kagent-dev/kagent/helm/kagent-crds \
    --version "$KAGENT_VERSION" \
    --namespace kagent \
    --kube-context "$KUBE_CTX" \
    --timeout 5m \
    --wait
fi

if helm status kagent -n kagent --kube-context "$KUBE_CTX" &>/dev/null; then
  warn "kagent already installed - skipping"
else
  info "Installing kagent"
  KAGENT_DB_URL="postgres://kagent:${KAGENT_DB_PASSWORD:-kagent}@postgres.platform.svc.cluster.local:5432/kagent?sslmode=disable"
  helm upgrade --install kagent \
    oci://ghcr.io/kagent-dev/kagent/helm/kagent \
    --version "$KAGENT_VERSION" \
    --namespace kagent \
    --kube-context "$KUBE_CTX" \
    --set providers.openAI.apiKey="${OPENAI_API_KEY:-placeholder}" \
    ${OPENAI_BASE_URL:+--set providers.openAI.baseUrl="$OPENAI_BASE_URL"} \
    --set grafana-mcp.enabled=false \
    --set database.postgres.url="$KAGENT_DB_URL" \
    --set database.postgres.vectorEnabled=true \
    --set database.postgres.bundled.enabled=false \
    --set controller.loglevel=debug \
    --set ui.service.type=ClusterIP \
    --set controller.service.type=ClusterIP \
    --timeout 5m
fi

info "Waiting for kagent-controller to become Available..."
kubectl wait deployment/kagent-controller \
  --namespace kagent \
  --context "$KUBE_CTX" \
  --for=condition=Available \
  --timeout=600s

info "Verify: kubectl get pods -n kagent"

step "05_kagent - Done"
