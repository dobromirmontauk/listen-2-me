"""Transcription-related data models."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


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
    # New fields for dual-mode transcription
    audio_start_time: Optional[float] = None  # Audio timestamp when chunk started (seconds)
    audio_end_time: Optional[float] = None    # Audio timestamp when chunk ended (seconds)
    transcription_mode: str = "realtime"       # "realtime" | "batch"
    batch_id: Optional[str] = None            # For grouping batch results