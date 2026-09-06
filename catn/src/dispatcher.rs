use cubecl::prelude::*;
use cubecl::cuda::CudaRuntime;
use cubecl_runtime::client::ComputeClient;
use tenferro_tensor::Tensor;
use tenferro_gpu::cuda::CudaBackend;

use crate::state::CellularState;
use crate::kernels::erosion::{self, CHI_TARGET};
use crate::kernels::propagate;

/// Top-level dispatcher for one CATN execution cycle.
///
/// Step order per tick:
///   1. Erosion kernel    — SVD truncation (χ ≤ 64, ε = 0.001)
///   2. Recharge daemon   — host-side / light kernel bookkeeping
///   3. Propagation kernel — contractions + mirror-goto + ‖Ψ‖₂ = 1
pub struct CatnDispatcher {
    pub client:  ComputeClient<<CudaRuntime as Runtime>::Server,
                               <CudaRuntime as Runtime>::Channel>,
    pub backend: CudaBackend,
}

impl CatnDispatcher {
    pub fn new() -> Result<Self, Box<dyn std::error::Error>> {
        let device  = Default::default();
        let client  = CudaRuntime::client(&device);
        let backend = CudaBackend::new()?;
        Ok(Self { client, backend })
    }

    /// One full cellular step (erosion → recharge → propagate).
    pub fn step(
        &mut self,
        cell: &mut CellularState,
    ) -> Result<(), Box<dyn std::error::Error>> {
        // ── 1. Erosion ───────────────────────────────────────────────────
        // Obtain raw CubeCL array handles from tenferro tensors.
        // In production: use tenferro-gpu's ToCubeCL trait or explicit binding.
        let (input_h, mut u_h, mut s_h, mut v_h) =
            self.prepare_erosion_buffers(cell)?;

        let rows = cell.state.shape()[0] as u32;
        let cols = cell.state.shape()[1] as u32;

        erosion::launch_erosion::<CudaRuntime>(
            &self.client,
            &input_h,
            &mut u_h, &mut s_h, &mut v_h,
            rows, cols,
        );

        // ── 2. Recharge daemon ───────────────────────────────────────────
        self.recharge_daemon(cell)?;

        // ── 3. Propagation ───────────────────────────────────────────────
        let (mut state_h, neigh_h, axes_h, n_axes) =
            self.prepare_propagate_buffers(cell)?;
        let state_len = cell.state.size() as u32;

        propagate::launch_propagate::<CudaRuntime>(
            &self.client,
            &mut state_h, &neigh_h, &axes_h,
            n_axes, state_len,
        );

        self.client.sync();
        Ok(())
    }

    fn recharge_daemon(
        &mut self,
        _cell: &mut CellularState,
    ) -> Result<(), Box<dyn std::error::Error>> {
        // Host-side: update auxiliary charges, Lagrange multipliers,
        // or local learning rates after truncation.
        // May delegate to a tiny CubeCL kernel; left as a stub here.
        Ok(())
    }

    fn prepare_erosion_buffers(
        &self,
        _cell: &CellularState,
    ) -> Result<
        (ArrayHandle<CudaRuntime, f32>,
         ArrayHandle<CudaRuntime, f32>,
         ArrayHandle<CudaRuntime, f32>,
         ArrayHandle<CudaRuntime, f32>),
        Box<dyn std::error::Error>,
    > {
        // Bridge tenferro Tensor → CubeCL ArrayHandle.
        // Concrete implementation depends on tenferro-gpu handle API version.
        todo!("tenferro Tensor → CubeCL ArrayHandle binding for erosion buffers")
    }

    fn prepare_propagate_buffers(
        &self,
        _cell: &CellularState,
    ) -> Result<
        (ArrayHandle<CudaRuntime, f32>,
         ArrayHandle<CudaRuntime, f32>,
         ArrayHandle<CudaRuntime, u32>,
         u32),
        Box<dyn std::error::Error>,
    > {
        todo!("tenferro Tensor → CubeCL ArrayHandle binding for propagation buffers")
    }

    /// Serialize final tenferro tensors into the output struct.
    /// Tensor remains on device; caller may download via .to_host().
    pub fn export(&self, cell: &CellularState) -> CatnOutput {
        CatnOutput {
            state: cell.state.clone(),
            chi:   cell.chi.clone(),
        }
    }
}

/// Final serialized CATN result.
#[derive(Debug)]
pub struct CatnOutput {
    /// State tensor (on CUDA device unless explicitly downloaded).
    pub state: Tensor,
    /// Active bond dimensions after last erosion step.
    pub chi: Vec<usize>,
}
