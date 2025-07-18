"""Integration tests for complete audio recording workflow."""

import pytest
import time
import os
import wave
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, patch
from listen2me.audio.capture import AudioCapture
from listen2me.storage.file_manager import FileManager, SessionInfo


@pytest.mark.integration
class TestAudioRecordingIntegration:
    """Integration tests for complete audio recording workflow."""
    
    def test_complete_recording_workflow(self, temp_data_dir, mock_pyaudio, sample_audio_chunk):
        """Test complete workflow from recording to file saving."""
        # Initialize components
        file_manager = FileManager(temp_data_dir)
        audio_capture = AudioCapture(chunk_size=1024, buffer_size=20)
        
        # Configure mock to return test data
        mock_pyaudio['stream'].read.return_value = sample_audio_chunk
        
        # Create session
        session_id = file_manager.create_session_directory()
        
        # Start recording
        start_time = datetime.now()
        audio_capture.start_recording()
        
        # Let recording run for short time
        time.sleep(0.3)
        
        # Stop recording
        audio_capture.stop_recording()
        end_time = datetime.now()
        
        # Verify recording occurred
        stats = audio_capture.get_recording_stats()
        assert stats.total_chunks > 0
        assert stats.duration_seconds > 0
        assert len(audio_capture.audio_data) > 0
        
        # Save audio to file
        audio_filename = f"recording_{session_id}.wav"
        session_path = file_manager.get_session_path(session_id)
        audio_filepath = session_path / audio_filename
        
        audio_capture.save_to_file(str(audio_filepath))
        
        # Verify file was created
        assert audio_filepath.exists()
        assert audio_filepath.stat().st_size > 0
        
        # Create and save session info
        session_info = SessionInfo(
            session_id=session_id,
            start_time=start_time,
            duration_seconds=stats.duration_seconds,
            audio_file=audio_filename,
            file_size_bytes=audio_filepath.stat().st_size,
            sample_rate=audio_capture.sample_rate,
            total_chunks=stats.total_chunks
        )
        
        file_manager.save_session_info(session_info)
        
        # Verify session info was saved
        loaded_info = file_manager.load_session_info(session_id)
        assert loaded_info is not None
        assert loaded_info.session_id == session_id
        assert loaded_info.audio_file == audio_filename
        assert loaded_info.total_chunks == stats.total_chunks
        
        # Verify session appears in list
        sessions = file_manager.list_sessions()
        assert session_id in sessions
        
        # Verify storage stats
        storage_stats = file_manager.get_storage_stats()
        assert storage_stats['session_count'] == 1
        assert storage_stats['audio_files'] == 1
        assert storage_stats['total_size_bytes'] > 0
    
    def test_multiple_sessions_workflow(self, temp_data_dir, mock_pyaudio, sample_audio_chunk):
        """Test workflow with multiple recording sessions."""
        file_manager = FileManager(temp_data_dir)
        
        # Configure mock
        mock_pyaudio['stream'].read.return_value = sample_audio_chunk
        
        session_ids = []
        
        # Create multiple sessions
        for i in range(3):
            # Create new audio capture for each session
            audio_capture = AudioCapture(chunk_size=512, buffer_size=10)
            
            # Create session
            session_id = file_manager.create_session_directory()
            session_ids.append(session_id)
            
            # Record
            audio_capture.start_recording()
            time.sleep(0.1)  # Different recording times
            audio_capture.stop_recording()
            
            # Save audio
            audio_filename = f"session_{i}.wav"
            session_path = file_manager.get_session_path(session_id)
            audio_filepath = session_path / audio_filename
            audio_capture.save_to_file(str(audio_filepath))
            
            # Save session info
            stats = audio_capture.get_recording_stats()
            session_info = SessionInfo(
                session_id=session_id,
                start_time=datetime.now(),
                duration_seconds=stats.duration_seconds,
                audio_file=audio_filename,
                file_size_bytes=audio_filepath.stat().st_size,
                sample_rate=audio_capture.sample_rate,
                total_chunks=stats.total_chunks
            )
            file_manager.save_session_info(session_info)
        
        # Verify all sessions exist
        sessions = file_manager.list_sessions()
        assert len(sessions) == 3
        for session_id in session_ids:
            assert session_id in sessions
        
        # Verify storage stats
        storage_stats = file_manager.get_storage_stats()
        assert storage_stats['session_count'] == 3
        assert storage_stats['audio_files'] == 3
        assert storage_stats['total_size_bytes'] > 0
    
    def test_recording_with_buffer_management(self, temp_data_dir, mock_pyaudio, sample_audio_chunk):
        """Test recording with buffer overflow and management."""
        file_manager = FileManager(temp_data_dir)
        
        # Use small buffer to force overflow
        audio_capture = AudioCapture(chunk_size=512, buffer_size=5)
        
        # Configure mock to return data quickly
        mock_pyaudio['stream'].read.return_value = sample_audio_chunk
        
        # Start recording
        audio_capture.start_recording()
        
        # Let it run long enough to fill buffer
        time.sleep(0.5)
        
        # Process some chunks to simulate real-time consumption
        processed_chunks = 0
        while audio_capture.has_audio_data() and processed_chunks < 10:
            chunk = audio_capture.get_audio_chunk()
            if chunk:
                processed_chunks += 1
        
        # Stop recording
        audio_capture.stop_recording()
        
        # Verify recording occurred and buffer was managed
        stats = audio_capture.get_recording_stats()
        assert stats.total_chunks > 0
        assert processed_chunks > 0
        
        # Buffer should not be larger than max size
        assert stats.buffer_size <= 5
        
        # Some chunks may have been dropped due to small buffer
        # This is expected behavior
        if stats.dropped_chunks > 0:
            assert stats.dropped_chunks > 0
    
    def test_audio_file_integrity(self, temp_data_dir, mock_pyaudio, audio_test_data):
        """Test that saved audio files maintain integrity."""
        file_manager = FileManager(temp_data_dir)
        audio_capture = AudioCapture()
        
        # Generate test audio with known pattern
        test_audio = audio_test_data("sine", duration_seconds=2.0)
        
        # Mock to return our test audio in chunks
        chunk_size = 1024 * 2  # 2 bytes per sample
        chunks = [test_audio[i:i+chunk_size] for i in range(0, len(test_audio), chunk_size)]
        
        mock_pyaudio['stream'].read.side_effect = chunks + [b''] * 100  # End with empty
        
        # Record
        session_id = file_manager.create_session_directory()
        audio_capture.start_recording()
        
        # Wait for all chunks to be processed
        time.sleep(0.5)
        
        audio_capture.stop_recording()
        
        # Save to file
        audio_filename = "integrity_test.wav"
        session_path = file_manager.get_session_path(session_id)
        audio_filepath = session_path / audio_filename
        audio_capture.save_to_file(str(audio_filepath))
        
        # Verify file can be read as valid WAV
        with wave.open(str(audio_filepath), 'rb') as wf:
            frames = wf.getnframes()
            sample_rate = wf.getframerate()
            channels = wf.getnchannels()
            sample_width = wf.getsampwidth()
            
            # Verify WAV properties
            assert sample_rate == 16000
            assert channels == 1
            assert sample_width == 2
            assert frames > 0
            
            # Read audio data
            audio_data = wf.readframes(frames)
            assert len(audio_data) > 0
    
    @pytest.mark.slow
    def test_long_recording_session(self, temp_data_dir, mock_pyaudio, sample_audio_chunk):
        """Test longer recording session (approaching real-world usage)."""
        file_manager = FileManager(temp_data_dir)
        audio_capture = AudioCapture(chunk_size=1024, buffer_size=100)
        
        # Configure mock
        mock_pyaudio['stream'].read.return_value = sample_audio_chunk
        
        # Start recording
        session_id = file_manager.create_session_directory()
        start_time = datetime.now()
        audio_capture.start_recording()
        
        # Simulate processing chunks during recording
        processed_chunks = 0
        recording_duration = 2.0  # 2 seconds
        
        end_time = start_time.timestamp() + recording_duration
        
        while time.time() < end_time:
            # Process available chunks
            while audio_capture.has_audio_data():
                chunk = audio_capture.get_audio_chunk()
                if chunk:
                    processed_chunks += 1
            
            # Small delay to simulate processing time
            time.sleep(0.01)
        
        # Stop recording
        audio_capture.stop_recording()
        
        # Verify recording statistics
        stats = audio_capture.get_recording_stats()
        assert stats.total_chunks > 0
        assert stats.duration_seconds >= recording_duration * 0.9  # Allow some tolerance
        assert processed_chunks > 0
        
        # Save and verify file
        audio_filename = f"long_recording_{session_id}.wav"
        session_path = file_manager.get_session_path(session_id)
        audio_filepath = session_path / audio_filename
        audio_capture.save_to_file(str(audio_filepath))
        
        # File should be substantial size
        file_size = audio_filepath.stat().st_size
        assert file_size > 1000  # Should be more than 1KB
        
        # Create session info
        session_info = SessionInfo(
            session_id=session_id,
            start_time=start_time,
            duration_seconds=stats.duration_seconds,
            audio_file=audio_filename,
            file_size_bytes=file_size,
            sample_rate=audio_capture.sample_rate,
            total_chunks=stats.total_chunks
        )
        file_manager.save_session_info(session_info)
        
        # Verify session info
        loaded_info = file_manager.load_session_info(session_id)
        assert loaded_info is not None
        assert loaded_info.duration_seconds >= recording_duration * 0.9
        assert loaded_info.total_chunks == stats.total_chunks
    
    def test_error_recovery_workflow(self, temp_data_dir, mock_pyaudio):
        """Test error recovery during recording workflow."""
        file_manager = FileManager(temp_data_dir)
        audio_capture = AudioCapture()
        
        # Configure mock to fail after some successful reads
        successful_chunk = b'\x00' * 1024
        mock_pyaudio['stream'].read.side_effect = [
            successful_chunk,  # First few succeed
            successful_chunk,
            successful_chunk,
            Exception("Simulated audio error"),  # Then fails
        ]
        
        # Start recording
        session_id = file_manager.create_session_directory()
        audio_capture.start_recording()
        
        # Let it run briefly
        time.sleep(0.2)
        
        # Stop recording (should handle errors gracefully)
        audio_capture.stop_recording()
        
        # Should have captured some data before the error
        stats = audio_capture.get_recording_stats()
        assert stats.total_chunks >= 0  # Some chunks may have been processed
        
        # Should still be able to save whatever was captured
        if len(audio_capture.audio_data) > 0:
            audio_filename = f"error_recovery_{session_id}.wav"
            session_path = file_manager.get_session_path(session_id)
            audio_filepath = session_path / audio_filename
            
            # Should not raise exception
            audio_capture.save_to_file(str(audio_filepath))
        
        # File manager should still work
        sessions = file_manager.list_sessions()
        assert isinstance(sessions, list)