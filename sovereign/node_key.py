"""
Sovereign Node Key — SnapKitty execution gate.
Without a valid key, model routing refuses to compute.
"""
import hmac
import hashlib
import os
import time
from typing import Optional

SNAPKITTY_KEY_PREFIX = "SNK-"
KEY_HEADER = "X-Sovereign-Node-Key"
KEY_ENV = "SNAPKITTY_NODE_KEY"

# Public key material — the HMAC secret is sovereign (not in this file)
# Contact: licensing@snapkittywest.dev
_SOVEREIGN_SECRET = os.environ.get("SNAPKITTY_NODE_SECRET", "")

def verify_node_key(key: str) -> bool:
    """
    Verify a sovereign node key.
    Keys are HMAC-SHA256 signed tokens issued by the Trust.
    Without SNAPKITTY_NODE_SECRET set, all keys are rejected.
    """
    if not key or not key.startswith(SNAPKITTY_KEY_PREFIX):
        return False
    if not _SOVEREIGN_SECRET:
        return False
    try:
        # Format: SNK-{payload}-{signature}
        parts = key[len(SNAPKITTY_KEY_PREFIX):].rsplit("-", 1)
        if len(parts) != 2:
            return False
        payload, signature = parts
        expected = hmac.new(
            _SOVEREIGN_SECRET.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()[:32]
        return hmac.compare_digest(expected, signature)
    except Exception:
        return False

def require_node_key(key: Optional[str] = None) -> None:
    """
    Raise if no valid node key. Call at model routing entry points.
    """
    k = key or os.environ.get(KEY_ENV, "")
    if not verify_node_key(k):
        raise PermissionError(
            "\n"
            "  ╔══════════════════════════════════════════════════╗\n"
            "  ║     SOVEREIGN NODE KEY REQUIRED                  ║\n"
            "  ║                                                  ║\n"
            "  ║  This software requires a valid SnapKitty       ║\n"
            "  ║  node key to activate model routing.            ║\n"
            "  ║                                                  ║\n"
            "  ║  Get your key:                                   ║\n"
            "  ║  licensing@snapkittywest.dev                     ║\n"
            "  ║  https://github.com/SNAPKITTYWEST               ║\n"
            "  ║                                                  ║\n"
            "  ║  Copyright (C) 2026 Bel Esprit D'Accord         ║\n"
            "  ║  Irrevocable Trust (EIN 42-697643)               ║\n"
            "  ╚══════════════════════════════════════════════════╝\n"
        )

# FastAPI / Flask middleware helper
def node_key_middleware(request_headers: dict) -> None:
    key = request_headers.get(KEY_HEADER, "")
    require_node_key(key)
