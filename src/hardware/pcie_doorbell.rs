// pcie_doorbell.rs — PCIe Doorbell Driver (Rust)
//
// Author: Ahmad Ali Parr — Bel Esprit D'Accord Irrevocable Trust
//
// Performs the "Doorbell Kick" — writes a unique sequence to MMIO to
// trigger the pcie_doorbell_latch.v hardware module, which pulses
// trigger_event to the Kalman Filter / QNN update pipeline.

use core::ptr::{read_volatile, write_volatile};
use core::sync::atomic::{fence, Ordering};

#[repr(C)]
pub struct PcieDoorbellRegs {
    pub doorbell: u32,
    pub latch_st: u32,
    pub control:  u32,
}

pub struct DoorbellDriver {
    base_addr: *mut PcieDoorbellRegs,
}

impl DoorbellDriver {
    pub unsafe fn new(addr: usize) -> Self {
        Self { base_addr: addr as *mut PcieDoorbellRegs }
    }

    /// Kick — writes sequence to MMIO; triggers latch on value change.
    pub fn kick(&self, sequence: u32) {
        unsafe {
            // Wait for previous latch to clear
            while read_volatile(&(*self.base_addr).latch_st) != 0 {
                core::hint::spin_loop();
            }
            // Write kick sequence
            write_volatile(&mut (*self.base_addr).doorbell, sequence);
            // Full memory fence — ensures write visible to PCIe
            fence(Ordering::SeqCst);
        }
    }

    /// Poll — check if hardware acknowledged the kick.
    pub fn poll_latch(&self) -> bool {
        unsafe { read_volatile(&(*self.base_addr).latch_st) != 0 }
    }
}
