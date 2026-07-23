"""saas-common - shared library for the SaaS agent platform.

Active baseline:
    pip install saas-common[tool]

Compatibility tail:
    saas_common.agent_base
    saas_common.state

These modules remain importable for pre-ADR-009 compatibility, but they are
not part of the active declarative baseline or current in-repo codepaths.
"""

from .auth import tenant_id_from_env
from .config import Settings, get_settings
from .state import BaseState
from .supabase_client import TenantDB

__all__ = ["TenantDB", "BaseState", "Settings", "get_settings", "tenant_id_from_env"]
