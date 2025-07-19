"""Data models for notes and processed audio chunks."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum


class ProcessingStatus(Enum):
    """Status of processing for different stages."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class AudioChunk:
    """Raw audio chunk with metadata."""
    chunk_id: str
    session_id: str
    start_time: float  # Seconds from session start
    end_time: float    # Seconds from session start
    audio_data: bytes  # Raw audio bytes
    sample_rate: int
    timestamp: datetime
    processing_status: ProcessingStatus = ProcessingStatus.PENDING


@dataclass
class RawTranscription:
    """Raw transcription result from speech-to-text service."""
    transcription_id: str
    chunk_id: str
    session_id: str
    text: str
    confidence: float
    service: str  # "google", "whisper", etc.
    language: str
    processing_time: float
    timestamp: datetime
    transcription_mode: str  # "realtime" or "batch"
    alternatives: Optional[List[str]] = None
    batch_id: Optional[str] = None


@dataclass
class ProcessedTranscription:
    """Cleaned and processed transcription."""
    processed_id: str
    raw_transcription_ids: List[str]  # Source raw transcriptions
    session_id: str
    text: str  # Cleaned text
    confidence: float
    processing_service: str  # "claude", "gpt-4", etc.
    processing_time: float
    timestamp: datetime
    source_audio_start: float
    source_audio_end: float


@dataclass
class ConceptAnnotation:
    """Key concept annotation for transcription."""
    annotation_id: str
    concept_id: str
    concept_name: str
    confidence: float
    start_char: int  # Character position in text
    end_char: int    # Character position in text
    timestamp: datetime


@dataclass
class AnnotatedTranscription:
    """Transcription with concept annotations."""
    annotation_id: str
    processed_transcription_id: str
    session_id: str
    text: str  # Same as processed transcription
    annotations: List[ConceptAnnotation]
    processing_service: str  # "gpt-4", "claude", etc.
    processing_time: float
    timestamp: datetime


@dataclass
class ProcessedChunk:
    """Complete processed chunk with all stages of processing."""
    chunk_id: str
    session_id: str
    
    # Audio data
    audio: AudioChunk
    
    # Transcription stages (may be None if not yet processed)
    raw_transcriptions: List[RawTranscription] = field(default_factory=list)
    processed_transcription: Optional[ProcessedTranscription] = None
    annotated_transcription: Optional[AnnotatedTranscription] = None
    
    # Processing status for each stage
    raw_transcription_status: ProcessingStatus = ProcessingStatus.PENDING
    processed_transcription_status: ProcessingStatus = ProcessingStatus.PENDING
    annotation_status: ProcessingStatus = ProcessingStatus.PENDING
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class SessionNotes:
    """Complete notes for a recording session."""
    session_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    
    # All processed chunks for this session
    processed_chunks: List[ProcessedChunk] = field(default_factory=list)
    
    # Session-level metadata
    total_chunks: int = 0
    completed_chunks: int = 0
    processing_progress: float = 0.0  # 0.0 to 1.0
    
    # File references
    audio_file_path: Optional[str] = None
    session_file_path: Optional[str] = None
    
    # Session status
    is_recording: bool = False
    is_processing: bool = False
    is_complete: bool = False


@dataclass
class NotesQuery:
    """Query parameters for fetching processed chunks."""
    session_id: str
    high_watermark: Optional[datetime] = None  # Only return chunks newer than this
    include_audio: bool = False  # Whether to include raw audio data
    include_raw_transcriptions: bool = True
    include_processed_transcriptions: bool = True
    include_annotations: bool = True
    limit: Optional[int] = None  # Maximum number of chunks to return
    
    # Filtering options
    min_confidence: Optional[float] = None
    transcription_mode: Optional[str] = None  # "realtime", "batch", or None for all
    processing_status: Optional[ProcessingStatus] = None


@dataclass
class NotesResponse:
    """Response from notes service with processed chunks."""
    session_id: str
    chunks: List[ProcessedChunk]
    new_high_watermark: Optional[datetime]  # Client should use this for next query
    total_chunks_available: int
    has_more: bool  # True if more chunks available beyond limit
    session_status: SessionNotes
    query_timestamp: datetime = field(default_factory=datetime.now)