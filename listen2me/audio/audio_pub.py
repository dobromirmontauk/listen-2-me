"""Audio publisher module for pub/sub event publishing."""

import logging
from typing import Callable
from pubsub import pub
from ..models.events import AudioEvent

logger = logging.getLogger(__name__)


class AudioPublisher:
    """Publishes audio events using pubsub.pub for pub/sub architecture."""
    
    def __init__(self, topic: str = "audio_events"):
        """Initialize audio publisher.
        
        Args:
            topic: Pub/sub topic name for audio events
        """
        self.topic = topic
        logger.info(f"AudioPublisher initialized with topic: {topic}")
    
    def publish_audio_event(self, audio_event: AudioEvent) -> None:
        """Publish an audio event to the pub/sub topic.
        
        Args:
            audio_event: AudioEvent to publish
        """
        pub.sendMessage(self.topic, event=audio_event)
        # logger.debug(f"Published audio event: {audio_event.chunk_id}")