"""
Qwen3 forced-alignment wrapper.

Provides:
  Qwen3ForceAlignProcessor  — multilingual tokeniser + timestamp encoder/decoder
  Qwen3ForcedAligner        — HF-style model wrapper with .from_pretrained() and .align()
  ForcedAlignItem           — per-token span (text, start_time, end_time)
  ForcedAlignResult         — sequence of ForcedAlignItem for one audio
"""

from __future__ import annotations

import os
import unicodedata
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union

import torch
from transformers import AutoConfig, AutoModel, AutoProcessor

from qwen_asr.core.transformers_backend import (
    Qwen3ASRConfig,
    Qwen3ASRForConditionalGeneration,
    Qwen3ASRProcessor,
)

from .utils import AudioLike, ensure_list, normalize_audios


# ---------------------------------------------------------------------------
# Text processor — tokenisation + timestamp encoding
# ---------------------------------------------------------------------------

class Qwen3ForceAlignProcessor:
    def __init__(self) -> None:
        ko_dict_path = os.path.join(
            os.path.dirname(__file__), "assets", "korean_dict_jieba.dict"
        )
        ko_scores: Dict[str, float] = {}
        with open(ko_dict_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                word = line.split()[0]
                ko_scores[word] = 1.0
        self.ko_score = ko_scores
        self.ko_tokenizer = None

    # ------------------------------------------------------------------
    # Character-level helpers
    # ------------------------------------------------------------------

    def is_kept_char(self, ch: str) -> bool:
        if ch == "'":
            return True
        cat = unicodedata.category(ch)
        return cat.startswith("L") or cat.startswith("N")

    def clean_token(self, token: str) -> str:
        return "".join(ch for ch in token if self.is_kept_char(ch))

    def is_cjk_char(self, ch: str) -> bool:
        code = ord(ch)
        return (
            0x4E00 <= code <= 0x9FFF       # CJK Unified Ideographs
            or 0x3400 <= code <= 0x4DBF    # Extension A
            or 0x20000 <= code <= 0x2A6DF  # Extension B
            or 0x2A700 <= code <= 0x2B73F  # Extension C
            or 0x2B740 <= code <= 0x2B81F  # Extension D
            or 0x2B820 <= code <= 0x2CEAF  # Extension E
            or 0xF900 <= code <= 0xFAFF    # Compatibility Ideographs
        )

    # ------------------------------------------------------------------
    # Tokenisers per script family
    # ------------------------------------------------------------------

    def tokenize_chinese_mixed(self, text: str) -> List[str]:
        tokens: List[str] = []
        current_latin: List[str] = []

        def flush_latin() -> None:
            nonlocal current_latin
            if current_latin:
                token = "".join(current_latin)
                cleaned = self.clean_token(token)
                if cleaned:
                    tokens.append(cleaned)
                current_latin = []

        for ch in text:
            if self.is_cjk_char(ch):
                flush_latin()
                tokens.append(ch)
            else:
                if self.is_kept_char(ch):
                    current_latin.append(ch)
                else:
                    flush_latin()

        flush_latin()
        return tokens

    def tokenize_japanese(self, text: str) -> List[str]:
        import nagisa
        words = nagisa.tagging(text).words
        tokens: List[str] = []
        for w in words:
            cleaned = self.clean_token(w)
            if cleaned:
                tokens.append(cleaned)
        return tokens

    def tokenize_korean(self, ko_tokenizer: Any, text: str) -> List[str]:
        raw_tokens = ko_tokenizer.tokenize(text)
        tokens: List[str] = []
        for w in raw_tokens:
            w_clean = self.clean_token(w)
            if w_clean:
                tokens.append(w_clean)
        return tokens

    def split_segment_with_chinese(self, seg: str) -> List[str]:
        tokens: List[str] = []
        buf: List[str] = []

        def flush_buf() -> None:
            nonlocal buf
            if buf:
                tokens.append("".join(buf))
                buf = []

        for ch in seg:
            if self.is_cjk_char(ch):
                flush_buf()
                tokens.append(ch)
            else:
                buf.append(ch)

        flush_buf()
        return tokens

    def tokenize_space_lang(self, text: str) -> List[str]:
        tokens: List[str] = []
        for seg in text.split():
            cleaned = self.clean_token(seg)
            if cleaned:
                tokens.extend(self.split_segment_with_chinese(cleaned))
        return tokens

    # ------------------------------------------------------------------
    # Timestamp fixing (LIS-based outlier repair)
    # ------------------------------------------------------------------

    def fix_timestamp(self, data: Any) -> List[int]:
        data = data.tolist()
        n = len(data)

        dp = [1] * n
        parent = [-1] * n

        for i in range(1, n):
            for j in range(i):
                if data[j] <= data[i] and dp[j] + 1 > dp[i]:
                    dp[i] = dp[j] + 1
                    parent[i] = j

        max_length = max(dp)
        max_idx = dp.index(max_length)

        lis_indices: List[int] = []
        idx = max_idx
        while idx != -1:
            lis_indices.append(idx)
            idx = parent[idx]
        lis_indices.reverse()

        is_normal = [False] * n
        for idx in lis_indices:
            is_normal[idx] = True

        result = data.copy()
        i = 0

        while i < n:
            if not is_normal[i]:
                j = i
                while j < n and not is_normal[j]:
                    j += 1

                anomaly_count = j - i

                left_val = None
                for k in range(i - 1, -1, -1):
                    if is_normal[k]:
                        left_val = result[k]
                        break

                right_val = None
                for k in range(j, n):
                    if is_normal[k]:
                        right_val = result[k]
                        break

                if anomaly_count <= 2:
                    for k in range(i, j):
                        if left_val is None:
                            result[k] = right_val
                        elif right_val is None:
                            result[k] = left_val
                        else:
                            result[k] = (
                                left_val
                                if (k - (i - 1)) <= (j - k)
                                else right_val
                            )
                else:
                    if left_val is not None and right_val is not None:
                        step = (right_val - left_val) / (anomaly_count + 1)
                        for k in range(i, j):
                            result[k] = left_val + step * (k - i + 1)
                    elif left_val is not None:
                        for k in range(i, j):
                            result[k] = left_val
                    elif right_val is not None:
                        for k in range(i, j):
                            result[k] = right_val

                i = j
            else:
                i += 1

        return [int(res) for res in result]

    # ------------------------------------------------------------------
    # Encode / parse
    # ------------------------------------------------------------------

    def encode_timestamp(
        self, text: str, language: str
    ) -> tuple[List[str], str]:
        lang = language.lower()

        if lang == "japanese":
            word_list = self.tokenize_japanese(text)
        elif lang == "korean":
            if self.ko_tokenizer is None:
                from soynlp.tokenizer import LTokenizer
                self.ko_tokenizer = LTokenizer(scores=self.ko_score)
            word_list = self.tokenize_korean(self.ko_tokenizer, text)
        else:
            word_list = self.tokenize_space_lang(text)

        input_text = (
            "<timestamp><timestamp>".join(word_list)
            + "<timestamp><timestamp>"
        )
        input_text = "<|audio_start|><|audio_pad|><|audio_end|>" + input_text
        return word_list, input_text

    def parse_timestamp(
        self, word_list: List[str], timestamp: Any
    ) -> List[Dict[str, Any]]:
        timestamp_fixed = self.fix_timestamp(timestamp)
        output: List[Dict[str, Any]] = []
        for i, word in enumerate(word_list):
            output.append(
                {
                    "text": word,
                    "start_time": timestamp_fixed[i * 2],
                    "end_time": timestamp_fixed[i * 2 + 1],
                }
            )
        return output


# ---------------------------------------------------------------------------
# Output dataclasses
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ForcedAlignItem:
    """One aligned token span."""
    text: str
    start_time: float
    end_time: float


@dataclass(frozen=True)
class ForcedAlignResult:
    """Forced alignment output for one sample."""
    items: List[ForcedAlignItem]

    def __iter__(self):
        return iter(self.items)

    def __len__(self) -> int:
        return len(self.items)

    def __getitem__(self, idx: int) -> ForcedAlignItem:
        return self.items[idx]


# ---------------------------------------------------------------------------
# Model wrapper
# ---------------------------------------------------------------------------

class Qwen3ForcedAligner:
    """
    HuggingFace-style wrapper for Qwen3-ForcedAligner model inference.

    Usage:
        aligner = Qwen3ForcedAligner.from_pretrained("Qwen/Qwen3-ForcedAligner", device_map="cuda")
        results = aligner.align(audio, text, language="Chinese")
    """

    def __init__(
        self,
        model: Qwen3ASRForConditionalGeneration,
        processor: Qwen3ASRProcessor,
        aligner_processor: Qwen3ForceAlignProcessor,
    ) -> None:
        self.model = model
        self.processor = processor
        self.aligner_processor = aligner_processor

        self.device = getattr(model, "device", None)
        if self.device is None:
            try:
                self.device = next(model.parameters()).device
            except StopIteration:
                self.device = torch.device("cpu")

        self.timestamp_token_id = int(model.config.timestamp_token_id)
        self.timestamp_segment_time = float(model.config.timestamp_segment_time)

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    @classmethod
    def from_pretrained(
        cls,
        pretrained_model_name_or_path: str,
        **kwargs: Any,
    ) -> "Qwen3ForcedAligner":
        """
        Load Qwen3-ForcedAligner from a HF repo or local directory.

        Registers config/model/processor auto-classes, then constructs the
        instance with the loaded model, HF processor, and text aligner processor.
        """
        AutoConfig.register("qwen3_asr", Qwen3ASRConfig)
        AutoModel.register(Qwen3ASRConfig, Qwen3ASRForConditionalGeneration)
        AutoProcessor.register(Qwen3ASRConfig, Qwen3ASRProcessor)

        model = AutoModel.from_pretrained(pretrained_model_name_or_path, **kwargs)
        if not isinstance(model, Qwen3ASRForConditionalGeneration):
            raise TypeError(
                f"AutoModel returned {type(model)}, "
                f"expected Qwen3ASRForConditionalGeneration."
            )

        processor = AutoProcessor.from_pretrained(
            pretrained_model_name_or_path, fix_mistral_regex=True
        )
        aligner_processor = Qwen3ForceAlignProcessor()

        return cls(
            model=model,
            processor=processor,
            aligner_processor=aligner_processor,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _to_structured_items(
        self, timestamp_output: List[Dict[str, Any]]
    ) -> ForcedAlignResult:
        items: List[ForcedAlignItem] = []
        for it in timestamp_output:
            items.append(
                ForcedAlignItem(
                    text=str(it.get("text", "")),
                    start_time=float(it.get("start_time", 0)),
                    end_time=float(it.get("end_time", 0)),
                )
            )
        return ForcedAlignResult(items=items)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @torch.inference_mode()
    def align(
        self,
        audio: Union[AudioLike, List[AudioLike]],
        text: Union[str, List[str]],
        language: Union[str, List[str]],
    ) -> List[ForcedAlignResult]:
        """
        Run forced alignment for a batch or a single sample.

        Args:
            audio:   path / URL / base64 / (np.ndarray, sr) — mono 16 kHz expected.
            text:    transcript(s) to align.
            language: e.g. "Chinese", "English", "Japanese", "Korean".

        Returns:
            One ForcedAlignResult per sample; items carry .text, .start_time, .end_time.
        """
        texts = ensure_list(text)
        languages = ensure_list(language)
        audios = normalize_audios(audio)

        if len(languages) == 1 and len(audios) > 1:
            languages = languages * len(audios)

        if not (len(audios) == len(texts) == len(languages)):
            raise ValueError(
                f"Batch size mismatch: "
                f"audio={len(audios)}, text={len(texts)}, language={len(languages)}"
            )

        word_lists: List[List[str]] = []
        aligner_input_texts: List[str] = []
        for t, lang in zip(texts, languages):
            word_list, aligner_input_text = self.aligner_processor.encode_timestamp(
                t, lang
            )
            word_lists.append(word_list)
            aligner_input_texts.append(aligner_input_text)

        inputs = self.processor(
            text=aligner_input_texts,
            audio=audios,
            return_tensors="pt",
            padding=True,
        )
        inputs = inputs.to(self.model.device).to(self.model.dtype)

        logits = self.model.thinker(**inputs).logits
        output_ids = logits.argmax(dim=-1)

        results: List[ForcedAlignResult] = []
        for input_id, output_id, word_list in zip(
            inputs["input_ids"], output_ids, word_lists
        ):
            masked_output_id = output_id[input_id == self.timestamp_token_id]
            timestamp_ms = (
                (masked_output_id * self.timestamp_segment_time)
                .to("cpu")
                .numpy()
            )
            timestamp_output = self.aligner_processor.parse_timestamp(
                word_list, timestamp_ms
            )
            for it in timestamp_output:
                it["start_time"] = round(it["start_time"] / 1000.0, 3)
                it["end_time"] = round(it["end_time"] / 1000.0, 3)
            results.append(self._to_structured_items(timestamp_output))

        return results

    def get_supported_languages(self) -> Optional[List[str]]:
        """Return sorted list of supported language names, or None."""
        fn = getattr(self.model, "get_support_languages", None)
        if not callable(fn):
            return None
        langs = fn()
        if langs is None:
            return None
        return sorted({str(x).lower() for x in langs})
