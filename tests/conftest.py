"""Pytest configuration and fixtures for Listen2Me tests."""

import pytest
import tempfile
import os
import logging
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
import numpy as np
import wave


# Configure logging for tests
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@pytest.fixture
def temp_data_dir():
    """Create temporary directory for test data."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir


@pytest.fixture
def sample_audio_chunk():
    """Generate a sample audio chunk for testing."""
    # Generate 1024 samples of 16-bit audio (sine wave)
    sample_rate = 16000
    duration = 1024 / sample_rate  # ~0.064 seconds
    freq = 440  # A4 note
    
    t = np.linspace(0, duration, 1024, False)
    wave_data = np.sin(2 * np.pi * freq * t)
    
    # Convert to 16-bit integers
    audio_data = (wave_data * 32767).astype(np.int16)
    return audio_data.tobytes()


@pytest.fixture
def mock_pyaudio():
    """Mock PyAudio for testing without actual audio hardware."""
    with patch('pyaudio.PyAudio') as mock_pyaudio_class:
        mock_pyaudio_instance = Mock()
        mock_stream = Mock()
        
        # Configure mock stream
        mock_stream.read.return_value = b'\x00' * 2048  # Silent audio
        mock_stream.stop_stream.return_value = None
        mock_stream.close.return_value = None
        
        # Configure mock PyAudio instance
        mock_pyaudio_instance.open.return_value = mock_stream
        mock_pyaudio_instance.terminate.return_value = None
        mock_pyaudio_instance.get_sample_size.return_value = 2
        
        # Configure mock PyAudio class
        mock_pyaudio_class.return_value = mock_pyaudio_instance
        
        yield {
            'class': mock_pyaudio_class,
            'instance': mock_pyaudio_instance,
            'stream': mock_stream
        }


@pytest.fixture
def sample_audio_file(temp_data_dir, sample_audio_chunk):
    """Create a sample WAV file for testing."""
    file_path = Path(temp_data_dir) / "test_audio.wav"
    
    # Create a simple WAV file with test data
    with wave.open(str(file_path), 'wb') as wf:
        wf.setnchannels(1)  # Mono
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(16000)  # 16kHz
        
        # Write multiple chunks to create a longer file
        for _ in range(100):  # ~6.4 seconds of audio
            wf.writeframes(sample_audio_chunk)
    
    return str(file_path)


@pytest.fixture(scope="session")
def test_config():
    """Test configuration settings."""
    return {
        "audio": {
            "sample_rate": 16000,
            "chunk_size": 1024,
            "buffer_size": 10,
            "channels": 1
        },
        "storage": {
            "max_age_days": 30
        }
    }


@pytest.fixture
def mock_audio_capture():
    """Mock AudioCapture for testing."""
    from listen2me.audio.capture import AudioStats
    
    mock = Mock()
    mock.is_recording = False
    mock.sample_rate = 16000
    mock.chunk_size = 1024
    mock.channels = 1
    
    # Mock methods
    mock.start_recording.return_value = None
    mock.stop_recording.return_value = None
    mock.get_audio_chunk.return_value = b'\x00' * 1024
    mock.has_audio_data.return_value = True
    mock.get_buffer_size.return_value = 5
    mock.save_to_file.return_value = None
    mock.get_audio_data_size.return_value = 10240
    mock.clear_audio_data.return_value = None
    
    # Mock stats
    mock.get_recording_stats.return_value = AudioStats(
        is_recording=True,
        duration_seconds=10.0,
        buffer_size=5,
        sample_rate=16000,
        chunk_size=1024,
        total_chunks=100,
        dropped_chunks=0,
        peak_level=0.5
    )
    
    return mock


@pytest.fixture
def audio_test_data():
    """Generate various audio test data patterns."""
    def generate_audio(pattern="sine", duration_seconds=1.0, sample_rate=16000):
        """Generate audio data for testing.
        
        Args:
            pattern: Type of audio pattern ('sine', 'noise', 'silence')
            duration_seconds: Duration of audio
            sample_rate: Sample rate in Hz
            
        Returns:
            bytes: Audio data as bytes
        """
        samples = int(duration_seconds * sample_rate)
        
        if pattern == "sine":
            # Generate sine wave
            t = np.linspace(0, duration_seconds, samples, False)
            wave_data = np.sin(2 * np.pi * 440 * t)  # 440 Hz sine wave
        elif pattern == "noise":
            # Generate white noise
            wave_data = np.random.uniform(-1, 1, samples)
        elif pattern == "silence":
            # Generate silence
            wave_data = np.zeros(samples)
        else:
            raise ValueError(f"Unknown pattern: {pattern}")
        
        # Convert to 16-bit integers
        audio_data = (wave_data * 32767).astype(np.int16)
        return audio_data.tobytes()
    
    return generate_audio


@pytest.fixture
def performance_timer():
    """Timer fixture for performance testing."""
    import time
    
    class Timer:
        def __init__(self):
            self.start_time = None
            self.end_time = None
        
        def start(self):
            self.start_time = time.time()
        
        def stop(self):
            self.end_time = time.time()
        
        def elapsed(self):
            if self.start_time is None or self.end_time is None:
                return None
            return self.end_time - self.start_time
        
        def __enter__(self):
            self.start()
            return self
        
        def __exit__(self, *args):
            self.stop()
    
    return Timer()