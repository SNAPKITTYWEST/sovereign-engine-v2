"""
nomic_embedder.py — BOB's nomic-embed-text embedder.

Source: DEVFLOW-FINANCE/collectivekitty/lib/knowledge/embed.ts
        (BOB orchestrator knowledge layer)

Model:  nomic-embed-text via Ollama (localhost:11434)
Dims:   768 — same dimension as DeBERTa / BURT-IMMA hidden size
Cache:  in-process MD5-keyed LRU (CACHE_MAX=2048 entries)

This is the embedding layer BOB uses for semantic knowledge retrieval.
Connecting it to the sovereign text pipeline replaces the hash-based
skeleton embedder with real semantic vectors.

Fallback: if Ollama is not running, falls back to SkeletonEmbedder
(hash-based deterministic vectors at the same 768-dim).
"""

from __future__ import annotations

import hashlib
import json
import urllib.request
import urllib.error
from collections import OrderedDict
from typing import Optional

import numpy as np


OLLAMA_EMBED_URL = "http://localhost:11434/api/embeddings"
EMBED_MODEL      = "nomic-embed-text"
DIMS             = 768
CACHE_MAX        = 2048


class NomicEmbedder:
    """
    Drop-in replacement for SkeletonEmbedder that calls nomic-embed-text
    via the BOB knowledge layer's Ollama endpoint.

    If Ollama is not reachable, falls back to deterministic hash embeddings
    so the pipeline always produces output.
    """

    def __init__(
        self,
        ollama_url: str  = OLLAMA_EMBED_URL,
        model:      str  = EMBED_MODEL,
        dims:       int  = DIMS,
    ) -> None:
        self._url   = ollama_url
        self._model = model
        self._dims  = dims
        self._cache: OrderedDict[str, np.ndarray] = OrderedDict()
        self._alive = self._probe()
        if self._alive:
            print(f"[nomic-embed] Ollama reachable — using {model} ({dims}-dim)")
        else:
            print(f"[nomic-embed] Ollama not reachable — using skeleton fallback")

    def _probe(self) -> bool:
        try:
            req = urllib.request.Request(
                self._url.replace("/api/embeddings", "/api/tags"),
                method="GET"
            )
            with urllib.request.urlopen(req, timeout=0.5):
                return True
        except Exception:
            return False

    def _cache_key(self, text: str) -> str:
        return hashlib.md5(text.encode()).hexdigest()

    def _skeleton_vec(self, text: str) -> np.ndarray:
        """Deterministic 768-dim fallback (hash-seeded)."""
        seed = abs(hash(text)) % (2**31)
        rng  = np.random.default_rng(seed)
        v    = rng.normal(0, 0.1, self._dims).astype(np.float32)
        return v / (np.linalg.norm(v) + 1e-8)

    def embed_text(self, text: str) -> np.ndarray:
        """
        Embed a single string → (768,) float32 vector.
        Mirrors embed() from collectivekitty/lib/knowledge/embed.ts.
        """
        key = self._cache_key(text)
        if key in self._cache:
            return self._cache[key]

        if not self._alive:
            vec = self._skeleton_vec(text)
        else:
            try:
                body = json.dumps({"model": self._model, "prompt": text}).encode()
                req  = urllib.request.Request(
                    self._url,
                    data=body,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=10.0) as resp:
                    data = json.loads(resp.read())
                emb = data.get("embedding", [])
                if len(emb) != self._dims:
                    vec = self._skeleton_vec(text)
                else:
                    vec = np.array(emb, dtype=np.float32)
            except Exception:
                vec = self._skeleton_vec(text)

        # LRU eviction
        if len(self._cache) >= CACHE_MAX:
            self._cache.popitem(last=False)
        self._cache[key] = vec
        return vec

    def embed(self, text: str, max_tokens: int = 48) -> np.ndarray:
        """
        Embed text into a (max_tokens, 768) token-level matrix.

        Strategy: embed the full text as one 768-dim vector, then
        tile per-word embeddings so the BURT-IMMA encoder sees a sequence.
        Full-text embedding is injected as the first row for global context.
        """
        words   = text.split()[:max_tokens]
        result  = np.zeros((max(len(words), 1), self._dims), dtype=np.float32)

        # Full-text embedding → row 0 (global context)
        full_vec = self.embed_text(text)
        result[0] = full_vec

        # Per-word embeddings → subsequent rows
        for i, word in enumerate(words):
            if i < len(result):
                result[i] = 0.7 * self.embed_text(word) + 0.3 * full_vec

        return result   # (T, 768)

    def embed_batch(self, texts: list[str]) -> list[np.ndarray]:
        """Embed a batch of strings. Mirrors embedBatch() from embed.ts."""
        return [self.embed_text(t) for t in texts]

    def similarity(self, a: str, b: str) -> float:
        """Cosine similarity between two texts (0=orthogonal, 1=identical)."""
        va = self.embed_text(a)
        vb = self.embed_text(b)
        return float(np.dot(va, vb) / (np.linalg.norm(va) * np.linalg.norm(vb) + 1e-8))

    def entailment_score(self, premise: str, hypothesis: str) -> float:
        """
        Semantic similarity as a proxy entailment score.
        Range [0, 1] — high = semantically close = likely entailed.

        Production: use bert-agent DeBERTa cross-encoder for true entailment.
        """
        cos = self.similarity(premise, hypothesis)
        return (cos + 1.0) / 2.0   # [-1, 1] → [0, 1]
