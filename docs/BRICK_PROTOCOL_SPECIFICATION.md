# SKUNKSLAB FEDERATED BRICK PROTOCOL

## BRICK = Bound Repository Integrity & Cryptographic Kernel

**Version:** 1.0  
**Status:** Formal Specification  
**Date:** 2026-08-12

---

## Overview

BRICK is a federated repository integrity and identity sealing scheme that combines:
- **SHA3-256**: Deterministic content/tree hashing
- **AES-256-GCM**: Authenticated encryption for sealed manifests
- **SAML 2.0**: Federated identity binding and assertion

Each repository becomes a content-addressed "brick" that can be instantly validated or rejected by federation nodes via cryptographic verification.

---

## Core Architecture

```
Repository Tree
      ↓ canonicalize
Manifest(repo_id, commit, paths, file_hashes, policy)
      ↓ SHA3-256
ROOT_HASH
      ↓ AES-256-GCM encrypt
SEALED_BRICK
      ↓ SAML bind
FEDERATED_BRICK_RECEIPT
```

---

## Cryptographic Primitives

### 1. File-Level Hashing

```
H_file = SHA3-256(file_bytes)
```

For each file in the repository, compute its SHA3-256 digest.

### 2. Repository Tree Hash

```
H_tree = SHA3-256(
           repo_id ||
           commit_id ||
           sort(path_i || H_file_i)
         )
```

- Concatenate repository ID and commit ID
- Sort all (path, file_hash) pairs lexicographically
- Hash the canonical representation

This ensures:
- ✓ Same content always produces same hash (deterministic)
- ✓ Any file change is instantly detectable
- ✓ Canonical ordering prevents collision attacks

### 3. BRICK Identifier

```
BRICK_ID = SHA3-256(
             "SKUNKSLAB-BRICK-v1" ||
             H_tree ||
             federation_id ||
             policy_id
           )
```

- Include protocol version to prevent downgrade
- Include federation ID (separates federated domains)
- Include policy ID (encodes governance rules)
- This becomes the Authenticated Associated Data (AAD) for encryption

### 4. Sealed Material via AES-256-GCM

```
K_repo = derive_key(master_secret, repo_id, federation_id)
nonce = random(96 bits)

C, TAG = AES-256-GCM(
           K_repo,
           nonce,
           manifest,
           AAD = BRICK_ID || repo_id || federation_id
         )
```

- Derive encryption key from master secret (never use SAML material as key)
- Generate random nonce for each encryption
- Encrypt the full manifest (includes all metadata)
- Authentication tag ensures integrity and binds identity

### 5. SAML Identity Binding

The SAML assertion provides:
- Federation issuer (which federation node issued this)
- Subject (who owns/authored the repository)
- Assertion ID (unique identifier within federation)
- Timestamp and signature

**Important:** SAML is NOT used as cryptographic key material. Instead:
- Derive AES key independently via secure key derivation (HKDF, Argon2, etc.)
- Bind SAML identity metadata into the AAD
- Verify SAML signature separately from AES-GCM tag

---

## BRICK Receipt Structure

```json
{
  "brick_id": "SHA3_DIGEST_HEX",
  "repository_hash": "H_TREE_HEX",
  "ciphertext_hash": "SHA3_256(C || TAG)_HEX",
  "saml_issuer": "federation.example.com",
  "saml_subject": "user@example.com",
  "saml_assertion_id": "uuid",
  "policy_id": "policy_v1",
  "timestamp": "2026-08-12T11:03:00Z",
  "nonce": "BASE64_ENCODED_NONCE",
  "ciphertext": "BASE64_ENCODED_C",
  "auth_tag": "BASE64_ENCODED_TAG"
}
```

---

## Verification Algorithm

Federation nodes verify a BRICK receipt as follows:

### Step 1: Recompute H_tree
```
H_tree' = SHA3-256(
            repo_id ||
            commit_id ||
            sort(path_i || H_file_i)
          )

Assert H_tree' == receipt.repository_hash
```

### Step 2: Verify SAML Assertion
```
saml_cert = fetch_issuer_certificate(receipt.saml_issuer)
Assert verify_signature(receipt.saml_assertion, saml_cert) == TRUE
Assert receipt.saml_subject matches authorization policy
```

### Step 3: Recompute BRICK_ID
```
BRICK_ID' = SHA3-256(
              "SKUNKSLAB-BRICK-v1" ||
              H_tree' ||
              receipt.federation_id ||
              receipt.policy_id
            )

Assert BRICK_ID' == receipt.brick_id
```

