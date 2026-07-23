"""Environment-based configuration."""

import os
from functools import lru_cache

_DEFAULT_KAGENT_URL = "http://kagent-controller.kagent.svc:8083"


class Settings:
    """Reads config from environment variables.

    Phase 0: tenant_id is hardcoded via TENANT_ID env var.
    Phase 1+: extracted from JWT claims instead.
    """

    database_url: str
    vault_secrets_path: str
    tenant_id: str
    org_id: str
    agent_name: str
    kagent_url: str

    def __init__(self) -> None:
        self.database_url = os.environ["DATABASE_URL"]
        self.vault_secrets_path = os.environ.get("VAULT_SECRETS_PATH", "/vault/secrets")
        self.tenant_id = os.environ["TENANT_ID"]
        self.org_id = os.environ.get("ORG_ID", os.environ.get("ORG", "default"))
        self.agent_name = os.environ.get("AGENT_NAME", "agent")
        self.kagent_url = os.environ.get("KAGENT_URL", _DEFAULT_KAGENT_URL)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
