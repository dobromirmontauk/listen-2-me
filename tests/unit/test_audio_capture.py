"""Unit tests for AudioCapture class."""

import pytest
import time
import threading
from unittest.mock import Mock, patch, call
import numpy as np
from listen2me.audio.capture import AudioCapture, AudioStats


@pytest.mark.unit
class TestAudioCapture:
    """Test cases for AudioCapture class."""
    
    def test_initialization(self):
        """Test AudioCapture initialization with default parameters."""
        capture = AudioCapture()
        
        assert capture.sample_rate == 16000
        assert capture.chunk_size == 1024
        assert capture.channels == 1
        assert capture.is_recording is False
        assert capture.total_chunks == 0
        assert capture.dropped_chunks == 0
        assert capture.peak_level == 0.0
        assert len(capture.audio_data) == 0
    
    def test_initialization_custom_parameters(self):
        """Test AudioCapture initialization with custom parameters."""
        capture = AudioCapture(
            sample_rate=44100,
            chunk_size=2048,
            buffer_size=50,
            channels=2
        )
        
        assert capture.sample_rate == 44100
        assert capture.chunk_size == 2048
        assert capture.channels == 2
        assert capture.audio_queue.maxsize == 50
    
    def test_start_recording(self, mock_pyaudio):
        """Test starting audio recording."""
        capture = AudioCapture()
        
        # Mock the recording method to prevent actual recording
        with patch.object(capture, '_record_continuously') as mock_record:
            capture.start_recording()
            
            assert capture.is_recording is True
            assert capture.start_time is not None
            assert capture.recording_thread is not None
            assert capture.recording_thread.daemon is True
            mock_record.assert_called_once()
    
    def test_start_recording_already_recording(self, mock_pyaudio):
        """Test starting recording when already recording."""
        capture = AudioCapture()
        capture.is_recording = True
        
        with patch.object(capture, '_record_continuously') as mock_record:
            capture.start_recording()
            
            # Should not start new recording
            mock_record.assert_not_called()
    
    def test_stop_recording(self, mock_pyaudio):
        """Test stopping audio recording."""
        capture = AudioCapture()
        
        # Start recording first
        with patch.object(capture, '_record_continuously'):
            capture.start_recording()
            
            # Stop recording
            capture.stop_recording()
            
            assert capture.is_recording is False
            assert capture.stop_event.is_set()
    
    def test_stop_recording_not_recording(self, mock_pyaudio):
        """Test stopping recording when not recording."""
        capture = AudioCapture()
        
        # Should handle gracefully
        capture.stop_recording()
        assert capture.is_recording is False
    
    def test_get_audio_chunk_empty_queue(self, mock_pyaudio):
        """Test getting audio chunk from empty queue."""
        capture = AudioCapture()
        
        chunk = capture.get_audio_chunk()
        assert chunk is None
    
    def test_get_audio_chunk_with_data(self, mock_pyaudio, sample_audio_chunk):
        """Test getting audio chunk with data in queue."""
        capture = AudioCapture()
        
        # Put test data in queue
        capture.audio_queue.put(sample_audio_chunk)
        
        chunk = capture.get_audio_chunk()
        assert chunk == sample_audio_chunk
    
    def test_has_audio_data(self, mock_pyaudio, sample_audio_chunk):
        """Test checking if audio data is available."""
        capture = AudioCapture()
        
        # Initially empty
        assert capture.has_audio_data() is False
        
        # Add data
        capture.audio_queue.put(sample_audio_chunk)
        assert capture.has_audio_data() is True
        
        # Remove data
        capture.get_audio_chunk()
        assert capture.has_audio_data() is False
    
    def test_get_buffer_size(self, mock_pyaudio, sample_audio_chunk):
        """Test getting buffer size."""
        capture = AudioCapture()
        
        assert capture.get_buffer_size() == 0
        
        # Add some chunks
        capture.audio_queue.put(sample_audio_chunk)
        capture.audio_queue.put(sample_audio_chunk)
        
        assert capture.get_buffer_size() == 2
    
    def test_get_recording_stats(self, mock_pyaudio):
        """Test getting recording statistics."""
        capture = AudioCapture()
        
        stats = capture.get_recording_stats()
        
        assert isinstance(stats, AudioStats)
        assert stats.is_recording is False
        assert stats.duration_seconds >= 0
        assert stats.buffer_size == 0
        assert stats.sample_rate == 16000
        assert stats.chunk_size == 1024
        assert stats.total_chunks == 0
        assert stats.dropped_chunks == 0
        assert stats.peak_level == 0.0
    
    def test_get_recording_stats_while_recording(self, mock_pyaudio):
        """Test getting recording statistics while recording."""
        capture = AudioCapture()
        
        with patch.object(capture, '_record_continuously'):
            capture.start_recording()
            
            # Wait a bit to ensure some time passes
            time.sleep(0.1)
            
            stats = capture.get_recording_stats()
            assert stats.is_recording is True
            assert stats.duration_seconds > 0
            
            capture.stop_recording()
    
    def test_save_to_file_no_data(self, mock_pyaudio, temp_data_dir):
        """Test saving audio to file with no data."""
        capture = AudioCapture()
        filepath = f"{temp_data_dir}/test_empty.wav"
        
        # Should handle gracefully
        capture.save_to_file(filepath)
    
    def test_save_to_file_with_data(self, mock_pyaudio, temp_data_dir, sample_audio_chunk):
        """Test saving audio to file with data."""
        capture = AudioCapture()
        filepath = f"{temp_data_dir}/test_with_data.wav"
        
        # Add some test data
        capture.audio_data = [sample_audio_chunk, sample_audio_chunk]
        
        # Mock PyAudio instance for get_sample_size
        capture.pyaudio_instance = Mock()
        capture.pyaudio_instance.get_sample_size.return_value = 2
        
        capture.save_to_file(filepath)
        
        # Verify file was created
        import os
        assert os.path.exists(filepath)
        assert os.path.getsize(filepath) > 0
    
    def test_get_audio_data_size(self, mock_pyaudio, sample_audio_chunk):
        """Test getting audio data size."""
        capture = AudioCapture()
        
        assert capture.get_audio_data_size() == 0
        
        # Add some data
        capture.audio_data = [sample_audio_chunk, sample_audio_chunk]
        expected_size = len(sample_audio_chunk) * 2
        
        assert capture.get_audio_data_size() == expected_size
    
    def test_clear_audio_data(self, mock_pyaudio, sample_audio_chunk):
        """Test clearing audio data."""
        capture = AudioCapture()
        
        # Add some data
        capture.audio_data = [sample_audio_chunk, sample_audio_chunk]
        assert len(capture.audio_data) == 2
        
        # Clear data
        capture.clear_audio_data()
        assert len(capture.audio_data) == 0
    
    @pytest.mark.slow
    def test_record_continuously_integration(self, mock_pyaudio):
        """Integration test for continuous recording."""
        capture = AudioCapture(chunk_size=512, buffer_size=10)
        
        # Configure mock to return test data
        test_chunk = b'\x00' * 1024  # 1024 bytes of silence
        mock_pyaudio['stream'].read.return_value = test_chunk
        
        # Start recording
        capture.start_recording()
        
        # Let it run for a short time
        time.sleep(0.2)
        
        # Stop recording
        capture.stop_recording()
        
        # Verify recording occurred
        assert capture.total_chunks > 0
        assert len(capture.audio_data) > 0
        
        # Verify data is available in queue
        chunks_available = 0
        while capture.has_audio_data():
            chunk = capture.get_audio_chunk()
            if chunk:
                chunks_available += 1
        
        assert chunks_available > 0
    
    def test_peak_level_calculation(self, mock_pyaudio):
        """Test peak level calculation during recording."""
        capture = AudioCapture()
        
        # Create audio data with known peak
        samples = np.array([0, 16383, 0, -16383, 0], dtype=np.int16)  # 50% peak
        test_chunk = samples.tobytes()
        
        # Mock stream to return our test data
        mock_pyaudio['stream'].read.return_value = test_chunk
        
        # Start and quickly stop recording
        capture.start_recording()
        time.sleep(0.1)
        capture.stop_recording()
        
        # Peak should be approximately 0.5 (16383 / 32768)
        assert capture.peak_level > 0.4
        assert capture.peak_level < 0.6
    
    def test_queue_overflow_handling(self, mock_pyaudio):
        """Test handling of queue overflow (buffer full)."""
        capture = AudioCapture(buffer_size=2)  # Very small buffer
        
        # Configure mock to return data continuously
        test_chunk = b'\x00' * 1024
        mock_pyaudio['stream'].read.return_value = test_chunk
        
        # Start recording
        capture.start_recording()
        
        # Let it run long enough to overflow buffer
        time.sleep(0.2)
        
        # Stop recording
        capture.stop_recording()
        
        # Should have dropped some chunks
        assert capture.dropped_chunks > 0
        
        # Buffer should not exceed maximum size
        assert capture.get_buffer_size() <= 2
    
    def test_destructor_cleanup(self, mock_pyaudio):
        """Test that destructor properly cleans up resources."""
        capture = AudioCapture()
        
        # Test that destructor calls stop_recording when is_recording is True
        with patch.object(AudioCapture, 'stop_recording') as mock_stop:
            capture.is_recording = True
            
            # Trigger destructor
            capture.__del__()
            
            # Should call stop_recording
            mock_stop.assert_called_once()