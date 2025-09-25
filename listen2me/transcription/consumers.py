"""Unified transcription consumer and audio processing components."""

import time
import asyncio
import logging
import threading
import traceback
import queue
from typing import List, Optional, Callable, NamedTuple

from ..models.events import AudioEvent
from ..models.transcription import TranscriptionResult
from .base import AbstractTranscriptionBackend

logger = logging.getLogger(__name__)


class TranscriptionTask(NamedTuple):
    """A task to be processed by a worker thread."""
    audio_events: List[AudioEvent]
    audio_buffer: bytes
    is_final: bool


class TranscriptionAudioConsumer:
    """Manages a pool of worker threads to process transcription tasks from a queue."""

    def __init__(self,
                 name: str,
                 backend: AbstractTranscriptionBackend,
                 trigger_chunks: int,
                 result_callback: Optional[Callable[['TranscriptionResult'],
                                                    None]] = None,
                 max_concurrent_threads: int = 4):
        self.name = name
        self.backend = backend
        self.trigger_chunks = trigger_chunks
        self.result_callback = result_callback
        self.max_concurrent_threads = max_concurrent_threads

        # Audio buffering
        self.audio_buffer = bytearray()
        self.audio_events = []
        self.chunk_start_time = None
        self.chunks_in_buffer = 0

        # Thread-safe queue for transcription tasks
        self.task_queue = queue.Queue()
        self.worker_threads = []
        self.chunk_counter = 0
        self.shutdown_event = threading.Event()

        self._start_workers()

    def _start_workers(self):
        """Create and start the pool of worker threads."""
        for i in range(self.max_concurrent_threads):
            thread = threading.Thread(target=self._worker_loop)
            thread.name = f"worker_{self.name}_{i}"
            thread.daemon = True
            thread.start()
            self.worker_threads.append(thread)
        logger.info(
            f"Started {len(self.worker_threads)} {self.name} consumer workers")

    def _worker_loop(self):
        """The main loop for each worker thread. Initializes an asyncio loop."""
        thread_name = threading.current_thread().name
        logger.debug(f"Worker thread {thread_name} starting")
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            while True:
                # Block indefinitely until a task is available
                task = self.task_queue.get()

                if task is None:
                    # Sentinel value received, time to exit
                    logger.debug(f"Worker {thread_name} received sentinel, exiting.")
                    self.task_queue.task_done()
                    break

                logger.debug(f"Worker {thread_name} got task with chunks starting {task.audio_events[0].chunk_id}")
                try:
                    loop.run_until_complete(self._transcribe_buffer(task.audio_events, task.audio_buffer, task.is_final))
                except Exception as e:
                    logger.error(f"Unhandled exception in transcription task for {thread_name}: {e}", exc_info=True)
                finally:
                    logger.debug(f"Worker {thread_name} marking task as done.")
                    self.task_queue.task_done()
        finally:
            loop.close()
            logger.debug(f"Worker thread {thread_name} exiting and closing its event loop.")

    def on_audio_chunk(self, event: AudioEvent) -> None:
        """Process audio chunk and add a task to the queue if needed."""
        if self.shutdown_event.is_set():
            return

        self.audio_events.append(event)
        self.audio_buffer.extend(event.audio_data)
        if len(event.audio_data) > 0:
            self.chunks_in_buffer += 1

        if self.chunk_start_time is None:
            self.chunk_start_time = event.timestamp

        should_transcribe_target = self.chunks_in_buffer >= self.trigger_chunks
        should_transcribe_final = event.final and self.chunks_in_buffer > 0

        if should_transcribe_target or should_transcribe_final:
            audio_events_copy, audio_buffer_copy = self._copy_and_clear_audio_buffer(
            )
            task = TranscriptionTask(audio_events=audio_events_copy,
                                     audio_buffer=audio_buffer_copy,
                                     is_final=event.final)
            logger.debug(f"Putting task on queue for {self.name}; "
                         f"buffer_size={len(audio_buffer_copy)} bytes; "
                         f"events={len(audio_events_copy)}")
            self.task_queue.put(task)

    def _copy_and_clear_audio_buffer(self):
        """Atomically copy and clear the audio buffer."""
        audio_events_copy = self.audio_events.copy()
        audio_buffer_copy = bytes(self.audio_buffer)
        self.audio_events.clear()
        self.audio_buffer.clear()
        self.chunks_in_buffer = 0
        self.chunk_start_time = None
        return audio_events_copy, audio_buffer_copy

    async def _transcribe_buffer(self,
                                 audio_events: List[AudioEvent],
                                 audio_buffer: bytes,
                                 is_final: bool = False) -> None:
        """The core transcription logic for a single buffer."""
        if not audio_buffer:
            logger.warning("Skipping transcription for empty audio buffer")
            return

        self.chunk_counter += 1
        first_event = audio_events[0]
        last_event = audio_events[-1]
        suffix = f"{self.chunk_counter}-final" if is_final else str(
            self.chunk_counter)
        chunk_id = f"{self.name}.{first_event.chunk_id}-{last_event.chunk_id}.{suffix}"

        logger.info(f"Transcribing chunk: {chunk_id} using {self.name}")
        result = await self._transcribe_with_backend(self.backend,
                                                     audio_buffer, chunk_id,
                                                     is_final)

        if result:
            audio_start_time = first_event.timestamp
            last_duration_s = (last_event.chunk_duration_ms or 0) / 1000.0
            audio_end_time = last_event.timestamp + last_duration_s

            result.audio_start_time = audio_start_time
            result.audio_end_time = audio_end_time
            result.is_final = is_final

            logger.info(
                f"✅ {self.name.upper()}: '{result.text}' ({result.confidence:.1%}) via {result.service}"
            )
            if self.result_callback:
                self.result_callback(result)

    async def _transcribe_with_backend(
            self,
            backend: AbstractTranscriptionBackend,
            audio_data: bytes,
            chunk_id: str,
            is_final: bool = False) -> Optional[TranscriptionResult]:
        """Calls the backend and enhances the result."""
        result = backend.transcribe_chunk(chunk_id, audio_data)
        if result:
            result.chunk_id = chunk_id
            result.transcription_mode = self.name
        return result

    def shutdown(self, timeout: float = 30.0) -> bool:
        """Gracefully shut down the consumer and its worker threads using a non-blocking poll."""
        logger.info(
            f"[dmontauk] Shutting down {self.name} consumer with polling...")
        self.shutdown_event.set()

        # Non-blocking wait for the queue to be processed
        logger.info(
            f"[{self.name}] Waiting up to {timeout}s for task queue to empty..."
        )
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.task_queue.empty(
            ) and self.task_queue.unfinished_tasks == 0:
                logger.info(
                    f"[{self.name}] Task queue is empty. Proceeding with shutdown."
                )
                break
            logger.debug(
                f"[{self.name}] Queue not empty. Unfinished tasks: {self.task_queue.unfinished_tasks}. Waiting..."
            )
            time.sleep(1)
        else:  # This runs if the loop finishes without a break
            logger.warning(
                f"[{self.name}] Timeout reached while waiting for queue. {self.task_queue.unfinished_tasks} tasks remain."
            )

        # Now, stop the worker threads
        logger.debug(
            f"[{self.name}] Sending {len(self.worker_threads)} sentinel values to workers."
        )
        for _ in self.worker_threads:
            self.task_queue.put(None)

        # Wait for all worker threads to terminate
        logger.debug(
            f"[{self.name}] Waiting for worker threads to terminate...")
        for thread in self.worker_threads:
            thread.join(2.0)  # Give each thread a couple of seconds to die
            if thread.is_alive():
                logger.warning(
                    f"Worker thread {thread.name} did not terminate cleanly.")

        logger.info(f"{self.name} consumer shutdown complete.")
        return True

    def get_pending_task_count(self) -> int:
        """Get the number of pending transcription tasks."""
        return self.task_queue.qsize()
