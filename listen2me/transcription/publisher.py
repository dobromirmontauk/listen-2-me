"""Transcription publisher module for pub/sub event publishing."""

import logging
from typing import Callable
from pubsub import pub
from ..models.transcription import TranscriptionResult

logger = logging.getLogger(__name__)


class TranscriptionPublisher:
    """Publishes transcription results using pubsub.pub for pub/sub architecture."""
    
    def __init__(self, topic: str):
        """Initialize transcription publisher.
        
        Args:
            topic: Pub/sub topic name for transcription results
        """
        self.topic = topic
        logger.info(f"TranscriptionPublisher initialized with topic: {topic}")
    
    def publish_transcription_result(self, result: TranscriptionResult) -> None:
        """Publish a transcription result to the pub/sub topic.
        
        Args:
            result: TranscriptionResult to publish
        """
        pub.sendMessage(self.topic, result=result)
        logger.debug(f"Published transcription result: {result.chunk_id} ({result.transcription_mode})")
    
    def get_callback(self) -> Callable[[TranscriptionResult], None]:
        """Get callback function for TranscriptionConsumer to use.
        
        Returns:
            Callback function that publishes transcription results
        """
        return self.publish_transcription_result
