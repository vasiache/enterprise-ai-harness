"""Tests for auth helpers."""

import pytest
from saas_common.auth import tenant_id_from_env


def test_tenant_id_from_env(monkeypatch):
    monkeypatch.setenv("TENANT_ID", "tech-support")
    assert tenant_id_from_env() == "tech-support"


def test_tenant_id_from_env_raises_if_missing(monkeypatch):
    monkeypatch.delenv("TENANT_ID", raising=False)
    with pytest.raises(RuntimeError, match="TENANT_ID"):
        tenant_id_from_env()
