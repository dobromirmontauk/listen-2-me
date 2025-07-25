"""Event models for pub/sub audio processing architecture."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Any, Dict
from abc import ABC, abstractmethod


@dataclass
class AudioEvent:
    """Audio chunk event with metadata."""
    chunk_id: str
    audio_data: bytes
    timestamp: float  # Unix timestamp when chunk was captured
    sequence_number: int
    sample_rate: int = 16000
    channels: int = 1
    chunk_duration_ms: Optional[int] = None  # Duration of this chunk in milliseconds
    final: bool = False  # True if this is the final chunk for the session
    
    def __post_init__(self):
        """Calculate chunk duration if not provided."""
        if self.chunk_duration_ms is None and self.audio_data:
            # Calculate based on 16-bit audio (2 bytes per sample)
            bytes_per_second = self.sample_rate * self.channels * 2
            duration_seconds = len(self.audio_data) / bytes_per_second
            self.chunk_duration_ms = int(duration_seconds * 1000)


@dataclass
class TranscriptionEvent:
    """Transcription result event."""
    event_id: str
    transcription_result: Any  # TranscriptionResult from models.transcription
    consumer_type: str  # "realtime", "batch", etc.
    source_chunk_ids: list[str] = field(default_factory=list)  # Which audio chunks contributed
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class SessionEvent:
    """Session lifecycle event."""
    event_id: str
    event_type: str  # "started", "stopped", "error"
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)