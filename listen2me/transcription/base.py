"""Abstract base classes for transcription backends."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class TranscriptionResult:
    """Result of a transcription operation."""
    text: str
    confidence: float
    processing_time: float
    timestamp: datetime
    service: str
    language: str = "en-US"
    alternatives: Optional[list] = None
    is_final: bool = True
    chunk_id: Optional[str] = None


class AbstractTranscriptionBackend(ABC):
    """Abstract base class for transcription backends."""

    def __init__(self, language: str = "en-US"):
        """Initialize backend with language preference."""
        self.language = language
        self.stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "total_processing_time": 0.0,
            "avg_confidence": 0.0,
            "errors": []
        }
    
    @abstractmethod
    def transcribe_chunk(self, audio_chunk: bytes, sample_rate: int = 16000) -> TranscriptionResult:
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
    
    def get_stats(self) -> Dict[str, Any]:
        """Get backend performance statistics."""
        stats = self.stats.copy()
        
        if stats["total_requests"] > 0:
            stats["success_rate"] = stats["successful_requests"] / stats["total_requests"]
            stats["avg_processing_time"] = stats["total_processing_time"] / stats["total_requests"]
        else:
            stats["success_rate"] = 0.0
            stats["avg_processing_time"] = 0.0
            
        return stats
    
    def _update_stats(self, result: TranscriptionResult, error: Optional[Exception] = None):
        """Update internal statistics."""
        self.stats["total_requests"] += 1
        
        if error:
            self.stats["failed_requests"] += 1
            self.stats["errors"].append({
                "timestamp": datetime.now().isoformat(),
                "error": str(error),
                "type": type(error).__name__
            })
            # Keep only last 10 errors
            if len(self.stats["errors"]) > 10:
                self.stats["errors"] = self.stats["errors"][-10:]
        else:
            self.stats["successful_requests"] += 1
            self.stats["total_processing_time"] += result.processing_time
            
            # Update running average confidence
            current_avg = self.stats["avg_confidence"]
            successful_count = self.stats["successful_requests"]
            self.stats["avg_confidence"] = (
                (current_avg * (successful_count - 1) + result.confidence) / successful_count
            )
    
    def is_healthy(self) -> bool:
        """Check if backend is operating normally."""
        total = self.stats["total_requests"]
        if total == 0:
            return True  # No requests yet, assume healthy
            
        success_rate = self.stats["successful_requests"] / total
        
        # Be more lenient - require at least 2 failures and < 50% success rate
        if total >= 2 and success_rate < 0.5:
            return False
        
        return True
    
    def reset_health(self) -> None:
        """Reset backend health statistics."""
        logger.info(f"Resetting health stats for {self.__class__.__name__}")
        self.stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "total_processing_time": 0.0,
            "avg_confidence": 0.0,
            "errors": []
        }