
ALTER TABLE platform.audit_log
    ADD CONSTRAINT fk_audit_log_tenant
    FOREIGN KEY (tenant_id) REFERENCES platform.tenants (id)
    ON DELETE RESTRICT;

ALTER TABLE platform.usage_daily
    ADD CONSTRAINT fk_usage_daily_tenant
    FOREIGN KEY (tenant_id) REFERENCES platform.tenants (id)
    ON DELETE RESTRICT;

ALTER TABLE orders.leads
    ADD CONSTRAINT fk_leads_tenant
    FOREIGN KEY (tenant_id) REFERENCES platform.tenants (id)
    ON DELETE RESTRICT;
