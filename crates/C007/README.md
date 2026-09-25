# `gap_tensor_invariants` (C007)

Tier 0 — gap tensor primitives. *Generated from the crate source; regenerate after API changes.*

Well-formedness invariants for gap tensor nodes and tensors:

* a non-nil node carries a candidate prime;
* a Nil node is clean (zero multiplicity and zero weight);
* spectral weights are finite and non-negative;
* consecutive non-nil nodes (in row-major order) differ in prime by at most
  `SIGMA_GAP_MAX` — a larger jump is dissonance.

## Dependencies

- [C001 `gap_tensor_core`](../C001/README.md)
- [C002 `gap_tensor_primes`](../C002/README.md)
- [C004 `gap_tensor_shape`](../C004/README.md)

## Public API

| Item | Description |
|---|---|
| `enum Violation` | A single invariant violation, located by flat node index. |
| `struct InvariantReport` | Result of checking a node sequence. |
| `fn InvariantReport::is_valid(&self) -> bool` | True iff no violations were found. |
| `fn check_node(index: usize, node: &GapTensorNode) -> Vec<Violation>` | Node-local invariants for the node at `index`. |
| `fn check_nodes(nodes: &[GapTensorNode]) -> InvariantReport` | Check every node-local invariant plus dissonance between consecutive non-nil nodes. |
| `fn check_tensor(tensor: &GapTensor) -> InvariantReport` | Check a tensor's nodes in row-major order. |

## Tests

`cargo test -p gap_tensor_invariants` runs 3 unit tests.
