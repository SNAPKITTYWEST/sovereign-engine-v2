"""
Local Embeddings Provider (sentence-transformers)
Part of SOVEREIGN PYTHON LLM ENGINE
"""

import numpy as np


class LocalEmbeddings:
    """
    Local embedding model using sentence-transformers.
    """

    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        """
        Initialize local embeddings.

        Args:
            model_name: Hugging Face model name
        """
        self.model_name = model_name
        self._model = None

    def _load_model(self):
        """Lazy load model"""
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name)

    async def encode(self, text: str, model: str | None = None) -> np.ndarray:
        """
        Encode single text to embedding.

        Args:
            text: Input text
            model: Model name (ignored for local, uses model_name from init)

        Returns:
            Embedding vector
        """
        import asyncio

        self._load_model()

        # Run in thread pool (sentence-transformers is sync)
        embedding = await asyncio.to_thread(
            self._model.encode,
            text,
            convert_to_numpy=True
        )

        return embedding

    async def encode_batch(
        self,
        texts: list[str],
        model: str | None = None
    ) -> list[np.ndarray]:
        """
        Encode multiple texts to embeddings.

        Args:
            texts: List of input texts
            model: Model name (ignored)

        Returns:
            List of embedding vectors
        """
        import asyncio

        self._load_model()

        # Batch encode
        embeddings = await asyncio.to_thread(
            self._model.encode,
            texts,
            convert_to_numpy=True,
            show_progress_bar=False
        )

        return [emb for emb in embeddings]
