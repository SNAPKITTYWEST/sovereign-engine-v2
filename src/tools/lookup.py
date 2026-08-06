"""
On-Demand Tool Lookup System for Supervisor Agents
Part of SOVEREIGN PYTHON LLM ENGINE

Features:
- Semantic (TF-IDF style keyword) search over tool title, description, tags
- Per-session tool checkout / checkin tracking
- Smart recommendation with risk-class gating
- Popularity metrics across all agents
- Full catalog export for UI display
"""

from __future__ import annotations

import math
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .registry import ApprovalPolicy, RiskClass, ToolDefinition, ToolRegistry


# ==========================================
# Data-classes
# ==========================================

@dataclass
class ToolQuery:
    """
    Natural-language capability query issued by a supervisor agent.

    Attributes:
        query: Free-text description of the needed capability.
        agent_id: Identifier of the requesting agent.
        namespace_filter: Restrict results to these namespaces (None = all).
        risk_max: Exclude tools whose risk_class exceeds this value (None = all).
        top_k: Maximum number of results to return.
    """
    query: str
    agent_id: str
    namespace_filter: list[str] | None = None
    risk_max: RiskClass | None = None
    top_k: int = 5


@dataclass
class ToolCheckout:
    """
    Record that an agent has checked out a specific tool for use.

    Attributes:
        agent_id: The agent that checked out the tool.
        tool_id: The tool that was checked out.
        checked_out_at: ISO-8601 timestamp of first checkout.
        use_count: How many times the agent has invoked the tool.
        last_used: ISO-8601 timestamp of most recent use (None if unused).
    """
    agent_id: str
    tool_id: str
    checked_out_at: str
    use_count: int = 0
    last_used: str | None = None

    def record_use(self) -> None:
        """Increment use counter and update last_used timestamp."""
        self.use_count += 1
        self.last_used = _utcnow()


@dataclass
class ToolLookupResult:
    """
    Result returned from a tool search query.

    Attributes:
        tools: Ranked list of matching ToolDefinitions (best first).
        scores: Map of tool_id -> normalised relevance score [0.0, 1.0].
        query: The original query that produced this result.
        from_cache: True if the result was served from the session cache.
    """
    tools: list[ToolDefinition]
    scores: dict[str, float]
    query: ToolQuery
    from_cache: bool = False


# ==========================================
# Internal helpers
# ==========================================

