"""
Parallel Retrieval
Part of SOVEREIGN PYTHON LLM ENGINE

Retrieve from multiple sources in parallel and merge results.
"""

from typing import Any
from dataclasses import dataclass
import asyncio
from datetime import datetime

from ..models.entities import RetrievalSource, RetrievalRequest, RetrievalResult
from ..core.protocols import Retriever
from ..core.evidence import WORMLedger


@dataclass
class ParallelRetrieverConfig:
    """Configuration for parallel retriever"""
    max_concurrent: int = 5
    timeout_per_source: float = 10.0
    merge_strategy: str = "interleave"  # "interleave" or "score"
    log_to_worm: bool = True


class ParallelRetriever:
    """
    Parallel retrieval from multiple sources.

    Executes retrieval from all sources concurrently and merges results.
    """

    def __init__(
        self,
        retrievers: dict[RetrievalSource, Retriever],
        worm_ledger: WORMLedger | None = None,
        config: ParallelRetrieverConfig | None = None
    ):
        """
        Initialize parallel retriever.

        Args:
            retrievers: Map of source → retriever
            worm_ledger: Optional WORM ledger
            config: Configuration
        """
        self.retrievers = retrievers
        self.worm_ledger = worm_ledger
        self.config = config or ParallelRetrieverConfig()

        self.semaphore = asyncio.Semaphore(self.config.max_concurrent)

    async def retrieve(
        self,
        request: RetrievalRequest
    ) -> list[RetrievalResult]:
        """
        Retrieve from all sources in parallel.

        Args:
            request: Retrieval request

        Returns:
            Merged list of retrieval results
        """
        # Create retrieval tasks for each source
        tasks = []

        for source, retriever in self.retrievers.items():
            task = self._retrieve_from_source(
                source,
                retriever,
                request
            )
            tasks.append(task)

        # Execute in parallel
        results_lists = await asyncio.gather(*tasks, return_exceptions=True)

        # Flatten and filter errors
        all_results: list[RetrievalResult] = []
        for results in results_lists:
            if isinstance(results, Exception):
                # Log error but continue
                if self.worm_ledger and self.config.log_to_worm:
                    await self.worm_ledger.append({
                        "event": "parallel_retrieval_error",
                        "query": request.query,
                        "error": str(results),
                        "timestamp": datetime.utcnow().isoformat()
                    })
                continue

            all_results.extend(results)

        # Merge results
        merged = self._merge_results(all_results)

        # Apply limit
        if request.limit:
            merged = merged[:request.limit]

        # Log to WORM
        if self.worm_ledger and self.config.log_to_worm:
            await self.worm_ledger.append({
                "event": "parallel_retrieval_complete",
                "query": request.query,
                "sources": [s.value for s in self.retrievers.keys()],
                "results_count": len(merged),
                "timestamp": datetime.utcnow().isoformat()
            })

        return merged

    async def _retrieve_from_source(
        self,
        source: RetrievalSource,
        retriever: Retriever,
        request: RetrievalRequest
    ) -> list[RetrievalResult]:
        """
        Retrieve from single source with timeout and concurrency control.

        Args:
            source: Retrieval source
            retriever: Retriever instance
            request: Retrieval request

        Returns:
            List of results from this source
        """
        async with self.semaphore:
            try:
                # Execute retrieval with timeout
                results = await asyncio.wait_for(
                    retriever.retrieve(request),
                    timeout=self.config.timeout_per_source
                )

                # Tag results with source
                for result in results:
                    if not hasattr(result, 'source') or result.source is None:
                        result.source = source

                return results

            except asyncio.TimeoutError:
                # Log timeout
                if self.worm_ledger and self.config.log_to_worm:
                    await self.worm_ledger.append({
                        "event": "retrieval_timeout",
                        "source": source.value,
                        "query": request.query,
                        "timeout": self.config.timeout_per_source,
                        "timestamp": datetime.utcnow().isoformat()
                    })
                return []

            except Exception as e:
                # Re-raise to be caught by gather
                raise e

    def _merge_results(
        self,
        results: list[RetrievalResult]
    ) -> list[RetrievalResult]:
        """
        Merge results from multiple sources.

        Args:
            results: All results from all sources

        Returns:
            Merged and deduplicated results
        """
        if self.config.merge_strategy == "score":
            # Sort by score descending
            return sorted(results, key=lambda r: r.score or 0.0, reverse=True)

        elif self.config.merge_strategy == "interleave":
            # Interleave results from different sources
            by_source: dict[RetrievalSource, list[RetrievalResult]] = {}

            for result in results:
                source = result.source or RetrievalSource.VECTOR
                if source not in by_source:
                    by_source[source] = []
                by_source[source].append(result)

            # Interleave
            merged = []
            sources = list(by_source.keys())
            max_length = max(len(results) for results in by_source.values())

            for i in range(max_length):
                for source in sources:
                    if i < len(by_source[source]):
                        merged.append(by_source[source][i])

            return merged

        else:
            # Default: return as-is
            return results


class DeduplicatingRetriever:
    """
    Wrapper that deduplicates retrieval results.

    Useful for removing near-duplicate documents.
    """

    def __init__(
        self,
        base_retriever: ParallelRetriever,
        similarity_threshold: float = 0.95
    ):
        """
        Initialize deduplicating retriever.

        Args:
            base_retriever: Base retriever
            similarity_threshold: Threshold for considering docs as duplicates
        """
        self.base_retriever = base_retriever
        self.similarity_threshold = similarity_threshold

    async def retrieve(
        self,
        request: RetrievalRequest
    ) -> list[RetrievalResult]:
        """
        Retrieve and deduplicate.

        Args:
            request: Retrieval request

        Returns:
            Deduplicated results
        """
        results = await self.base_retriever.retrieve(request)

        # Deduplicate
        deduplicated = []
        seen_hashes = set()

        for result in results:
            # Hash content
            content_hash = hash(result.content)

            if content_hash not in seen_hashes:
                deduplicated.append(result)
                seen_hashes.add(content_hash)

        return deduplicated


class RerankingRetriever:
    """
    Wrapper that reranks retrieval results.

    Calls reranking model to improve relevance.
    """

    def __init__(
        self,
        base_retriever: ParallelRetriever,
        reranker: Any  # Will be rerank tool from tools.rerank
    ):
        """
        Initialize reranking retriever.

        Args:
            base_retriever: Base retriever
            reranker: Reranker instance
        """
        self.base_retriever = base_retriever
        self.reranker = reranker

    async def retrieve(
        self,
        request: RetrievalRequest
    ) -> list[RetrievalResult]:
        """
        Retrieve and rerank.

        Args:
            request: Retrieval request

        Returns:
            Reranked results
        """
        # Retrieve
        results = await self.base_retriever.retrieve(request)

        if not results:
            return results

        # Extract documents
        documents = [r.content for r in results]

        # Rerank
        reranked = await self.reranker.rerank(
            query=request.query,
            documents=documents,
            top_k=len(documents)
        )

        # Rebuild results with new scores
        reranked_results = []
        for (doc, score) in reranked:
            # Find original result
            original = next((r for r in results if r.content == doc), None)
            if original:
                # Update score
                original.score = score
                reranked_results.append(original)

        return reranked_results
