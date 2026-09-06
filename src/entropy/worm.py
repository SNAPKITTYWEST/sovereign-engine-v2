"""WORM chain sealing — SHA-256 append-only audit receipts."""
from __future__ import annotations

import hashlib
import json
import time


def worm_seal(data: dict) -> str:
    """SHA-256 seal of a dictionary. Returns hex string."""
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


class WORMChain:
    """Append-only audit chain. Each entry hashes the previous."""

    def __init__(self) -> None:
        self._entries: list[dict] = []
        self._head = "0" * 64

    def append(self, data: dict) -> str:
        entry = {"prev": self._head, "ts": round(time.time(), 3), "data": data}
        seal  = worm_seal(entry)
        self._entries.append({**entry, "seal": seal})
        self._head = seal
        return seal

    @property
    def head(self) -> str:
        return self._head

    @property
    def length(self) -> int:
        return len(self._entries)

    def verify(self) -> bool:
        """Verify the chain is unbroken."""
        for e in self._entries:
            entry_copy = {k: v for k, v in e.items() if k != "seal"}
            if worm_seal(entry_copy) != e["seal"]:
                return False
        return True
