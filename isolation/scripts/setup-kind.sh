#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLUSTER_DIR="$SCRIPT_DIR/cluster"

ROOT_DIR="$(dirname "$SCRIPT_DIR")"
source "$CLUSTER_DIR/common.sh"
load_env

run_step() {
  local script="$CLUSTER_DIR/$1"
  echo ""
  echo "════════════════════════════════════════════════════════"
  echo "  Running: $1"
  echo "════════════════════════════════════════════════════════"
  bash "$script"
}

run_step 01_kind.sh
run_step 03_platform.sh
run_step 04_migrations.sh
run_step 05_kagent.sh
run_step 07_tools.sh

KIND_CLUSTER_NAME="${KIND_CLUSTER_NAME:-multitenant-agent-k8s}"
KUBE_CTX="kind-${KIND_CLUSTER_NAME}"
REGISTRY_PORT="5001"

echo ""
echo -e "\033[0;32m══ Setup complete ══\033[0m"
echo ""
echo "  Cluster:  $KIND_CLUSTER_NAME"
echo "  Context:  $KUBE_CTX"
echo "  Registry: localhost:${REGISTRY_PORT}"
echo ""
echo "Port-forwards:"
echo "  kubectl port-forward -n platform svc/postgres     5432:5432  # Postgres"
echo "  kubectl port-forward -n platform svc/gotrue       9999:9999  # GoTrue"
echo "  kubectl port-forward -n kagent   svc/kagent-ui    3000:8080  # kagent UI"
echo ""
echo "Verify platform + shared-tools:"
echo "  kubectl get pods -n platform"
echo "  kubectl get pods -n kagent"
echo ""
echo "Then bootstrap tenants (reads .env):"
echo "  bash scripts/bootstrap-data.sh"
echo ""
echo "After bootstrap, verify tenants:"
echo "  kubectl get agents,pods -n tenant-alpha"
echo "  kubectl get agents,pods -n tenant-beta"
echo ""

echo -e "\033[1;33m══ Live status ══\033[0m"
echo ""
echo -e "\033[0;32m[platform]\033[0m"
kubectl get pods -n platform --context "$KUBE_CTX"
echo ""
echo -e "\033[0;32m[kagent]\033[0m"
kubectl get pods -n kagent --context "$KUBE_CTX"
echo ""
echo -e "\033[0;32m[shared-tools]\033[0m"
kubectl get pods -n shared-tools --context "$KUBE_CTX"
echo ""
echo -e "\033[0;32m[tenant-alpha]\033[0m"
kubectl get pods -n tenant-alpha --context "$KUBE_CTX" 2>/dev/null || echo "  (namespace not found)"
echo ""
echo -e "\033[0;32m[tenant-beta]\033[0m"
kubectl get pods -n tenant-beta --context "$KUBE_CTX" 2>/dev/null || echo "  (namespace not found)"
