"""
Layer 0: Trust Root & Core Infrastructure
Part of SOVEREIGN PYTHON LLM ENGINE

Exports:
- Cryptography (crypto.py): hash_content, sign_artifact, generate_signing_key, SigningKey
- Evidence ledger (evidence.py): WORMLedger, EvidenceRecord
- Binary storage (storage.py): WORMFile, CheckpointFile
- Path security (path_jail.py): PathJail, SSRFGuard
- Type protocols (types.py): Model, Tool, etc.
"""

from .crypto import (
    ContentHash,
    Signature,
    SigningKey,
    hash_content,
    sign_artifact,
    generate_signing_key,
)

from .evidence import (
    WORMLedger,
    EvidenceRecord,
)

from .storage import (
    WORMFile,
    WORMRecord,
    CheckpointFile,
    CheckpointRecord,
)

from .path_jail import (
    PathJail,
    PathJailError,
    SSRFGuard,
)

from .protocols import (
    Model,
    Tool,
)

__all__ = [
    # Cryptography
    "ContentHash",
    "Signature",
    "SigningKey",
    "hash_content",
    "sign_artifact",
    "generate_signing_key",

    # Evidence & ledger
    "WORMLedger",
    "EvidenceRecord",

    # Storage
    "WORMFile",
    "WORMRecord",
    "CheckpointFile",
    "CheckpointRecord",

    # Path security
    "PathJail",
    "PathJailError",
    "SSRFGuard",

    # Protocols
    "Model",
    "Tool",
]
