"""Google Speech-to-Text transcription backend."""

import time
import logging
from datetime import datetime
from typing import Optional, Dict, Any

from .base import AbstractTranscriptionBackend
from ..models.transcription import TranscriptionResult

from google.cloud import speech
from google.api_core import exceptions as gax_exceptions
from google.oauth2 import service_account

logger = logging.getLogger(__name__)


class GoogleSpeechBackend(AbstractTranscriptionBackend):
    """Google Speech-to-Text API backend for transcription."""
    
    def __init__(self, 
                 credentials_path: Optional[str] = None,
                 sample_rate: int = 16000,
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
        if not self.credentials_path:
            raise ValueError("Google credentials path is required - cannot initialize without credentials")
        self.use_enhanced = use_enhanced
        self.enable_automatic_punctuation = enable_automatic_punctuation
        self.client = None
        self.project_id = None
        self.service_name = "Google Speech-to-Text"
        self.config = speech.RecognitionConfig(
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
        
    def initialize(self) -> bool:
        """Initialize Google Speech client and verify credentials."""
        # Load credentials directly from JSON file
        logger.info(f"Loading Google credentials from: {self.credentials_path}")
        credentials = service_account.Credentials.from_service_account_file(self.credentials_path)
        
        # Initialize client with direct credentials - CRASH if credentials are invalid
        self.client = speech.SpeechClient(credentials=credentials)
        
        # Get project ID from credentials
        self.project_id = credentials.project_id
        logger.info(f"Using Google Cloud project: {self.project_id}")
        
        logger.info("Google Speech-to-Text backend initialized successfully")
        return True
    
    def transcribe_chunk(self, chunk_id: str, audio_chunk: bytes) -> TranscriptionResult:
        """Transcribe audio chunk using Google Speech-to-Text."""
        start_time = time.time()
        
        logger.debug(f"Chunk ID: {chunk_id}; Audio chunk size: {len(audio_chunk)} bytes; Language: {self.language}; Enhanced model: {self.use_enhanced}; Auto punctuation: {self.enable_automatic_punctuation}")
        
        # Create audio object
        audio = speech.RecognitionAudio(content=audio_chunk)
        # Perform synchronous speech recognition with a per-request timeout
        try:
            response = self.client.recognize(config=self.config, audio=audio, timeout=2.0)
        except gax_exceptions.DeadlineExceeded as e:
            logger.error("Google STT recognize deadline exceeded for chunk %s", chunk_id)
            raise RuntimeError(f"Google Speech recognize timeout (chunk={chunk_id}): {e}") from e
        except gax_exceptions.ServiceUnavailable as e:
            logger.error("Google STT service unavailable for chunk %s", chunk_id)
            raise RuntimeError(f"Google Speech service unavailable (chunk={chunk_id}): {e}") from e
        except gax_exceptions.GoogleAPICallError as e:
            logger.error("Google STT API call error for chunk %s: %s", chunk_id, e)
            raise RuntimeError(f"Google Speech API error (chunk={chunk_id}): {e}") from e
        processing_time = time.time() - start_time
            
        if not response.results:
            # No speech detected
            logger.debug(f"--- NO SPEECH DETECTED ---")
            result = TranscriptionResult(
                text="[NO_SPEECH_DETECTED]",
                confidence=0.0,
                processing_time=processing_time,
                timestamp=datetime.now(),
                service=self.service_name,
                language=self.language,
                chunk_id=chunk_id,
                is_final=True
            )
        else:
            result = self.__extract_transcription_result(response, processing_time, chunk_id)

        return result
        
    def __extract_transcription_result(self, response: speech.RecognizeResponse, processing_time: float, chunk_id: str) -> TranscriptionResult:
        recognition_result = response.results[0]
        alternative = recognition_result.alternatives[0]
        
        logger.debug(f"--- SPEECH DETECTED ---")
        logger.debug(f"Transcript='{alternative.transcript}'(conf={alternative.confidence}, total_alternatives={len(recognition_result.alternatives)})")
        # Note: is_final is only available in streaming recognition, not synchronous
        
        # Extract alternatives if available
        alternatives = []
        for i, alt in enumerate(recognition_result.alternatives[1:5]):  # Up to 4 alternatives
            alternatives.append({
                "text": alt.transcript,
                "confidence": alt.confidence
            })
            logger.debug(f"Alternative {i+1}: '{alt.transcript}' (confidence: {alt.confidence})")
        logger.debug(f"✅ TRANSCRIPTION SUCCESS: '{alternative.transcript}' "
                    f"(confidence: {alternative.confidence:.2f}, "
                    f"processing_time: {processing_time:.3f}s)") 
        return TranscriptionResult(
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

    def cleanup(self) -> None:
        """Clean up Google Speech client resources."""
        pass
    
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