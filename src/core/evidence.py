"""
Layer 0: WORM Evidence Ledger
Part of SOVEREIGN PYTHON LLM ENGINE

Append-only binary ledger backed by storage.WORMFile (struct-packed records).
No JSON, no text, no injection surface.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

from .crypto import ContentHash, Signature, SigningKey, hash_content, sign_artifact
from .storage import WORMFile, WORMRecord


# ─────────────────────────────────────────────
# Evidence Record (public API type)
# ─────────────────────────────────────────────

@dataclass(frozen=True)
class EvidenceRecord:
    timestamp_ns: int
    event_type:   str
    content_hash: bytes
    signature:    bytes
    payload:      bytes
    metadata:     bytes
    prev_hash:    bytes

    @property
    def timestamp(self) -> float:
        return self.timestamp_ns / 1_000_000_000


def _record_from_worm(w: WORMRecord) -> EvidenceRecord:
    return EvidenceRecord(
        timestamp_ns=w.timestamp_ns,
        event_type=w.event_type,
        content_hash=w.content_hash,
        signature=w.signature,
        payload=w.payload,
        metadata=w.metadata,
        prev_hash=w.prev_hash
    )


# ─────────────────────────────────────────────
# WORM Ledger
# ─────────────────────────────────────────────

class WORMLedger:
    """
    Write-Once-Read-Many append-only ledger.

    Backed by binary struct-packed records (WORMFile).
    No JSONL, no text encoding, no injection surface.

    Public API is unchanged from the JSONL version —
    callers pass raw bytes for payload, raw bytes for metadata.
    """

    def __init__(self, ledger_path: Path, signing_key: SigningKey | None = None):
        self._file = WORMFile(ledger_path, signing_key=signing_key)
        self.ledger_path = ledger_path
        self.signing_key = signing_key

    def append(
        self,
        event_type: str,
        data: bytes | dict | str | None = None,
        metadata: bytes | dict | str | None = None
    ) -> EvidenceRecord:
        """
        Append evidence record.

        data and metadata accept:
          bytes  — written as-is
          dict   — encoded as UTF-8 key=value pairs (no JSON)
          str    — encoded as UTF-8
          None   — empty bytes
        """
        payload  = self._coerce(data)
        meta     = self._coerce(metadata)
        rec      = self._file.append(event_type, payload, meta)
        return _record_from_worm(rec)

    def read_all(self) -> list[EvidenceRecord]:
        return [_record_from_worm(r) for r in self._file.scan()]

    def scan(self) -> Iterator[EvidenceRecord]:
        for r in self._file.scan():
            yield _record_from_worm(r)

    def verify_chain(self) -> bool:
        valid, _ = self._file.verify_chain()
        return valid

    def get_records_by_type(self, event_type: str) -> list[EvidenceRecord]:
        return [_record_from_worm(r) for r in self._file.scan_by_type(event_type)]

    def count(self) -> int:
        return self._file.count()

    @staticmethod
    def _coerce(value: bytes | dict | str | None) -> bytes:
        if value is None:
            return b''
        if isinstance(value, bytes):
            return value
        if isinstance(value, str):
            return value.encode('utf-8')
        if isinstance(value, dict):
            # Flat key=value encoding — no JSON, no injection
            parts = []
            for k, v in value.items():
                k_s = str(k).replace('=', '_').replace('\n', '_')
                v_s = str(v).replace('\n', '_')
                parts.append(f"{k_s}={v_s}")
            return '\n'.join(parts).encode('utf-8')
        return str(value).encode('utf-8')


# ─────────────────────────────────────────────
# Stats helper
# ─────────────────────────────────────────────

def ledger_stats(ledger: WORMLedger) -> dict[str, Any]:
    records = ledger.read_all()
    event_counts: dict[str, int] = {}
    for r in records:
        event_counts[r.event_type] = event_counts.get(r.event_type, 0) + 1
    return {
        'total_records':   len(records),
        'event_counts':    event_counts,
        'first_timestamp': records[0].timestamp if records else None,
        'last_timestamp':  records[-1].timestamp if records else None,
        'chain_valid':     ledger.verify_chain()
    }
