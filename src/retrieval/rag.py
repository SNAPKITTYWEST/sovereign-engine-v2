"""
RAG Pipeline
Part of SOVEREIGN PYTHON LLM ENGINE

Complete Retrieval-Augmented Generation pipeline.
"""

from typing import AsyncIterator
from dataclasses import dataclass
from datetime import datetime

from ..models.entities import Message, MessageRole, RetrievalRequest, RetrievalResult
from ..core.protocols import Model, VectorStore
from ..tools.embeddings.encode import EmbeddingsTool
from .parallel import ParallelRetriever
from ..core.evidence import WORMLedger


@dataclass
class RAGConfig:
    """Configuration for RAG pipeline"""
    top_k: int = 5
    score_threshold: float = 0.7
    use_reranking: bool = True
    context_window: int = 8000  # Max tokens for context
    log_to_worm: bool = True


class RAGPipeline:
    """
    Complete RAG (Retrieval-Augmented Generation) pipeline.

    Steps:
    1. Embed query
    2. Retrieve top-K documents
    3. Optionally rerank
    4. Format context
    5. Generate answer with LLM
    """

    def __init__(
        self,
        model: Model,
        retriever: ParallelRetriever,
        embeddings: EmbeddingsTool,
        worm_ledger: WORMLedger | None = None,
        config: RAGConfig | None = None
    ):
        """
        Initialize RAG pipeline.

        Args:
            model: LLM for generation
            retriever: Parallel retriever
            embeddings: Embeddings tool
            worm_ledger: Optional WORM ledger
            config: Configuration
        """
        self.model = model
        self.retriever = retriever
        self.embeddings = embeddings
        self.worm_ledger = worm_ledger
        self.config = config or RAGConfig()

    async def query(
        self,
        question: str,
        filters: dict | None = None,
        stream: bool = False
    ) -> str | AsyncIterator[str]:
        """
        Query the RAG system.

        Args:
            question: User question
            filters: Optional metadata filters
            stream: Whether to stream response

        Returns:
            Answer string (or stream of chunks)
        """
        # 1. Retrieve relevant documents
        retrieval_request = RetrievalRequest(
            query=question,
            limit=self.config.top_k,
            score_threshold=self.config.score_threshold,
            filters=filters
        )

        results = await self.retriever.retrieve(retrieval_request)

        # 2. Format context
        context = self._format_context(results)

        # 3. Build prompt
        prompt = self._build_prompt(question, context)

        # 4. Generate answer
        messages = [
            {"role": "system", "content": "You are a helpful assistant that answers questions based on provided context."},
            {"role": "user", "content": prompt}
        ]

        if stream:
            # Streaming not implemented in base Model protocol yet
            # Return async generator wrapper
            answer = await self.model.generate(
                messages=messages,
                temperature=0.3,
                max_tokens=2048
            )

            # Log to WORM
            if self.worm_ledger and self.config.log_to_worm:
                await self._log_to_worm(question, results, answer)

            async def stream_wrapper():
                yield answer

            return stream_wrapper()
        else:
            answer = await self.model.generate(
                messages=messages,
                temperature=0.3,
                max_tokens=2048
            )

            # Log to WORM
            if self.worm_ledger and self.config.log_to_worm:
                await self._log_to_worm(question, results, answer)

            return answer

    async def query_with_citations(
        self,
        question: str,
        filters: dict | None = None
    ) -> tuple[str, list[RetrievalResult]]:
        """
        Query with source citations.

        Args:
            question: User question
            filters: Optional filters

        Returns:
            (answer, source_documents) tuple
        """
        # Retrieve
        retrieval_request = RetrievalRequest(
            query=question,
            limit=self.config.top_k,
            score_threshold=self.config.score_threshold,
            filters=filters
        )

        results = await self.retriever.retrieve(retrieval_request)

        # Format context
        context = self._format_context(results)

        # Build prompt with citation instruction
        prompt = f"""Answer the question based on the provided context.
Cite sources using [Source N] notation.

Context:
{context}

Question: {question}

Answer:"""

        # Generate
        messages = [
            {"role": "system", "content": "You are a helpful assistant that answers questions and cites sources."},
            {"role": "user", "content": prompt}
        ]

        answer = await self.model.generate(
            messages=messages,
            temperature=0.3,
            max_tokens=2048
        )

        # Log to WORM
        if self.worm_ledger and self.config.log_to_worm:
            await self._log_to_worm(question, results, answer)

        return answer, results

    def _format_context(self, results: list[RetrievalResult]) -> str:
        """
        Format retrieval results into context string.

        Args:
            results: Retrieved documents

        Returns:
            Formatted context
        """
        if not results:
            return "No relevant documents found."

        context_parts = []

        for i, result in enumerate(results, 1):
            source_info = ""
            if result.metadata:
                source_info = f" ({result.metadata.get('source', 'Unknown')})"

            context_parts.append(
                f"[Source {i}]{source_info}\n{result.content}\n"
            )

        return "\n".join(context_parts)

    def _build_prompt(self, question: str, context: str) -> str:
        """
        Build RAG prompt.

        Args:
            question: User question
            context: Retrieved context

        Returns:
            Formatted prompt
        """
        return f"""Answer the question based on the following context.
If the context doesn't contain enough information, say so.

Context:
{context}

Question: {question}

Answer:"""

    async def _log_to_worm(
        self,
        question: str,
        results: list[RetrievalResult],
        answer: str
    ) -> None:
        """Log RAG query to WORM ledger"""
        if not self.worm_ledger:
            return

        await self.worm_ledger.append({
            "event": "rag_query",
            "question": question,
            "retrieved_docs": len(results),
            "top_score": results[0].score if results else None,
            "answer_length": len(answer),
            "timestamp": datetime.utcnow().isoformat()
        })


