"""UI-related data models."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class TranscriptionStatus:
    """Status information for transcription session."""
    session_id: Optional[str] = None
    is_recording: bool = False
    is_transcribing: bool = False
    duration_seconds: float = 0.0
    total_chunks: int = 0
    chunks_processed: int = 0
    peak_level: float = 0.0
    current_text: str = ""
    transcription_results: list = None
    
    def __post_init__(self):
        if self.transcription_results is None:
            self.transcription_results = []