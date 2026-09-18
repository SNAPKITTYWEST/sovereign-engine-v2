/// tensor_erosion — local SVD truncation kernel.
///
/// Accepts a local tensor block, performs truncated SVD with:
///   ε = 0.001  (relative singular-value threshold)
///   χ_target ≤ 64  (max retained rank)
///
/// The insertion point for a device SVD routine (tiled Jacobi / iterative QR)
/// is marked below. CubeCL does not ship a full SVD; this kernel provides the
/// control flow and truncation logic around the SVD insertion point.

use cubecl::prelude::*;
use cubecl::cuda::CudaRuntime;

pub const EPSILON:     f32 = 0.001;
pub const CHI_TARGET:  u32 = 64;

#[cube(launch_unchecked)]
pub fn tensor_erosion<F: Float>(
    input:      &Array<F>,
    u_out:      &mut Array<F>,
    s_out:      &mut Array<F>,
    v_out:      &mut Array<F>,
    rows:       u32,
    cols:       u32,
    #[comptime] chi_max: u32,
) {
    let tid = ABSOLUTE_POS;
    if tid >= rows * cols {
        return;
    }

    // ── SVD insertion point ──────────────────────────────────────────────
    // Real implementation:
    //   1. Load block into shared memory / registers.
    //   2. Compute SVD (U, S, V) via tiled Jacobi or external device library.
    //   3. s_out[0..min(rows,cols)] = singular values (descending).
    //   4. u_out, v_out = factor columns/rows.
    // The comptime chi_max ensures the rank budget is a compile-time constant.
    // ────────────────────────────────────────────────────────────────────

    // Truncation logic (executed by unit 0 after SVD synchronisation)
    if UNIT_POS == 0 {
        let rank = u32::min(rows, cols);
        let mut total_energy = F::new(0.0);
        for i in 0..rank {
            let s = s_out[i];
            total_energy += s * s;
        }

        let mut kept_energy = F::new(0.0);
        let mut kept        = 0u32;
        for i in 0..rank {
            let s = s_out[i];
            kept_energy += s * s;
            kept += 1;
            // Stop when relative discarded energy < ε, or rank budget exhausted
            let discarded = (total_energy - kept_energy) / total_energy;
            if discarded < F::new(EPSILON) || kept >= chi_max {
                break;
            }
        }

        // Zero out discarded singular values and corresponding factor columns
        for i in kept..rank {
            s_out[i] = F::new(0.0);
        }
    }

    // Element-wise stub: pass-through above threshold, zero below
    // (replace with the reconstructed U S V^T product after SVD)
    let val = input[ABSOLUTE_POS];
    u_out[ABSOLUTE_POS] = if F::abs(val) > F::new(EPSILON) { val } else { F::new(0.0) };
}

/// Host-side launch helper.
pub fn launch_erosion<R: Runtime>(
    client:     &ComputeClient<R::Server, R::Channel>,
    input:      &ArrayHandle<R, f32>,
    u_out:      &mut ArrayHandle<R, f32>,
    s_out:      &mut ArrayHandle<R, f32>,
    v_out:      &mut ArrayHandle<R, f32>,
    rows:       u32,
    cols:       u32,
) {
    let n     = (rows * cols) as usize;
    let cube  = CubeDim::new_1d(256);
    let count = CubeCount::Static(((n + 255) / 256) as u32, 1, 1);

    unsafe {
        tensor_erosion::launch_unchecked::<f32, R>(
            client,
            count,
            cube,
            ArrayArg::from_raw_parts(input,  n, 1),
            ArrayArg::from_raw_parts(u_out,  n, 1),
            ArrayArg::from_raw_parts(s_out,  rows.min(cols) as usize, 1),
            ArrayArg::from_raw_parts(v_out,  n, 1),
            rows,
            cols,
            CHI_TARGET,
        );
    }
}
