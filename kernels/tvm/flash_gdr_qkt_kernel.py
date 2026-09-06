# flash_gdr_qkt_kernel.py
# Full TileLang Flash-GDR QK^T kernel.
# Computes S[B, N, H, N] = scale * Q[B, N, H, D] @ K[B, N, H, D]^T
# using double-buffered TMA async loads and pipelined MMA tiles.
#
# Constants match GDR config: BLOCK_S=64, BLOCK_D=128, BLOCK_H=8, MMA=16x8x16

import tilelang
import tilelang.language as T
from tilelang import Profiler

BLOCK_S = 64
BLOCK_D = 128
BLOCK_H = 8
NUM_WARPS = 8
THREADS   = NUM_WARPS * 32
MMA_M, MMA_N, MMA_K = 16, 8, 16


@tilelang.jit(
    pass_configs={
        tilelang.PassConfigKey.TL_ENABLE_FAST_MATH: True,
    }
)
def flash_gdr_qkt_kernel(
    batch_size: int,
    seq_len:    int,
    num_kv_heads: int,
    head_dim:   int,
    scale:      float,
) -> tilelang.Kernel:

    @T.prim_func
    def kernel(
        Q: T.Tensor([batch_size, seq_len, num_kv_heads, head_dim], "float16"),
        K: T.Tensor([batch_size, seq_len, num_kv_heads, head_dim], "float16"),
        S: T.Tensor([batch_size, seq_len, num_kv_heads, seq_len], "float32"),
    ):
        bx = T.get_block_idx(0)
        by = T.get_block_idx(1)

        tiles_per_seq  = T.ceildiv(seq_len, BLOCK_S)
        head_batch_idx = bx // tiles_per_seq
        tile_row       = bx % tiles_per_seq
        tile_col       = by

        batch = head_batch_idx // num_kv_heads
        head  = head_batch_idx % num_kv_heads

        row_start = tile_row * BLOCK_S
        col_start = tile_col * BLOCK_S

        if row_start >= seq_len or col_start >= seq_len:
            return

        # Double-buffered shared memory (dynamic SRAM)
        Q_shared = T.alloc_shared((2, BLOCK_S, head_dim), "float16",
                                  scope="shared.dyn")
        K_shared = T.alloc_shared((2, BLOCK_S, head_dim), "float16",
                                  scope="shared.dyn")

        # FP32 accumulator fragment distributed across warps
        S_frag = T.alloc_fragment((BLOCK_S, BLOCK_S), "float32")
        T.clear(S_frag)

        # Stage 0: prefetch first tile via TMA
        T.tma_copy(
            Q[batch, row_start:row_start + BLOCK_S, head, 0:head_dim],
            Q_shared[0, :, :]
        )
        T.tma_copy(
            K[batch, col_start:col_start + BLOCK_S, head, 0:head_dim],
            K_shared[0, :, :]
        )
        T.tma_wait(0)

        # K-dimension loop (128 / MMA_K = 8 MMA steps)
        for k_tile in T.Pipelined(T.ceildiv(head_dim, MMA_K), num_stages=2):
            stage      = k_tile % 2
            next_stage = (k_tile + 1) % 2

            # Compute on current stage
            T.gemm(
                Q_shared[stage, :, k_tile * MMA_K:(k_tile + 1) * MMA_K],
                K_shared[stage, :, k_tile * MMA_K:(k_tile + 1) * MMA_K],
                S_frag,
                transpose_B=True,
                clear_accum=False,
                policy=T.GemmWarpPolicy.FullWarp,
            )

            # Async prefetch next stage
            if k_tile + 1 < T.ceildiv(head_dim, MMA_K):
                next_k = (k_tile + 1) * MMA_K
                T.tma_copy(
                    Q[batch, row_start:row_start + BLOCK_S, head,
                      next_k:next_k + MMA_K],
                    Q_shared[next_stage, :, k_tile * MMA_K:(k_tile + 1) * MMA_K],
                )
                T.tma_copy(
                    K[batch, col_start:col_start + BLOCK_S, head,
                      next_k:next_k + MMA_K],
                    K_shared[next_stage, :, k_tile * MMA_K:(k_tile + 1) * MMA_K],
                )

        # Scale and write back
        for i, j in T.Parallel(BLOCK_S, BLOCK_S):
            S_frag[i, j] *= scale

        T.tma_copy(
            S_frag,
            S[batch, row_start:row_start + BLOCK_S, head,
              col_start:col_start + BLOCK_S],
        )

    return kernel


if __name__ == "__main__":
    import torch

    B, N, H, D = 1, 2048, 8, 128
    sc = D ** -0.5

    print("Compiling Flash GDR QK^T Kernel...")
    kernel = flash_gdr_qkt_kernel(B, N, H, D, sc)

    print("\n--- PTX (first 5000 chars) ---")
    print(kernel.get_ptx()[:5000])

    print("\nRunning Profiler Verification...")
    profiler = Profiler(kernel)

    q_t = torch.randn(B, N, H, D, dtype=torch.float16, device="cuda")
    k_t = torch.randn(B, N, H, D, dtype=torch.float16, device="cuda")
    s_t = torch.empty(B, N, H, N, dtype=torch.float32, device="cuda")

    ref = (torch.matmul(q_t.transpose(1, 2),
                        k_t.transpose(1, 2).transpose(-1, -2))
           * sc)
    ref = ref.permute(0, 2, 1, 3).contiguous()

    profiler.func(q_t, k_t, s_t)

    max_err = (s_t - ref).abs().max().item()
    print(f"Max abs error vs torch: {max_err:.6f}")
    assert max_err < 1e-2, "Numerical verification failed"
    print("Numerical verification passed.")
