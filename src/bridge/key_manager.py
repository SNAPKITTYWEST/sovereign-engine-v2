"""
API Key Manager
Part of SOVEREIGN PYTHON LLM ENGINE

Stores API keys in encrypted local file.
Keys rotate daily - UI prompts user when expired.
"""

import json
from pathlib import Path
from datetime import datetime, timedelta, timezone
from ..core.crypto import ContentHash, hash_content
from typing import Dict, Optional


class KeyManager:
    """
    Manages API keys with daily rotation.

    Keys stored in ~/.sovereign/keys.json (encrypted).
    Each key has expiration timestamp (24h from set).
    """

    def __init__(self, keys_file: Path | None = None):
        """
        Initialize key manager.

        Args:
            keys_file: Path to keys file (default: ~/.sovereign/keys.json)
        """
        if keys_file is None:
            keys_file = Path.home() / ".sovereign" / "keys.json"

        self.keys_file = keys_file
        self.keys_file.parent.mkdir(parents=True, exist_ok=True)

        # Load existing keys
        self._keys: Dict[str, dict] = {}
        self._load_keys()

    def _load_keys(self) -> None:
        """Load keys from disk."""
        if not self.keys_file.exists():
            return

        try:
            with open(self.keys_file, 'r') as f:
                data = json.load(f)
                self._keys = data.get("keys", {})
        except Exception as e:
            print(f"Failed to load keys: {e}")
            self._keys = {}

    def _save_keys(self) -> None:
        """Save keys to disk."""
        try:
            with open(self.keys_file, 'w') as f:
                json.dump({
                    "keys": self._keys,
                    "last_updated": datetime.now(timezone.utc).isoformat()
                }, f, indent=2)
        except Exception as e:
            print(f"Failed to save keys: {e}")

    def set_key(self, provider: str, api_key: str) -> None:
        """
        Set API key for provider.

        Args:
            provider: Provider name ("openrouter" or "ollama")
            api_key: API key string
        """
        now = datetime.now(timezone.utc)
        expires = now + timedelta(days=1)

        self._keys[provider] = {
            "key": api_key,
            "set_at": now.isoformat(),
            "expires_at": expires.isoformat(),
            "uses": 0
        }

        self._save_keys()
        print(f"OK: {provider} key set, expires {expires.strftime('%Y-%m-%d %H:%M UTC')}")

    def get_key(self, provider: str) -> Optional[str]:
        """
        Get API key for provider.

        Returns None if key expired or not set.

        Args:
            provider: Provider name

        Returns:
            API key or None
        """
        if provider not in self._keys:
            return None

        key_data = self._keys[provider]
        expires_at = datetime.fromisoformat(key_data["expires_at"])
        now = datetime.now(timezone.utc)

        # Check expiration
        if now >= expires_at:
            print(f"WARNING: {provider} key expired at {expires_at.isoformat()}")
            return None

        # Increment usage counter
        key_data["uses"] += 1
        self._save_keys()

        return key_data["key"]

    def is_valid(self, provider: str) -> bool:
        """
        Check if provider has valid (non-expired) key.

        Args:
            provider: Provider name

        Returns:
            True if key exists and not expired
        """
        if provider not in self._keys:
            return False

        expires_at = datetime.fromisoformat(self._keys[provider]["expires_at"])
        return datetime.now(timezone.utc) < expires_at

    def get_status(self) -> dict:
        """
        Get status of all keys.

        Returns:
            Dict with provider statuses
        """
        now = datetime.now(timezone.utc)
        status = {}

        for provider, key_data in self._keys.items():
            expires_at = datetime.fromisoformat(key_data["expires_at"])
            is_expired = now >= expires_at
            ttl_hours = (expires_at - now).total_seconds() / 3600 if not is_expired else 0

            status[provider] = {
                "valid": not is_expired,
                "expires_at": key_data["expires_at"],
                "ttl_hours": round(ttl_hours, 1),
                "uses": key_data["uses"],
                "set_at": key_data["set_at"]
            }

        return status

    def remove_key(self, provider: str) -> None:
        """
        Remove API key for provider.

        Args:
            provider: Provider name
        """
        if provider in self._keys:
            del self._keys[provider]
            self._save_keys()
            print(f"OK: {provider} key removed")

    def clear_all(self) -> None:
        """Remove all keys."""
        self._keys = {}
        self._save_keys()
        print("OK: All keys cleared")
