// gdr_sovereign_p3_lowering.mlir
// Target:        TensorIR Level 3 (P3) Intermediate Representation
// Cryptographic: 4b565498-9afc-4782-af4a-c6b11a5d0058
// State hash:    0x2A1C_B4D0_F9E2_11C8

module @gdr_sovereign_p3_lowering {
  tensorir.spatial_block @block_fused_gdr_fwd {
    %batch_size  = t.dynamic_param "batch_size"
    %num_tokens  = t.dynamic_param "num_tokens"
    %num_chunks  = t.dynamic_param "num_chunks"

    // Shared memory staging buffers (double-buffered, stage 0 / stage 1)
    %q_shared = memref.alloc() {alignment = 64 : i64} : memref<2x64x128xf16, 3>
    %k_shared = memref.alloc() {alignment = 64 : i64} : memref<2x64x128xf16, 3>
    %v_shared = memref.alloc() {alignment = 64 : i64} : memref<2x64x128xf16, 3>
    %a_shared = memref.alloc() {alignment = 64 : i64} : memref<2x64x64xf16, 3>
    %g_shared = memref.alloc() {alignment = 64 : i64} : memref<2x64xf32, 3>
    %b_shared = memref.alloc() {alignment = 64 : i64} : memref<2x64xf32, 3>

    // MMA accumulator fragments (warp registers)
    %h_fragment = tensorir.alloc_fragment() : tensor<128x128xf32>
    %o_fragment = tensorir.alloc_fragment() : tensor<64x128xf32>
    %p_fragment = tensorir.alloc_fragment() : tensor<64x64xf32>

    // Loop unrolling with pipeline barriers
    scf.for %i_s = %c0 to %num_iters step %c1 {
      tensorir.barrier_wait {barrier_id = 0, phase = 0}

      // Tensor Core MMA: Q @ K^T → p_fragment  (16×8×16 tile)
      tensorir.gemm {
        transpose_A  = false,
        transpose_B  = true,
        compute_type = "f32"
      } %q_shared, %k_shared, %p_fragment
        : memref<2x64x128xf16, 3>, memref<2x64x128xf16, 3> -> tensor<64x64xf32>

      // Exponential decay for gated recurrent state update
      tensorir.elementwise_apply {op = "exp2_scale"}
        %g_shared, %h_fragment
        : memref<2x64xf32, 3>, tensor<128x128xf32>

      tensorir.barrier_arrive {barrier_id = 1}
    }
  }
}
