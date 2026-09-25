# type_checking_interface

Minimal Lean 4-flavored type system used as a common vocabulary for every
"lemma library" crate in Tier 7 (C071-C080) to describe formal statements.

## What it does

`LeanType`: `Prop`, `Type(usize)` (universe-indexed), `Arrow(Box<LeanType>,
Box<LeanType>)`, `Custom(String)` — enough structure to write down a
proposition's shape and pretty-print it (`to_string`, e.g.
`"Prop → Prop"`). `ProofTerm`: `Axiom(String)`, `Trivial`, `Reference(String)`,
`App(Box<ProofTerm>, Box<ProofTerm>)` — `is_complete()` returns true for
`Trivial`/`Axiom`/`Reference` but **false for `App`**, i.e. an explicit
function-application proof term is never considered complete by this logic.
`TypeContext` is a pair of `BTreeMap<String, LeanType>` for variables and
theorems, with lookup/insert.

## Public API

- `LeanType` (+ `prop()`, `type_u(u)`, `arrow(from, to)`, `to_string()`)
- `ProofTerm` (+ `axiom(name)`, `is_complete()`)
- `TypeContext` (+ `add_variable`, `add_theorem`, `lookup_variable`,
  `lookup_theorem`)

## Pipeline role

Depends on `gap_tensor_core` (C001) and `gap_tensor_spectral` (C003) for
workspace wiring only — neither is used in this file. This is the shared
vocabulary crate: every lemma library in C072-C080 imports `LeanType` and
`ProofTerm` from here, and it's the closest thing this workspace has to an
actual Lean AST — but it does not talk to a real Lean 4 process; there is no
FFI, subprocess call, or `.lean` file parsing anywhere in this crate.

## Non-obvious design decisions / gaps

- This is **not** a real interface to the Lean 4 type checker despite the
  crate name — it's a Rust-side mirror/stub of Lean's syntax used to track
  bookkeeping (which obligations exist, whether they're "proven") without
  ever invoking Lean. Anyone expecting FFI or subprocess integration here
  will be surprised; the actual correspondence to Lean proofs would need to
  happen in the runtime-binding layer (C091-C100), which is currently
  unimplemented.
- `ProofTerm::App(_)` always reporting `is_complete() == false` means a
  "real" composed proof term built via function application can never be
  marked closed through this API — only trivial/axiom/reference proofs can.
  If `App` is meant to represent legitimate proof composition, this is a
  functional gap, not just a placeholder.
