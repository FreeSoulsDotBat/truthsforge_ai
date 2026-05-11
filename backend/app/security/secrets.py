from __future__ import annotations

import json
import os
from pathlib import Path

from cryptography.fernet import Fernet

from app.core.config import settings
from app.core.contracts import ProviderName, ProviderSecretStatus

ENV_KEY_BY_PROVIDER = {
    ProviderName.openai: "OPENAI_API_KEY",
    ProviderName.anthropic: "ANTHROPIC_API_KEY",
    ProviderName.google: "GOOGLE_API_KEY",
}


class SecretStore:
    def __init__(self, state_dir: Path = settings.state_dir) -> None:
        self.state_dir = state_dir
        self.key_path = state_dir / "secret.key"
        self.secrets_path = state_dir / "secrets.json"
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.fernet = Fernet(self._load_or_create_key())

    def _load_or_create_key(self) -> bytes:
        if self.key_path.exists():
            return self.key_path.read_bytes()
        key = Fernet.generate_key()
        self.key_path.write_bytes(key)
        return key

    def _read_local(self) -> dict[str, str]:
        if not self.secrets_path.exists():
            return {}
        return json.loads(self.secrets_path.read_text(encoding="utf-8"))

    def _write_local(self, payload: dict[str, str]) -> None:
        self.secrets_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def get_api_key(self, provider: ProviderName) -> str | None:
        env_value = os.getenv(ENV_KEY_BY_PROVIDER[provider])
        if env_value:
            return env_value
        encrypted = self._read_local().get(provider.value)
        if not encrypted:
            return None
        return self.fernet.decrypt(encrypted.encode("utf-8")).decode("utf-8")

    def set_api_key(self, provider: ProviderName, api_key: str) -> None:
        payload = self._read_local()
        payload[provider.value] = self.fernet.encrypt(api_key.encode("utf-8")).decode("utf-8")
        self._write_local(payload)

    def delete_api_key(self, provider: ProviderName) -> None:
        payload = self._read_local()
        payload.pop(provider.value, None)
        self._write_local(payload)

    def status(self, provider: ProviderName) -> ProviderSecretStatus:
        if os.getenv(ENV_KEY_BY_PROVIDER[provider]):
            return ProviderSecretStatus(provider=provider, configured=True, source="env")
        configured = provider.value in self._read_local()
        return ProviderSecretStatus(
            provider=provider,
            configured=configured,
            source="local" if configured else "none",
        )

    def all_statuses(self) -> list[ProviderSecretStatus]:
        return [self.status(provider) for provider in ProviderName]


_secret_store: SecretStore | None = None


def get_secret_store() -> SecretStore:
    global _secret_store
    if _secret_store is None:
        _secret_store = SecretStore()
    return _secret_store
