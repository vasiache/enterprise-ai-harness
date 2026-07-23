#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

REGISTRY_PORT="${REGISTRY_PORT:-5001}"
REGISTRY="localhost:${REGISTRY_PORT}"

_src_hash() {
  local dockerfile="$1"
  shift
  {
    cat "${ROOT_DIR}/${dockerfile}"
    for p in "$@"; do
      find "${ROOT_DIR}/${p}" -type f 2>/dev/null | sort | xargs cat 2>/dev/null
    done
  } | sha256sum | cut -c1-16
}

_image_hash() {
  local tag="$1"
  docker inspect --format '{{ index .Config.Labels "src-hash" }}' "${tag}" 2>/dev/null || true
}

build_and_push() {
  local name="$1"
  local dockerfile="$2"
  shift 2

  local tag="${REGISTRY}/${name}:latest"
  local current_hash
  current_hash=$(_src_hash "${dockerfile}" "$@")

  local image_hash
  image_hash=$(_image_hash "${tag}")

  if [[ "${FORCE_BUILD:-0}" != "1" && -n "${image_hash}" && "${image_hash}" == "${current_hash}" ]]; then
    echo "[build] ${name} - up to date (hash=${current_hash}), skipping"
    return 0
  fi

  echo "[build] ${name} -> ${tag}  (hash=${current_hash})"
  docker build \
    --label "src-hash=${current_hash}" \
    -t "${tag}" \
    -f "${ROOT_DIR}/${dockerfile}" \
    "${ROOT_DIR}"
  docker push "${tag}"
}

build_and_push "ping-tool"         "tools/ping-tool/Dockerfile"         "tools/ping-tool" "packages/saas-common"
build_and_push "tenant-info-tool"  "tools/tenant-info-tool/Dockerfile"  "tools/tenant-info-tool" "packages/saas-common"

build_and_push "order-tracker"     "tools/order-tracker/Dockerfile"     "tools/order-tracker" "packages/saas-common"

build_and_push "tg-bot"            "channels/tg-bot/Dockerfile"         "channels/tg-bot" "packages/saas-common"

