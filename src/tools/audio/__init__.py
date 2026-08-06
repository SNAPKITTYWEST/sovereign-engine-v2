"""
Audio Namespace
Part of SOVEREIGN PYTHON LLM ENGINE

Audio transcription, synthesis, and processing tools.
"""

from .transcribe import AudioTranscriber
from .synthesize import AudioSynthesizer

__all__ = [
    "AudioTranscriber",
    "AudioSynthesizer",
]
