
CREATE SCHEMA IF NOT EXISTS orders;

CREATE TABLE IF NOT EXISTS orders.leads (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       TEXT NOT NULL,
    customer_tg_id  BIGINT,
    product         TEXT,
    price           NUMERIC(12, 2),
    status          TEXT NOT NULL DEFAULT 'new', -- 'new','qualified','sold','lost'
    commission_rate NUMERIC(5, 4) DEFAULT 0.05,  -- e.g. 0.05 = 5%
    commission_amount NUMERIC(12, 2)
        GENERATED ALWAYS AS (price * commission_rate) STORED,
    created_at      TIMESTAMPTZ DEFAULT now(),
    sold_at         TIMESTAMPTZ,
    metadata        JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_leads_tenant ON orders.leads(tenant_id);
CREATE INDEX IF NOT EXISTS idx_leads_status ON orders.leads(tenant_id, status);
