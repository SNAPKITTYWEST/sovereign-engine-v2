"""
dag_ir.py — Custom Compiler DAG Meta-Engine for Qwen3ASR Pipeline.

Lowering pipeline:
  qwen3asr dialect → Fortran subroutines → AVX-512/AMX assembly → x86-64

Code generators:
  FortranCodeGen   → FORTRAN 97 subroutine skeletons
  AssemblyCodeGen  → AVX-512/AMX GEMM kernel stubs
  HaskellCodeGen   → Foreign import ccall bindings for Fortran symbols
"""

from __future__ import annotations

import hashlib
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Set, Tuple


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class OpKind(Enum):
    # High-level qwen3asr dialect ops
    CONV2D_GELU        = auto()
    FLATTEN_TIME_FREQ  = auto()
    LINEAR             = auto()
    SINUSOID_POS       = auto()
    LAYERNORM          = auto()
    MULTI_HEAD_ATTN    = auto()
    RESIDUAL_ADD       = auto()
    GELU               = auto()
    # Composite
    ENCODER_LAYER      = auto()
    AUDIO_ENCODER      = auto()
    MERGE_EMBEDDINGS   = auto()
    # Lowered
    GEMM               = auto()
    TDPBF16PS          = auto()   # AMX
    VFMADD231PS        = auto()   # AVX-512
    CONV2D_GELU_F      = auto()   # Fortran subroutine
    ENCODER_LAYER_F    = auto()


class Precision(Enum):
    FP32  = "f32"
    FP16  = "f16"
    BF16  = "bf16"
    INT8  = "i8"


# ---------------------------------------------------------------------------
# TensorSpec
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TensorSpec:
    shape:     Tuple[Optional[int], ...]   # None = dynamic
    dtype:     Precision
    alignment: int = 64
    name:      str = ""

    def size_bytes(self) -> int:
        numel = 1
        for d in self.shape:
            if d is not None:
                numel *= d
        elem = 4 if self.dtype == Precision.FP32 else 2
        return numel * elem


# ---------------------------------------------------------------------------
# DAGNode
# ---------------------------------------------------------------------------

@dataclass
class DAGNode:
    id:           str
    kind:         OpKind
    inputs:       List[str]       = field(default_factory=list)
    outputs:      List[TensorSpec] = field(default_factory=list)
    attrs:        Dict[str, Any]  = field(default_factory=dict)
    metadata:     Dict[str, Any]  = field(default_factory=dict)
    lowered_from: Optional[str]   = None

    def __hash__(self):
        return hash(self.id)

    def verify_checklist(self) -> List[str]:
        """Return a list of CUFF violations; empty = clean."""
        violations: List[str] = []

        for out in self.outputs:
            if out.alignment % 64 != 0:
                violations.append(
                    f"{self.id}: output '{out.name}' not 64-byte aligned"
                )

        if self.kind in (OpKind.GEMM, OpKind.TDPBF16PS, OpKind.VFMADD231PS):
            for dim in ("m", "n", "k"):
                val = self.attrs.get(dim, 0)
                if isinstance(val, int) and val <= 0:
                    violations.append(f"{self.id}: GEMM dim '{dim}' must be > 0")

        if self.kind == OpKind.MULTI_HEAD_ATTN:
            expected_scale = self.attrs.get("head_dim", 1) ** -0.5
            actual_scale   = self.attrs.get("scale", None)
            if actual_scale is None or abs(actual_scale - expected_scale) > 1e-6:
                violations.append(
                    f"{self.id}: attention scale must be 1/sqrt(head_dim)"
                )

        if self.kind == OpKind.ENCODER_LAYER:
            if not self.attrs.get("residual_after_attn", False):
                violations.append(f"{self.id}: missing residual after attention")
            if not self.attrs.get("residual_after_ffn", False):
                violations.append(f"{self.id}: missing residual after FFN")

        return violations


# ---------------------------------------------------------------------------
# DAG
# ---------------------------------------------------------------------------

class DAG:
    def __init__(self) -> None:
        self.nodes:     Dict[str, DAGNode]  = {}
        self.edges:     Dict[str, Set[str]] = {}
        self.rev_edges: Dict[str, Set[str]] = {}

    def add_node(self, node: DAGNode) -> None:
        if node.id in self.nodes:
            raise ValueError(f"Duplicate node id: {node.id}")
        self.nodes[node.id]     = node
        self.edges[node.id]     = set()
        self.rev_edges[node.id] = set()
        for inp in node.inputs:
            self._add_edge(inp, node.id)

    def _add_edge(self, src: str, dst: str) -> None:
        if src not in self.nodes or dst not in self.nodes:
            raise ValueError(f"Edge references unknown node: {src} -> {dst}")
        self.edges[src].add(dst)
        self.rev_edges[dst].add(src)

    def topological_order(self) -> List[str]:
        """Kahn's algorithm — raises if cycle detected."""
        indeg = {nid: len(self.rev_edges[nid]) for nid in self.nodes}
        queue = [nid for nid, d in indeg.items() if d == 0]
        order: List[str] = []
        while queue:
            nid = queue.pop(0)
            order.append(nid)
            for succ in self.edges[nid]:
                indeg[succ] -= 1
                if indeg[succ] == 0:
                    queue.append(succ)
        if len(order) != len(self.nodes):
            raise ValueError("Graph has cycles")
        return order

    def verify_all(self) -> Dict[str, List[str]]:
        return {
            nid: v
            for nid, node in self.nodes.items()
            if (v := node.verify_checklist())
        }


