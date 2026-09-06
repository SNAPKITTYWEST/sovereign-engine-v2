# restored_gdr_kernel.py
# TileLang kernel restored by reversing the SASS→PTX→TensorIR decompilation path.
# Demonstrates the round-trip: HMMA.16816 / LDSM → mma.sync / ldmatrix → T.gemm.

import tilelang
import tilelang.language as T


@tilelang.jit(
    pass_configs={
        tilelang.PassConfigKey.TL_ENABLE_FAST_MATH: True,
    }
)
def restored_gdr_kernel(
    q: T.Tensor([1, 2048, 8, 128], "float16"),
    k: T.Tensor([1, 2048, 8, 128], "float16"),
    o: T.Tensor([1, 2048, 32, 128], "float32"),
):
    with T.Kernel(32, threads=512) as (bbhv,):
        q_shared  = T.alloc_shared((64, 128), dtype="float16")
        k_shared  = T.alloc_shared((64, 128), dtype="float16")
        p_fragment = T.alloc_fragment((64, 64), dtype="float32")

        # T.gemm lowers to mma.sync.aligned.m16n8k16.row.col
        T.gemm(q_shared, k_shared, p_fragment,
               transpose_B=True, clear_accum=True)
