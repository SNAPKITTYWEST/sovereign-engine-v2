# Security interfaces and limits

This guide describes checks in the source and where callers must apply them. It is not a security certification.

## Path boundaries

[PathJail.resolve](../src/core/path_jail.py) resolves a path and checks membership under configured roots, rejects control characters, and checks selected Windows device names. Use the returned path for the operation.

### Local example

```python
from pathlib import Path
from tempfile import TemporaryDirectory
from src.core.path_jail import PathJail, PathJailError

with TemporaryDirectory() as directory:
    root = Path(directory).resolve()
    jail = PathJail([root])
    assert jail.resolve(root / "example.txt") == root / "example.txt"
    try:
        jail.resolve(root.parent / "outside.txt")
    except PathJailError:
        print("outside path rejected")
    else:
        raise AssertionError("expected rejection")
```

This check is not an OS sandbox and does not make a later file open atomic with validation. Handlers in [loader.py](../src/tools/loader.py) must be inspected individually; constructing a jail in the engine does not route all filesystem calls through it.

## Network boundaries

`SSRFGuard.check_url` checks URL scheme and hostname text against blocked hosts/prefixes. It does not resolve DNS and revalidate the actual destination or follow-up redirects. It is not a complete DNS-rebinding defense.

The HTTP bridge installs wildcard CORS and has no authentication middleware in its current route setup. `/tool/execute` invokes handlers directly. Keep it on loopback for development; deployment requires authentication, authorization, request validation, and network-level restrictions.

## Evidence ledger

[WORMLedger](../src/core/evidence.py) wraps the binary [WORMFile](../src/core/storage.py). `append(event_type, data, metadata)` is synchronous and accepts bytes, strings, dictionaries, or None. `scan()` yields records. `verify_chain()` reports chain validity.

Binary encoding does not eliminate malicious content or filesystem modification. Hash-chain verification is not interchangeable with verification of every signature against a trusted identity. Preserve signing-key provenance separately; the engine currently generates a new key during construction.

## Tool approval

Risk classes and approval policies are metadata until the execution path enforces them. See [Tools](TOOLS.md). Review direct handler calls, native fallback, shell/code execution, and external service credentials as distinct boundaries.

## Node capabilities and formal claims

[node_key.py](../sovereign/node_key.py) checks a nonempty capability file and active status if an authorization file exists. It does not verify expiry or signatures. The separate execution-gate script is incomplete at the documented baseline. The direct runner does not call it.

A theorem about a model does not certify the running application. The [formal sources](../research/formal/) include axioms, postulates, and admitted proofs; report specific checker results rather than a repository-wide proof claim.
