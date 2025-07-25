"""Transcription service that manages transcription consumers."""

import logging
from pubsub import pub
from typing import Dict, Any 

from listen2me.transcription.consumers import TranscriptionAudioConsumer
from listen2me.transcription.publisher import TranscriptionPublisher
from ..transcription import GoogleSpeechBackend
from ..config import Listen2MeConfig

logger = logging.getLogger(__name__)


class TranscriptionService:
    """Service that manages transcription consumers and their lifecycle."""
    
    def __init__(self, config: Listen2MeConfig, topic: str):
        """Initialize transcription service.
        
        Args:
            config: Application configuration
            pubsub: Pub/sub manager for communication
        """
        self.config = config
        self.topic = topic
        self.is_running = False
    
    def start_transcription_consumers(self, chunks_per_second: float) -> Dict[str, Any]:
        """Start all configured transcription consumers.
        
        Args:
            chunks_per_second: Number of audio chunks per second (calculated from sample_rate / chunk_size)
            
        Returns:
            Result dictionary with success status
        """
        backend = self._create_google_speech_backend()

        # Get transcription timing settings from config
        realtime_duration = self.config.get('transcription.realtime.chunk_duration_seconds', 2.0)
        batch_duration = self.config.get('transcription.batch.window_duration_seconds', 10.0)
        
        # Calculate trigger chunks based on duration
        realtime_trigger_chunks = int(chunks_per_second * realtime_duration)
        batch_trigger_chunks = int(chunks_per_second * batch_duration)
        
        logger.info(f"Transcription triggers: realtime={realtime_trigger_chunks} chunks ({realtime_duration}s), batch={batch_trigger_chunks} chunks ({batch_duration}s)")
        
        # Create transcription publishers
        self.realtime_publisher = TranscriptionPublisher("transcription.realtime")
        self.batch_publisher = TranscriptionPublisher("transcription.batch")
        
        # Create and configure consumers with result callbacks
        self.realtime_consumer = TranscriptionAudioConsumer(
            name="realtime",
            backend=backend,
            trigger_chunks=realtime_trigger_chunks,
            result_callback=self.realtime_publisher.get_callback()
        )
        pub.subscribe(self.realtime_consumer.on_audio_chunk, self.topic)
            
        self.batch_consumer = TranscriptionAudioConsumer(
            name="batch",
            backend=backend,
            trigger_chunks=batch_trigger_chunks,
            result_callback=self.batch_publisher.get_callback()
        )
        pub.subscribe(self.batch_consumer.on_audio_chunk, self.topic)


    def shutdown_transcription(self) -> Dict[str, Any]:
        """Shutdown all transcription consumers and wait for completion.
        
        Returns:
            Result dictionary with success status
        """
        logger.info("Shutting down transcription service...")
        
        # Unsubscribe from pub/sub
        try:
            pub.unsubscribe(self.realtime_consumer.on_audio_chunk, self.topic)
            pub.unsubscribe(self.batch_consumer.on_audio_chunk, self.topic)
        except Exception as e:
            logger.warning(f"Error during unsubscribe: {e}")
        
        # Shutdown consumers and wait for completion
        realtime_success = self.realtime_consumer.shutdown(timeout=30.0)
        batch_success = self.batch_consumer.shutdown(timeout=30.0)
        
        # Clean up backend
        try:
            self.realtime_consumer.backend.cleanup()
        except Exception as e:
            logger.warning(f"Error cleaning up realtime backend: {e}")
        
        success = realtime_success and batch_success
        logger.info(f"Transcription service shutdown complete: success={success}")
        
        return {
            "success": success,
            "realtime_shutdown": realtime_success,
            "batch_shutdown": batch_success
        }
    
    def _create_google_speech_backend(self) -> GoogleSpeechBackend:
        """Create and initialize transcription backend.
        
        Returns:
            Initialized backend or None if failed
        """
        credentials_path = self.config.get_google_credentials_path()
        language = self.config.get('google_cloud.language', 'en-US')
        use_enhanced = self.config.get('google_cloud.use_enhanced_model', True)
        enable_punctuation = self.config.get('google_cloud.enable_automatic_punctuation', True)
        
        logger.info(f"Initializing Google Speech backend...")
        logger.debug(f"Config: language={language}, enhanced={use_enhanced}, punctuation={enable_punctuation}")
        
        # Initialize backend
        backend = GoogleSpeechBackend(
            credentials_path=credentials_path,
            language=language,
            use_enhanced=use_enhanced,
            enable_automatic_punctuation=enable_punctuation
        )
        
        if not backend.initialize():
            raise RuntimeError("Google Speech backend failed to initialize")
        
        logger.info("✅ Google Speech backend initialized successfully")
        return backend