def _utcnow() -> str:
    """Return current UTC time as ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _tokenize(text: str) -> list[str]:
    """
    Tokenize text into lowercase words.

    Splits on whitespace and punctuation, discards empty tokens.
    """
    return [t for t in re.split(r"[^a-z0-9_]+", text.lower()) if t]


def _tool_namespace(tool: ToolDefinition) -> str:
    """Extract namespace (first segment) from a tool_id like 'ns.name'."""
    return tool.tool_id.split(".")[0]


# ==========================================
# TF-IDF style keyword scorer
# ==========================================

def keyword_score(
    tool: ToolDefinition,
    query_terms: list[str],
) -> float:
    """
    Compute a weighted keyword-match score for a single tool.

    Scoring weights:
        - Title match: 3 points per term occurrence
        - Description match: 2 points per term occurrence
        - Tag match: 1 point per term occurrence

    Returns:
        Raw (un-normalised) score as a float.  Zero means no match.
    """
    if not query_terms:
        return 0.0

    title_tokens = _tokenize(tool.title)
    desc_tokens = _tokenize(tool.description)
    tag_tokens: list[str] = []
    for tag in tool.tags:
        tag_tokens.extend(_tokenize(tag))

    score = 0.0
    for term in query_terms:
        score += title_tokens.count(term) * 3.0
        score += desc_tokens.count(term) * 2.0
        score += tag_tokens.count(term) * 1.0

    return score


def _rank_tools(
    tools: list[ToolDefinition],
    query_terms: list[str],
    risk_max: RiskClass | None,
    namespace_filter: list[str] | None,
    top_k: int,
) -> tuple[list[ToolDefinition], dict[str, float]]:
    """
    Score, filter, sort and truncate a list of tools.

    Args:
        tools: Candidate pool.
        query_terms: Tokenised query.
        risk_max: Hard ceiling on risk class (inclusive); None = no limit.
        namespace_filter: Restrict to these namespaces; None = all.
        top_k: Maximum results to return.

    Returns:
        (ranked_tools, scores_dict) where scores are normalised to [0, 1].
    """
    raw: dict[str, float] = {}

    for tool in tools:
        # Namespace gate
        if namespace_filter is not None:
            ns = _tool_namespace(tool)
            if ns not in namespace_filter:
                continue

        # Risk gate
        if risk_max is not None and tool.risk_class > risk_max:
            continue

        raw[tool.tool_id] = keyword_score(tool, query_terms)

    # Drop tools with zero relevance when there are query terms
    if query_terms:
        raw = {tid: s for tid, s in raw.items() if s > 0.0}

    if not raw:
        return [], {}

    # Normalise
    max_score = max(raw.values())
    if max_score == 0.0:
        normalised = {tid: 0.0 for tid in raw}
    else:
        normalised = {tid: s / max_score for tid, s in raw.items()}

    # Sort descending by score then alphabetically for determinism
    sorted_ids = sorted(normalised, key=lambda tid: (-normalised[tid], tid))
    top_ids = sorted_ids[:top_k]

    tool_map = {t.tool_id: t for t in tools}
    ranked = [tool_map[tid] for tid in top_ids if tid in tool_map]
    scores = {tid: normalised[tid] for tid in top_ids}

    return ranked, scores


# ==========================================
# Cache
# ==========================================

@dataclass
class _CacheEntry:
    result: ToolLookupResult
    created_at: float  # monotonic seconds


class _SessionCache:
    """
    Per-agent LRU-ish cache for search results.

    Stores the last ``capacity`` distinct query strings per agent.
    Entries older than ``ttl_seconds`` are treated as stale.
    """

    def __init__(self, capacity: int = 32, ttl_seconds: float = 300.0) -> None:
        self._capacity = capacity
        self._ttl = ttl_seconds
        # agent_id -> {cache_key -> _CacheEntry}
        self._store: dict[str, dict[str, _CacheEntry]] = defaultdict(dict)

    @staticmethod
    def _key(query: ToolQuery) -> str:
        ns = ",".join(sorted(query.namespace_filter)) if query.namespace_filter else ""
        risk = str(int(query.risk_max)) if query.risk_max is not None else ""
        return f"{query.query}|{ns}|{risk}|{query.top_k}"

    def get(self, query: ToolQuery) -> ToolLookupResult | None:
        import time
        bucket = self._store[query.agent_id]
        key = self._key(query)
        entry = bucket.get(key)
        if entry is None:
            return None
        if time.monotonic() - entry.created_at > self._ttl:
            del bucket[key]
            return None
        return entry.result

    def put(self, query: ToolQuery, result: ToolLookupResult) -> None:
        import time
        bucket = self._store[query.agent_id]
        # Evict oldest if at capacity
        if len(bucket) >= self._capacity:
            oldest_key = next(iter(bucket))
            del bucket[oldest_key]
        key = self._key(query)
        bucket[key] = _CacheEntry(result=result, created_at=time.monotonic())

    def invalidate_agent(self, agent_id: str) -> None:
        self._store.pop(agent_id, None)


# ==========================================
# ToolLookupRegistry
# ==========================================

class ToolLookupRegistry:
    """
    On-demand tool lookup and checkout manager for supervisor agents.

    Wraps a ToolRegistry and adds:
    - Keyword-scored search with namespace/risk filtering
    - Per-agent checkout / checkin session tracking
    - Smart recommendations
    - Popularity counters
    - Full catalog export
    """

    def __init__(
        self,
        registry: ToolRegistry,
        cache_capacity: int = 32,
        cache_ttl_seconds: float = 300.0,
    ) -> None:
        """
        Initialise the lookup registry.

        Args:
            registry: Underlying ToolRegistry to query.
            cache_capacity: Maximum cached queries per agent.
            cache_ttl_seconds: Cache entry lifetime in seconds.
        """
        self._registry = registry
        self._cache = _SessionCache(
            capacity=cache_capacity,
            ttl_seconds=cache_ttl_seconds,
        )

        # agent_id -> {tool_id -> ToolCheckout}
        self._checkouts: dict[str, dict[str, ToolCheckout]] = defaultdict(dict)

        # tool_id -> total checkout count (across all agents, all time)
        self._global_checkout_counts: dict[str, int] = defaultdict(int)

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(self, query: ToolQuery) -> ToolLookupResult:
        """
        Search for tools matching a natural-language capability description.

        Results are scored using weighted keyword matching:
            title ×3, description ×2, tags ×1
        Scores are normalised to [0.0, 1.0].  Results are filtered by
        namespace and risk class when specified on the query.

        Args:
            query: ToolQuery describing the needed capability.

        Returns:
            ToolLookupResult with ranked tools and per-tool scores.
        """
        # Cache hit
        cached = self._cache.get(query)
        if cached is not None:
            # Mark as served from cache
            cached_result = ToolLookupResult(
                tools=cached.tools,
                scores=cached.scores,
                query=query,
                from_cache=True,
            )
            return cached_result

        all_tools = self._registry.list_all()
        query_terms = _tokenize(query.query)

        ranked, scores = _rank_tools(
            tools=all_tools,
            query_terms=query_terms,
            risk_max=query.risk_max,
            namespace_filter=query.namespace_filter,
            top_k=query.top_k,
        )

        result = ToolLookupResult(
            tools=ranked,
            scores=scores,
            query=query,
            from_cache=False,
        )

        self._cache.put(query, result)
        return result

    # ------------------------------------------------------------------
    # Checkout / checkin
    # ------------------------------------------------------------------

    def checkout(self, agent_id: str, tool_id: str) -> ToolCheckout:
        """
        Mark a tool as checked-out by an agent.

        If the agent already holds a checkout for the tool, the existing
        record is returned (idempotent).

        Args:
            agent_id: Identifier of the requesting agent.
            tool_id: Tool to check out.

        Returns:
            ToolCheckout record.

        Raises:
            KeyError: If tool_id is not registered.
        """
        tool = self._registry.get(tool_id)
        if tool is None:
            raise KeyError(f"Tool not registered: {tool_id!r}")

        agent_checkouts = self._checkouts[agent_id]

        if tool_id in agent_checkouts:
            return agent_checkouts[tool_id]

        record = ToolCheckout(
            agent_id=agent_id,
            tool_id=tool_id,
            checked_out_at=_utcnow(),
        )
        agent_checkouts[tool_id] = record
        self._global_checkout_counts[tool_id] += 1
        return record

    def checkin(self, agent_id: str, tool_id: str) -> None:
        """
        Return a tool checkout (remove from agent's active session).

        No-op if the agent does not hold a checkout for the tool.

        Args:
            agent_id: Identifier of the returning agent.
            tool_id: Tool to check in.
        """
        agent_checkouts = self._checkouts.get(agent_id, {})
        agent_checkouts.pop(tool_id, None)

    def record_use(self, agent_id: str, tool_id: str) -> None:
        """
        Record that an agent used a checked-out tool.

        Increments use_count and updates last_used on the checkout record.
        Auto-checks-out the tool if the agent does not have an active record.

        Args:
            agent_id: Identifier of the using agent.
            tool_id: Tool that was used.
        """
        if agent_id not in self._checkouts or tool_id not in self._checkouts[agent_id]:
            self.checkout(agent_id, tool_id)

        self._checkouts[agent_id][tool_id].record_use()

    # ------------------------------------------------------------------
    # Agent tool queries
    # ------------------------------------------------------------------

    def get_agent_tools(self, agent_id: str) -> list[ToolDefinition]:
        """
        Return all tools currently checked out by an agent.

        Args:
            agent_id: Identifier of the agent.

        Returns:
            List of ToolDefinitions; empty list if none checked out.
        """
        agent_checkouts = self._checkouts.get(agent_id, {})
        result: list[ToolDefinition] = []
        for tool_id in agent_checkouts:
            tool = self._registry.get(tool_id)
            if tool is not None:
                result.append(tool)
        return result

    def get_agent_checkouts(self, agent_id: str) -> list[ToolCheckout]:
        """
        Return all ToolCheckout records for an agent.

        Args:
            agent_id: Identifier of the agent.

        Returns:
            List of ToolCheckout objects.
        """
        return list(self._checkouts.get(agent_id, {}).values())

    def release_agent(self, agent_id: str) -> None:
        """
        Check in all tools held by an agent (end-of-session cleanup).

        Args:
            agent_id: Identifier of the agent.
        """
        self._checkouts.pop(agent_id, None)
        self._cache.invalidate_agent(agent_id)

    # ------------------------------------------------------------------
    # Recommendations
    # ------------------------------------------------------------------

    def recommend(
        self,
        task_description: str,
        agent_id: str,
        top_k: int = 5,
    ) -> list[ToolDefinition]:
        """
        Recommend tools for a task, applying agent-context risk gating.

        Strategy:
        1. Score all tools by keyword match against task_description.
        2. Boost scores of tools already checked out by the agent (×1.25).
        3. Penalise NEVER-approval tools (score set to 0).
        4. Return top_k by combined score.

        Args:
            task_description: Natural-language description of the task.
            agent_id: Requesting agent (used for session-aware boosting).
            top_k: Maximum recommendations to return.

        Returns:
            Ranked list of ToolDefinitions.
        """
        query_terms = _tokenize(task_description)
        all_tools = self._registry.list_all()
        agent_tool_ids = {t.tool_id for t in self.get_agent_tools(agent_id)}

        raw: dict[str, float] = {}
        for tool in all_tools:
            # Disabled tools are never recommended
            if tool.approval_policy == ApprovalPolicy.NEVER:
                continue

            score = keyword_score(tool, query_terms)

            # Familiarity boost: agent already knows this tool
            if tool.tool_id in agent_tool_ids:
                score *= 1.25

            raw[tool.tool_id] = score

        # Filter zero-score tools when query has terms
        if query_terms:
            raw = {tid: s for tid, s in raw.items() if s > 0.0}

        if not raw:
            return []

        max_score = max(raw.values())
        if max_score == 0.0:
            return []

        sorted_ids = sorted(raw, key=lambda tid: (-raw[tid], tid))[:top_k]
        tool_map = {t.tool_id: t for t in all_tools}
        return [tool_map[tid] for tid in sorted_ids if tid in tool_map]

    # ------------------------------------------------------------------
    # Popularity
    # ------------------------------------------------------------------

    def get_popular(self, top_n: int = 10) -> list[tuple[str, int]]:
        """
        Return the most-checked-out tools across all agents.

        Args:
            top_n: How many entries to return.

        Returns:
            List of (tool_id, checkout_count) sorted descending by count.
        """
        sorted_items = sorted(
            self._global_checkout_counts.items(),
            key=lambda kv: (-kv[1], kv[0]),
        )
        return sorted_items[:top_n]

    # ------------------------------------------------------------------
    # Catalog export
    # ------------------------------------------------------------------

    def export_catalog(self) -> dict[str, Any]:
        """
        Export the full tool catalog for UI display.

        Includes tool definitions, registry statistics, popularity data
        and active checkout summary.

        Returns:
            Dictionary suitable for JSON serialisation.
        """
        base_catalog = self._registry.export_catalog()

        # Active checkouts summary
        active: list[dict[str, Any]] = []
        for agent_id, checkouts in self._checkouts.items():
            for co in checkouts.values():
                active.append({
                    "agent_id": agent_id,
                    "tool_id": co.tool_id,
                    "checked_out_at": co.checked_out_at,
                    "use_count": co.use_count,
                    "last_used": co.last_used,
                })

        popular = [
            {"tool_id": tid, "checkout_count": cnt}
            for tid, cnt in self.get_popular()
        ]

        base_catalog["active_checkouts"] = active
        base_catalog["popular_tools"] = popular
        base_catalog["checkout_stats"] = {
            "total_active": sum(
                len(v) for v in self._checkouts.values()
            ),
            "total_agents_with_checkouts": len(
                [a for a, v in self._checkouts.items() if v]
            ),
        }
        return base_catalog
