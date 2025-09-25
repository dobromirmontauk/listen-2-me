"""Audio capture module with continuous recording capabilities and event publishing."""

import pyaudio
import wave
import time
import logging
from threading import Thread, Event
from typing import Optional, Dict, Any, List, Callable
from ..models.audio import AudioStats
from ..models.events import AudioEvent
from datetime import datetime
import numpy as np


logger = logging.getLogger(__name__)


class AudioCapture:
    """Continuous audio capture with event publishing for pub/sub architecture."""
    
    def __init__(
        self,
        callback: Callable[[AudioEvent], None],
        sample_rate: int = 16000,
        chunk_size: int = 1024,
        channels: int = 1,
        format: int = pyaudio.paInt16,
    ):
        """Initialize audio capture with specified parameters.
        
        Args:
            sample_rate: Audio sample rate (16kHz for Whisper compatibility)
            chunk_size: Size of each audio chunk in samples
            channels: Number of audio channels (1 for mono)
            format: Audio format (16-bit signed int)
        """
        self.audio_event_callback = callback
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.channels = channels
        self.format = format
        
        # Recording thread management
        self.recording_thread: Optional[Thread] = None
        self.stop_event = Event()
        self.is_recording = False
        
        # Statistics tracking
        self.start_time: Optional[datetime] = None
        self.total_chunks = 0
        
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
        
        # Start recording thread
        self.recording_thread = Thread(target=self._record_continuously, daemon=True)
        self.recording_thread.name = "AudioCaptureThread"
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
        logger.info(f"Recording stopped. Total chunks: {self.total_chunks}")
        
    def __open_audio_stream(self) -> pyaudio.Stream:
        # Open audio stream
        self.pyaudio_instance = pyaudio.PyAudio()
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
        return stream
    
    def __read_audio_chunk(self, stream: pyaudio.Stream) -> bytes:
        audio_chunk = stream.read(
            self.chunk_size, 
            # TODO(dmontauk): should this be true?
            exception_on_overflow=False
        )
        
        self.total_chunks += 1
        return audio_chunk
    
    def __publish_audio_event(self, audio_chunk: bytes) -> None:
        # Create audio event
        audio_event = AudioEvent(
            chunk_id=f"chunk_{self.total_chunks}",
            audio_data=audio_chunk,
            timestamp=time.time(),
            sequence_number=self.total_chunks,
            sample_rate=self.sample_rate,
            channels=self.channels,
            final=self.stop_event.is_set()
        )
        
        # Publish event (non-blocking)
        self.audio_event_callback(audio_event)
    
    def _record_continuously(self) -> None:
        """Internal method: continuous recording loop in background thread."""
        try:
            stream = self.__open_audio_stream()
            while not self.stop_event.is_set():
                audio_chunk = self.__read_audio_chunk(stream)
                self.__publish_audio_event(audio_chunk)
            # Publish final event, so consumers know we are done
            audio_chunk = self.__read_audio_chunk(stream)
            self.__publish_audio_event(audio_chunk)
        finally:
            # Clean up audio resources
            if stream:
                stream.stop_stream()
                stream.close()
            if self.pyaudio_instance:
                self.pyaudio_instance.terminate()
                self.pyaudio_instance = None
    
    def get_recording_stats(self) -> AudioStats:
        """Get current recording statistics."""
        duration = 0.0
        if self.start_time:
            duration = (datetime.now() - self.start_time).total_seconds()
        
        return AudioStats(
            is_recording=self.is_recording,
            duration_seconds=duration,
            buffer_size=0,  # No buffer in pub/sub mode
            sample_rate=self.sample_rate,
            chunk_size=self.chunk_size,
            total_chunks=self.total_chunks,
        )
    
    def __del__(self):
        """Ensure resources are cleaned up on deletion."""
        if self.is_recording:
            self.stop_recording()