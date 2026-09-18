/// propagate_mirror — combined propagate + mirror-goto kernel.
///
/// Performs:
///   1. Multi-axis tensor contractions over active neighbourhood graph.
///   2. Mirror-goto operator (local topology rewiring / index permutation).
///   3. Unitary projection: ‖Ψ‖₂ = 1.
///
/// The norm projection requires a global reduction; the kernel handles the
/// per-element scaling step after the reduction is written to device memory.

use cubecl::prelude::*;
use cubecl::cuda::CudaRuntime;

#[cube(launch_unchecked)]
pub fn propagate_mirror<F: Float>(
    state:      &mut Array<F>,  // Ψ — updated in place
    neigh:      &Array<F>,      // packed neighbourhood bond tensors
    axis_pairs: &Array<u32>,    // contraction axis metadata
    n_axes:     u32,
    state_len:  u32,
    norm_inv:   F,              // 1 / ‖Ψ‖₂ (pre-computed by host or reduction kernel)
) {
    let tid = ABSOLUTE_POS;
    if tid >= state_len {
        return;
    }

    // ── Multi-axis tensor contractions ───────────────────────────────────
    // Production implementation: einsum-style gather-scatter or batched GEMM
    // over the active neighbourhood edges defined by axis_pairs[0..n_axes].
    // Mirror-goto operator rewires the local index map before / after contracting.
    //
    // Architectural sketch (axes are compile-time constants when possible):
    //   let mut acc = F::new(0.0);
    //   for edge in 0..n_axes {
    //       let a_idx  = axis_pairs[edge * 2];
    //       let b_idx  = axis_pairs[edge * 2 + 1];
    //       acc += state[a_idx] * neigh[b_idx];
    //   }
    //   state[tid] = acc;
    let _ = (neigh, axis_pairs, n_axes); // suppress unused warnings in scaffold

    // ── Unitary projection ───────────────────────────────────────────────
    // Apply pre-computed scale factor (1/‖Ψ‖₂) so that ‖Ψ‖₂ = 1 after update.
    if norm_inv > F::new(0.0) {
        state[tid] = state[tid] * norm_inv;
    }
}

/// Host-side: compute ‖Ψ‖₂, then launch propagate kernel.
pub fn launch_propagate<R: Runtime>(
    client:    &ComputeClient<R::Server, R::Channel>,
    state:     &mut ArrayHandle<R, f32>,
    neigh:     &ArrayHandle<R, f32>,
    axes:      &ArrayHandle<R, u32>,
    n_axes:    u32,
    state_len: u32,
) {
    // Step 1: reduce ‖Ψ‖₂ on the device (two-pass or warp-shuffle approach)
    // For now: placeholder norm = 1.0 (no-op projection)
    let norm_inv: f32 = 1.0;

    let cube  = CubeDim::new_1d(256);
    let count = CubeCount::Static(
        ((state_len as usize + 255) / 256) as u32, 1, 1
    );
    let neigh_len = neigh.size();
    let axes_len  = axes.size();

    unsafe {
        propagate_mirror::launch_unchecked::<f32, R>(
            client,
            count,
            cube,
            ArrayArg::from_raw_parts(state, state_len as usize, 1),
            ArrayArg::from_raw_parts(neigh, neigh_len,           1),
            ArrayArg::from_raw_parts(axes,  axes_len,            1),
            n_axes,
            state_len,
            ScalarArg::new(norm_inv),
        );
    }
}
