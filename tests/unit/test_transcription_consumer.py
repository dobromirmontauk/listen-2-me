import pytest
import time
import logging
from unittest.mock import MagicMock, call

from listen2me.transcription.consumers import TranscriptionAudioConsumer
from listen2me.transcription.base import AbstractTranscriptionBackend
from listen2me.models.events import AudioEvent
from listen2me.models.transcription import TranscriptionResult

logger = logging.getLogger(__name__)


class MockTranscriptionBackend(AbstractTranscriptionBackend):
    """A mock backend that simulates transcription delay."""
    def __init__(self, processing_time: float = 0.1):
        self.processing_time = processing_time

    def transcribe_chunk(self, chunk_id: str, audio_chunk: bytes) -> TranscriptionResult:
        logger.debug(f"MockBackend: Starting transcription for {chunk_id} (will take {self.processing_time}s)")
        time.sleep(self.processing_time)
        result_text = f"Transcription for {chunk_id}"
        logger.debug(f"MockBackend: Finished transcription for {chunk_id}")
        return TranscriptionResult(
            text=result_text,
            confidence=0.99,
            processing_time=self.processing_time,
            timestamp=time.time(),
            service="mock"
        )

    def initialize(self) -> bool:
        return True

    def cleanup(self) -> None:
        pass


@pytest.fixture
def mock_backend():
    """Provides a mock transcription backend."""
    return MockTranscriptionBackend(processing_time=0.2)


@pytest.fixture
def mock_result_callback():
    """Provides a mock callback function to capture results."""
    return MagicMock()


def create_dummy_audio_event(chunk_id: int, is_final: bool = False) -> AudioEvent:
    """Creates a dummy audio event for testing."""
    return AudioEvent(
        chunk_id=f"chunk_{chunk_id}",
        audio_data=b'\x00' * 1024,
        timestamp=time.time(),
        sequence_number=chunk_id,
        final=is_final
    )


def test_consumer_shutdown_completes_with_pending_tasks(mock_backend, mock_result_callback):
    """ 
    Tests that the consumer shuts down gracefully even when there are tasks in the queue
    and a worker is busy.
    """
    # 1. Setup
    # One worker, trigger on every chunk to make testing easier
    consumer = TranscriptionAudioConsumer(
        name="test_consumer",
        backend=mock_backend,
        trigger_chunks=1,
        result_callback=mock_result_callback,
        max_concurrent_threads=1
    )

    # 2. Action
    # Put 5 tasks on the queue. The worker will start the first one.
    for i in range(5):
        consumer.on_audio_chunk(create_dummy_audio_event(i))
        time.sleep(0.01) # ensure they are processed in order

    # Give the first task a moment to be picked up by the worker
    time.sleep(0.1)
    
    # At this point, worker is busy with task 0, and 4 tasks are in the queue.
    # Now, call shutdown.
    shutdown_successful = consumer.shutdown(timeout=5.0)

    # 3. Assertions
    # The shutdown should not have timed out
    assert shutdown_successful, "Shutdown method timed out or failed"

    # All 5 tasks should have been processed and their results sent to the callback
    assert mock_result_callback.call_count == 5, "Not all tasks were processed before shutdown"