# ---------------------------------------------------------------------------
# Dialect: Qwen3ASR
# ---------------------------------------------------------------------------

class Qwen3ASRDialect:
    """Builds the high-level Qwen3-ASR audio encoder DAG."""

    @staticmethod
    def build_audio_encoder(
        d_model:    int = 512,
        n_heads:    int = 8,
        n_layers:   int = 12,
        d_ff:       int = 2048,
        mel_bins:   int = 80,
        output_dim: int = 512,
    ) -> DAG:
        dag = DAG()
        _ctr = [0]

        def nid(prefix: str) -> str:
            _ctr[0] += 1
            return f"{prefix}_{_ctr[0]}"

        # ── Inputs ──────────────────────────────────────────────────────────
        for name, spec in [
            ("features",      TensorSpec((None, mel_bins), Precision.FP32, name="mel_features")),
            ("feat_lens",     TensorSpec((None,),          Precision.INT8,  name="feat_lens")),
            ("aftercnn_lens", TensorSpec((None,),          Precision.INT8,  name="aftercnn_lens")),
        ]:
            dag.add_node(DAGNode(id=nid(name), kind=OpKind.AUDIO_ENCODER,
                                 outputs=[spec]))

        node_ids = list(dag.nodes.keys())
        feats_id       = node_ids[0]
        aftercnn_id    = node_ids[2]

        # ── CNN path: 3× Conv2d+GELU (stride 2) ─────────────────────────────
        cnn_in = feats_id
        for i in range(3):
            out_ch = 256 if i == 0 else 512
            cnn = DAGNode(
                id=nid(f"c{i+1}"),
                kind=OpKind.CONV2D_GELU,
                inputs=[cnn_in],
                outputs=[TensorSpec((None, None, None, out_ch), Precision.FP32,
                                    name=f"cnn_{i+1}_out")],
                attrs={"kernel": 3, "stride": 2, "pad": 1, "out_channels": out_ch},
            )
            dag.add_node(cnn)
            cnn_in = cnn.id

        # ── Flatten time+freq ────────────────────────────────────────────────
        flat = DAGNode(
            id=nid("flat"),
            kind=OpKind.FLATTEN_TIME_FREQ,
            inputs=[cnn_in],
            outputs=[TensorSpec((None, d_model), Precision.FP32, name="flattened")],
        )
        dag.add_node(flat)

        # ── Linear projection ────────────────────────────────────────────────
        proj = DAGNode(
            id=nid("proj"),
            kind=OpKind.LINEAR,
            inputs=[flat.id],
            outputs=[TensorSpec((None, d_model), Precision.FP32, name="proj_out")],
            attrs={"out_dim": d_model},
        )
        dag.add_node(proj)

        # ── Positional encoding ──────────────────────────────────────────────
        pos = DAGNode(
            id=nid("pos"),
            kind=OpKind.SINUSOID_POS,
            inputs=[proj.id],
            outputs=[TensorSpec((None, d_model), Precision.FP32, name="pos_enc")],
        )
        dag.add_node(pos)

        h = DAGNode(
            id=nid("h0"),
            kind=OpKind.RESIDUAL_ADD,
            inputs=[proj.id, pos.id],
            outputs=[TensorSpec((None, d_model), Precision.FP32, name="h0")],
        )
        dag.add_node(h)

        # ── Encoder layers ───────────────────────────────────────────────────
        for idx in range(n_layers):
            layer = DAGNode(
                id=nid(f"layer_{idx}"),
                kind=OpKind.ENCODER_LAYER,
                inputs=[h.id, aftercnn_id],
                outputs=[TensorSpec((None, d_model), Precision.FP32,
                                    name=f"h{idx+1}")],
                attrs={
                    "d_model": d_model,
                    "n_heads": n_heads,
                    "d_ff":    d_ff,
                    "head_dim": d_model // n_heads,
                    "scale":   (d_model // n_heads) ** -0.5,
                    "residual_after_attn": True,
                    "residual_after_ffn":  True,
                },
            )
            dag.add_node(layer)
            h = layer

        # ── Final LayerNorm + FFN head ───────────────────────────────────────
        ln = DAGNode(
            id=nid("ln_final"), kind=OpKind.LAYERNORM, inputs=[h.id],
            outputs=[TensorSpec((None, d_model), Precision.FP32, name="ln_out")],
            attrs={"eps": 1e-6},
        )
        dag.add_node(ln)

        p1 = DAGNode(
            id=nid("p1"), kind=OpKind.LINEAR, inputs=[ln.id],
            outputs=[TensorSpec((None, d_ff), Precision.FP32, name="p1_out")],
            attrs={"out_dim": d_ff},
        )
        dag.add_node(p1)

        act = DAGNode(
            id=nid("act"), kind=OpKind.GELU, inputs=[p1.id],
            outputs=[TensorSpec((None, d_ff), Precision.FP32, name="act_out")],
        )
        dag.add_node(act)

        out = DAGNode(
            id=nid("out"), kind=OpKind.LINEAR, inputs=[act.id],
            outputs=[TensorSpec((None, output_dim), Precision.FP32,
                                name="audio_embeddings")],
            attrs={"out_dim": output_dim},
        )
        dag.add_node(out)
        return dag


# ---------------------------------------------------------------------------
# Lowering passes
# ---------------------------------------------------------------------------

class LoweringPass(ABC):
    @abstractmethod
    def run(self, dag: DAG) -> DAG:
        ...


class DialectToFortranLowering(LoweringPass):
    FORTRAN_TEMPLATES: Dict[OpKind, str] = {
        OpKind.CONV2D_GELU:       "conv2d_gelu_f",
        OpKind.ENCODER_LAYER:     "encoder_layer_f",
        OpKind.LAYERNORM:         "layernorm_f",
        OpKind.LINEAR:            "linear_f",
        OpKind.GELU:              "gelu_f",
        OpKind.MULTI_HEAD_ATTN:   "attention_f",
        OpKind.RESIDUAL_ADD:      "residual_add_f",
        OpKind.FLATTEN_TIME_FREQ: "flatten_time_freq_f",
        OpKind.SINUSOID_POS:      "sinusoid_pos_f",
    }

    def run(self, dag: DAG) -> DAG:
        new_dag = DAG()
        id_map: Dict[str, str] = {}
        for nid in dag.topological_order():
            node = dag.nodes[nid]
            if node.kind in self.FORTRAN_TEMPLATES:
                sym = self.FORTRAN_TEMPLATES[node.kind]
                lo_kind = (OpKind.CONV2D_GELU_F
                           if node.kind == OpKind.CONV2D_GELU
                           else OpKind.ENCODER_LAYER_F)
                lowered = DAGNode(
                    id=f"{nid}_f",
                    kind=lo_kind,
                    inputs=[id_map.get(i, i) for i in node.inputs],
                    outputs=node.outputs,
                    attrs={**node.attrs, "fortran_symbol": sym},
                    lowered_from=nid,
                )
                new_dag.add_node(lowered)
                id_map[nid] = lowered.id
            else:
                new_dag.add_node(node)
                id_map[nid] = nid
        return new_dag


class FortranToAssemblyLowering(LoweringPass):
    def run(self, dag: DAG) -> DAG:
        new_dag = DAG()
        id_map: Dict[str, str] = {}
        for nid in dag.topological_order():
            node = dag.nodes[nid]
            if node.kind in (OpKind.ENCODER_LAYER_F,):
                d_model = node.attrs.get("d_model", 512)
                d_ff    = node.attrs.get("d_ff",    2048)
                for sub_id, tmpl, out_n in [
                    (f"{nid}_qkv",        "raw_qkv_gemm",       d_model * 3),
                    (f"{nid}_attn_score",  "raw_attn_score_gemm", None),
                    (f"{nid}_attn_out",    "raw_attn_out_gemm",   d_model),
                    (f"{nid}_ffn1",        "raw_ffn_gemm",        d_ff),
                    (f"{nid}_ffn2",        "raw_ffn_gemm",        d_model),
                ]:
                    out_shape = (None, out_n) if out_n else (None, None)
                    g = DAGNode(
                        id=sub_id,
                        kind=OpKind.GEMM,
                        inputs=[id_map.get(i, i) for i in node.inputs],
                        outputs=[TensorSpec(out_shape, Precision.FP32)],
                        attrs={"m": "seq", "n": out_n or "seq", "k": d_model,
                               "template": tmpl},
                        lowered_from=nid,
                    )
                    new_dag.add_node(g)
                id_map[nid] = f"{nid}_ffn2"
            else:
                new_dag.add_node(node)
                id_map[nid] = nid
        return new_dag


# ---------------------------------------------------------------------------
# Code generators
# ---------------------------------------------------------------------------

class CodeGen(ABC):
    @abstractmethod
    def emit(self, dag: DAG) -> str:
        ...


class FortranCodeGen(CodeGen):
    def emit(self, dag: DAG) -> str:
        lines = ["MODULE qwen3asr_generated", " IMPLICIT NONE", " INTERFACE"]
        seen: set = set()
        for nid in dag.topological_order():
            node = dag.nodes[nid]
            sym = node.attrs.get("fortran_symbol")
            if sym and sym not in seen:
                seen.add(sym)
                lines += [f" SUBROUTINE {sym}(...)", " END SUBROUTINE"]
        lines += [" END INTERFACE", "CONTAINS",
                  " ! Generated subroutine bodies in narm/fortran/",
                  "END MODULE qwen3asr_generated"]
        return "\n".join(lines)


class AssemblyCodeGen(CodeGen):
    def emit(self, dag: DAG) -> str:
        lines = ["; Generated AVX-512/AMX GEMM kernels", "; Target: x86-64", ""]
        seen: set = set()
        for nid in dag.topological_order():
            node = dag.nodes[nid]
            if node.kind == OpKind.GEMM:
                tmpl = node.attrs.get("template", "unknown_gemm")
                if tmpl not in seen:
                    seen.add(tmpl)
                    lines += [
                        f"; {nid} <- {tmpl}",
                        f"{tmpl}:",
                        " ; RDI=A RSI=B RDX=C RCX=M R8=N R9=K",
                        " ; vfmadd231ps / tdpbf16ps tile loop",
                        " vzeroupper",
                        " ret",
                        "",
                    ]
        return "\n".join(lines)


class HaskellCodeGen(CodeGen):
    def emit(self, dag: DAG) -> str:
        lines = [
            "{-# LANGUAGE ForeignFunctionInterface #-}",
            "module Qwen3ASRGenerated where",
            "",
            "import Foreign.C.Types",
            "import Foreign.Ptr",
            "import qualified Data.Vector.Storable as V",
            "",
        ]
        seen: set = set()
        for node in dag.nodes.values():
            sym = node.attrs.get("fortran_symbol")
            if sym and sym not in seen:
                seen.add(sym)
                lines += [
                    f'foreign import ccall "{sym}"',
                    f" c_{sym} :: Ptr CFloat -> Ptr CFloat"
                    " -> CInt -> CInt -> CInt -> CInt -> CInt -> IO ()",
                    "",
                ]
        lines += [
            "audioEncoder :: V.Vector Float -> V.Vector Int"
            " -> V.Vector Int -> IO (V.Vector Float)",
            "audioEncoder _feats _featLens _afterCnnLens = do",
            "  -- Generated FFI calls in topological order",
            "  pure V.empty",
            "",
            "mergeEmbeddings :: V.Vector Float -> V.Vector Float"
            " -> V.Vector Bool -> V.Vector Float",
            "mergeEmbeddings textEmbeds audioEmbeds isMultimodal =",
            "  V.zipWith3 (\\t a m -> if m then a else t)"
            " textEmbeds audioEmbeds isMultimodal",
        ]
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Pipeline driver
# ---------------------------------------------------------------------------

class CompilerPipeline:
    def __init__(self) -> None:
        self.passes:   List[LoweringPass]     = []
        self.codegens: Dict[str, CodeGen]     = {}

    def add_pass(self, p: LoweringPass) -> "CompilerPipeline":
        self.passes.append(p)
        return self

    def add_codegen(self, name: str, gen: CodeGen) -> "CompilerPipeline":
        self.codegens[name] = gen
        return self

    def run(self, dag: DAG) -> Dict[str, str]:
        current = dag
        for p in self.passes:
            current = p.run(current)

        violations = current.verify_all()
        if violations:
            raise RuntimeError(
                f"CUFF checklist violations:\n"
                + json.dumps(violations, indent=2)
            )

        return {name: gen.emit(current) for name, gen in self.codegens.items()}


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    dag = Qwen3ASRDialect.build_audio_encoder(
        d_model=512, n_heads=8, n_layers=12, d_ff=2048,
        mel_bins=80, output_dim=512,
    )
    print(f"High-level DAG: {len(dag.nodes)} nodes")

    pipeline = (
        CompilerPipeline()
        .add_pass(DialectToFortranLowering())
        .add_pass(FortranToAssemblyLowering())
        .add_codegen("fortran",  FortranCodeGen())
        .add_codegen("assembly", AssemblyCodeGen())
        .add_codegen("haskell",  HaskellCodeGen())
    )

    artifacts = pipeline.run(dag)
    for name, code in artifacts.items():
        print(f"\n=== {name.upper()} ===")
        print(code[:1500] + ("..." if len(code) > 1500 else ""))
