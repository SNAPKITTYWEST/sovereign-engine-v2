# prime_state_binding — UNIMPLEMENTED SCAFFOLD

`src/lib.rs` is a 7-line stub with no types, functions, or tests.

## Intended purpose (inferred from name + dependencies)

Depends on `prime_predicate` (C021), `gap_candidate_set` (C023),
`gap_ordering` (C024), and `runtime_state_snapshot` (C081, itself
unimplemented). Presumably meant to bind the prime-gap search state (which
candidates are live, current ordering) into the runtime snapshot, so a gap
search's runtime execution can be certified against
`gap_lemmas_library` (C073) and eventually `prime_gap_correspondence`
(C094).

## Status

Empty. Blocked on `runtime_state_snapshot` (C081).
