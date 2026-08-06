"""
Sovereign LLM Engine — Unified Entry Point
Part of SOVEREIGN PYTHON LLM ENGINE

Wires all subsystems into a single SovereignEngine class:
  - PythonDaemon   (async TCP daemon + task dispatch)
  - Swarm          (parallel agent execution)
  - ToolRegistry   (tool definitions + risk gating)
  - ToolLookupRegistry (semantic tool search + checkout)
  - RAGPipeline    (chunker + vector store + embeddings)
  - RoutingPipeline (11-stage MoE router)
  - ShadowAgent    (optional non-blocking observer)

Typical usage::

    import asyncio
    from src.sovereign import SovereignEngine

    async def main():
        engine = SovereignEngine()
        await engine.start()

        result = await engine.route("write python code to sort a list", {})
        print(result.merged_output)

        await engine.ingest("The quick brown fox", {"source": "example"})
        hits = await engine.search("brown fox")

    asyncio.run(main())
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

# ── Daemon / Swarm ──────────────────────────────────────────────────────────
from .daemon import PythonDaemon, Swarm

# ── Tool subsystem ──────────────────────────────────────────────────────────
from .tools.registry import ToolRegistry
from .tools.loader import load_all_tools
from .tools.lookup import ToolLookupRegistry

# ── Retrieval subsystem ─────────────────────────────────────────────────────
from .retrieval.pipeline import RAGPipeline, PipelineConfig
from .retrieval.chunker import SemanticChunker, ChunkConfig, ChunkStrategy
from .retrieval.vector_store import InMemoryVectorStore, EmbeddingGenerator

# ── Routing (MoE) ───────────────────────────────────────────────────────────
from .routing import RoutingPipeline
from .routing.dispatch import DispatchResult

logger = logging.getLogger("sovereign.engine")


# ---------------------------------------------------------------------------
# Default expert stubs — replaced by real agents at runtime
# ---------------------------------------------------------------------------

async def _expert_code(input_text: str, context: dict) -> str:
    """Default code expert stub."""
    return f"[code_expert] processed: {input_text[:80]}"


async def _expert_query(input_text: str, context: dict) -> str:
    """Default query expert stub."""
    return f"[query_expert] answered: {input_text[:80]}"


async def _expert_analysis(input_text: str, context: dict) -> str:
    """Default analysis expert stub."""
    return f"[analysis_expert] analysed: {input_text[:80]}"


DEFAULT_EXPERTS: dict[str, Any] = {
    "code_expert":     _expert_code,
    "query_expert":    _expert_query,
    "analysis_expert": _expert_analysis,
}


# ---------------------------------------------------------------------------
# SovereignEngine
# ---------------------------------------------------------------------------

class SovereignEngine:
    """
    Unified entry point for the Sovereign LLM Engine.

    Attributes:
        tool_lookup:      ToolLookupRegistry — semantic tool search for supervisor agents.
        swarm:            Swarm              — parallel async agent execution.
        routing_pipeline: RoutingPipeline    — 11-stage sparse MoE router.
    """

    def __init__(
        self,
        *,
        daemon_host: str = "127.0.0.1",
        daemon_port: int = 19002,
        experts: dict[str, Any] | None = None,
        top_k_routing: int = 2,
        rag_config: PipelineConfig | None = None,
        swarm_concurrency: int = 8,
        swarm_timeout_ms: int = 30_000,
    ) -> None:
        """
        Initialise all subsystems (no I/O performed here).

        Args:
            daemon_host:      TCP host for the background daemon.
            daemon_port:      TCP port for the background daemon.
            experts:          Expert callables for the MoE router.
                              Defaults to three built-in stubs.
            top_k_routing:    How many experts the router activates per request.
            rag_config:       Optional custom RAGPipeline configuration.
            swarm_concurrency: Max concurrent tasks in swarm operations.
            swarm_timeout_ms:  Per-task timeout for swarm operations.
        """
        # ── Tool subsystem ───────────────────────────────────────────────
        self._registry = ToolRegistry()
        self.tool_lookup = ToolLookupRegistry(self._registry)

        # ── Daemon ───────────────────────────────────────────────────────
        self._daemon = PythonDaemon(host=daemon_host, port=daemon_port)

        # ── Swarm ────────────────────────────────────────────────────────
        self.swarm = Swarm(
            concurrency=swarm_concurrency,
            task_timeout=swarm_timeout_ms / 1000.0,  # convert ms → seconds
        )

        # ── RAG pipeline ─────────────────────────────────────────────────
        self._rag = RAGPipeline(
            chunker=SemanticChunker(),
            vector_store=InMemoryVectorStore(),
            embedding_gen=EmbeddingGenerator(),
            config=rag_config or PipelineConfig(),
        )

        # ── MoE routing pipeline ─────────────────────────────────────────
        _experts = experts if experts is not None else DEFAULT_EXPERTS
        self.routing_pipeline = RoutingPipeline(
            experts=_experts,
            top_k=top_k_routing,
        )

        self._started = False
        logger.info("SovereignEngine initialised (daemon=%s:%s)", daemon_host, daemon_port)

    # -----------------------------------------------------------------------
    # Lifecycle
    # -----------------------------------------------------------------------

    async def start(self) -> None:
        """
        Start all async subsystems.

        - Loads all tools into the registry
        - Starts the background TCP daemon as a non-blocking task
        """
        if self._started:
            logger.warning("SovereignEngine.start() called more than once — ignored")
            return

        # Load tools (synchronous — fast)
        n_tools = load_all_tools(self._registry)
        logger.info("Loaded %d tools into registry", n_tools)

        # Start daemon in background (non-blocking)
        self._daemon_task = asyncio.create_task(
            self._daemon.start(), name="sovereign-daemon"
        )
        logger.info("Daemon started (background task)")

        self._started = True

    # -----------------------------------------------------------------------
    # Routing
    # -----------------------------------------------------------------------

    async def route(self, input: str, context: dict) -> dict:
        """
        Full MoE routing pipeline: parse → symbolic → Jordan → Jacobian →
        constraints → sparse-activation → dispatch → merge.

        Args:
            input:   Natural-language instruction or query.
            context: Arbitrary key-value context passed to experts.

        Returns:
            dict with keys:
              "merged_output"  — combined expert output string
              "active_experts" — list of expert names that were activated
              "weights"        — per-expert routing weight dict
              "success_count"  — number of experts that succeeded
              "failed_experts" — list of expert names that failed
        """
        dispatch: DispatchResult = await self.routing_pipeline.route(input, context)
        return {
            "merged_output":  dispatch.merged_output,
            "active_experts": dispatch.routing_weights.active_experts,
            "weights":        dispatch.routing_weights.weights,
            "success_count":  dispatch.success_count,
            "failed_experts": dispatch.failed_experts,
        }

    # -----------------------------------------------------------------------
    # RAG helpers
    # -----------------------------------------------------------------------

    async def ingest(self, text: str, metadata: dict) -> int:
        """
        Chunk *text*, embed every chunk, and add to the vector store.

        Args:
            text:     Raw text to ingest.
            metadata: Arbitrary key-value pairs attached to every chunk.

        Returns:
            Number of chunks added.
        """
        return await self._rag.ingest(text, metadata)

    async def search(self, query: str) -> list:
        """
        RAG search: embed *query* and return the most similar chunks.

        Args:
            query: Natural-language search string.

        Returns:
            List of dicts with keys "content", "score", and "metadata".
        """
        # RAGPipeline.search returns list[Chunk] directly
        chunks = await self._rag.search(query, top_k=self._rag.config.top_k)
        return [
            {
                "content":  chunk.content,
                "score":    round(chunk.embedding[0] if chunk.embedding else 0.0, 6),
                "metadata": chunk.metadata,
            }
            for chunk in chunks
        ]

    # -----------------------------------------------------------------------
    # Convenience: recommend tools (delegates to tool_lookup)
    # -----------------------------------------------------------------------

    def recommend(self, capability_query: str, agent_id: str, top_k: int = 5) -> list:
        """
        Shortcut for tool_lookup.recommend() — semantic tool search.

        Args:
            capability_query: Free-text description of the needed capability.
            agent_id:         Identifier of the requesting agent.
            top_k:            Maximum number of tools to return.

        Returns:
            List of ToolDefinition objects ranked by relevance.
        """
        return self.tool_lookup.recommend(capability_query, agent_id, top_k=top_k)
