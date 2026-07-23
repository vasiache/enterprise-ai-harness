
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'app_user') THEN
        CREATE ROLE app_user WITH LOGIN NOINHERIT NOBYPASSRLS
            PASSWORD 'apppassword';  -- overridden via helm values in prod
    END IF;
END
$$;

GRANT USAGE ON SCHEMA platform, orders TO app_user;
GRANT SELECT, INSERT, UPDATE, DELETE
    ON ALL TABLES IN SCHEMA platform TO app_user;
GRANT SELECT, INSERT, UPDATE, DELETE
    ON ALL TABLES IN SCHEMA orders TO app_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA platform
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA orders
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app_user;

GRANT USAGE ON ALL SEQUENCES IN SCHEMA platform TO app_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA platform
    GRANT USAGE ON SEQUENCES TO app_user;

DO $$
BEGIN
    IF EXISTS (SELECT FROM pg_namespace WHERE nspname = 'rag') THEN
        GRANT USAGE ON SCHEMA rag TO app_user;
        GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA rag TO app_user;
        ALTER DEFAULT PRIVILEGES IN SCHEMA rag
            GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app_user;
    END IF;
END
$$;

ALTER DATABASE postgres SET app.tenant_id = '';

ALTER TABLE platform.tenants ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_rls ON platform.tenants;
CREATE POLICY tenant_rls ON platform.tenants
    USING (id = current_setting('app.tenant_id', true));

ALTER TABLE platform.users ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_rls ON platform.users;
CREATE POLICY tenant_rls ON platform.users
    USING (tenant_id = current_setting('app.tenant_id', true));

ALTER TABLE platform.audit_log ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_rls ON platform.audit_log;
CREATE POLICY tenant_rls ON platform.audit_log
    USING (tenant_id = current_setting('app.tenant_id', true));

ALTER TABLE platform.usage_daily ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_rls ON platform.usage_daily;
CREATE POLICY tenant_rls ON platform.usage_daily
    USING (tenant_id = current_setting('app.tenant_id', true));

ALTER TABLE orders.leads ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_rls ON orders.leads;
CREATE POLICY tenant_rls ON orders.leads
    USING (tenant_id = current_setting('app.tenant_id', true));

DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'supabase_auth_admin') THEN
        CREATE ROLE supabase_auth_admin WITH LOGIN
            PASSWORD 'supabase_admin';  -- overridden via helm values in prod
    END IF;
END
$$;
