"""Session-related data models."""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class SessionInfo:
    """Information about a recording session."""
    session_id: str
    start_time: datetime
    duration_seconds: float
    audio_file: str
    file_size_bytes: int
    sample_rate: int
    total_chunks: int