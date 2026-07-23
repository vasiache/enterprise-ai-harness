#!/usr/bin/env bash

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
info()  { echo -e "${GREEN}[+]${NC} $*"; }
warn()  { echo -e "${YELLOW}[!]${NC} $*"; }
error() { echo -e "${RED}[✗]${NC} $*"; exit 1; }
step()  { echo -e "\n${GREEN}══ $* ══${NC}"; }

load_env() {
  if [[ -f "${ROOT_DIR}/.env" ]]; then
    set -a && source "${ROOT_DIR}/.env" && set +a
    info "Loaded .env from ${ROOT_DIR}/.env"
  fi
}

KIND_CLUSTER_NAME="${KIND_CLUSTER_NAME:-multitenant-agent-k8s}"
KUBE_CTX="kind-${KIND_CLUSTER_NAME}"
REGISTRY_NAME="kind-registry"
REGISTRY_PORT="5001"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-postgres}"
POSTGRES_APP_PASSWORD="${POSTGRES_APP_PASSWORD:-apppassword}"

KAGENT_VERSION="${KAGENT_VERSION:-0.8.1}"

OPENAI_BASE_URL="${OPENAI_BASE_URL:-}"
OPENAI_MODEL="${OPENAI_MODEL:-gpt-4o-mini}"


wait_for_tcp() {
  local host="$1" port="$2" max="${3:-30}" sleep_s="${4:-2}"
  info "Waiting for ${host}:${port} (up to $((max * sleep_s))s)..."
  for i in $(seq 1 "$max"); do
    if (: >/dev/tcp/"${host}"/"${port}") 2>/dev/null; then
      info "${host}:${port} reachable ✓"
      return 0
    fi
    warn "  attempt ${i}/${max} - not ready, retrying in ${sleep_s}s..."
    sleep "$sleep_s"
  done
  error "${host}:${port} not reachable after $((max * sleep_s))s"
}


load_images() {
  local cluster="$1"; shift
  for img in "$@"; do
    info "Ensuring image: $img"
    docker image inspect "$img" &>/dev/null || docker pull "$img"
    kind load docker-image "$img" --name "$cluster"
  done
}

detect_tg_proxy() {
  if [[ -n "${TG_HTTPS_PROXY:-}" ]]; then
    return  # already set
  fi
  local gw
  gw=$(docker network inspect kind 2>/dev/null \
    | grep '"Gateway"' \
    | grep -v ':' \
    | head -1 \
    | sed 's/.*"Gateway": "\(.*\)".*/\1/' || echo "")
  if [[ -n "$gw" ]]; then
    export TG_HTTPS_PROXY="http://${gw}:2080"
    info "TG_HTTPS_PROXY auto-detected: $TG_HTTPS_PROXY"
  fi
}
