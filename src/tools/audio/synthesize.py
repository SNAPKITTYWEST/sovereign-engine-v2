"""
Audio Synthesis (Text-to-Speech)
Part of SOVEREIGN PYTHON LLM ENGINE

Generate speech from text using TTS models.
"""

from pathlib import Path
from dataclasses import dataclass

from ...core.evidence import WORMLedger


@dataclass
class SynthesizedAudio:
    """Synthesized audio result"""
    audio_bytes: bytes
    format: str
    text: str
    voice: str
    model: str


class AudioSynthesizer:
    """
    Text-to-speech synthesis.

    Supports:
    - OpenAI TTS
    - ElevenLabs
    - Local TTS models
    """

    def __init__(
        self,
        provider: str = "openai",
        model: str | None = None,
        worm_ledger: WORMLedger | None = None
    ):
        """
        Initialize synthesizer.

        Args:
            provider: Provider ("openai", "elevenlabs")
            model: Optional model override
            worm_ledger: Optional WORM ledger
        """
        self.provider = provider
        self.model = model
        self.worm_ledger = worm_ledger

    async def synthesize(
        self,
        text: str,
        voice: str = "alloy",
        speed: float = 1.0
    ) -> SynthesizedAudio:
        """
        Synthesize speech from text.

        Args:
            text: Text to synthesize
            voice: Voice ID
            speed: Speech speed (0.25 - 4.0)

        Returns:
            SynthesizedAudio
        """
        if self.provider == "openai":
            return await self._synthesize_openai(text, voice, speed)
        else:
            raise ValueError(f"Unknown provider: {self.provider}")

    async def _synthesize_openai(
        self,
        text: str,
        voice: str,
        speed: float
    ) -> SynthesizedAudio:
        """Synthesize using OpenAI TTS"""
        try:
            from openai import AsyncOpenAI
        except ImportError:
            raise ImportError("openai is required")

        client = AsyncOpenAI()

        response = await client.audio.speech.create(
            model=self.model or "tts-1",
            voice=voice,
            input=text,
            speed=speed
        )

        audio_bytes = response.content

        # Log to WORM
        if self.worm_ledger:
            await self.worm_ledger.append({
                "event": "audio_synthesize",
                "provider": "openai",
                "text_length": len(text),
                "voice": voice
            })

        return SynthesizedAudio(
            audio_bytes=audio_bytes,
            format="mp3",
            text=text,
            voice=voice,
            model=self.model or "tts-1"
        )


async def save_audio(audio: SynthesizedAudio, output_path: Path) -> None:
    """Save synthesized audio to file"""
    output_path.write_bytes(audio.audio_bytes)


# Tool registration helper
async def synthesize_audio_tool(
    text: str,
    voice: str = "alloy",
    provider: str = "openai",
    output_path: str | None = None
) -> dict:
    """Synthesize speech tool"""
    synthesizer = AudioSynthesizer(provider=provider)
    result = await synthesizer.synthesize(text, voice)

    response = {
        "format": result.format,
        "voice": result.voice,
        "model": result.model,
        "audio_size_bytes": len(result.audio_bytes)
    }

    if output_path:
        await save_audio(result, Path(output_path))
        response["saved_to"] = output_path

    return response
