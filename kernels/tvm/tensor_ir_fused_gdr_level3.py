# TVM TensorIR Lowered PrimFunc (Level 3)
# Target: sm_86 (Ampere) / Deterministic Execution Graph
# Cryptographic anchor: 4b565498-9afc-4782-af4a-c6b11a5d0058

import tvm
from tvm import te
from tvm.script import tir as T


@T.prim_func
def tensor_ir_fused_gdr_level3(
    p_q: T.Buffer((1, 2048, 8, 128),  "float16"),
    p_k: T.Buffer((1, 2048, 8, 128),  "float16"),
    p_v: T.Buffer((1, 2048, 32, 128), "float16"),
    p_h: T.Buffer((1, 32, 32, 128, 128), "float16"),
    p_o: T.Buffer((1, 2048, 32, 128), "float16"),
):
    with T.block("root"):
        T.reads(p_q[0:1, 0:2048, 0:8, 0:128], p_k[0:1, 0:2048, 0:8, 0:128])
        T.writes(p_o[0:1, 0:2048, 0:32, 0:128])

        q_shared   = T.alloc_buffer((64, 128), "float16", scope="shared")
        k_shared   = T.alloc_buffer((64, 128), "float16", scope="shared")
        accum_reg  = T.alloc_buffer((64, 128), "float32", scope="local")

        for c_idx in T.serial(32):
            with T.block("chunk_loop"):
                T.evaluate(T.call_intrinsic("tvm_storage_sync", "shared"))

                for i, j, k in T.grid(64, 128, 128):
                    with T.block("gemm_update"):
                        vi, vj, vk = T.axis.remap("SSR", [i, j, k])
                        with T.init():
                            accum_reg[vi, vj] = T.float32(0.0)
                        accum_reg[vi, vj] = (
                            accum_reg[vi, vj] + q_shared[vi, vk] * k_shared[vj, vk]
                        )
