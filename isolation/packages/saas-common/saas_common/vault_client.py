"""Read secrets injected by HashiCorp Vault Agent sidecar.

Vault sidecar writes secrets as plain-text files into a tmpfs volume
mounted at VAULT_SECRETS_PATH (default: /vault/secrets).

File naming convention: /vault/secrets/<key>
Example:               /vault/secrets/openai-api-key

Never read secrets from environment variables or K8s ConfigMaps.
"""

import os
from functools import lru_cache
from pathlib import Path

_SECRETS_PATH = Path(os.environ.get("VAULT_SECRETS_PATH", "/vault/secrets"))


def read_secret(key: str) -> str:
    """Read a secret value from the Vault sidecar file.

    Args:
        key: Secret file name (e.g. 'openai-api-key', 'db-password')

    Returns:
        Secret value with surrounding whitespace stripped.

    Raises:
        FileNotFoundError: Secret file does not exist.
        PermissionError: File cannot be read.
    """
    path = _SECRETS_PATH / key
    return path.read_text().strip()


@lru_cache(maxsize=64)
def get_secret(key: str) -> str:
    """Cached version of read_secret - suitable for static secrets.

    Do NOT use for secrets that rotate during the process lifetime;
    use read_secret() directly in that case.
    """
    return read_secret(key)
