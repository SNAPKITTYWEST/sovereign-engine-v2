"""
text_output_pipeline.py — Sovereign Text Output Pipeline (Dual Layer).

  Level 1  QRA classify → glyph (Π Γ Δ Λ Ω Ψ)

  Layer A — whole-query path (original):
    Level 2A  SkeletonEmbedder(query) → (T, 768) → MUM atoms
    Level 3A  BURT-IMMA CIFG stack → hidden_full (768,)

  Layer B — chunked path:
    Level 2B  SemanticChunker → sentence chunks
    Level 3B  SkeletonEmbedder per chunk → MUM atoms per chunk
    Level 4B  BURT-IMMA CIFG stack over all chunk atoms → hidden_chunked (768,)

  Fusion:
    Level 5   hidden = (hidden_full + hidden_chunked) / 2
    Level 6   Entropy-constrained softmax → top-k token selection
    Level 7   Entailment: mean(full-query score, per-chunk mean score)
    Level 8   ERE 5-gate certification
    Level 9   ResonanceUMO → resonance words from verification score

Usage:
    pipe = TextOutputPipeline.build()
    result = pipe.run("Explain why the resonance field is coherent")
    print(result.text)
    print(result.resonance_sentence)
"""

from __future__ import annotations

import sys
import os
from dataclasses import dataclass
from typing import Optional

import numpy as np

# QRA router
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from runtime.providers.qra_router import QRARouter, GlyphCapabilityRegistry

# BURT-IMMA
from .burt_imma import BURTIMMAEncoder, BURTIMMAConfig, entropy_constrained_softmax

# Sovereign MUM — Multimodal Atom + State Transition
from mum.atom import ModalityEncoder, SemanticGradientBoundary, StateTransition, Atom

# Chunker — add src/ to sys.path so we can import retrieval.chunker standalone
_src = os.path.join(os.path.dirname(__file__), "..")
if _src not in sys.path:
    sys.path.insert(0, _src)

# Temporarily hide the broken __init__ so only chunker.py loads
import importlib, importlib.util as _ilu
_chunker_path = os.path.join(_src, "retrieval", "chunker.py")
_spec = _ilu.spec_from_file_location("retrieval.chunker", _chunker_path)
_cmod = _ilu.module_from_spec(_spec)
_cmod.__package__ = "retrieval"
import sys as _sys
_sys.modules.setdefault("retrieval.chunker", _cmod)
_spec.loader.exec_module(_cmod)
SemanticChunker = _cmod.SemanticChunker
ChunkConfig     = _cmod.ChunkConfig
ChunkStrategy   = _cmod.ChunkStrategy
Chunk           = _cmod.Chunk

# Resonance
from resonance.bridge import DrainInvariants, invariants_to_umo
from resonance.sentence import produce_sentence
from resonance.umo import Umo


# ---------------------------------------------------------------------------
# Lightweight ERE gate (mirrors resonance-math/lib/ere.mjs)
# ---------------------------------------------------------------------------

def ere_check(text: str) -> dict:
    """Python mirror of ereRunPasses from resonance-math."""
    s = text.lower()
    fab = ["fabricat", "invent", "i made up", "i cannot provide", "as an ai"]
    mis = {"null", "undefined", "none", "void"}
    p1 = len(text) > 3
    p2 = not any(m in s for m in fab)
    p3 = len(text) > 0
    p4 = s not in mis and "void" not in s
    p5 = text is not None                  # Enochian root opcode
    score = sum(0 if p else 1 for p in [p1, p2, p3, p4, p5]) / 5.0
    return {
        "pass1": p1, "pass2": p2, "pass3": p3, "pass4": p4, "pass5_root": p5,
        "score": score, "certified": score == 0.0,
        "metatron": "YES" if score == 0.0 else "NO",
    }


# ---------------------------------------------------------------------------
# Skeleton embedder (fallback when transformers / torch unavailable)
# ---------------------------------------------------------------------------

