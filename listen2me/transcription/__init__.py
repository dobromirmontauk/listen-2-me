"""Transcription module for Listen2Me."""

from .base import AbstractTranscriptionBackend
from ..models.transcription import TranscriptionResult
from .google_backend import GoogleSpeechBackend

__all__ = [
    "AbstractTranscriptionBackend",
    "TranscriptionResult", 
    "GoogleSpeechBackend",
]