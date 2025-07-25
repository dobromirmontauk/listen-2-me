"""Abstract base classes for transcription backends."""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from datetime import datetime
import logging

from ..models.transcription import TranscriptionResult

logger = logging.getLogger(__name__)


class AbstractTranscriptionBackend(ABC):
    """Abstract base class for transcription backends."""

    def __init__(self, language: str = "en-US"):
        """Initialize backend with language preference."""
        self.language = language
    
    @abstractmethod
    def transcribe_chunk(self, chunk_id: str, audio_chunk: bytes, sample_rate: int = 16000) -> TranscriptionResult:
        """Transcribe an audio chunk and return result.
        
        Args:
            audio_chunk: Raw audio data in bytes
            sample_rate: Sample rate of the audio in Hz
            
        Returns:
            TranscriptionResult with transcription and metadata
        """
        pass
    
    @abstractmethod
    def initialize(self) -> bool:
        """Initialize backend resources and verify configuration.
        
        Returns:
            True if initialization successful, False otherwise
        """
        pass
    
    @abstractmethod
    def cleanup(self) -> None:
        """Clean up backend resources."""
        pass
    