"""Transcription-related data models."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List


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


@dataclass
class CleanedTranscriptionResult:
    """Result of a transcription cleaning operation."""
    # Reference to original transcriptions
    original_chunk_ids: List[str]  # List of chunk IDs from original transcriptions
    
    # Cleaned content
    cleaned_text: str  # The complete cleaned transcription text
    
    # Cleaning metadata
    cleaning_timestamp: datetime
    cleaning_service: str  # e.g., "ChatGPT", "Claude", etc.
    cleaning_model: str    # e.g., "gpt-4o-mini", "claude-3-sonnet"
    
    # Quality metrics (optional)
    cleaning_confidence: Optional[float] = None  # Confidence in the cleaning quality
    original_texts: Optional[List[str]] = None   # Original texts for comparison
    cleaning_notes: Optional[str] = None         # Notes about what was cleaned/changed
    
    # Batch information
    cleaning_batch_id: Optional[str] = None      # For grouping cleaning operations
    sequence_number: Optional[int] = None        # Order in the cleaning sequence