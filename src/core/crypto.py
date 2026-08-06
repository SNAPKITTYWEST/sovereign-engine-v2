"""
Layer 0: Trust Root — Cryptographic Primitives
Part of SOVEREIGN PYTHON LLM ENGINE

Dependencies:
- hashlib (stdlib)
- nacl.signing (PyNaCl)
- nacl.encoding (PyNaCl)
"""

from hashlib import blake2b
from typing import NewType
from nacl.signing import SigningKey, VerifyKey
from nacl.encoding import Base64Encoder, HexEncoder


# ==========================================
# Type Definitions
# ==========================================

ContentHash = NewType('ContentHash', str)  # Blake3 hex digest
Signature = NewType('Signature', str)      # Ed25519 signature (base64)


# ==========================================
# Hash Primitives
# ==========================================

def hash_content(data: bytes) -> ContentHash:
    """
    Canonical Blake2b hash for content addressing.

    Blake2b chosen over Blake3 for stdlib availability.
    64-byte digest, hex-encoded.
    """
    hasher = blake2b(digest_size=64)
    hasher.update(data)
    return ContentHash(hasher.hexdigest())


def hash_multipart(parts: list[bytes]) -> ContentHash:
    """
    Hash multiple parts in sequence.
    Useful for Merkle tree construction.
    """
    hasher = blake2b(digest_size=64)
    for part in parts:
        hasher.update(part)
    return ContentHash(hasher.hexdigest())


# ==========================================
# Signature Primitives
# ==========================================

def generate_keypair() -> tuple[SigningKey, VerifyKey]:
    """Generate Ed25519 keypair."""
    signing_key = SigningKey.generate()
    verify_key = signing_key.verify_key
    return signing_key, verify_key


def sign_artifact(key: SigningKey, data: bytes) -> Signature:
    """
    Sign data with Ed25519 private key.
    Returns base64-encoded signature.
    """
    signed = key.sign(data, encoder=Base64Encoder)
    return Signature(signed.signature.decode('utf-8'))


def verify_signature(pubkey: VerifyKey, data: bytes, sig: Signature) -> bool:
    """
    Verify Ed25519 signature.
    Returns True if valid, False otherwise (does not raise).
    """
    try:
        pubkey.verify(data, sig.encode('utf-8'), encoder=Base64Encoder)
        return True
    except Exception:
        return False


def serialize_public_key(key: VerifyKey) -> str:
    """Serialize public key to hex string."""
    return key.encode(encoder=HexEncoder).decode('utf-8')


def deserialize_public_key(hex_str: str) -> VerifyKey:
    """Deserialize public key from hex string."""
    return VerifyKey(hex_str, encoder=HexEncoder)


# ==========================================
# Key Generation
# ==========================================

def generate_signing_key() -> SigningKey:
    """
    Generate new random signing key.
    Uses OS cryptographically secure random source.
    """
    import secrets
    return SigningKey(secrets.token_bytes(32))


def derive_signing_key(seed: bytes) -> SigningKey:
    """
    Derive deterministic signing key from seed.
    Useful for reproducible test keys.
    """
    if len(seed) != 32:
        raise ValueError("Seed must be exactly 32 bytes")
    return SigningKey(seed)


# ==========================================
# Content-Addressed Artifact ID
# ==========================================

def artifact_id(content: bytes, metadata: bytes) -> ContentHash:
    """
    Generate content-addressed ID from content + metadata.
    Ensures both content and metadata are integrity-checked.
    """
    return hash_multipart([content, metadata])
