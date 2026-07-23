
CREATE SCHEMA IF NOT EXISTS platform;

CREATE TABLE IF NOT EXISTS platform.tenants (
    id           TEXT PRIMARY KEY,          -- 'furnco', 'monitorco'
    plan         TEXT NOT NULL DEFAULT 'free',
    display_name TEXT,
    created_at   TIMESTAMPTZ DEFAULT now(),
    disabled_at  TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS platform.users (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   TEXT NOT NULL REFERENCES platform.tenants(id),
    org         TEXT NOT NULL,             -- 'sales', 'ops', 'management'
    email       TEXT,
    tg_id       BIGINT,
    role        TEXT NOT NULL DEFAULT 'user', -- 'user','org_admin','tenant_admin'
    created_at  TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_users_tenant ON platform.users(tenant_id);
CREATE INDEX IF NOT EXISTS idx_users_tg     ON platform.users(tg_id);