class ConversationalRAG:
    """
    RAG with conversation history.

    Maintains context across multiple turns.
    """

    def __init__(
        self,
        rag_pipeline: RAGPipeline,
        max_history: int = 10
    ):
        """
        Initialize conversational RAG.

        Args:
            rag_pipeline: Base RAG pipeline
            max_history: Maximum conversation turns to keep
        """
        self.rag = rag_pipeline
        self.max_history = max_history
        self.conversation_history: list[Message] = []

    async def query(
        self,
        question: str,
        filters: dict | None = None
    ) -> str:
        """
        Query with conversation context.

        Args:
            question: User question
            filters: Optional filters

        Returns:
            Answer
        """
        # Add user message to history
        self.conversation_history.append(
            Message(
                role=MessageRole.USER,
                content=question,
                created_at=datetime.utcnow()
            )
        )

        # Retrieve using current question
        retrieval_request = RetrievalRequest(
            query=question,
            limit=self.rag.config.top_k,
            score_threshold=self.rag.config.score_threshold,
            filters=filters
        )

        results = await self.rag.retriever.retrieve(retrieval_request)

        # Format context
        context = self.rag._format_context(results)

        # Build messages with history
        messages = [
            {"role": "system", "content": "You are a helpful assistant. Use the provided context and conversation history to answer questions."}
        ]

        # Add conversation history (limited)
        history_messages = self.conversation_history[-(self.max_history * 2):]
        for msg in history_messages:
            messages.append({
                "role": msg.role.value,
                "content": msg.content
            })

        # Add current context
        messages.append({
            "role": "user",
            "content": f"""Context:
{context}

Question: {question}

Answer:"""
        })

        # Generate
        answer = await self.rag.model.generate(
            messages=messages,
            temperature=0.3,
            max_tokens=2048
        )

        # Add assistant message to history
        self.conversation_history.append(
            Message(
                role=MessageRole.ASSISTANT,
                content=answer,
                created_at=datetime.utcnow()
            )
        )

        return answer

    def clear_history(self) -> None:
        """Clear conversation history"""
        self.conversation_history.clear()
