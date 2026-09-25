# resolution_tensored (C053)

## What it does
Represents `P_* ⊗_R N` (a projective resolution tensored with a module `N`) — but only at the level of **ranks**, not actual elements or differentials. `TensoredComplex` stores `p_ranks`, `n_rank`, and a separately-set `differential_ranks` vector; nothing here actually computes `d_i ⊗ id_N` from real differential data.

## Public API
- Re-exports `TensorProductModule`, `TensorElement`, `TensorGenerator` from C052.
- `TensoredComplex { p_ranks, n_rank, differential_ranks }` — `new(p_ranks, n_rank)` (initializes `differential_ranks` to all zeros), `tensored_rank(degree)` (= `p_rank * n_rank`), `set_differential_rank()`/`get_differential_rank()` (manual, external population), `verify_complex()` (checks `differential_ranks[i] <= tensored_rank(i)` — a necessary but very weak sanity bound, not an actual `d²=0` check despite the doc comment claiming to "verify that d² = 0"), `num_degrees()`, `total_rank()`.
- `TensoredComplexProperties { exact_at, kernel_ranks, image_ranks }` — `analyze(&TensoredComplex)` initializes all three vectors to zeros/false and **never computes anything** (see gap), `is_exact()`.

## Pipeline position
Depends on `differential_operator` (C043, unused — dead dependency), `differential_squared_zero` (C044, unused — dead dependency), `tensor_product_module` (C052). Feeds `derived_homology` (C054), which is where actual homology/Tor values are meant to come from — but C054 takes homology groups as an external `&[Option<HomologyGroup>]` parameter rather than deriving them from a `TensoredComplex`, so the connection between this crate's rank bookkeeping and real Tor computation is currently by convention/caller discipline, not enforced by the type system.

## Notes / gaps
- **Major gap — `verify_complex()` doesn't verify d²=0:** despite its doc comment ("Verify that d^2 = 0 in the tensored complex"), the implementation only checks that each stored `differential_ranks[i]` doesn't exceed the corresponding `tensored_rank(i)` — a dimension sanity bound satisfied by nearly any plausible rank assignment, including ones where `d²≠0`. There is no matrix, so no actual composition is or could be checked here; this crate operates purely on rank integers.
- **Major gap — `TensoredComplexProperties::analyze()` computes nothing:** it allocates correctly-sized `exact_at`/`kernel_ranks`/`image_ranks` vectors but fills them with `false`/`0` unconditionally — it does not inspect the `TensoredComplex` passed in at all beyond reading `num_degrees()` for sizing. `is_exact()` on a freshly-analyzed complex will therefore **always return `false`** (since `exact_at` is all `false`) regardless of the actual complex — this looks like a stub that was never wired up to real kernel/image computation (which would need actual matrices, not just ranks, so this crate's rank-only design may be an intentional architectural limitation rather than an oversight — worth confirming with whoever owns this layer).
- `differential_operator`/`differential_squared_zero` are unused dependencies — likely intended to back real `d²=0` checking that was never implemented.
- 4 unit tests, all only exercising rank arithmetic (`tensored_rank`, `total_rank`, vector sizing) — none exercise `verify_complex()` or `is_exact()` at all, so both gaps above are untested.
