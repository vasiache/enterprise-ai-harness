#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

source "$SCRIPT_DIR/cluster/common.sh"
load_env

PY="python3"
ADMIN="$ROOT_DIR/scripts/admin"
KUBE_CONTEXT="${KUBE_CONTEXT:-kind-multitenant-agent-k8s}"

_PF_POSTGRES_PID=""
_PF_PIDS_KEEP=()  # port-forwards, которые остаются жить после выхода скрипта
_cleanup_pf() {
  if [[ ${#_PF_PIDS_KEEP[@]} -gt 0 ]]; then
    info "port-forwards remain active (postgres, kagent, ping-tool): ${_PF_PIDS_KEEP[*]}"
    info "  logs: /tmp/pf-postgres.log  /tmp/pf-kagent.log  /tmp/pf-pingtool.log"
    info "  to stop: kill ${_PF_PIDS_KEEP[*]}"
  fi
}
trap _cleanup_pf EXIT

if ! nc -z 127.0.0.1 5432 2>/dev/null; then
  step "Starting postgres port-forward (localhost:5432)"
  kubectl port-forward -n platform svc/postgres 5432:5432 \
    --context "$KUBE_CONTEXT" &>/tmp/pf-postgres.log &
  _PF_POSTGRES_PID=$!
  _PF_PIDS_KEEP+=("$_PF_POSTGRES_PID")
  info "port-forward PID: $_PF_POSTGRES_PID"
else
  info "localhost:5432 already open - skipping port-forward"
fi

step "Waiting for postgres on localhost:5432"
wait_for_tcp 127.0.0.1 5432

step "Tenant: alpha"

info "create-tenant alpha"
$PY "$ADMIN/tenant.py" create-tenant --id alpha --plan free --name "Alpha Org" || warn "already exists"

info "create-org alpha/management"
$PY "$ADMIN/tenant.py" create-org --tenant alpha --org management --name "Management" || warn "already exists"

info "create-org alpha/sales"
$PY "$ADMIN/tenant.py" create-org --tenant alpha --org sales --name "Sales" || warn "already exists"

if [[ -n "${TG_BOT_TOKEN_ALPHA_MANAGEMENT:-}" ]]; then
  info "set-bot-token alpha/management"
  $PY "$ADMIN/tenant.py" set-bot-token \
    --tenant alpha --org management \
    --token "$TG_BOT_TOKEN_ALPHA_MANAGEMENT"
else
  warn "TG_BOT_TOKEN_ALPHA_MANAGEMENT not set - skipping bot token"
fi

step "Tenant: beta"

info "create-tenant beta"
$PY "$ADMIN/tenant.py" create-tenant --id beta --plan free --name "Beta Org" || warn "already exists"

info "create-org beta/management"
$PY "$ADMIN/tenant.py" create-org --tenant beta --org management --name "Management" || warn "already exists"

info "create-org beta/sales"
$PY "$ADMIN/tenant.py" create-org --tenant beta --org sales --name "Sales" || warn "already exists"

step "Users: alpha"

info "user admin@alpha.dev (tenant_admin, tg=298974200)"
$PY "$ADMIN/user.py" create \
  --tenant alpha --org management \
  --email admin@alpha.dev \
  --tg-id 298974200 \
  --role tenant_admin \
  || warn "already exists"

info "user seller@alpha.dev (user, tg=300000001)"
$PY "$ADMIN/user.py" create \
  --tenant alpha --org sales \
  --email seller@alpha.dev \
  --tg-id 300000001 \
  --role user \
  || warn "already exists"

step "Users: beta"

info "user admin@beta.dev (tenant_admin, no tg)"
$PY "$ADMIN/user.py" create \
  --tenant beta --org management \
  --email admin@beta.dev \
  --no-tg \
  --role tenant_admin \
  || warn "already exists"

info "user seller@beta.dev (user, tg=400000001)"
$PY "$ADMIN/user.py" create \
  --tenant beta --org sales \
  --email seller@beta.dev \
  --tg-id 400000001 \
  --role user \
  || warn "already exists"

step "Deploy tenants to K8s"

info "deploy alpha"
$PY "$ADMIN/tenant.py" deploy --tenant alpha

info "deploy beta"
$PY "$ADMIN/tenant.py" deploy --tenant beta

step "Starting port-forwards for local testing"

if ! nc -z 127.0.0.1 8083 2>/dev/null; then
  kubectl port-forward -n kagent svc/kagent-controller 8083:8083 \
    --context "$KUBE_CONTEXT" &>/tmp/pf-kagent.log &
  _pf_ka=$!; _PF_PIDS_KEEP+=("$_pf_ka")
  info "kagent port-forward → localhost:8083 (pid $_pf_ka)"
else
  info "localhost:8083 already open - skipping"
fi

if ! nc -z 127.0.0.1 8000 2>/dev/null; then
  kubectl port-forward -n shared-tools svc/ping-tool 8000:8000 \
    --context "$KUBE_CONTEXT" &>/tmp/pf-pingtool.log &
  _pf_pt=$!; _PF_PIDS_KEEP+=("$_pf_pt")
  info "ping-tool port-forward → localhost:8000 (pid $_pf_pt)"
else
  info "localhost:8000 already open - skipping"
fi

step "Done"
echo ""
info "DB state:"
echo "  python scripts/admin/tenant.py list-tenants"
echo "  python scripts/admin/user.py list --tenant alpha"
echo ""
info "K8s state:"
echo "  kubectl get pods -n tenant-alpha --context kind-multitenant-agent-k8s"
echo "  kubectl get pods -n tenant-beta  --context kind-multitenant-agent-k8s"
echo "  kubectl get agents -n tenant-alpha --context kind-multitenant-agent-k8s"
