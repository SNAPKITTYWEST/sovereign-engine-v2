"""
Vector Store
Part of SOVEREIGN PYTHON LLM ENGINE

InMemoryVectorStore with pure-Python cosine similarity, JSONL persistence,
full sync support, and a pluggable EmbeddingGenerator (local TF-IDF or OpenAI).

Pure stdlib + optional openai package — no numpy required.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import os
import random
import re
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .chunker import Chunk


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class VectorEntry:
    """A chunk paired with its embedding vector and an optional retrieval score."""
    id: str
    chunk: Chunk
    embedding: list[float]
    score: float = 0.0

    def to_dict(self) -> dict:
        """Serialise to a JSON-safe dict (for JSONL persistence)."""
        return {
            "id": self.id,
            "chunk": {
                "id": self.chunk.id,
                "content": self.chunk.content,
                "start_char": self.chunk.start_char,
                "end_char": self.chunk.end_char,
                "metadata": self.chunk.metadata,
                "token_count": self.chunk.token_count,
                "embedding": self.chunk.embedding,
            },
            "embedding": self.embedding,
            "score": self.score,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "VectorEntry":
        """Deserialise from a dict loaded from JSONL."""
        c = data["chunk"]
        chunk = Chunk(
            id=c["id"],
            content=c["content"],
            start_char=c["start_char"],
            end_char=c["end_char"],
            metadata=c.get("metadata", {}),
            token_count=c.get("token_count", 0),
            embedding=c.get("embedding"),
        )
        return cls(
            id=data["id"],
            chunk=chunk,
            embedding=data["embedding"],
            score=data.get("score", 0.0),
        )


@dataclass
class SearchResult:
    """Result of a vector similarity search."""
    entries: list[VectorEntry]
    query: str
    top_k: int
    search_time_ms: float


@dataclass
class SyncResult:
    """Statistics from a sync operation."""
    added: int = 0
    updated: int = 0
    deleted: int = 0
    unchanged: int = 0
    sync_time_ms: float = 0.0


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------

class VectorStore(ABC):
    """Abstract vector store interface."""

    @abstractmethod
    async def add(self, entries: list[VectorEntry]) -> None:
        """Add or replace entries in the store."""

    @abstractmethod
    async def search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
    ) -> SearchResult:
        """Return the top-k most similar entries to *query_embedding*."""

    @abstractmethod
    async def delete(self, ids: list[str]) -> None:
        """Remove entries by id."""

    @abstractmethod
    async def sync(self, source: list[VectorEntry]) -> SyncResult:
        """
        Sync the store so it exactly mirrors *source*.

        Adds new entries, updates changed entries, removes stale entries.
        """

    @abstractmethod
    async def count(self) -> int:
        """Return the number of stored entries."""


# ---------------------------------------------------------------------------
# Pure-Python helpers
# ---------------------------------------------------------------------------

def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two equal-length float lists."""
    if len(a) != len(b):
        raise ValueError(f"Vector length mismatch: {len(a)} vs {len(b)}")
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (math.sqrt(na) * math.sqrt(nb))


