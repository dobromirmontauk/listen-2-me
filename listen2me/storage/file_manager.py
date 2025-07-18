"""File management module for audio and data storage."""

import os
import json
import logging
import shutil
import random
import string
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict


logger = logging.getLogger(__name__)


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


class FileManager:
    """Manages file storage and organization for audio recordings and metadata."""
    
    def __init__(self, data_dir: str = "./data"):
        """Initialize file manager with data directory.
        
        Args:
            data_dir: Base directory for storing all data
        """
        self.data_dir = Path(data_dir)
        self.audio_dir = self.data_dir / "audio"
        self.sessions_dir = self.data_dir / "sessions"
        self.logs_dir = self.data_dir / "logs"
        
        # Create directory structure
        self._ensure_directories()
        
        logger.info(f"FileManager initialized with data_dir: {self.data_dir}")
    
    def _ensure_directories(self) -> None:
        """Ensure all required directories exist."""
        for directory in [self.data_dir, self.audio_dir, self.sessions_dir, self.logs_dir]:
            directory.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Ensured directory exists: {directory}")
    
    def create_session_directory(self) -> str:
        """Create new session directory with timestamp and random suffix.
        
        Returns:
            Session ID (timestamp-based with random suffix)
        """
        # Include random suffix to ensure uniqueness
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        random_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=4))
        session_id = f"{timestamp}_{random_suffix}"
        session_path = self.sessions_dir / session_id
        session_path.mkdir(exist_ok=True)
        
        logger.info(f"Created session directory: {session_path}")
        return session_id
    
    def save_audio_file(self, audio_data: bytes, session_id: str, filename: str = None) -> str:
        """Save audio data to file and return path.
        
        Args:
            audio_data: Raw audio data bytes
            session_id: Session identifier
            filename: Optional custom filename
            
        Returns:
            Full path to saved audio file
        """
        if filename is None:
            timestamp = datetime.now().strftime("%H%M%S")
            filename = f"audio_{timestamp}.wav"
        
        # Ensure .wav extension
        if not filename.endswith('.wav'):
            filename += '.wav'
        
        session_path = self.sessions_dir / session_id
        session_path.mkdir(exist_ok=True)
        
        audio_file_path = session_path / filename
        
        try:
            with open(audio_file_path, 'wb') as f:
                f.write(audio_data)
            
            logger.info(f"Audio file saved: {audio_file_path} ({len(audio_data)} bytes)")
            return str(audio_file_path)
            
        except Exception as e:
            logger.error(f"Error saving audio file: {e}")
            raise
    
    def save_session_info(self, session_info: SessionInfo) -> str:
        """Save session information to JSON file.
        
        Args:
            session_info: Session information to save
            
        Returns:
            Path to saved session info file
        """
        session_path = self.sessions_dir / session_info.session_id
        session_path.mkdir(exist_ok=True)
        
        info_file = session_path / "session_info.json"
        
        try:
            # Convert datetime to string for JSON serialization
            info_dict = asdict(session_info)
            info_dict['start_time'] = session_info.start_time.isoformat()
            
            with open(info_file, 'w') as f:
                json.dump(info_dict, f, indent=2)
            
            logger.info(f"Session info saved: {info_file}")
            return str(info_file)
            
        except Exception as e:
            logger.error(f"Error saving session info: {e}")
            raise
    
    def load_session_info(self, session_id: str) -> Optional[SessionInfo]:
        """Load session information from JSON file.
        
        Args:
            session_id: Session identifier
            
        Returns:
            SessionInfo object or None if not found
        """
        info_file = self.sessions_dir / session_id / "session_info.json"
        
        if not info_file.exists():
            logger.warning(f"Session info file not found: {info_file}")
            return None
        
        try:
            with open(info_file, 'r') as f:
                data = json.load(f)
            
            # Convert ISO string back to datetime
            data['start_time'] = datetime.fromisoformat(data['start_time'])
            
            return SessionInfo(**data)
            
        except Exception as e:
            logger.error(f"Error loading session info: {e}")
            return None
    
    def list_sessions(self) -> List[str]:
        """List all available session IDs.
        
        Returns:
            List of session IDs sorted by creation time
        """
        try:
            sessions = []
            for path in self.sessions_dir.iterdir():
                if path.is_dir() and (path / "session_info.json").exists():
                    sessions.append(path.name)
            
            sessions.sort()  # Sort chronologically
            logger.debug(f"Found {len(sessions)} sessions")
            return sessions
            
        except Exception as e:
            logger.error(f"Error listing sessions: {e}")
            return []
    
    def get_session_path(self, session_id: str) -> Path:
        """Get full path to session directory.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Path to session directory
        """
        return self.sessions_dir / session_id
    
    def cleanup_old_sessions(self, max_age_days: int = 30) -> int:
        """Clean up old session files.
        
        Args:
            max_age_days: Maximum age in days before cleanup
            
        Returns:
            Number of sessions cleaned up
        """
        cutoff_time = datetime.now().timestamp() - (max_age_days * 24 * 60 * 60)
        cleaned_count = 0
        
        try:
            for session_path in self.sessions_dir.iterdir():
                if session_path.is_dir():
                    # Check if session is old enough
                    if session_path.stat().st_mtime < cutoff_time:
                        shutil.rmtree(session_path)
                        cleaned_count += 1
                        logger.info(f"Cleaned up old session: {session_path}")
            
            logger.info(f"Cleaned up {cleaned_count} old sessions")
            return cleaned_count
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
            return 0
    
    def get_storage_stats(self) -> Dict[str, Any]:
        """Get storage usage statistics.
        
        Returns:
            Dictionary with storage statistics
        """
        try:
            total_size = 0
            session_count = 0
            audio_files = 0
            
            for session_path in self.sessions_dir.iterdir():
                if session_path.is_dir():
                    session_count += 1
                    for file_path in session_path.rglob("*"):
                        if file_path.is_file():
                            total_size += file_path.stat().st_size
                            if file_path.suffix == '.wav':
                                audio_files += 1
            
            return {
                "total_size_bytes": total_size,
                "total_size_mb": round(total_size / (1024 * 1024), 2),
                "session_count": session_count,
                "audio_files": audio_files,
                "data_directory": str(self.data_dir)
            }
            
        except Exception as e:
            logger.error(f"Error getting storage stats: {e}")
            return {}