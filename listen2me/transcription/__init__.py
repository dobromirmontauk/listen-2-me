"""Transcription module for Listen2Me."""

from .base import AbstractTranscriptionBackend, TranscriptionResult
from .engine import TranscriptionEngine
from .google_backend import GoogleSpeechBackend

__all__ = [
    "AbstractTranscriptionBackend",
    "TranscriptionResult", 
    "TranscriptionEngine",
    "GoogleSpeechBackend",
]