### Step 4: Verify AES-GCM Authentication
```
K_repo' = derive_key(master_secret, repo_id, federation_id)
TAG' = AES-256-GCM-VERIFY(
         K_repo',
         receipt.nonce,
         receipt.ciphertext,
         AAD = receipt.brick_id || repo_id || federation_id
       )

Assert TAG' == receipt.auth_tag
```

### Step 5: Decrypt and Validate Manifest
```
manifest = AES-256-GCM-DECRYPT(
             K_repo',
             receipt.nonce,
             receipt.ciphertext,
             receipt.auth_tag,
             AAD = receipt.brick_id || repo_id || federation_id
           )

Assert manifest.policy_id == receipt.policy_id
Assert manifest.federation_id == receipt.federation_id
```

**If all steps pass:** BRICK is valid and can be accepted.  
**If any step fails:** BRICK is invalid and must be rejected instantly.

---

## Federation Policy Binding

Each BRICK includes a `policy_id` that encodes:
- Which federation nodes are allowed to hold this brick
- What operations are permitted (read, write, fork, merge)
- Governance rules (voting thresholds, audit requirements)
- Revocation mechanisms

The policy is included in:
1. The BRICK_ID computation (makes it part of the identity)
2. The AES-GCM AAD (makes it authenticated)
3. The SAML assertion (binds it to issuing authority)

---

## Security Properties

### Integrity
- ✓ SHA3-256 detects any single-bit change
- ✓ AES-GCM authentication tag prevents forgery
- ✓ SAML signature prevents issuer spoofing

### Authenticity
- ✓ SAML assertion binds to federated identity
- ✓ AES-GCM tag proves encryption wasn't tampered with
- ✓ Policy binding ensures only authorized federations accept

### Confidentiality
- ✓ AES-256-GCM protects manifest contents
- ✓ Nonce randomization prevents replay
- ✓ Key derivation prevents key reuse across repos

### Availability
- ✓ No key escrow (each repo has independent derived key)
- ✓ Stateless verification (no server required)
- ✓ Instant rejection (no expensive validation)

---

## Implementation Checklist

- [ ] SHA3-256 hash computation (use libssl or libgcrypt)
- [ ] AES-256-GCM encryption/decryption with nonce handling
- [ ] HKDF key derivation from master secret
- [ ] SAML 2.0 assertion parsing and signature verification
- [ ] BRICK receipt JSON serialization
- [ ] Verification algorithm implementation
- [ ] Federation policy enforcement
- [ ] Test suite (positive + negative cases)
- [ ] Performance benchmarking
- [ ] Documentation and examples

---

## Example: BRICK Sealing a Repository

```rust
// Input: repository contents
let repo_id = "snapkitty/ledger-core";
let commit_id = "a1b2c3d4";
let files = vec![
  ("src/main.rs", "sha3_hash_here"),
  ("src/lib.rs", "sha3_hash_there"),
];

// Step 1: Compute H_tree
let h_tree = sha3_256(
  format!("{}||{}", repo_id, commit_id) +
  &canonical_sort_and_concat(files)
);

// Step 2: Compute BRICK_ID
let brick_id = sha3_256(
  format!("SKUNKSLAB-BRICK-v1||{}||{}||policy_v1", h_tree, "fed.example.com")
);

// Step 3: Derive AES key
let k_repo = hkdf_derive(master_secret, repo_id, "fed.example.com");

// Step 4: Encrypt manifest
let (ciphertext, tag) = aes_256_gcm_encrypt(
  k_repo,
  random_nonce_96bits(),
  manifest_json,
  aad = format!("{}||{}||fed.example.com", brick_id, repo_id)
);

// Step 5: Create BRICK receipt
let receipt = BrickReceipt {
  brick_id,
  repository_hash: h_tree,
  ciphertext_hash: sha3_256(&format!("{}{}", ciphertext, tag)),
  saml_issuer: "fed.example.com",
  saml_subject: "alice@fed.example.com",
  policy_id: "policy_v1",
  timestamp: now(),
  // ... other fields
};

// Return receipt (can be broadcast to federation)
receipt.to_json()
```

---

## References

- **NIST FIPS 202**: SHA-3 Standard
- **NIST SP 800-38D**: GCM and GMAC Mode
- **OASIS SAML 2.0 Standard**: Assertions and Protocols
- **RFC 5869**: HMAC-based Extract-and-Expand Key Derivation Function (HKDF)

---

## Status

✓ Specification complete  
✓ Cryptographic primitives defined  
✓ Verification algorithm specified  
✓ Security properties documented  
✓ Ready for implementation

**Next:** Implement BRICK verification in Rust/JS  
**Goal:** Federated repository integrity at scale
