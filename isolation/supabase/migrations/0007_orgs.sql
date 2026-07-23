
CREATE TABLE IF NOT EXISTS platform.orgs (
    id           TEXT        NOT NULL,              -- 'sales', 'management', 'default'
    tenant_id    TEXT        NOT NULL REFERENCES platform.tenants(id) ON DELETE CASCADE,
    display_name TEXT,                              -- human-readable: 'Отдел продаж'
    tg_bot_token TEXT,                              -- Telegram bot token for this org
    created_at   TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (tenant_id, id)                    -- composite PK: (furnco, sales)
);

CREATE INDEX IF NOT EXISTS idx_orgs_tenant ON platform.orgs(tenant_id);

ALTER TABLE platform.users
    ADD COLUMN IF NOT EXISTS org_id TEXT NOT NULL DEFAULT 'default';

INSERT INTO platform.orgs (tenant_id, id, display_name)
SELECT t.id, 'default', 'Default'
FROM platform.tenants t
LEFT JOIN platform.orgs o
  ON o.tenant_id = t.id AND o.id = 'default'
WHERE o.tenant_id IS NULL;

UPDATE platform.users
SET org_id = COALESCE(NULLIF(org, ''), 'default')
WHERE org_id IS NULL OR org_id = 'default';

INSERT INTO platform.orgs (tenant_id, id, display_name)
SELECT DISTINCT
    u.tenant_id,
    COALESCE(NULLIF(u.org, ''), 'default'),
    COALESCE(NULLIF(u.org, ''), 'Default')
FROM platform.users u
LEFT JOIN platform.orgs o
  ON o.tenant_id = u.tenant_id
 AND o.id = COALESCE(NULLIF(u.org, ''), 'default')
WHERE o.tenant_id IS NULL;

ALTER TABLE platform.users
    DROP CONSTRAINT IF EXISTS users_tenant_org_fk,
    ADD CONSTRAINT users_tenant_org_fk
    FOREIGN KEY (tenant_id, org_id)
    REFERENCES platform.orgs (tenant_id, id);

ALTER TABLE platform.users
    ALTER COLUMN org_id DROP DEFAULT;

ALTER TABLE platform.orgs ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_rls ON platform.orgs;
CREATE POLICY tenant_rls ON platform.orgs
    USING (tenant_id = current_setting('app.tenant_id', true));

GRANT SELECT, INSERT, UPDATE, DELETE ON platform.orgs TO app_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA platform
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app_user;
