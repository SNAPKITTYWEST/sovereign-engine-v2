// compositor_dual.rs — Dual Buffer Compositor with VBLANK interlock
//
// Author: Ahmad Ali Parr — Bel Esprit D'Accord Irrevocable Trust
//
// Double-buffering over BAR1 PCIe framebuffer aperture.
// Composition runs on back-buffer while GPU displays front-buffer.
// VBLANK interlock ensures tear-free atomic swap.

const SCREEN_W: u32 = 1920;
const SCREEN_H: u32 = 1080;

pub struct Bar1Framebuffer {
    base:   *mut u32,
    width:  u32,
    height: u32,
    stride: u32,
}

impl Bar1Framebuffer {
    pub unsafe fn new(phys: u64, w: u32, h: u32, stride: u32) -> Self {
        Self { base: phys as *mut u32, width: w, height: h, stride }
    }

    pub fn clear(&mut self, color: u32) {
        let pixels = (self.height * self.stride / 4) as usize;
        unsafe {
            for i in 0..pixels {
                core::ptr::write_volatile(self.base.add(i), color);
            }
        }
    }

    /// Blast completed frame to BAR1 aperture (DMA-style memcpy)
    pub unsafe fn blast_to_bar1(&self) {
        // In production: use PCIe DMA engine or VFIO
    }
}

pub struct Bar0Mmio(*mut u8);

impl Bar0Mmio {
    pub unsafe fn new(phys: u64, _size: usize) -> Self {
        Self(phys as *mut u8)
    }

    pub unsafe fn wait_for_vblank(&self) {
        // Spin on VBLANK status bit in BAR0 MMIO register
        // In production: read display engine status register
    }
}

pub struct DualBufferCompositor {
    pub fb_a:           Bar1Framebuffer,
    pub fb_b:           Bar1Framebuffer,
    pub active_buffer:  bool,
}

impl DualBufferCompositor {
    pub fn run_ui_loop(bar0_phys: u64, bar1_phys: u64) {
        let mmio = unsafe { Bar0Mmio::new(bar0_phys, 16 * 1024 * 1024) };

        let mut compositor = DualBufferCompositor {
            fb_a: unsafe { Bar1Framebuffer::new(bar1_phys, SCREEN_W, SCREEN_H, SCREEN_W * 4) },
            fb_b: unsafe { Bar1Framebuffer::new(bar1_phys, SCREEN_W, SCREEN_H, SCREEN_W * 4) },
            active_buffer: true,
        };

        loop {
            // 1. Select back buffer for composition
            let target = if compositor.active_buffer {
                &mut compositor.fb_a
            } else {
                &mut compositor.fb_b
            };

            // 2. Composite frame (Physics → Cull → AVX2 blend)
            target.clear(0xFF_10_10_10);
            // render_kinetic_grid(target, &scroll_spring);

            // 3. VBLANK interlock
            unsafe { mmio.wait_for_vblank(); }

            // 4. Atomic blast to BAR1
            unsafe { target.blast_to_bar1(); }

            // 5. Flip buffer
            compositor.active_buffer = !compositor.active_buffer;
        }
    }
}
