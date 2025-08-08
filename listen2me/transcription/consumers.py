"""Unified transcription consumer and audio processing components."""

import time
import asyncio
import logging
import threading
import traceback
from typing import List, Optional, Callable

from ..models.events import AudioEvent 
from ..models.transcription import TranscriptionResult
from .base import AbstractTranscriptionBackend

logger = logging.getLogger(__name__)


class TranscriptionAudioConsumer:
    """Unified transcription consumer - handles both realtime and batch transcription."""
    
    def __init__(self, 
                 name: str,
                 backend: AbstractTranscriptionBackend, 
                 trigger_chunks: int,
                 result_callback: Optional[Callable[['TranscriptionResult'], None]] = None):
        self.name = name
        self.backend = backend
        self.trigger_chunks = trigger_chunks
        self.result_callback = result_callback
        
        # Audio buffering
        self.audio_buffer = bytearray()
        self.audio_events = []
        self.chunk_start_time = None
        self.chunks_in_buffer = 0
        
        # Audio format assumptions (must match AudioCapture settings)

        
        # Calculate chunk-based triggers
        # self.target_chunks = int(self.trigger_duration * self.chunks_per_second)
        # self.min_chunks = int(0.5 * self.chunks_per_second)  # ~8 chunks for 0.5s minimum
        
        # Transcription tracking
        self.transcription_tasks = []
        self.active_threads = []
        self.chunk_counter = 0
        self.last_transcription_time = time.time()
        self.is_done = False
        self.shutdown_event = threading.Event()
        
    def on_audio_chunk(self, event: AudioEvent) -> None:
        """Process audio chunk for transcription.
        
        Args:
            event: Audio event to process
        """
        # Add audio to buffer and count chunks (don't count empty final chunks)
        self.audio_events.append(event)
        self.audio_buffer.extend(event.audio_data)
        if len(event.audio_data) > 0:
            self.chunks_in_buffer += 1
        
        if self.chunk_start_time is None:
            self.chunk_start_time = event.timestamp
        
        # Check if we should transcribe
        should_transcribe_target = self.chunks_in_buffer >= self.trigger_chunks
        should_transcribe_final = event.final and self.chunks_in_buffer > 0
        should_transcribe = should_transcribe_target or should_transcribe_final
        
        if should_transcribe:
            audio_events_copy, audio_buffer_copy = self.__copy_and_clear_audio_events()
            # Run transcription in background thread to avoid blocking
            thread = threading.Thread(
                target=self._run_transcription_sync,
                args=(audio_events_copy, audio_buffer_copy, event.final),
                daemon=True
            )
            thread.name = f"transcription_{self.name}_{self.chunk_counter}"
            self.active_threads.append(thread)
            thread.start()

    def __copy_and_clear_audio_events(self):
        """Copy and clear audio events."""
        audio_events_copy = self.audio_events.copy()
        audio_buffer_copy = bytes(self.audio_buffer)  # Convert bytearray to bytes
        self.audio_events.clear()
        self.audio_buffer.clear()
        self.chunks_in_buffer = 0
        self.chunk_start_time = None
        return audio_events_copy, audio_buffer_copy
    
    def _run_transcription_sync(self, audio_events: List[AudioEvent], audio_buffer: bytes, is_final: bool = False) -> None:
        """Run transcription in a synchronous manner for threading."""
        current_thread = threading.current_thread()
        logger.debug(f"Running transcription in thread: {current_thread.name}")
        try:
            # Create new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._transcribe_buffer(audio_events, audio_buffer, is_final))
        except Exception as e:
            logger.error(f"Error in transcription thread: {e}")
            logger.error(traceback.format_exc())
        finally:
            loop.close()
            # Remove this thread from active threads
            if current_thread in self.active_threads:
                self.active_threads.remove(current_thread)
    
    async def _transcribe_buffer(self, audio_events: List[AudioEvent], audio_buffer: bytes, is_final: bool = False) -> None:
        self.chunk_counter += 1
        suffix = f"{self.chunk_counter}-final" if is_final else str(self.chunk_counter)
        first_event = audio_events[0]
        last_event = audio_events[-1]

        chunk_id = f"{self.name}.{first_event.chunk_id}-{last_event.chunk_id}.{suffix}"
        logger.info(f"Transcribing chunk: {chunk_id} using {self.name}")
        task = asyncio.create_task(
            self._transcribe_with_backend(self.backend, audio_buffer, chunk_id, is_final)
        )
        self.transcription_tasks.append(task)
        result = await task

        # Attach accurate audio timing based on AudioEvent timestamps (recording time, not wall clock)
        audio_start_time = first_event.timestamp
        # last_event.chunk_duration_ms may be None for empty final events; default to 0 in that case
        last_duration_s = (last_event.chunk_duration_ms or 0) / 1000.0
        audio_end_time = last_event.timestamp + last_duration_s

        result.audio_start_time = audio_start_time
        result.audio_end_time = audio_end_time
        result.is_final = is_final
        logger.info(f"✅ {self.name.upper()}: '{result.text}' ({result.confidence:.1%}) via {result.service}")
        
        self.result_callback(result)
        
    
    async def _transcribe_with_backend(self, backend: AbstractTranscriptionBackend, 
                                     audio_data: bytes, chunk_id: str, 
                                     is_final: bool = False) -> Optional[TranscriptionResult]:
        # Create transcription result with timing
        result = backend.transcribe_chunk(chunk_id, audio_data)
        
        # Enhance with our metadata
        result.chunk_id = chunk_id
        # result.audio_start_time = start_time
        # result.audio_end_time = end_time
        result.transcription_mode = self.name

        if is_final:
            self.is_done = True

        return result
    
    def shutdown(self, timeout: float = 30.0) -> bool:
        """Shutdown the consumer and wait for all pending tasks to complete.
        
        Args:
            timeout: Maximum time to wait for tasks to complete in seconds
            
        Returns:
            True if all tasks completed within timeout, False otherwise
        """
        logger.info(f"Shutting down {self.name} consumer with {len(self.active_threads)} active threads")
        self.shutdown_event.set()
        
        # Wait for all active threads to complete
        start_time = time.time()
        while self.active_threads and (time.time() - start_time) < timeout:
            remaining_threads = [t for t in self.active_threads if t.is_alive()]
            if not remaining_threads:
                break
            logger.debug(f"{self.name} consumer: {len(remaining_threads)} threads still running")
            time.sleep(0.1)
        
        # Check if any threads are still running
        still_running = [t for t in self.active_threads if t.is_alive()]
        if still_running:
            logger.warning(f"{self.name} consumer: {len(still_running)} threads did not complete within {timeout}s")
            return False
        else:
            logger.info(f"{self.name} consumer shutdown complete")
            return True
    
    def get_pending_task_count(self) -> int:
        """Get the number of pending transcription tasks.
        
        Returns:
            Number of active transcription threads
        """
        return len([t for t in self.active_threads if t.is_alive()])