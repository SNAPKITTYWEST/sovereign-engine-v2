"""
RAG Pipeline
Part of SOVEREIGN PYTHON LLM ENGINE

Wires SemanticChunker + VectorStore + EmbeddingGenerator into a complete
ingest → search → format pipeline.

Pure stdlib; no external deps beyond chunker.py and vector_store.py.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .chunker import Chunk, ChunkConfig, ChunkStrategy, SemanticChunker
from .vector_store import (
    EmbeddingGenerator,
    InMemoryVectorStore,
    SearchResult,
    VectorEntry,
    VectorStore,
)


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class PipelineConfig:
    """Top-level configuration for the RAG pipeline."""
    chunk_config: ChunkConfig = field(
        default_factory=lambda: ChunkConfig(
            strategy=ChunkStrategy.FIXED_SIZE,
            chunk_size=512,
            chunk_overlap=64,
            min_chunk_size=5,
        )
    )
    embedding_provider: str = "local"   # "local" | "openai"
    top_k: int = 5
    score_threshold: float = 0.0        # Minimum similarity score to include
    context_separator: str = "\n\n---\n\n"
    include_metadata_in_context: bool = True


# ---------------------------------------------------------------------------
# RAGPipeline
# ---------------------------------------------------------------------------

class RAGPipeline:
    """
    Full RAG pipeline: ingest documents, search by natural-language query,
    and format retrieved chunks as a context string for an LLM.

    Typical usage::

        chunker   = SemanticChunker()
        store     = InMemoryVectorStore(persist_path="./index.jsonl")
        emb_gen   = EmbeddingGenerator()
        pipeline  = RAGPipeline(chunker, store, emb_gen)

        # Ingest
        n = await pipeline.ingest(text, metadata={"source": "manual.pdf"})

        # Search
        chunks = await pipeline.search("How does it work?", top_k=5)

        # Format for LLM prompt
        context = await pipeline.search_and_format("How does it work?", top_k=5)
    """

    def __init__(
        self,
        chunker: SemanticChunker | None = None,
        vector_store: VectorStore | None = None,
        embedding_gen: EmbeddingGenerator | None = None,
        config: PipelineConfig | None = None,
    ) -> None:
        """
        Args:
            chunker:       Semantic chunker instance (defaults to SemanticChunker()).
            vector_store:  Vector store instance (defaults to InMemoryVectorStore()).
            embedding_gen: Embedding generator (defaults to EmbeddingGenerator()).
            config:        Pipeline configuration.
        """
        self.chunker = chunker or SemanticChunker()
        self.vector_store = vector_store or InMemoryVectorStore()
        self.embedding_gen = embedding_gen or EmbeddingGenerator()
        self.config = config or PipelineConfig()

    # ------------------------------------------------------------------
    # Ingest
    # ------------------------------------------------------------------

    async def ingest(
        self,
        text: str,
        metadata: dict | None = None,
    ) -> int:
        """
        Chunk *text*, embed every chunk, and add them to the vector store.

        Args:
            text:     Raw text to ingest.
            metadata: Key-value pairs attached to every produced chunk
                      (e.g. ``{"source": "manual.pdf", "page": 3}``).

        Returns:
            Number of chunks added to the vector store.
        """
        metadata = metadata or {}
        chunks = self.chunker.chunk(text, self.config.chunk_config, metadata)
        if not chunks:
            return 0

        entries = await self._chunks_to_entries(chunks)
        await self.vector_store.add(entries)
        return len(entries)

    async def ingest_file(
        self,
        path: Path | str,
        metadata: dict | None = None,
    ) -> int:
        """
        Read a file from disk and ingest its contents.

        Args:
            path:     Path to a plain-text file.
            metadata: Additional metadata (``source`` and ``filename`` are
                      set automatically from *path*).

        Returns:
            Number of chunks added to the vector store.
        """
        path = Path(path)
        base_meta = {
            "source": str(path),
            "filename": path.name,
        }
        if metadata:
            base_meta.update(metadata)

        chunks = self.chunker.chunk_file(path, self.config.chunk_config)
        # Overwrite/merge metadata
        for chunk in chunks:
            chunk.metadata = {**base_meta, **chunk.metadata}

        if not chunks:
            return 0

        entries = await self._chunks_to_entries(chunks)
        await self.vector_store.add(entries)
        return len(entries)

    async def ingest_documents(
        self,
        docs: list[dict],
    ) -> int:
        """
        Ingest a list of document dicts.

        Each dict must have a ``"text"`` key; all other keys become metadata.

        Args:
            docs: List of document dicts.

        Returns:
            Total number of chunks added across all documents.
        """
        chunks = self.chunker.chunk_documents(docs, self.config.chunk_config)
        if not chunks:
            return 0

        entries = await self._chunks_to_entries(chunks)
        await self.vector_store.add(entries)
        return len(entries)

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    async def search(
        self,
        query: str,
        top_k: int | None = None,
    ) -> list[Chunk]:
        """
        Embed *query* and return the top-k most relevant chunks.

        Args:
            query: Natural-language search query.
            top_k: Number of results (defaults to ``config.top_k``).

        Returns:
            List of Chunk objects, most relevant first.
        """
        k = top_k if top_k is not None else self.config.top_k
        query_embedding = await self._embed_query(query)

        result: SearchResult = await self.vector_store.search(query_embedding, top_k=k)

        chunks: list[Chunk] = []
        for entry in result.entries:
            if entry.score >= self.config.score_threshold:
                # Attach the retrieval score to chunk metadata for transparency
                chunk = entry.chunk
                chunk.metadata["_score"] = round(entry.score, 4)
                chunks.append(chunk)

        return chunks

    async def search_and_format(
        self,
        query: str,
        top_k: int | None = None,
    ) -> str:
        """
        Search for relevant chunks and format them as a ready-to-use context string.

        The formatted string is suitable for insertion into an LLM prompt.

        Args:
            query: Natural-language search query.
            top_k: Number of results (defaults to ``config.top_k``).

        Returns:
            Formatted context string.
        """
        chunks = await self.search(query, top_k=top_k)
        if not chunks:
            return "No relevant context found."

        return self._format_chunks(chunks)

    # ------------------------------------------------------------------
    # Sync / management helpers
    # ------------------------------------------------------------------

    async def rebuild_index(
        self,
        docs: list[dict],
    ) -> int:
        """
        Clear the vector store and re-ingest all *docs* from scratch.

        Useful for a full re-index after content changes.

        Returns:
            Total chunk count after rebuild.
        """
        if isinstance(self.vector_store, InMemoryVectorStore):
            await self.vector_store.clear()

        return await self.ingest_documents(docs)

    async def chunk_count(self) -> int:
        """Return total number of chunks in the vector store."""
        return await self.vector_store.count()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _embed_query(self, query: str) -> list[float]:
        """Embed a single query string."""
        vectors = await self.embedding_gen.generate(
            [query],
            provider=self.config.embedding_provider,
        )
        if not vectors:
            raise RuntimeError("Embedding generator returned empty result for query.")
        return vectors[0]

    async def _chunks_to_entries(
        self,
        chunks: list[Chunk],
    ) -> list[VectorEntry]:
        """Embed all chunks and wrap them in VectorEntry objects."""
        texts = [chunk.content for chunk in chunks]
        embeddings = await self.embedding_gen.generate(
            texts,
            provider=self.config.embedding_provider,
        )

        entries: list[VectorEntry] = []
        for chunk, embedding in zip(chunks, embeddings):
            entry = VectorEntry(
                id=chunk.id or str(uuid.uuid4()),
                chunk=chunk,
                embedding=embedding,
            )
            entries.append(entry)
        return entries

    def _format_chunks(self, chunks: list[Chunk]) -> str:
        """
        Format a list of chunks into a human/LLM-readable context block.

        Each chunk is numbered and optionally annotated with source metadata.
        """
        parts: list[str] = []

        for i, chunk in enumerate(chunks, start=1):
            header_parts = [f"[{i}]"]

            if self.config.include_metadata_in_context and chunk.metadata:
                # Only include human-useful fields
                useful_keys = ("source", "filename", "page", "section", "title")
                meta_items = [
                    f"{k}={chunk.metadata[k]}"
                    for k in useful_keys
                    if k in chunk.metadata
                ]
                if meta_items:
                    header_parts.append("(" + ", ".join(meta_items) + ")")

            score = chunk.metadata.get("_score")
            if score is not None:
                header_parts.append(f"score={score}")

            header = " ".join(header_parts)
            parts.append(f"{header}\n{chunk.content}")

        return self.config.context_separator.join(parts)


# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------

def create_pipeline(
    persist_path: str | Path | None = None,
    strategy: str = "recursive",
    chunk_size: int = 512,
    chunk_overlap: int = 64,
    embedding_provider: str = "local",
    top_k: int = 5,
) -> RAGPipeline:
    """
    Convenience factory for the most common pipeline configuration.

    Args:
        persist_path:        JSONL file path for vector store persistence.
        strategy:            Chunking strategy name (e.g. ``"recursive"``).
        chunk_size:          Target chunk size in tokens.
        chunk_overlap:       Overlap between consecutive chunks in tokens.
        embedding_provider:  ``"local"`` or ``"openai"``.
        top_k:               Default number of search results.

    Returns:
        Fully configured :class:`RAGPipeline` ready for use.
    """
    from .chunker import ChunkStrategy as CS

    strategy_map = {
        "fixed_size":     CS.FIXED_SIZE,
        "sentence":       CS.SENTENCE,
        "paragraph":      CS.PARAGRAPH,
        "semantic":       CS.SEMANTIC,
        "sliding_window": CS.SLIDING_WINDOW,
        "recursive":      CS.RECURSIVE,
    }

    chunk_strategy = strategy_map.get(strategy, CS.RECURSIVE)

    chunk_cfg = ChunkConfig(
        strategy=chunk_strategy,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )

    pipeline_cfg = PipelineConfig(
        chunk_config=chunk_cfg,
        embedding_provider=embedding_provider,
        top_k=top_k,
    )

    store: VectorStore = InMemoryVectorStore(persist_path=persist_path)

    return RAGPipeline(
        chunker=SemanticChunker(),
        vector_store=store,
        embedding_gen=EmbeddingGenerator(),
        config=pipeline_cfg,
    )
