#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
source "$SCRIPT_DIR/common.sh"
load_env

PING_TOOL_IMAGE="localhost:${REGISTRY_PORT}/ping-tool:latest"
TENANT_INFO_TOOL_IMAGE="localhost:${REGISTRY_PORT}/tenant-info-tool:latest"
ORDER_TRACKER_IMAGE="localhost:${REGISTRY_PORT}/order-tracker:latest"
TG_BOT_IMAGE="localhost:${REGISTRY_PORT}/tg-bot:latest"

step "Tool images"

bash "$ROOT_DIR/scripts/build-tools.sh"

for img in "$PING_TOOL_IMAGE" "$TENANT_INFO_TOOL_IMAGE" "$ORDER_TRACKER_IMAGE" "$TG_BOT_IMAGE"; do
  info "Loading into Kind: $img"
  kind load docker-image "$img" --name "$KIND_CLUSTER_NAME"
done

step "shared-tools"

kubectl label namespace shared-tools kubernetes.io/metadata.name=shared-tools \
  --context "$KUBE_CTX" --overwrite 2>/dev/null || true

if helm status shared-tools -n shared-tools --kube-context "$KUBE_CTX" &>/dev/null; then
  warn "shared-tools already installed - skipping"
else
  info "Installing shared-tools"
  helm upgrade --install shared-tools "$ROOT_DIR/helm/charts/shared-tools" \
    --namespace shared-tools \
    --kube-context "$KUBE_CTX" \
    --set pingTool.image="$PING_TOOL_IMAGE" \
    --timeout 3m
fi

kubectl wait deployment/ping-tool \
  --namespace shared-tools \
  --context "$KUBE_CTX" \
  --for=condition=Available \
  --timeout=120s


step "07_tools - Done"
info "Verify:"
echo "  kubectl get pods -n shared-tools"

