"""
Audio Transcription
Part of SOVEREIGN PYTHON LLM ENGINE

Transcribe audio using Whisper and other models.
"""

from typing import Any
from pathlib import Path
from dataclasses import dataclass

from ...core.evidence import WORMLedger


@dataclass
class Transcription:
    """Transcription result"""
    text: str
    language: str | None
    segments: list[dict[str, Any]]
    duration: float | None
    model: str


class AudioTranscriber:
    """
    Audio transcription using multiple providers.

    Supports:
    - OpenAI Whisper API
    - AWS Bedrock (if available)
    - Local Whisper model
    """

    def __init__(
        self,
        provider: str = "openai",
        model: str | None = None,
        worm_ledger: WORMLedger | None = None
    ):
        """
        Initialize transcriber.

        Args:
            provider: Provider ("openai", "local")
            model: Optional model override
            worm_ledger: Optional WORM ledger
        """
        self.provider = provider
        self.model = model
        self.worm_ledger = worm_ledger

    async def transcribe(
        self,
        audio_path: Path,
        language: str | None = None
    ) -> Transcription:
        """
        Transcribe audio file.

        Args:
            audio_path: Path to audio file
            language: Optional language code

        Returns:
            Transcription
        """
        if self.provider == "openai":
            return await self._transcribe_openai(audio_path, language)
        elif self.provider == "local":
            return await self._transcribe_local(audio_path, language)
        else:
            raise ValueError(f"Unknown provider: {self.provider}")

    async def _transcribe_openai(
        self,
        audio_path: Path,
        language: str | None
    ) -> Transcription:
        """Transcribe using OpenAI Whisper API"""
        try:
            from openai import AsyncOpenAI
        except ImportError:
            raise ImportError("openai is required")

        client = AsyncOpenAI()

        with open(audio_path, "rb") as audio_file:
            if language:
                response = await client.audio.transcriptions.create(
                    model=self.model or "whisper-1",
                    file=audio_file,
                    language=language,
                    response_format="verbose_json"
                )
            else:
                response = await client.audio.transcriptions.create(
                    model=self.model or "whisper-1",
                    file=audio_file,
                    response_format="verbose_json"
                )

        # Log to WORM
        if self.worm_ledger:
            await self.worm_ledger.append({
                "event": "audio_transcribe",
                "provider": "openai",
                "file": str(audio_path),
                "duration": response.duration
            })

        return Transcription(
            text=response.text,
            language=response.language,
            segments=response.segments or [],
            duration=response.duration,
            model=self.model or "whisper-1"
        )

    async def _transcribe_local(
        self,
        audio_path: Path,
        language: str | None
    ) -> Transcription:
        """Transcribe using local Whisper model"""
        try:
            import whisper
        except ImportError:
            raise ImportError("openai-whisper is required. Install: pip install openai-whisper")

        import asyncio

        def _sync_transcribe():
            model = whisper.load_model(self.model or "base")

            result = model.transcribe(
                str(audio_path),
                language=language
            )

            return Transcription(
                text=result["text"],
                language=result.get("language"),
                segments=result.get("segments", []),
                duration=None,
                model=self.model or "base"
            )

        return await asyncio.to_thread(_sync_transcribe)


# Tool registration helper
async def transcribe_audio_tool(
    audio_path: str,
    provider: str = "openai",
    language: str | None = None
) -> dict:
    """Transcribe audio tool"""
    transcriber = AudioTranscriber(provider=provider)
    result = await transcriber.transcribe(Path(audio_path), language)

    return {
        "text": result.text,
        "language": result.language,
        "duration": result.duration,
        "segments_count": len(result.segments)
    }
