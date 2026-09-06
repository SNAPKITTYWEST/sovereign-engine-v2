// ada_ffi.rs — Rust FFI bindings to magma_666.adb (GNAT-compiled C ABI)
//
// The Ada SPARK package M in magma_666.adb exports its operations via
// a C-compatible interface (pragma Export / Convention => C).
// This module wraps those C symbols with safe Rust types.
//
// Ada Core_State → Rust CoreState
//   Cells      : Matrix (4096 bits) → [u8; 512]
//   State      : Pulse_State        → PulseState enum
//   Polarity   : Polarity           → Polarity enum
//   Sequence   : Word16             → u16
//   Valid      : Boolean            → bool
//
// Ada MagmaI operations:
//   I(X)        = NOT X             (16-bit bitwise complement)
//   Fold_I(X,Y) = I(X) XOR I(Y)    (fold under imaginary)
//   Ectot(X)    = Fold_I(X, I(X))  = NOT(X XOR NOT(X XOR NOT X)) = invariant
//
// Connection to MAGMA protocol:
//   M.Persist(Core) → §ANCHOR:MNEMEX:WORM{ core_seq, core_hash }
//   M.Verify(Core)  → §SEAL:CIPHER:SIGN{ ok: true|false }
//   MagmaI.Ectot(X) → entropy contribution to sovereign entropy pool

use std::os::raw::{c_int, c_uchar, c_ushort};

// ---------------------------------------------------------------------------
// Raw C layout (must match magma_666.adb M package exactly)
// ---------------------------------------------------------------------------

const MATRIX_BYTES: usize = 512;   // 4096 bits / 8

#[repr(C)]
#[derive(Clone, Debug)]
pub struct CCoreState {
    pub cells:    [c_uchar; MATRIX_BYTES],
    pub state:    c_int,    // 0=Idle 1=Flowing 2=Latched 3=Persisted 4=Fault
    pub polarity: c_int,    // 0=Polar_NS 1=Polar_SN
    pub sequence: c_ushort,
    pub valid:    bool,
}

extern "C" {
    fn amd_magma_clear   (core: *mut CCoreState);
    fn amd_magma_pulse   (core: *mut CCoreState, input: *const c_uchar, len: usize) -> c_int;
    fn amd_magma_latch   (core: *mut CCoreState, polarity: c_int) -> c_int;
    fn amd_magma_persist (core: *mut CCoreState) -> c_int;
    fn amd_magma_resume  (core: *mut CCoreState) -> c_int;
    fn amd_magma_verify  (core: *const CCoreState) -> bool;
    fn amd_magma_imaginary(x: c_ushort) -> c_ushort;
    fn amd_magma_fold    (a: c_ushort, b: c_ushort) -> c_ushort;
    fn amd_magma_probe   () -> c_int;
}

// ---------------------------------------------------------------------------
// Safe Rust types
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, PartialEq)]
pub enum PulseState {
    Idle, Flowing, Latched, Persisted, Fault,
}

impl From<c_int> for PulseState {
    fn from(v: c_int) -> Self {
        match v { 1 => Self::Flowing, 2 => Self::Latched, 3 => Self::Persisted, _ => Self::Idle }
    }
}

#[derive(Debug, Clone, PartialEq)]
pub enum Polarity { NS, SN }

#[derive(Debug, Clone)]
pub struct CoreState {
    pub cells:    [u8; MATRIX_BYTES],
    pub state:    PulseState,
    pub polarity: Polarity,
    pub sequence: u16,
    pub valid:    bool,
}

impl CoreState {
    pub fn new() -> Self {
        Self {
            cells:    [0u8; MATRIX_BYTES],
            state:    PulseState::Idle,
            polarity: Polarity::NS,
            sequence: 0,
            valid:    true,
        }
    }

    fn to_c(&self) -> CCoreState {
        CCoreState {
            cells:    self.cells,
            state:    match self.state { PulseState::Flowing => 1, PulseState::Latched => 2, PulseState::Persisted => 3, PulseState::Fault => 4, _ => 0 },
            polarity: if self.polarity == Polarity::NS { 0 } else { 1 },
            sequence: self.sequence,
            valid:    self.valid,
        }
    }