def _entry_fingerprint(entry: VectorEntry) -> str:
    """Stable hash of an entry's content + embedding for change detection."""
    payload = entry.chunk.content + json.dumps(entry.embedding, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


# ---------------------------------------------------------------------------
# InMemoryVectorStore
# ---------------------------------------------------------------------------

class InMemoryVectorStore(VectorStore):
    """
    Vector store backed by an in-memory dict, with optional JSONL persistence.

    Thread-safe for single-process async usage (protected by asyncio.Lock).
    """

    def __init__(self, persist_path: Path | str | None = None) -> None:
        """
        Args:
            persist_path: If provided, the store is loaded from / saved to this
                          JSONL file automatically.
        """
        self._store: dict[str, VectorEntry] = {}
        self._lock = asyncio.Lock()
        self._persist_path: Path | None = (
            Path(persist_path) if persist_path else None
        )

        if self._persist_path and self._persist_path.exists():
            self._load_sync()

    # ------------------------------------------------------------------
    # VectorStore interface
    # ------------------------------------------------------------------

    async def add(self, entries: list[VectorEntry]) -> None:
        """Add or overwrite entries.  Persists to disk if path configured."""
        async with self._lock:
            for entry in entries:
                self._store[entry.id] = entry
            if self._persist_path:
                self._save_sync()

    async def search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
    ) -> SearchResult:
        """Brute-force cosine similarity search over all stored entries."""
        t0 = time.monotonic()
        async with self._lock:
            scored: list[tuple[float, VectorEntry]] = []
            for entry in self._store.values():
                try:
                    sim = _cosine_similarity(query_embedding, entry.embedding)
                except ValueError:
                    sim = 0.0
                scored.append((sim, entry))

        # Sort descending by similarity
        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[:top_k]

        results = []
        for sim, entry in top:
            # Return copies with score set
            scored_entry = VectorEntry(
                id=entry.id,
                chunk=entry.chunk,
                embedding=entry.embedding,
                score=sim,
            )
            results.append(scored_entry)

        elapsed_ms = (time.monotonic() - t0) * 1000.0
        return SearchResult(
            entries=results,
            query="<embedding>",
            top_k=top_k,
            search_time_ms=elapsed_ms,
        )

    async def delete(self, ids: list[str]) -> None:
        """Delete entries by id.  Silently ignores missing ids."""
        async with self._lock:
            for eid in ids:
                self._store.pop(eid, None)
            if self._persist_path:
                self._save_sync()

    async def sync(self, source: list[VectorEntry]) -> SyncResult:
        """
        Make the store match *source* exactly.

        - Entries in *source* but not in store  → added
        - Entries in both but content changed   → updated
        - Entries in both and unchanged         → unchanged
        - Entries in store but not in *source*  → deleted
        """
        t0 = time.monotonic()
        result = SyncResult()

        source_ids = {e.id for e in source}
        source_fps = {e.id: _entry_fingerprint(e) for e in source}

        async with self._lock:
            # Determine deletes
            to_delete = [eid for eid in self._store if eid not in source_ids]
            for eid in to_delete:
                del self._store[eid]
                result.deleted += 1

            # Add / update
            for entry in source:
                existing = self._store.get(entry.id)
                if existing is None:
                    self._store[entry.id] = entry
                    result.added += 1
                else:
                    existing_fp = _entry_fingerprint(existing)
                    if existing_fp != source_fps[entry.id]:
                        self._store[entry.id] = entry
                        result.updated += 1
                    else:
                        result.unchanged += 1

            if self._persist_path:
                self._save_sync()

        result.sync_time_ms = (time.monotonic() - t0) * 1000.0
        return result

    async def count(self) -> int:
        """Return number of stored entries."""
        async with self._lock:
            return len(self._store)

    # ------------------------------------------------------------------
    # Persistence helpers (synchronous — called inside async lock)
    # ------------------------------------------------------------------

    def _save_sync(self) -> None:
        """Write all entries to JSONL file."""
        assert self._persist_path is not None
        self._persist_path.parent.mkdir(parents=True, exist_ok=True)
        with self._persist_path.open("w", encoding="utf-8") as fh:
            for entry in self._store.values():
                fh.write(json.dumps(entry.to_dict()) + "\n")

    def _load_sync(self) -> None:
        """Load entries from JSONL file."""
        assert self._persist_path is not None
        with self._persist_path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    entry = VectorEntry.from_dict(data)
                    self._store[entry.id] = entry
                except (json.JSONDecodeError, KeyError):
                    # Skip corrupt lines
                    pass

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    async def save(self, path: Path | str | None = None) -> None:
        """Explicitly save to *path* (or the configured persist_path)."""
        target = Path(path) if path else self._persist_path
        if target is None:
            raise ValueError("No persist path configured.")
        async with self._lock:
            self._persist_path = target
            self._save_sync()

    async def load(self, path: Path | str) -> None:
        """Load entries from *path*, merging into the current store."""
        target = Path(path)
        async with self._lock:
            self._persist_path = target
            self._load_sync()

    async def clear(self) -> None:
        """Remove all entries from memory (does not delete the disk file)."""
        async with self._lock:
            self._store.clear()


# ---------------------------------------------------------------------------
# EmbeddingGenerator
# ---------------------------------------------------------------------------

