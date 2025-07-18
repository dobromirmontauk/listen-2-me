"""Audio capture module with continuous recording capabilities."""

import pyaudio
import wave
import time
import logging
from queue import Queue, Empty
from threading import Thread, Event
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from datetime import datetime
import numpy as np


logger = logging.getLogger(__name__)


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


class AudioCapture:
    """Continuous audio capture with background recording thread."""
    
    def __init__(
        self,
        sample_rate: int = 16000,
        chunk_size: int = 1024,
        buffer_size: int = 100,
        channels: int = 1,
        format: int = pyaudio.paInt16
    ):
        """Initialize audio capture with specified parameters.
        
        Args:
            sample_rate: Audio sample rate (16kHz for Whisper compatibility)
            chunk_size: Size of each audio chunk in samples
            buffer_size: Maximum number of chunks to buffer
            channels: Number of audio channels (1 for mono)
            format: Audio format (16-bit signed int)
        """
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.channels = channels
        self.format = format
        
        # Thread-safe queue for audio chunks
        self.audio_queue = Queue(maxsize=buffer_size)
        
        # Recording thread management
        self.recording_thread: Optional[Thread] = None
        self.stop_event = Event()
        self.is_recording = False
        
        # Statistics tracking
        self.start_time: Optional[datetime] = None
        self.total_chunks = 0
        self.dropped_chunks = 0
        self.peak_level = 0.0
        
        # Store all audio data for file saving
        self.audio_data: List[bytes] = []
        
        # PyAudio instance
        self.pyaudio_instance: Optional[pyaudio.PyAudio] = None
    
    def start_recording(self) -> None:
        """Start continuous recording in background thread."""
        if self.is_recording:
            logger.warning("Recording already in progress")
            return
        
        logger.info("Starting audio recording")
        self.stop_event.clear()
        self.start_time = datetime.now()
        self.total_chunks = 0
        self.dropped_chunks = 0
        self.peak_level = 0.0
        self.audio_data.clear()
        
        # Start recording thread
        self.recording_thread = Thread(target=self._record_continuously, daemon=True)
        self.recording_thread.start()
        self.is_recording = True
    
    def stop_recording(self) -> None:
        """Stop recording and clean up resources."""
        if not self.is_recording:
            logger.warning("No recording in progress")
            return
        
        logger.info("Stopping audio recording")
        self.stop_event.set()
        
        # Wait for recording thread to finish
        if self.recording_thread and self.recording_thread.is_alive():
            self.recording_thread.join(timeout=2.0)
            if self.recording_thread.is_alive():
                logger.warning("Recording thread did not stop cleanly")
        
        self.is_recording = False
        logger.info(f"Recording stopped. Total chunks: {self.total_chunks}, "
                   f"Dropped chunks: {self.dropped_chunks}")
    
    def _record_continuously(self) -> None:
        """Internal method: continuous recording loop in background thread."""
        self.pyaudio_instance = pyaudio.PyAudio()
        stream = None
        
        try:
            # Open audio stream
            stream = self.pyaudio_instance.open(
                format=self.format,
                channels=self.channels,
                rate=self.sample_rate,
                input=True,
                frames_per_buffer=self.chunk_size,
                stream_callback=None
            )
            
            logger.info(f"Audio stream opened: {self.sample_rate}Hz, "
                       f"{self.chunk_size} samples/chunk")
            
            while not self.stop_event.is_set():
                try:
                    # Read audio chunk from microphone
                    audio_chunk = stream.read(
                        self.chunk_size, 
                        exception_on_overflow=False
                    )
                    
                    # Convert to numpy array for peak level calculation
                    audio_array = np.frombuffer(audio_chunk, dtype=np.int16)
                    peak = np.max(np.abs(audio_array)) / 32768.0  # Normalize to 0-1
                    self.peak_level = max(self.peak_level, peak)
                    
                    # Store in audio data for file saving
                    self.audio_data.append(audio_chunk)
                    self.total_chunks += 1
                    
                    # Put chunk in queue for real-time processing
                    try:
                        self.audio_queue.put_nowait(audio_chunk)
                    except:
                        # Queue is full, drop oldest chunk
                        try:
                            self.audio_queue.get_nowait()
                            self.audio_queue.put_nowait(audio_chunk)
                            self.dropped_chunks += 1
                        except:
                            self.dropped_chunks += 1
                            
                except Exception as e:
                    logger.error(f"Error reading audio: {e}")
                    break
                    
        except Exception as e:
            logger.error(f"Error opening audio stream: {e}")
        finally:
            # Clean up audio resources
            if stream:
                stream.stop_stream()
                stream.close()
            if self.pyaudio_instance:
                self.pyaudio_instance.terminate()
                self.pyaudio_instance = None
    
    def get_audio_chunk(self) -> Optional[bytes]:
        """Get next audio chunk for processing (non-blocking).
        
        Returns:
            Audio chunk bytes or None if no data available
        """
        try:
            return self.audio_queue.get_nowait()
        except Empty:
            return None
    
    def has_audio_data(self) -> bool:
        """Check if audio data is available for processing."""
        return not self.audio_queue.empty()
    
    def get_buffer_size(self) -> int:
        """Get current number of buffered chunks."""
        return self.audio_queue.qsize()
    
    def get_recording_stats(self) -> AudioStats:
        """Get current recording statistics."""
        duration = 0.0
        if self.start_time:
            duration = (datetime.now() - self.start_time).total_seconds()
        
        return AudioStats(
            is_recording=self.is_recording,
            duration_seconds=duration,
            buffer_size=self.get_buffer_size(),
            sample_rate=self.sample_rate,
            chunk_size=self.chunk_size,
            total_chunks=self.total_chunks,
            dropped_chunks=self.dropped_chunks,
            peak_level=self.peak_level
        )
    
    def save_to_file(self, filepath: str) -> None:
        """Save recorded audio to WAV file.
        
        Args:
            filepath: Path to save the WAV file
        """
        if not self.audio_data:
            logger.warning("No audio data to save")
            return
        
        try:
            with wave.open(filepath, 'wb') as wf:
                wf.setnchannels(self.channels)
                wf.setsampwidth(self.pyaudio_instance.get_sample_size(self.format) if self.pyaudio_instance else 2)
                wf.setframerate(self.sample_rate)
                
                # Write all audio data
                for chunk in self.audio_data:
                    wf.writeframes(chunk)
            
            logger.info(f"Audio saved to {filepath}")
            
        except Exception as e:
            logger.error(f"Error saving audio file: {e}")
            raise
    
    def get_audio_data_size(self) -> int:
        """Get total size of recorded audio data in bytes."""
        return sum(len(chunk) for chunk in self.audio_data)
    
    def clear_audio_data(self) -> None:
        """Clear stored audio data (useful for memory management)."""
        self.audio_data.clear()
        logger.info("Audio data cleared")
    
    def __del__(self):
        """Ensure resources are cleaned up on deletion."""
        if self.is_recording:
            self.stop_recording()