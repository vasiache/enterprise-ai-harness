#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
source "$SCRIPT_DIR/common.sh"
load_env

step "Checking prerequisites"
for cmd in kind kubectl helm docker; do
  command -v "$cmd" &>/dev/null || error "Missing: $cmd - please install it first"
  info "$cmd: OK"
done

step "Kind cluster"
if kind get clusters 2>/dev/null | grep -q "^${KIND_CLUSTER_NAME}$"; then
  warn "Cluster '${KIND_CLUSTER_NAME}' already exists - skipping creation"
else
  info "Creating cluster '${KIND_CLUSTER_NAME}'"
  kind create cluster \
    --name "$KIND_CLUSTER_NAME" \
    --config "$ROOT_DIR/scripts/kind-config.yaml" \
    --image "kindest/node:v1.32.0"
fi
info "Using context: $KUBE_CTX"

step "Pre-pulling images into Kind nodes"

load_images "$KIND_CLUSTER_NAME" \
  "supabase/postgres:15.6.1.143" \
  "supabase/gotrue:v2.151.0"

load_images "$KIND_CLUSTER_NAME" \
  "cr.kagent.dev/kagent-dev/kagent/controller:${KAGENT_VERSION}" \
  "cr.kagent.dev/kagent-dev/kagent/ui:${KAGENT_VERSION}" \
  "cr.kagent.dev/kagent-dev/kagent/app:${KAGENT_VERSION}" \
  "ghcr.io/kagent-dev/kagent/tools:0.1.2" \
  "ghcr.io/kagent-dev/kmcp/controller:0.2.7" \
  "ghcr.io/kagent-dev/doc2vec/mcp:1.1.14"

step "Local Docker registry"

if docker inspect "$REGISTRY_NAME" &>/dev/null; then
  warn "Registry '$REGISTRY_NAME' already running"
else
  docker run -d --restart=always -p "127.0.0.1:${REGISTRY_PORT}:5000" \
    --network bridge --name "$REGISTRY_NAME" registry:2
  info "Registry started at localhost:${REGISTRY_PORT}"
fi

if ! docker network inspect kind | grep -q "$REGISTRY_NAME" 2>/dev/null; then
  docker network connect kind "$REGISTRY_NAME" 2>/dev/null || true
fi

kubectl apply --context "$KUBE_CTX" -f - <<EOF
apiVersion: v1
kind: ConfigMap
metadata:
  name: local-registry-hosting
  namespace: kube-public
data:
  localRegistryHosting.v1: |
    host: "localhost:${REGISTRY_PORT}"
    help: "https://kind.sigs.k8s.io/docs/user/local-registry/"
EOF

for node in $(kind get nodes --name "$KIND_CLUSTER_NAME"); do
  docker exec "$node" mkdir -p /etc/containerd/certs.d/localhost:${REGISTRY_PORT}
  docker exec "$node" sh -c "cat > /etc/containerd/certs.d/localhost:${REGISTRY_PORT}/hosts.toml" <<TOML
[host."http://${REGISTRY_NAME}:5000"]
TOML
done

step "Namespaces"
for ns in kagent platform shared-tools; do
  kubectl create namespace "$ns" --context "$KUBE_CTX" --dry-run=client -o yaml \
    | kubectl apply --context "$KUBE_CTX" -f -
  kubectl label namespace "$ns" \
    kubernetes.io/metadata.name="$ns" \
    --context "$KUBE_CTX" --overwrite
  info "namespace/$ns"
done

kubectl label namespace kube-system \
  kubernetes.io/metadata.name=kube-system \
  --context "$KUBE_CTX" --overwrite 2>/dev/null || true

step "01_kind - Done"
info "Cluster:  $KIND_CLUSTER_NAME"
info "Context:  $KUBE_CTX"
info "Registry: localhost:${REGISTRY_PORT}"