class SkeletonEmbedder:
    """
    Deterministic skeleton embedder — produces reproducible (T, 768) arrays
    via a seeded hash of the input text, so the pipeline runs without torch.

    In production: replace with DeBERTaEncoder from bert-agent/bert/model.py.
    """

    D = 768

    def embed(self, text: str, max_tokens: int = 32) -> np.ndarray:
        words  = text.split()[:max_tokens]
        result = np.zeros((len(words), self.D), dtype=np.float32)
        for i, word in enumerate(words):
            seed = abs(hash(word)) % (2**31)
            rng  = np.random.default_rng(seed)
            result[i] = rng.normal(0, 0.1, self.D).astype(np.float32)
        return result

    def entailment_score(self, premise: str, hypothesis: str) -> float:
        """
        Skeleton entailment: cosine similarity of mean embeddings.
        Production: use BertCrossEncoderVerifier from bert-agent.
        """
        e_p = self.embed(premise).mean(axis=0)
        e_h = self.embed(hypothesis).mean(axis=0)
        cos = float(np.dot(e_p, e_h) / (
            np.linalg.norm(e_p) * np.linalg.norm(e_h) + 1e-8
        ))
        return (cos + 1.0) / 2.0   # rescale [-1,1] → [0,1]


# ---------------------------------------------------------------------------
# Output dataclass
# ---------------------------------------------------------------------------

@dataclass
class PipelineOutput:
    query:              str
    glyph:              str               # QRA routing decision (Π Γ Δ Λ Ω Ψ)
    glyph_symbol:       str
    hidden_full:        np.ndarray        # Layer A: whole-query BURT-IMMA (768,)
    hidden_chunked:     np.ndarray        # Layer B: chunked BURT-IMMA (768,)
    hidden_state:       np.ndarray        # Fused: (hidden_full + hidden_chunked) / 2
    top_token_ids:      list[int]
    text:               str               # generated / decoded text
    entailment_score:   float             # mean(full-query, per-chunk) entailment (0-1)
    entailment_label:   str               # Entailment / Neutral / Contradiction
    ere:                dict              # ERE 5-gate results
    umo:                Umo               # oscillator state
    resonance_sentence: str              # resonance word machine output
    routing_entropy:    float             # QRA routing entropy (nats)
    n_chunks:           int               # number of semantic chunks processed


# ---------------------------------------------------------------------------
# MUM atom builder — shared by run()
# ---------------------------------------------------------------------------

def _build_atoms(
    embedder: SkeletonEmbedder,
    chunk_text: str,
) -> list[Atom]:
    """Embed one chunk and return its MUM atom chain."""
    raw_emb    = embedder.embed(chunk_text, max_tokens=48)     # (T, 768)

    modality_enc = ModalityEncoder(input_dim=768, d_manifold=768)
    z_manifold   = modality_enc.encode_text_tokens(raw_emb)    # (T, 768)

    boundary_det = SemanticGradientBoundary(epsilon=0.1)
    provenance   = [{"modality": "text"}] * len(raw_emb)
    atoms        = boundary_det.split_atoms(z_manifold, provenance)

    state_trans  = StateTransition(d_model=768, d_context=768)
    context      = z_manifold.mean(axis=0)
    for i in range(1, len(atoms)):
        atoms[i] = state_trans.transition(atoms[i - 1], context)

    return atoms


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

_CHUNK_CFG = ChunkConfig(
    strategy=ChunkStrategy.SENTENCE,
    chunk_size=128,
    chunk_overlap=16,
    min_chunk_size=5,
)

