"""
Semantic Chunker
Part of SOVEREIGN PYTHON LLM ENGINE

Multiple chunking strategies: fixed_size, sentence, paragraph, semantic,
sliding_window, recursive (markdown-aware).

Pure stdlib — no numpy, no third-party deps.
"""

from __future__ import annotations

import math
import re
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Iterator


# ---------------------------------------------------------------------------
# Enums & dataclasses
# ---------------------------------------------------------------------------

class ChunkStrategy(Enum):
    FIXED_SIZE = "fixed_size"
    SENTENCE = "sentence"
    PARAGRAPH = "paragraph"
    SEMANTIC = "semantic"
    SLIDING_WINDOW = "sliding_window"
    RECURSIVE = "recursive"


@dataclass
class Chunk:
    """A single chunk of text with positional and token metadata."""
    id: str
    content: str
    start_char: int
    end_char: int
    metadata: dict = field(default_factory=dict)
    token_count: int = 0
    embedding: list[float] | None = None

    def __post_init__(self) -> None:
        if not self.id:
            self.id = str(uuid.uuid4())


@dataclass
class ChunkConfig:
    """Configuration for a chunking run."""
    strategy: ChunkStrategy = ChunkStrategy.FIXED_SIZE
    chunk_size: int = 512        # tokens
    chunk_overlap: int = 64      # tokens
    min_chunk_size: int = 50     # tokens; smaller chunks are dropped
    separator: str = "\n\n"


# ---------------------------------------------------------------------------
# TF-IDF helpers (pure stdlib)
# ---------------------------------------------------------------------------

def _tokenize(text: str) -> list[str]:
    """Lower-case word tokenization."""
    return re.findall(r"[a-z0-9]+", text.lower())


def _tf_idf_vector(
    tokens: list[str],
    idf: dict[str, float],
    vocab: list[str],
) -> list[float]:
    """Compute a normalised TF-IDF vector for *tokens* over *vocab*."""
    tf: dict[str, float] = {}
    total = len(tokens) or 1
    for t in tokens:
        tf[t] = tf.get(t, 0) + 1
    for t in tf:
        tf[t] /= total

    vec = [tf.get(w, 0.0) * idf.get(w, 0.0) for w in vocab]

    # L2-normalise
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]


def _cosine(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two equal-length vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(x * x for x in b)) or 1.0
    return dot / (na * nb)


def _build_idf(corpus: list[list[str]]) -> dict[str, float]:
    """Compute IDF dict from a list of token lists."""
    n = len(corpus) or 1
    df: dict[str, int] = {}
    for tokens in corpus:
        for t in set(tokens):
            df[t] = df.get(t, 0) + 1
    return {t: math.log((n + 1) / (freq + 1)) + 1.0 for t, freq in df.items()}


# ---------------------------------------------------------------------------
# Sentence splitting helpers
# ---------------------------------------------------------------------------

# Matches sentence-ending punctuation followed by whitespace or end-of-string.
_SENTENCE_RE = re.compile(r'(?<=[.!?])\s+')

def _split_sentences(text: str) -> list[str]:
    """Split text on sentence boundaries, keeping the delimiter."""
    parts = _SENTENCE_RE.split(text.strip())
    # Re-add the trailing space that was stripped as the split delimiter
    sentences = []
    remaining = text.strip()
    for part in parts:
        sentences.append(part)
        remaining = remaining[len(part):].lstrip()
    return [s for s in sentences if s.strip()]


# ---------------------------------------------------------------------------
# Markdown header detection
# ---------------------------------------------------------------------------

_HEADER_RE = re.compile(r'^(#{1,6})\s+(.+)$', re.MULTILINE)


def _split_by_headers(text: str) -> list[tuple[str, str]]:
    """
    Split text by markdown headers.

    Returns list of (section_title, section_body) tuples.
    The first element may have an empty title if text precedes any header.
    """
    sections: list[tuple[str, str]] = []
    last_pos = 0
    last_title = ""

    for m in _HEADER_RE.finditer(text):
        body = text[last_pos : m.start()].strip()
        if body or last_title:
            sections.append((last_title, body))
        last_title = m.group(0)
        last_pos = m.end()

    # Tail
    tail = text[last_pos:].strip()
    sections.append((last_title, tail))

    return [(t, b) for t, b in sections if t or b]


