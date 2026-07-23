
CREATE TABLE IF NOT EXISTS platform.audit_log (
    id          BIGSERIAL,
    tenant_id   TEXT NOT NULL,
    ts          TIMESTAMPTZ DEFAULT now(),
    actor       TEXT NOT NULL,             -- user_id or 'system'
    action      TEXT NOT NULL,             -- 'agent.invoke','tool.call','auth.login'
    resource    TEXT,                      -- 'agent/sales-agent'
    detail      JSONB,
    ip          INET,
    PRIMARY KEY (id, ts)
) PARTITION BY RANGE (ts);

CREATE TABLE IF NOT EXISTS platform.audit_log_default
    PARTITION OF platform.audit_log DEFAULT;

CREATE INDEX IF NOT EXISTS idx_audit_tenant_ts
    ON platform.audit_log(tenant_id, ts DESC);