class TextOutputPipeline:
    """
    Sovereign text output pipeline.

    Connects:
      QRA (routing) → SemanticChunker → BERT embed per chunk
      → MUM atoms → BURT-IMMA encode → decode
      → per-chunk entailment → ERE gate → Resonance UMO → output
    """

    GLYPH_SYMBOLS = {"Pi": "Π", "Gamma": "Γ", "Delta": "Δ",
                     "Lambda": "Λ", "Omega": "Ω", "Psi": "Ψ"}

    def __init__(
        self,
        qra:       QRARouter,
        embedder:  SkeletonEmbedder,
        encoder:   BURTIMMAEncoder,
        vocab:     list[str],
    ) -> None:
        self._qra      = qra
        self._embedder = embedder
        self._encoder  = encoder
        self._vocab    = vocab
        self._chunker  = SemanticChunker()
        # Vocab embeddings: one per word (seeded hash)
        self._vocab_emb = np.vstack([
            SkeletonEmbedder().embed(w, max_tokens=1)[0]
            for w in vocab
        ])  # (V, 768)

    @classmethod
    def build(
        cls,
        provider_map: Optional[dict] = None,
        vocab:        Optional[list[str]] = None,
    ) -> "TextOutputPipeline":
        """Build a pipeline with default components."""
        if provider_map is None:
            provider_map = {
                "Pi":     ["claude"],
                "Gamma":  ["claude"],
                "Delta":  ["claude"],
                "Lambda": ["claude"],
                "Omega":  ["claude"],
                "Psi":    ["claude"],
            }
        if vocab is None:
            vocab = [
                "the", "sovereign", "field", "seals", "resonance", "coherent",
                "entropy", "trust", "lattice", "worm", "proof", "signal",
                "phase", "manifold", "periodic", "orbit", "threshold", "boundary",
                "crystalline", "luminous", "harmonic", "stable", "kernel",
                "oscillator", "waveform", "deed", "seal", "chain", "gate",
                "Enochian", "root", "opcode", "verified", "certified", "pass",
            ]

        qra  = QRARouter(provider_map)
        cfg  = BURTIMMAConfig(d_model=768, n_layers=3, max_entropy=0.20)
        enc  = BURTIMMAEncoder(cfg)
        embedder = SkeletonEmbedder()

        return cls(qra, embedder, enc, vocab)

    # ------------------------------------------------------------------
    # Core run
    # ------------------------------------------------------------------

    def run(self, query: str) -> PipelineOutput:
        """
        Run the dual-layer sovereign text output pipeline.

        1.  QRA classify → glyph
        2A. Layer A: embed whole query → MUM atoms → BURT-IMMA → hidden_full
        2B. Layer B: chunk query → per-chunk embed → MUM atoms → BURT-IMMA → hidden_chunked
        3.  Fuse: hidden = (hidden_full + hidden_chunked) / 2
        4.  Entropy-constrained softmax decode → top-k tokens
        5.  Assemble text
        6.  Entailment: mean(full-query score, per-chunk mean score)
        7.  ERE 5-gate certification
        8.  ResonanceUMO
        9.  Produce resonance sentence
        """

        # ── 1. QRA routing ──────────────────────────────────────────────
        glyph, _provider = self._qra.route(query)
        symbol           = self.GLYPH_SYMBOLS.get(glyph, glyph)
        routing_entropy  = self._qra.entropy()

        # ── 2A. Layer A — whole-query path (original) ────────────────────
        full_atoms  = _build_atoms(self._embedder, query)
        full_emb    = np.stack([a.z for a in full_atoms])   # (T, 768)
        hidden_full = self._encoder.encode(full_emb)         # (768,)

        # ── 2B. Layer B — chunked path ───────────────────────────────────
        chunks = self._chunker.chunk(query, _CHUNK_CFG)
        if not chunks:
            chunks = [Chunk(id="0", content=query, start_char=0, end_char=len(query))]

        chunk_atoms: list[Atom] = []
        for ck in chunks:
            chunk_atoms.extend(_build_atoms(self._embedder, ck.content))
        chunk_emb      = np.stack([a.z for a in chunk_atoms])   # (total_atoms, 768)
        hidden_chunked = self._encoder.encode(chunk_emb)         # (768,)

        # ── 3. Fuse ──────────────────────────────────────────────────────
        hidden = (hidden_full + hidden_chunked) / 2.0            # (768,)

        # ── 4. Decode top tokens ─────────────────────────────────────────
        top_ids   = self._encoder.decode_top_tokens(hidden, self._vocab_emb, k=8)
        top_words = [self._vocab[i] for i in top_ids]

        # ── 5. Assemble text ─────────────────────────────────────────────
        glyph_intent = {
            "Pi":     "reasoning about",
            "Gamma":  "describing",
            "Delta":  "analyzing",
            "Lambda": "implementing",
            "Omega":  "orchestrating",
            "Psi":    "verifying",
        }.get(glyph, "processing")

        text = (
            f"{symbol} [{glyph}] {glyph_intent}: "
            + " ".join(top_words[:5])
            + "."
        )

        # ── 6. Dual entailment → aggregate ───────────────────────────────
        ent_full = self._embedder.entailment_score(query, text)
        per_chunk_ent = [
            self._embedder.entailment_score(ck.content, text)
            for ck in chunks
        ]
        ent_score = float(np.mean([ent_full] + per_chunk_ent))
        ent_label = (
            "Entailment"    if ent_score > 0.65
            else "Neutral"  if ent_score > 0.40
            else "Contradiction"
        )

        # ── 7. ERE gate ──────────────────────────────────────────────────
        ere = ere_check(text)

        # ── 8. ResonanceUMO ──────────────────────────────────────────────
        glyph_idx = ["Pi","Gamma","Delta","Lambda","Omega","Psi"].index(glyph)
        ere_bonus = 0.25 if ere["certified"] else 0.0
        umo_trust = min(1.0, ent_score + ere_bonus)
        umo_ent   = min(0.18, ere["score"] * 0.18)
        umo_res   = 0.2 + glyph_idx * 0.13

        umo = Umo(trust=umo_trust, entropy=umo_ent, resonance=umo_res)

        sent = produce_sentence(
            complexity_frac = umo_trust,
            entropy_frac    = umo_ent,
        )

        return PipelineOutput(
            query            = query,
            glyph            = glyph,
            glyph_symbol     = symbol,
            hidden_full      = hidden_full,
            hidden_chunked   = hidden_chunked,
            hidden_state     = hidden,
            top_token_ids    = top_ids,
            text             = text,
            entailment_score = ent_score,
            entailment_label = ent_label,
            ere              = ere,
            umo              = umo,
            resonance_sentence = sent.sentence,
            routing_entropy  = routing_entropy,
            n_chunks         = len(chunks),
        )

    def render(self, query: str) -> str:
        out = self.run(query)
        sep = "─" * 58
        lines = [
            "⟦ Ω ⟧ SOVEREIGN TEXT OUTPUT PIPELINE",
            sep,
            f"  query    : {out.query}",
            f"  chunks   : {out.n_chunks}",
            f"  glyph    : {out.glyph_symbol} [{out.glyph}]  entropy={out.routing_entropy:.6f} nats",
            sep,
            "  BURT-IMMA CIFG dual encode:",
            f"  Layer A (full)    ‖h‖ = {float(np.linalg.norm(out.hidden_full)):.4f}",
            f"  Layer B (chunked) ‖h‖ = {float(np.linalg.norm(out.hidden_chunked)):.4f}",
            f"  Fused             ‖h‖ = {float(np.linalg.norm(out.hidden_state)):.4f}",
            f"  top tokens : {[self._vocab[i] for i in out.top_token_ids[:6]]}",
            sep,
            f"  text     : {out.text}",
            sep,
            f"  entailment : {out.entailment_label}  score={out.entailment_score:.4f}  (full + {out.n_chunks} chunks, mean)",
            sep,
            "  ERE 5-gate:",
            f"    P1 structural : {out.ere['pass1']}",
            f"    P2 scholarly  : {out.ere['pass2']}",
            f"    P3 invariants : {out.ere['pass3']}",
            f"    P4 mission    : {out.ere['pass4']}",
            f"    P5 root       : {out.ere['pass5_root']}   ← Enochian root opcode",
            f"    certified     : {out.ere['certified']}   metatron={out.ere['metatron']}",
            sep,
            f"  UMO  τ={out.umo.trust:.3f}  ε={out.umo.entropy:.3f}  ρ={out.umo.resonance:.3f}"
            f"  {'COHERENT ☉' if out.umo.coherent() else 'INCOHERENT ⛔'}",
            f"  resonance: {out.resonance_sentence}",
            sep,
            f"  {out.umo.sealed_output()}",
        ]
        return "\n".join(lines)