class EmbeddingGenerator:
    """
    Generate embeddings for lists of text strings.

    Providers:
    - ``"local"``: TF-IDF sparse vectors projected to 384 dimensions.
                   Pure Python, no external deps.
    - ``"openai"``: OpenAI text-embedding-ada-002 (requires ``openai`` package
                    and ``OPENAI_API_KEY`` env var).

    Usage::

        gen = EmbeddingGenerator()
        embeddings = await gen.generate(["hello world", "foo bar"])
    """

    DIMS = 384  # output dimensionality for local provider

    def __init__(self, batch_size: int = 32) -> None:
        self.batch_size = batch_size
        # Deterministic projection matrix seeded from a fixed value
        self._projection: list[list[float]] | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def generate(
        self,
        texts: list[str],
        provider: str = "local",
    ) -> list[list[float]]:
        """
        Generate embeddings for *texts*.

        Args:
            texts:    List of input strings.
            provider: ``"local"`` or ``"openai"``.

        Returns:
            List of float vectors, one per input text.
        """
        if not texts:
            return []

        if provider == "openai":
            return await self._generate_openai(texts)
        else:
            return await self._generate_local(texts)

    # ------------------------------------------------------------------
    # Local TF-IDF → projection provider
    # ------------------------------------------------------------------

    async def _generate_local(self, texts: list[str]) -> list[list[float]]:
        """TF-IDF sparse → dense projection, all pure Python."""
        results: list[list[float]] = []

        # Process in batches to keep memory bounded
        for batch_start in range(0, len(texts), self.batch_size):
            batch = texts[batch_start : batch_start + self.batch_size]
            token_lists = [self._tokenize(t) for t in batch]

            # Build IDF from this batch
            idf = self._build_idf(token_lists)
            vocab = sorted(idf.keys())  # stable order

            # Ensure projection matrix is sized for current vocab
            proj = self._get_projection(len(vocab))

            for tl in token_lists:
                sparse = self._tfidf_vector(tl, idf, vocab)
                dense = self._project(sparse, proj)
                dense = self._l2_normalize(dense)
                results.append(dense)

        return results

    def _get_projection(self, input_dim: int) -> list[list[float]]:
        """
        Return a deterministic random Gaussian projection matrix of shape
        (input_dim × DIMS).  Re-generated when input_dim grows.
        """
        if (
            self._projection is None
            or len(self._projection) != input_dim
        ):
            rng = random.Random(42)
            self._projection = [
                [rng.gauss(0, 1.0 / math.sqrt(self.DIMS)) for _ in range(self.DIMS)]
                for _ in range(input_dim)
            ]
        return self._projection

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        return re.findall(r"[a-z0-9]+", text.lower())

    @staticmethod
    def _build_idf(corpus: list[list[str]]) -> dict[str, float]:
        n = len(corpus) or 1
        df: dict[str, int] = {}
        for tokens in corpus:
            for t in set(tokens):
                df[t] = df.get(t, 0) + 1
        return {t: math.log((n + 1) / (freq + 1)) + 1.0 for t, freq in df.items()}

    @staticmethod
    def _tfidf_vector(
        tokens: list[str],
        idf: dict[str, float],
        vocab: list[str],
    ) -> list[float]:
        total = len(tokens) or 1
        tf: dict[str, float] = {}
        for t in tokens:
            tf[t] = tf.get(t, 0) + 1.0 / total
        return [tf.get(w, 0.0) * idf.get(w, 0.0) for w in vocab]

    @staticmethod
    def _project(sparse: list[float], proj: list[list[float]]) -> list[float]:
        """Multiply sparse (1 × input_dim) by proj (input_dim × DIMS)."""
        dims = len(proj[0]) if proj else EmbeddingGenerator.DIMS
        result = [0.0] * dims
        for i, val in enumerate(sparse):
            if val == 0.0:
                continue
            row = proj[i]
            for j in range(dims):
                result[j] += val * row[j]
        return result

    @staticmethod
    def _l2_normalize(vec: list[float]) -> list[float]:
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [x / norm for x in vec]

    # ------------------------------------------------------------------
    # OpenAI provider
    # ------------------------------------------------------------------

    async def _generate_openai(self, texts: list[str]) -> list[list[float]]:
        """
        Call OpenAI embeddings API.

        Requires:
        - ``pip install openai``
        - ``OPENAI_API_KEY`` environment variable set

        Falls back to local provider if openai is unavailable.
        """
        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            # Fall back silently
            return await self._generate_local(texts)

        try:
            import openai  # type: ignore[import]
        except ImportError:
            return await self._generate_local(texts)

        client = openai.AsyncOpenAI(api_key=api_key)
        results: list[list[float]] = []

        for batch_start in range(0, len(texts), self.batch_size):
            batch = texts[batch_start : batch_start + self.batch_size]
            response = await client.embeddings.create(
                model="text-embedding-ada-002",
                input=batch,
            )
            for item in response.data:
                results.append(item.embedding)

        return results
