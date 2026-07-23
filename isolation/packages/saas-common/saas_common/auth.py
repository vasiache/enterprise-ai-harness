"""JWT extraction helpers.

Phase 0: tenant_id comes from TENANT_ID environment variable (hardcoded
         per pod - set by kagent Agent CRD env section).
Phase 1+: extracted from GoTrue RS256 JWT passed via AgentGateway in
          the Authorization header. Claims shape:
          {"sub": "<uuid>", "app_metadata": {"tenant_id": "...", "org": "...", "role": "..."}}
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from jose import JWTError, jwt


@dataclass(frozen=True)
class Claims:
    sub: str
    tenant_id: str
    org: str
    role: str


def extract_claims(token: str, jwks_url: str | None = None) -> Claims:
    """Decode and validate a GoTrue RS256 JWT.

    In Phase 0 this is not called - use tenant_id_from_env() instead.
    In Phase 1+ AgentGateway forwards a verified JWT; we still validate
    locally for defence-in-depth.

    Args:
        token:    Raw bearer token (without 'Bearer ' prefix).
        jwks_url: GoTrue JWKS endpoint. Falls back to GOTRUE_JWKS_URL env var.

    Raises:
        ValueError: Token is invalid or missing required claims.
    """
    url = jwks_url or os.environ.get("GOTRUE_JWKS_URL", "")
    try:
        payload = jwt.decode(token, url, algorithms=["RS256"])
    except JWTError as e:
        raise ValueError(f"Invalid JWT: {e}") from e

    app_meta = payload.get("app_metadata", {})
    try:
        return Claims(
            sub=payload["sub"],
            tenant_id=app_meta["tenant_id"],
            org=app_meta["org"],
            role=app_meta.get("role", "user"),
        )
    except KeyError as e:
        raise ValueError(f"JWT missing required claim: {e}") from e


def tenant_id_from_env() -> str:
    """Return TENANT_ID env var - used in Phase 0 before JWT auth is wired."""
    tid = os.environ.get("TENANT_ID", "")
    if not tid:
        raise RuntimeError("TENANT_ID env var is not set")
    return tid
