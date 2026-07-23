
CREATE TABLE IF NOT EXISTS platform.usage_daily (
    tenant_id     TEXT NOT NULL,
    day           DATE NOT NULL,
    agent_calls   BIGINT DEFAULT 0,
    tool_calls    BIGINT DEFAULT 0,
    llm_tokens    BIGINT DEFAULT 0,
    storage_bytes BIGINT DEFAULT 0,
    PRIMARY KEY (tenant_id, day)
);