# ---------------------------------------------------------------------------
# Main chunker class
# ---------------------------------------------------------------------------

class SemanticChunker:
    """
    Multi-strategy semantic chunker.

    Usage::

        config = ChunkConfig(strategy=ChunkStrategy.SEMANTIC, chunk_size=256)
        chunks = SemanticChunker().chunk(text, config, metadata={"source": "doc.pdf"})
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def chunk(
        self,
        text: str,
        config: ChunkConfig | None = None,
        metadata: dict | None = None,
    ) -> list[Chunk]:
        """
        Chunk *text* using the strategy in *config*.

        Args:
            text:     Raw input text.
            config:   Chunking configuration (defaults to FIXED_SIZE/512 tokens).
            metadata: Arbitrary key-value pairs attached to every produced chunk.

        Returns:
            List of :class:`Chunk` objects.
        """
        config = config or ChunkConfig()
        metadata = metadata or {}

        strategy_map = {
            ChunkStrategy.FIXED_SIZE:     self._fixed_size,
            ChunkStrategy.SENTENCE:       self._sentence,
            ChunkStrategy.PARAGRAPH:      self._paragraph,
            ChunkStrategy.SEMANTIC:       self._semantic,
            ChunkStrategy.SLIDING_WINDOW: self._sliding_window,
            ChunkStrategy.RECURSIVE:      self._recursive,
        }

        handler = strategy_map[config.strategy]
        raw_chunks = list(handler(text, config))

        # Build Chunk objects, attach metadata, filter tiny chunks
        chunks: list[Chunk] = []
        for content, start, end in raw_chunks:
            tc = self.estimate_tokens(content)
            if tc < config.min_chunk_size:
                continue
            chunk = Chunk(
                id=str(uuid.uuid4()),
                content=content,
                start_char=start,
                end_char=end,
                metadata=dict(metadata),
                token_count=tc,
            )
            chunks.append(chunk)

        return chunks

    def chunk_file(
        self,
        path: Path,
        config: ChunkConfig | None = None,
    ) -> list[Chunk]:
        """
        Read a file and chunk its text content.

        Args:
            path:   Path to the text file.
            config: Chunking configuration.

        Returns:
            List of Chunk objects with ``source`` metadata set to the file path.
        """
        path = Path(path)
        text = path.read_text(encoding="utf-8", errors="replace")
        meta = {"source": str(path), "filename": path.name}
        return self.chunk(text, config, metadata=meta)

    def chunk_documents(
        self,
        docs: list[dict],
        config: ChunkConfig | None = None,
    ) -> list[Chunk]:
        """
        Chunk a list of document dicts.

        Each dict must have a ``"text"`` key; all other keys become metadata.

        Args:
            docs:   List of document dicts.
            config: Chunking configuration.

        Returns:
            Flat list of Chunk objects from all documents.
        """
        all_chunks: list[Chunk] = []
        for doc in docs:
            text = doc.get("text", "")
            meta = {k: v for k, v in doc.items() if k != "text"}
            all_chunks.extend(self.chunk(text, config, metadata=meta))
        return all_chunks

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """
        Estimate token count for *text*.

        Uses the heuristic: word_count × 1.3 (good for English prose).
        """
        return int(len(text.split()) * 1.3)

    # ------------------------------------------------------------------
    # Private strategy implementations
    # ------------------------------------------------------------------

    def _fixed_size(
        self,
        text: str,
        config: ChunkConfig,
    ) -> Iterator[tuple[str, int, int]]:
        """Yield (content, start_char, end_char) for fixed-size token windows."""
        words = text.split()
        if not words:
            return

        # Convert token counts to word counts (inverse of 1.3 factor)
        word_size = max(1, int(config.chunk_size / 1.3))
        word_overlap = max(0, int(config.chunk_overlap / 1.3))
        step = max(1, word_size - word_overlap)

        # Build cumulative char positions for words
        positions = _word_positions(text)

        i = 0
        while i < len(words):
            end_idx = min(i + word_size, len(words))
            window_words = words[i:end_idx]
            content = " ".join(window_words)
            start_char = positions[i][0]
            end_char = positions[end_idx - 1][1]
            yield content, start_char, end_char
            if end_idx == len(words):
                break
            i += step

    def _sentence(
        self,
        text: str,
        config: ChunkConfig,
    ) -> Iterator[tuple[str, int, int]]:
        """Yield chunks aligned to sentence boundaries."""
        sentences = _split_sentences(text)
        if not sentences:
            return

        # Map sentences back to character positions
        sent_positions = _locate_substrings(text, sentences)

        buf: list[str] = []
        buf_tokens = 0
        buf_start = 0

        for idx, sent in enumerate(sentences):
            sent_tokens = self.estimate_tokens(sent)
            start_char, end_char = sent_positions[idx]

            if buf_tokens + sent_tokens > config.chunk_size and buf:
                yield " ".join(buf), buf_start, sent_positions[idx - 1][1]
                # Overlap: keep last few sentences that fit within overlap budget
                overlap_buf, overlap_tokens = _trim_to_tokens(
                    list(reversed(buf)), config.chunk_overlap
                )
                buf = list(reversed(overlap_buf))
                buf_tokens = overlap_tokens
                buf_start = sent_positions[idx - len(buf)][0] if buf else start_char

            if not buf:
                buf_start = start_char
            buf.append(sent)
            buf_tokens += sent_tokens

        if buf:
            last_idx = len(sentences) - 1
            yield " ".join(buf), buf_start, sent_positions[last_idx][1]

    def _paragraph(
        self,
        text: str,
        config: ChunkConfig,
    ) -> Iterator[tuple[str, int, int]]:
        """Yield chunks aligned to paragraph (blank-line) boundaries."""
        sep = config.separator or "\n\n"
        # Split keeping positions
        paragraphs: list[tuple[str, int, int]] = []
        search_start = 0
        for raw_para in text.split(sep):
            para = raw_para.strip()
            if para:
                pos = text.find(para, search_start)
                paragraphs.append((para, pos, pos + len(para)))
                search_start = pos + len(para)

        if not paragraphs:
            return

        buf: list[str] = []
        buf_tokens = 0
        buf_start = paragraphs[0][1]

        for para_text, p_start, p_end in paragraphs:
            para_tokens = self.estimate_tokens(para_text)

            if buf_tokens + para_tokens > config.chunk_size and buf:
                yield "\n\n".join(buf), buf_start, p_start - 1
                buf = []
                buf_tokens = 0
                buf_start = p_start

            buf.append(para_text)
            buf_tokens += para_tokens

        if buf:
            last_end = paragraphs[-1][2]
            yield "\n\n".join(buf), buf_start, last_end

    def _semantic(
        self,
        text: str,
        config: ChunkConfig,
    ) -> Iterator[tuple[str, int, int]]:
        """
        Merge consecutive sentences into chunks while cosine similarity stays high.

        When similarity between the growing chunk and the next sentence drops
        below a threshold, start a new chunk.
        """
        sentences = _split_sentences(text)
        if not sentences:
            return
        if len(sentences) == 1:
            yield sentences[0], 0, len(text)
            return

        sent_positions = _locate_substrings(text, sentences)

        # Build TF-IDF vectors for every sentence
        token_lists = [_tokenize(s) for s in sentences]
        idf = _build_idf(token_lists)
        vocab = list(idf.keys())
        vectors = [_tf_idf_vector(tl, idf, vocab) for tl in token_lists]

        # Similarity threshold: start a new chunk when similarity drops below this
        sim_threshold = 0.25

        buf_sents: list[str] = []
        buf_tokens = 0
        buf_start = sent_positions[0][0]
        # Running centroid of the current chunk
        centroid: list[float] = list(vectors[0])

        for idx, sent in enumerate(sentences):
            s_tokens = self.estimate_tokens(sent)
            s_vec = vectors[idx]

            if buf_sents:
                sim = _cosine(centroid, s_vec)
                too_large = buf_tokens + s_tokens > config.chunk_size
                dissimilar = sim < sim_threshold

                if too_large or dissimilar:
                    yield " ".join(buf_sents), buf_start, sent_positions[idx - 1][1]
                    buf_sents = []
                    buf_tokens = 0
                    buf_start = sent_positions[idx][0]
                    centroid = list(s_vec)

            if not buf_sents:
                buf_start = sent_positions[idx][0]
            buf_sents.append(sent)
            buf_tokens += s_tokens

            # Update centroid (running mean of vectors)
            n = len(buf_sents)
            centroid = [(centroid[i] * (n - 1) + s_vec[i]) / n for i in range(len(centroid))]

        if buf_sents:
            yield " ".join(buf_sents), buf_start, sent_positions[-1][1]

    def _sliding_window(
        self,
        text: str,
        config: ChunkConfig,
    ) -> Iterator[tuple[str, int, int]]:
        """Yield overlapping windows of fixed token size."""
        # Same as fixed_size but step = 1 token window of (size - overlap)
        # Re-use _fixed_size which already implements overlap
        yield from self._fixed_size(text, config)

    def _recursive(
        self,
        text: str,
        config: ChunkConfig,
    ) -> Iterator[tuple[str, int, int]]:
        """
        Recursively split: headers → paragraphs → sentences.

        Markdown-aware: splits on ## headers first, then blank lines, then sentences.
        """
        # Level 1: split by markdown headers
        sections = _split_by_headers(text)

        for title, body in sections:
            section_text = (title + "\n" + body).strip() if title else body.strip()
            if not section_text:
                continue
            section_tokens = self.estimate_tokens(section_text)

            if section_tokens <= config.chunk_size:
                # Entire section fits: yield as-is
                pos = text.find(section_text)
                if pos == -1:
                    pos = 0
                yield section_text, pos, pos + len(section_text)
                continue

            # Level 2: split by paragraphs within section
            para_config = ChunkConfig(
                strategy=ChunkStrategy.PARAGRAPH,
                chunk_size=config.chunk_size,
                chunk_overlap=config.chunk_overlap,
                min_chunk_size=config.min_chunk_size,
                separator=config.separator,
            )
            para_chunks = list(self._paragraph(section_text, para_config))

            for para_content, p_start, p_end in para_chunks:
                para_tokens = self.estimate_tokens(para_content)

                if para_tokens <= config.chunk_size:
                    abs_pos = text.find(para_content)
                    if abs_pos == -1:
                        abs_pos = p_start
                    yield para_content, abs_pos, abs_pos + len(para_content)
                    continue

                # Level 3: split by sentences within paragraph
                sent_config = ChunkConfig(
                    strategy=ChunkStrategy.SENTENCE,
                    chunk_size=config.chunk_size,
                    chunk_overlap=config.chunk_overlap,
                    min_chunk_size=config.min_chunk_size,
                )
                for sent_content, s_start, s_end in self._sentence(para_content, sent_config):
                    abs_pos = text.find(sent_content)
                    if abs_pos == -1:
                        abs_pos = s_start
                    yield sent_content, abs_pos, abs_pos + len(sent_content)


# ---------------------------------------------------------------------------
# Internal utilities
# ---------------------------------------------------------------------------

def _word_positions(text: str) -> list[tuple[int, int]]:
    """Return list of (start_char, end_char) for each whitespace-delimited word."""
    positions: list[tuple[int, int]] = []
    for m in re.finditer(r'\S+', text):
        positions.append((m.start(), m.end()))
    return positions


def _locate_substrings(text: str, parts: list[str]) -> list[tuple[int, int]]:
    """
    Find (start, end) char positions for each element of *parts* within *text*.

    Searches left-to-right, advancing the cursor after each match so overlapping
    occurrences are handled correctly.
    """
    positions: list[tuple[int, int]] = []
    cursor = 0
    for part in parts:
        idx = text.find(part, cursor)
        if idx == -1:
            # Fall back: use cursor position
            idx = cursor
        end = idx + len(part)
        positions.append((idx, end))
        cursor = end
    return positions


def _trim_to_tokens(
    sentences: list[str],
    max_tokens: int,
) -> tuple[list[str], int]:
    """
    Keep a suffix of *sentences* whose total token count fits within *max_tokens*.

    *sentences* is expected to be in reverse order (most-recent first).
    Returns (kept_sentences_in_order, total_tokens).
    """
    chunker = SemanticChunker()
    kept: list[str] = []
    total = 0
    for sent in sentences:
        t = chunker.estimate_tokens(sent)
        if total + t > max_tokens:
            break
        kept.append(sent)
        total += t
    return kept, total
