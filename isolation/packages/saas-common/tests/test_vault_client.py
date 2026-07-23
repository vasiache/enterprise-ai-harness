"""Tests for vault_client secret reading."""

from unittest.mock import patch

import pytest
import saas_common.vault_client as vc


def test_read_secret_strips_whitespace(tmp_path):
    secret_file = tmp_path / "openai-api-key"
    secret_file.write_text("  sk-test-key\n")

    with patch.object(vc, "_SECRETS_PATH", tmp_path):
        assert vc.read_secret("openai-api-key") == "sk-test-key"


def test_read_secret_missing_raises(tmp_path):
    with patch.object(vc, "_SECRETS_PATH", tmp_path):
        with pytest.raises(FileNotFoundError):
            vc.read_secret("does-not-exist")


def test_get_secret_is_cached(tmp_path):
    secret_file = tmp_path / "api-key"
    secret_file.write_text("value1")

    with patch.object(vc, "_SECRETS_PATH", tmp_path):
        vc.get_secret.cache_clear()
        v1 = vc.get_secret("api-key")
        secret_file.write_text("value2")
        v2 = vc.get_secret("api-key")
        assert v1 == v2 == "value1"
        vc.get_secret.cache_clear()
