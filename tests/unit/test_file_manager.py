"""Unit tests for FileManager class."""

import pytest
import os
import json
import tempfile
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from listen2me.storage.file_manager import FileManager, SessionInfo


@pytest.mark.unit
class TestFileManager:
    """Test cases for FileManager class."""
    
    def test_initialization(self, temp_data_dir):
        """Test FileManager initialization."""
        fm = FileManager(temp_data_dir)
        
        assert fm.data_dir == Path(temp_data_dir)
        assert fm.audio_dir == Path(temp_data_dir) / "audio"
        assert fm.sessions_dir == Path(temp_data_dir) / "sessions"
        assert fm.logs_dir == Path(temp_data_dir) / "logs"
        
        # Check directories were created
        assert fm.data_dir.exists()
        assert fm.audio_dir.exists()
        assert fm.sessions_dir.exists()
        assert fm.logs_dir.exists()
    
    def test_initialization_default_path(self):
        """Test FileManager initialization with default path."""
        with patch.object(Path, 'mkdir') as mock_mkdir:
            fm = FileManager()
            
            assert fm.data_dir == Path("./data")
            # Should call mkdir for each directory
            assert mock_mkdir.call_count >= 4
    
    def test_create_session_directory(self, temp_data_dir):
        """Test creating session directory."""
        fm = FileManager(temp_data_dir)
        
        session_id = fm.create_session_directory()
        
        # Session ID should be timestamp format with random suffix
        assert len(session_id) == 20  # YYYYMMDD_HHMMSS_XXXX
        assert session_id.count("_") == 2
        
        # Directory should exist
        session_path = fm.sessions_dir / session_id
        assert session_path.exists()
        assert session_path.is_dir()
    
    def test_save_audio_file(self, temp_data_dir, sample_audio_chunk):
        """Test saving audio file."""
        fm = FileManager(temp_data_dir)
        session_id = fm.create_session_directory()
        
        # Save audio data
        filepath = fm.save_audio_file(sample_audio_chunk, session_id, "test_audio.wav")
        
        # Verify file was saved
        assert os.path.exists(filepath)
        assert os.path.getsize(filepath) == len(sample_audio_chunk)
        
        # Verify file content
        with open(filepath, 'rb') as f:
            saved_data = f.read()
        assert saved_data == sample_audio_chunk
    
    def test_save_audio_file_auto_filename(self, temp_data_dir, sample_audio_chunk):
        """Test saving audio file with auto-generated filename."""
        fm = FileManager(temp_data_dir)
        session_id = fm.create_session_directory()
        
        # Save without specifying filename
        filepath = fm.save_audio_file(sample_audio_chunk, session_id)
        
        # Should create file with timestamp filename
        assert os.path.exists(filepath)
        filename = os.path.basename(filepath)
        assert filename.startswith("audio_")
        assert filename.endswith(".wav")
    
    def test_save_audio_file_add_wav_extension(self, temp_data_dir, sample_audio_chunk):
        """Test saving audio file adds .wav extension if missing."""
        fm = FileManager(temp_data_dir)
        session_id = fm.create_session_directory()
        
        # Save with filename without extension
        filepath = fm.save_audio_file(sample_audio_chunk, session_id, "test_audio")
        
        # Should add .wav extension
        assert filepath.endswith(".wav")
        assert os.path.exists(filepath)
    
    def test_save_session_info(self, temp_data_dir):
        """Test saving session information."""
        fm = FileManager(temp_data_dir)
        session_id = fm.create_session_directory()
        
        # Create session info
        session_info = SessionInfo(
            session_id=session_id,
            start_time=datetime.now(),
            duration_seconds=120.5,
            audio_file="test_audio.wav",
            file_size_bytes=1024,
            sample_rate=16000,
            total_chunks=100
        )
        
        # Save session info
        info_path = fm.save_session_info(session_info)
        
        # Verify file was created
        assert os.path.exists(info_path)
        
        # Verify content
        with open(info_path, 'r') as f:
            data = json.load(f)
        
        assert data['session_id'] == session_id
        assert data['duration_seconds'] == 120.5
        assert data['audio_file'] == "test_audio.wav"
        assert data['file_size_bytes'] == 1024
        assert data['sample_rate'] == 16000
        assert data['total_chunks'] == 100
        assert 'start_time' in data
    
    def test_load_session_info(self, temp_data_dir):
        """Test loading session information."""
        fm = FileManager(temp_data_dir)
        session_id = fm.create_session_directory()
        
        # Create and save session info
        original_info = SessionInfo(
            session_id=session_id,
            start_time=datetime.now(),
            duration_seconds=60.0,
            audio_file="test.wav",
            file_size_bytes=2048,
            sample_rate=44100,
            total_chunks=50
        )
        fm.save_session_info(original_info)
        
        # Load session info
        loaded_info = fm.load_session_info(session_id)
        
        # Verify loaded data matches original
        assert loaded_info is not None
        assert loaded_info.session_id == original_info.session_id
        assert loaded_info.duration_seconds == original_info.duration_seconds
        assert loaded_info.audio_file == original_info.audio_file
        assert loaded_info.file_size_bytes == original_info.file_size_bytes
        assert loaded_info.sample_rate == original_info.sample_rate
        assert loaded_info.total_chunks == original_info.total_chunks
        
        # Times should be close (within a few milliseconds)
        time_diff = abs((loaded_info.start_time - original_info.start_time).total_seconds())
        assert time_diff < 0.001
    
    def test_load_session_info_not_found(self, temp_data_dir):
        """Test loading session info for non-existent session."""
        fm = FileManager(temp_data_dir)
        
        # Try to load non-existent session
        loaded_info = fm.load_session_info("nonexistent_session")
        
        assert loaded_info is None
    
    def test_list_sessions_empty(self, temp_data_dir):
        """Test listing sessions when no sessions exist."""
        fm = FileManager(temp_data_dir)
        
        sessions = fm.list_sessions()
        assert sessions == []
    
    def test_list_sessions_with_data(self, temp_data_dir):
        """Test listing sessions with multiple sessions."""
        fm = FileManager(temp_data_dir)
        
        # Create multiple sessions
        session_ids = []
        for i in range(3):
            session_id = fm.create_session_directory()
            session_ids.append(session_id)
            
            # Create session info file to make it valid
            session_info = SessionInfo(
                session_id=session_id,
                start_time=datetime.now(),
                duration_seconds=60.0,
                audio_file=f"test_{i}.wav",
                file_size_bytes=1024,
                sample_rate=16000,
                total_chunks=50
            )
            fm.save_session_info(session_info)
        
        # List sessions
        sessions = fm.list_sessions()
        
        assert len(sessions) == 3
        # Should be sorted chronologically
        assert sessions == sorted(session_ids)
    
    def test_get_session_path(self, temp_data_dir):
        """Test getting session path."""
        fm = FileManager(temp_data_dir)
        session_id = "test_session_123"
        
        expected_path = Path(temp_data_dir) / "sessions" / session_id
        actual_path = fm.get_session_path(session_id)
        
        assert actual_path == expected_path
    
    def test_cleanup_old_sessions(self, temp_data_dir):
        """Test cleaning up old sessions."""
        fm = FileManager(temp_data_dir)
        
        # Create old session directory
        old_session_id = "old_session"
        old_session_path = fm.sessions_dir / old_session_id
        old_session_path.mkdir()
        
        # Make it appear old by modifying timestamp
        old_time = datetime.now() - timedelta(days=35)
        old_timestamp = old_time.timestamp()
        os.utime(old_session_path, (old_timestamp, old_timestamp))
        
        # Create recent session
        recent_session_id = fm.create_session_directory()
        
        # Cleanup old sessions (30 day threshold)
        cleaned_count = fm.cleanup_old_sessions(max_age_days=30)
        
        assert cleaned_count == 1
        assert not old_session_path.exists()
        assert fm.get_session_path(recent_session_id).exists()
    
    def test_get_storage_stats_empty(self, temp_data_dir):
        """Test getting storage statistics with no data."""
        fm = FileManager(temp_data_dir)
        
        stats = fm.get_storage_stats()
        
        assert stats['total_size_bytes'] == 0
        assert stats['total_size_mb'] == 0.0
        assert stats['session_count'] == 0
        assert stats['audio_files'] == 0
        assert stats['data_directory'] == str(fm.data_dir)
    
    def test_get_storage_stats_with_data(self, temp_data_dir, sample_audio_chunk):
        """Test getting storage statistics with data."""
        fm = FileManager(temp_data_dir)
        
        # Create sessions with data
        session_ids = []
        total_expected_size = 0
        
        for i in range(2):
            session_id = fm.create_session_directory()
            session_ids.append(session_id)
            
            # Save audio file
            filepath = fm.save_audio_file(sample_audio_chunk, session_id, f"audio_{i}.wav")
            total_expected_size += len(sample_audio_chunk)
            
            # Save session info
            session_info = SessionInfo(
                session_id=session_id,
                start_time=datetime.now(),
                duration_seconds=60.0,
                audio_file=f"audio_{i}.wav",
                file_size_bytes=len(sample_audio_chunk),
                sample_rate=16000,
                total_chunks=50
            )
            info_path = fm.save_session_info(session_info)
            
            # Add session info file size
            total_expected_size += os.path.getsize(info_path)
        
        # Get statistics
        stats = fm.get_storage_stats()
        
        assert stats['total_size_bytes'] == total_expected_size
        assert stats['total_size_mb'] == round(total_expected_size / (1024 * 1024), 2)
        assert stats['session_count'] == 2
        assert stats['audio_files'] == 2
        assert stats['data_directory'] == str(fm.data_dir)
    
    def test_error_handling_save_audio_file(self, temp_data_dir):
        """Test error handling when saving audio file fails."""
        fm = FileManager(temp_data_dir)
        session_id = fm.create_session_directory()
        
        # Try to save to invalid path (readonly directory)
        with patch('builtins.open', side_effect=PermissionError("Access denied")):
            with pytest.raises(PermissionError):
                fm.save_audio_file(b"test data", session_id, "test.wav")
    
    def test_error_handling_load_session_info(self, temp_data_dir):
        """Test error handling when loading invalid session info."""
        fm = FileManager(temp_data_dir)
        session_id = fm.create_session_directory()
        
        # Create invalid JSON file
        info_path = fm.sessions_dir / session_id / "session_info.json"
        with open(info_path, 'w') as f:
            f.write("invalid json content")
        
        # Should return None on error
        loaded_info = fm.load_session_info(session_id)
        assert loaded_info is None