"""Audio-related data models."""

from dataclasses import dataclass


@dataclass
class AudioStats:
    """Audio recording statistics."""
    is_recording: bool
    duration_seconds: float
    buffer_size: int
    sample_rate: int
    chunk_size: int
    total_chunks: int
    dropped_chunks: int
    peak_level: float


@dataclass
class AudioFrame:
    """A single audio frame with timestamp."""
    data: bytes
    timestamp: float  # Time when this frame was captured
    frame_number: int