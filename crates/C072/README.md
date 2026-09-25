# obligation_management

Generic proof-obligation tracking: create obligations, mark them proven,
track dependencies, and topologically order them.

## What it does

`Obligation { id, proposition: LeanType, status: ObligationStatus, proof:
Option<ProofTerm>, dependencies: BTreeSet<String> }`.
`ObligationStatus` is `Open | InProgress | Closed | Failed` (note:
`InProgress` and `Failed` are never actually set anywhere in this crate —
`prove()` only ever transitions `Open -> Closed`, nothing sets `InProgress`
or `Failed`). `dependencies_satisfied` checks all named dependencies are
`Closed` in a given obligation list (linear scan per dependency).
`ObligationManager` holds a `BTreeMap<String, Obligation>` plus a shared
`TypeContext`, with counts and a `topological_order()` (recursive DFS,
dependencies emitted before dependents; silently ignores dependencies that
don't exist in the map, and does not detect cycles — a cyclic dependency
graph would still terminate because of the `visited` set, but would produce
a silently incomplete/incorrect order rather than an error).

## Public API

- `ObligationStatus`, `Obligation` (+ `new`, `add_dependency`,
  `dependencies_satisfied`, `prove`)
- `ObligationManager::new`, `add_obligation`, `get_obligation[_mut]`,
  `count_open`, `count_closed`, `topological_order`

## Pipeline role

Depends on `gap_tensor_trace` (C010, unused in this file) and
`type_checking_interface` (C071). This is the generic obligation-tracking
engine that `lean_obligation_aggregator` (C080) wraps with tier-grouping and
reporting; the seven domain-specific lemma libraries (C073-C079) each define
their own parallel lemma/status types rather than reusing `Obligation`
directly.

## Gaps / weak spots

- `topological_order` doesn't detect or report cycles — a self-referential
  or mutually-dependent obligation set would silently produce an order that
  is not actually a valid topological sort of the intended DAG (each id is
  visited once via the `visited` guard, so it terminates, but the emitted
  order can violate a dependency edge inside a cycle).
- `ObligationStatus::InProgress` and `::Failed` are declared but unreachable
  through the public API in this crate — no method ever sets them.