    fn from_c(c: &CCoreState) -> Self {
        Self {
            cells:    c.cells,
            state:    PulseState::from(c.state),
            polarity: if c.polarity == 0 { Polarity::NS } else { Polarity::SN },
            sequence: c.sequence,
            valid:    c.valid,
        }
    }
}

// ---------------------------------------------------------------------------
// Safe wrappers
// ---------------------------------------------------------------------------

/// Probe hardware — returns true if amd_magma driver is available
pub fn probe() -> bool {
    unsafe { amd_magma_probe() == 0 }
}

/// M.Clear(Core) — reset to Idle state
pub fn clear(core: &mut CoreState) {
    let mut c = core.to_c();
    unsafe { amd_magma_clear(&mut c); }
    *core = CoreState::from_c(&c);
}

/// M.Pulse(Core, Input) — load matrix, transition Idle→Flowing
pub fn pulse(core: &mut CoreState, input: &[u8; MATRIX_BYTES]) -> bool {
    let mut c = core.to_c();
    let ok = unsafe { amd_magma_pulse(&mut c, input.as_ptr(), MATRIX_BYTES) == 0 };
    *core = CoreState::from_c(&c);
    ok
}

/// M.Latch(Core, Polarity) — Flowing→Latched
pub fn latch(core: &mut CoreState, pol: Polarity) -> bool {
    let mut c = core.to_c();
    let p = if pol == Polarity::NS { 0 } else { 1 };
    let ok = unsafe { amd_magma_latch(&mut c, p) == 0 };
    *core = CoreState::from_c(&c);
    ok
}

/// M.Persist(Core) — Latched→Persisted
pub fn persist(core: &mut CoreState) -> bool {
    let mut c = core.to_c();
    let ok = unsafe { amd_magma_persist(&mut c) == 0 };
    *core = CoreState::from_c(&c);
    ok
}

/// M.Resume(Core) — Persisted→Idle (if Verify passes)
pub fn resume(core: &mut CoreState) -> bool {
    let mut c = core.to_c();
    let ok = unsafe { amd_magma_resume(&mut c) == 0 };
    *core = CoreState::from_c(&c);
    ok
}

/// M.Verify(Core) — structural integrity check
pub fn verify(core: &CoreState) -> bool {
    let c = core.to_c();
    unsafe { amd_magma_verify(&c) }
}

// ---------------------------------------------------------------------------
// MagmaI operations — imaginary algebra
// ---------------------------------------------------------------------------

/// MagmaI.I(X) = NOT X  (maps to 0J¯1 in APL Wick rotation)
pub fn imaginary(x: u16) -> u16 {
    unsafe { amd_magma_imaginary(x) }
}

/// MagmaI.Fold_I(X,Y) = I(X) XOR I(Y)
pub fn fold_i(x: u16, y: u16) -> u16 {
    unsafe { amd_magma_fold(amd_magma_imaginary(x), amd_magma_imaginary(y)) }
}

/// MagmaI.Ectot(X) = Fold_I(X, I(X)) = I(X) XOR I(I(X)) = I(X) XOR X = NOT(X) XOR X
/// This is always 0xFFFF for any X — the "total complement" / identity under imaginary fold
pub fn ectot(x: u16) -> u16 {
    fold_i(x, imaginary(x))
}

/// Pure Rust fallback (no FFI) — used when Ada library not linked
pub mod pure {
    pub fn imaginary(x: u16) -> u16 { !x }
    pub fn fold(a: u16, b: u16) -> u16 { a ^ b }
    pub fn fold_i(x: u16, y: u16) -> u16 { fold(imaginary(x), imaginary(y)) }
    pub fn ectot(x: u16) -> u16 { fold_i(x, imaginary(x)) }

    #[cfg(test)]
    mod tests {
        use super::*;
        #[test] fn ectot_is_always_ffff() { assert_eq!(ectot(0x0000), 0xFFFF); assert_eq!(ectot(0xABCD), 0xFFFF); }
        #[test] fn imaginary_is_not()     { assert_eq!(imaginary(0x0F0F), 0xF0F0); }
    }
}
