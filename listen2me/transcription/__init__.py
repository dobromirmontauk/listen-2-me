"""Transcription module for Listen2Me."""

from .base import AbstractTranscriptionBackend
from ..models.transcription import TranscriptionResult
from .engine import TranscriptionEngine
from .google_backend import GoogleSpeechBackend
from .dual_engine import DualTranscriptionEngine

__all__ = [
    "AbstractTranscriptionBackend",
    "TranscriptionResult", 
    "TranscriptionEngine",
    "GoogleSpeechBackend",
    "DualTranscriptionEngine",
]