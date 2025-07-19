"""Rolling audio buffer for batch transcription processing."""

import time
import logging
import threading
from collections import deque
from typing import Optional, Tuple
from ..models.audio import AudioFrame

logger = logging.getLogger(__name__)




class RollingAudioBuffer:
    """Rolling audio buffer that maintains a fixed duration of audio for batch processing."""
    
    def __init__(self, duration_seconds: float, sample_rate: int = 16000, channels: int = 1):
        """Initialize rolling audio buffer.
        
        Args:
            duration_seconds: How many seconds of audio to keep in buffer
            sample_rate: Audio sample rate
            channels: Number of audio channels
        """
        self.duration_seconds = duration_seconds
        self.sample_rate = sample_rate
        self.channels = channels
        self.bytes_per_sample = 2  # 16-bit audio
        
        # Calculate buffer capacity
        self.bytes_per_second = sample_rate * channels * self.bytes_per_sample
        self.max_buffer_bytes = int(self.bytes_per_second * duration_seconds)
        
        # Thread-safe buffer
        self.buffer = deque()
        self.lock = threading.Lock()
        self.total_bytes = 0
        self.frame_counter = 0
        self.start_time = None
        
        logger.info(f"RollingAudioBuffer initialized: {duration_seconds}s capacity, "
                   f"{self.max_buffer_bytes} bytes max")
    
    def add_audio_chunk(self, audio_data: bytes) -> None:
        """Add audio chunk to the rolling buffer."""
        if not audio_data:
            return
            
        current_time = time.time()
        if self.start_time is None:
            self.start_time = current_time
            
        with self.lock:
            # Create audio frame with timestamp
            frame = AudioFrame(
                data=audio_data,
                timestamp=current_time,
                frame_number=self.frame_counter
            )
            self.frame_counter += 1
            
            # Add to buffer
            self.buffer.append(frame)
            self.total_bytes += len(audio_data)
            
            # Remove old frames to maintain buffer size
            while self.total_bytes > self.max_buffer_bytes and self.buffer:
                old_frame = self.buffer.popleft()
                self.total_bytes -= len(old_frame.data)
            
            logger.debug(f"Added audio chunk: {len(audio_data)} bytes, "
                        f"buffer now has {len(self.buffer)} frames ({self.total_bytes} bytes)")
    
    def get_audio_window(self, duration_seconds: float, 
                        start_offset_seconds: float = 0.0) -> Optional[Tuple[bytes, float, float]]:
        """Get a window of audio from the buffer.
        
        Args:
            duration_seconds: How many seconds of audio to extract
            start_offset_seconds: How many seconds back from current time to start
            
        Returns:
            Tuple of (audio_bytes, start_timestamp, end_timestamp) or None if insufficient data
        """
        if not self.buffer:
            return None
            
        current_time = time.time()
        target_start_time = current_time - start_offset_seconds - duration_seconds
        target_end_time = current_time - start_offset_seconds
        
        with self.lock:
            # Find frames within the target time window
            selected_frames = []
            
            for frame in self.buffer:
                if target_start_time <= frame.timestamp <= target_end_time:
                    selected_frames.append(frame)
            
            if not selected_frames:
                logger.debug(f"No frames found in time window {target_start_time:.3f} - {target_end_time:.3f}")
                return None
            
            # Combine audio data from selected frames
            audio_chunks = [frame.data for frame in selected_frames]
            combined_audio = b''.join(audio_chunks)
            
            actual_start_time = selected_frames[0].timestamp
            actual_end_time = selected_frames[-1].timestamp
            
            logger.debug(f"Extracted audio window: {len(selected_frames)} frames, "
                        f"{len(combined_audio)} bytes, "
                        f"time range {actual_start_time:.3f} - {actual_end_time:.3f}")
            
            return combined_audio, actual_start_time, actual_end_time
    
    def get_buffer_stats(self) -> dict:
        """Get buffer statistics."""
        with self.lock:
            oldest_timestamp = self.buffer[0].timestamp if self.buffer else None
            newest_timestamp = self.buffer[-1].timestamp if self.buffer else None
            buffer_duration = (newest_timestamp - oldest_timestamp) if oldest_timestamp and newest_timestamp else 0
            
            return {
                "frame_count": len(self.buffer),
                "total_bytes": self.total_bytes,
                "buffer_duration_seconds": buffer_duration,
                "oldest_timestamp": oldest_timestamp,
                "newest_timestamp": newest_timestamp,
                "capacity_seconds": self.duration_seconds,
                "capacity_bytes": self.max_buffer_bytes
            }
    
    def clear(self) -> None:
        """Clear the buffer."""
        with self.lock:
            self.buffer.clear()
            self.total_bytes = 0
            self.frame_counter = 0
            self.start_time = None
            logger.debug("Audio buffer cleared")