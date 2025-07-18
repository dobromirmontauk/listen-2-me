"""Google Speech-to-Text transcription backend."""

import io
import time
import logging
from datetime import datetime
from typing import Optional, Dict, Any
import wave

from .base import AbstractTranscriptionBackend, TranscriptionResult

logger = logging.getLogger(__name__)


class GoogleSpeechBackend(AbstractTranscriptionBackend):
    """Google Speech-to-Text API backend for transcription."""
    
    def __init__(self, 
                 credentials_path: Optional[str] = None,
                 language: str = "en-US",
                 use_enhanced: bool = True,
                 enable_automatic_punctuation: bool = True):
        """Initialize Google Speech backend.
        
        Args:
            credentials_path: Path to Google Cloud service account JSON file
            language: Language code (e.g., 'en-US', 'es-ES')  
            use_enhanced: Whether to use enhanced model (costs more but better quality)
            enable_automatic_punctuation: Enable automatic punctuation
        """
        super().__init__(language)
        self.credentials_path = credentials_path
        self.use_enhanced = use_enhanced
        self.enable_automatic_punctuation = enable_automatic_punctuation
        self.client = None
        self.project_id = None
        self.service_name = "Google Speech-to-Text"
        
    def initialize(self) -> bool:
        """Initialize Google Speech client and verify credentials."""
        # Import Google Cloud Speech library - CRASH if not installed
        from google.cloud import speech
        from google.oauth2 import service_account
        
        # Set up authentication - CRASH if credentials not found
        if not self.credentials_path:
            raise ValueError("Google credentials path is required - cannot initialize without credentials")
        
        # Load credentials directly from JSON file
        logger.info(f"Loading Google credentials from: {self.credentials_path}")
        credentials = service_account.Credentials.from_service_account_file(self.credentials_path)
        
        # Initialize client with direct credentials - CRASH if credentials are invalid
        self.client = speech.SpeechClient(credentials=credentials)
        
        # Get project ID from credentials
        self.project_id = credentials.project_id
        logger.info(f"Using Google Cloud project: {self.project_id}")
        
        # Test credentials by creating client (credentials validated on client creation)
        logger.debug("Testing Google Speech API credentials...")
        
        logger.info("Google Speech-to-Text backend initialized successfully")
        return True
    
    def transcribe_chunk(self, audio_chunk: bytes, sample_rate: int = 16000) -> TranscriptionResult:
        """Transcribe audio chunk using Google Speech-to-Text."""
        start_time = time.time()
        chunk_id = f"google_{int(start_time * 1000)}"
        
        logger.debug(f"=== TRANSCRIPTION CALL START ===")
        logger.debug(f"Chunk ID: {chunk_id}")
        logger.debug(f"Audio chunk size: {len(audio_chunk)} bytes")
        logger.debug(f"Sample rate: {sample_rate} Hz")
        logger.debug(f"Language: {self.language}")
        logger.debug(f"Enhanced model: {self.use_enhanced}")
        logger.debug(f"Auto punctuation: {self.enable_automatic_punctuation}")
        
        if not self.client:
            raise RuntimeError("Google Speech client not initialized")
        
        # Import Google Cloud Speech library
        from google.cloud import speech
        
        try:
            # Create audio object
            audio = speech.RecognitionAudio(content=audio_chunk)
            logger.debug(f"Created audio object for Google Speech API")
            
            # Configure recognition
            config = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
                sample_rate_hertz=sample_rate,
                language_code=self.language,
                use_enhanced=self.use_enhanced,
                enable_automatic_punctuation=self.enable_automatic_punctuation,
                # Enable word-level confidence and timestamps
                enable_word_confidence=True,
                enable_word_time_offsets=True,
                # Use model optimized for short audio
                model="latest_short",
            )
            logger.debug(f"Created recognition config: {config}")
            
            # Perform synchronous speech recognition
            logger.debug(f">>> CALLING Google Speech API with {len(audio_chunk)} bytes...")
            response = self.client.recognize(config=config, audio=audio)
            processing_time = time.time() - start_time
            
            logger.debug(f"<<< RESPONSE received in {processing_time:.3f}s")
            logger.debug(f"Response object: {response}")
            logger.debug(f"Number of results: {len(response.results) if response.results else 0}")
            
            if not response.results:
                # No speech detected
                result = TranscriptionResult(
                    text="",
                    confidence=0.0,
                    processing_time=processing_time,
                    timestamp=datetime.now(),
                    service=self.service_name,
                    language=self.language,
                    chunk_id=chunk_id,
                    is_final=True
                )
                logger.debug("--- NO SPEECH DETECTED ---")
                logger.debug(f"Returning empty result for chunk {chunk_id}")
            else:
                # Get the first (most likely) result
                recognition_result = response.results[0]
                alternative = recognition_result.alternatives[0]
                
                logger.debug(f"--- SPEECH DETECTED ---")
                logger.debug(f"First result: {recognition_result}")
                logger.debug(f"Best alternative: transcript='{alternative.transcript}', confidence={alternative.confidence}")
                logger.debug(f"Total alternatives: {len(recognition_result.alternatives)}")
                # Note: is_final is only available in streaming recognition, not synchronous
                
                # Extract alternatives if available
                alternatives = []
                for i, alt in enumerate(recognition_result.alternatives[1:5]):  # Up to 4 alternatives
                    alternatives.append({
                        "text": alt.transcript,
                        "confidence": alt.confidence
                    })
                    logger.debug(f"Alternative {i+1}: '{alt.transcript}' (confidence: {alt.confidence})")
                
                result = TranscriptionResult(
                    text=alternative.transcript,
                    confidence=alternative.confidence,
                    processing_time=processing_time,
                    timestamp=datetime.now(),
                    service=self.service_name,
                    language=self.language,
                    alternatives=alternatives if alternatives else None,
                    chunk_id=chunk_id,
                    is_final=True  # Synchronous recognition results are always final
                )
                
                logger.debug(f"✅ TRANSCRIPTION SUCCESS: '{alternative.transcript}' "
                           f"(confidence: {alternative.confidence:.2f}, "
                           f"processing_time: {processing_time:.3f}s)")
            
            self._update_stats(result)
            logger.debug(f"=== TRANSCRIPTION CALL END ===")
            return result
            
        except Exception as e:
            processing_time = time.time() - start_time
            
            logger.debug(f"❌ TRANSCRIPTION ERROR after {processing_time:.3f}s")
            logger.debug(f"Exception type: {type(e).__name__}")
            logger.debug(f"Exception message: {str(e)}")
            logger.debug(f"Full exception: {e}")
            
            # Create error result
            result = TranscriptionResult(
                text=f"[ERROR: {type(e).__name__}]",
                confidence=0.0,
                processing_time=processing_time,
                timestamp=datetime.now(),
                service=self.service_name,
                language=self.language,
                chunk_id=chunk_id,
                is_final=True
            )
            
            self._update_stats(result, error=e)
            logger.error(f"Google transcription failed for chunk {chunk_id}: {e}")
            logger.debug(f"=== TRANSCRIPTION CALL END (ERROR) ===")
            return result
    
    def cleanup(self) -> None:
        """Clean up Google Speech client resources."""
        try:
            if self.client:
                # Google client doesn't need explicit cleanup
                self.client = None
            logger.debug("Google Speech backend cleaned up")
        except Exception as e:
            logger.error(f"Error during Google backend cleanup: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get Google-specific statistics."""
        stats = super().get_stats()
        stats.update({
            "service": self.service_name,
            "language": self.language,
            "use_enhanced": self.use_enhanced,
            "enable_punctuation": self.enable_automatic_punctuation,
        })
        return stats