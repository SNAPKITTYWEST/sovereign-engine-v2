"""
Layer 9: Retrieval Fabric
Part of SOVEREIGN PYTHON LLM ENGINE

RAG pipeline: SemanticChunker + InMemoryVectorStore + EmbeddingGenerator.
"""

from .parallel import ParallelRetriever
from .pipeline import RAGPipeline, PipelineConfig
from .chunker import SemanticChunker, ChunkConfig, ChunkStrategy
from .vector_store import InMemoryVectorStore, EmbeddingGenerator, VectorEntry, SearchResult

__all__ = [
    "ParallelRetriever",
    "RAGPipeline",
    "PipelineConfig",
    "SemanticChunker",
    "ChunkConfig",
    "ChunkStrategy",
    "InMemoryVectorStore",
    "EmbeddingGenerator",
    "VectorEntry",
    "SearchResult",
]
