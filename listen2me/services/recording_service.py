"""Core recording service that manages the entire recording lifecycle."""

import time
import logging
from typing import Optional, Dict, List, Any
from datetime import datetime

from ..audio.capture import AudioCapture
from ..transcription.dual_engine import DualTranscriptionEngine
from ..transcription import GoogleSpeechBackend
from ..models.audio import AudioStats
from ..models.transcription import TranscriptionResult
from ..config import Listen2MeConfig

logger = logging.getLogger(__name__)


class RecordingService:
    """Core service that manages recording, transcription, and audio processing."""
    
    def __init__(self, config: Listen2MeConfig):
        """Initialize recording service.
        
        Args:
            config: Application configuration
        """
        self.config = config
        self.audio_capture: Optional[AudioCapture] = None
        self.transcription_engine: Optional[DualTranscriptionEngine] = None
        
        # Recording state
        self.is_recording = False
        self.current_session_id: Optional[str] = None
        self.chunks_processed = 0
        
        # Transcription results storage
        self.realtime_transcriptions: List[TranscriptionResult] = []
        self.batch_transcriptions: List[TranscriptionResult] = []
        self.combined_transcriptions: List[TranscriptionResult] = []
        
        # Debug: ALL transcription attempts (including no speech)
        self.all_realtime_attempts: List[TranscriptionResult] = []
        self.all_batch_attempts: List[TranscriptionResult] = []
        
        # Initialize transcription engine on startup
        logger.info("Initializing RecordingService...")
        self._setup_transcription()
        logger.info("RecordingService ready")
    
    def _setup_transcription(self) -> None:
        """Set up dual-mode transcription engine with available backends."""
        logger.info("Starting dual-mode transcription setup...")
        backends = []
        
        # Get configuration values
        credentials_path = self.config.get_google_credentials_path()
        language = self.config.get('google_cloud.language', 'en-US')
        use_enhanced = self.config.get('google_cloud.use_enhanced_model', True)
        enable_punctuation = self.config.get('google_cloud.enable_automatic_punctuation', True)
        
        logger.info(f"Google credentials path: {credentials_path}")
        logger.debug(f"Config: language={language}, use_enhanced={use_enhanced}, punctuation={enable_punctuation}")
        
        # Initialize Google Speech backend
        logger.info("Initializing Google Speech backend...")
        google_backend = GoogleSpeechBackend(
            credentials_path=credentials_path,
            language=language,
            use_enhanced=use_enhanced,
            enable_automatic_punctuation=enable_punctuation
        )
        
        if google_backend.initialize():
            backends.append(google_backend)
            logger.info("✅ Google Speech backend initialized successfully")
        else:
            raise RuntimeError("Google Speech backend failed to initialize")
        
        # Get transcription configuration
        realtime_config = self.config.get('transcription.realtime', {})
        batch_config = self.config.get('transcription.batch', {})
        
        logger.info(f"Dual transcription config:")
        logger.info(f"  Real-time: {realtime_config}")
        logger.info(f"  Batch: {batch_config}")
        
        # Initialize dual transcription engine
        logger.info(f"Initializing dual transcription engine with {len(backends)} backends...")
        self.transcription_engine = DualTranscriptionEngine(
            backends=backends,
            realtime_config=realtime_config,
            batch_config=batch_config
        )
        
        if self.transcription_engine.initialize():
            logger.info("✅ Dual transcription engine initialized successfully")
        else:
            raise RuntimeError("Failed to initialize dual transcription engine")
    
    def check_microphone_available(self) -> bool:
        """Check if microphone is available for recording."""
        try:
            AudioCapture(
                sample_rate=16000,
                chunk_size=1024,
                buffer_size=10,
                channels=1
            )
            return True
        except Exception as e:
            logger.debug(f"Microphone not available: {e}")
            return False
    
    def get_transcription_info(self) -> str:
        """Get display information about transcription backends."""
        if not self.transcription_engine:
            return ""
        
        for backend in self.transcription_engine.backends:
            info = backend.get_display_info()
            if info:
                return info
        return ""
    
    def start_recording(self, session_id: str) -> Dict[str, Any]:
        """Start recording with given session ID.
        
        Args:
            session_id: Unique session identifier
            
        Returns:
            Result dictionary with success status and details
        """
        try:
            if self.is_recording:
                return {
                    "success": False,
                    "error": "Already recording",
                    "session_id": self.current_session_id
                }
            
            if not self.transcription_engine:
                return {
                    "success": False,
                    "error": "Transcription engine not initialized"
                }
            
            # Initialize audio capture
            self.audio_capture = AudioCapture(
                sample_rate=self.config.get('audio.sample_rate', 16000),
                chunk_size=self.config.get('audio.chunk_size', 1024),
                buffer_size=self.config.get('audio.buffer_size', 100),
                channels=self.config.get('audio.channels', 1)
            )
            
            # Set session state
            self.current_session_id = session_id
            self.chunks_processed = 0
            
            # Clear previous results
            self.realtime_transcriptions.clear()
            self.batch_transcriptions.clear()
            self.combined_transcriptions.clear()
            self.all_realtime_attempts.clear()
            self.all_batch_attempts.clear()
            
            # Start recording
            self.audio_capture.start_recording()
            self.is_recording = True
            
            logger.info(f"Started recording for session: {session_id}")
            
            return {
                "success": True,
                "session_id": session_id,
                "started_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error starting recording: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def stop_recording(self) -> Dict[str, Any]:
        """Stop recording and return results.
        
        Returns:
            Result dictionary with session data and transcription results
        """
        try:
            if not self.is_recording:
                return {
                    "success": False,
                    "error": "Not recording"
                }
            
            # Stop audio capture
            self.audio_capture.stop_recording()
            self.is_recording = False
            
            # Collect final transcription results
            self._collect_final_results()
            
            # Wait for pending transcriptions
            logger.info("Waiting for pending transcriptions...")
            time.sleep(3)
            
            # Collect any remaining results
            self._collect_final_results()
            
            # Get recording stats
            stats = self.audio_capture.get_recording_stats()
            
            session_data = {
                "success": True,
                "session_id": self.current_session_id,
                "stopped_at": datetime.now().isoformat(),
                "duration_seconds": stats.duration_seconds,
                "total_chunks": stats.total_chunks,
                "chunks_processed": self.chunks_processed,
                "realtime_transcriptions": len(self.realtime_transcriptions),
                "batch_transcriptions": len(self.batch_transcriptions),
                "total_attempts": {
                    "realtime": len(self.all_realtime_attempts),
                    "batch": len(self.all_batch_attempts)
                }
            }
            
            logger.info(f"Session stopped: {self.current_session_id}")
            return session_data
            
        except Exception as e:
            logger.error(f"Error stopping recording: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _collect_final_results(self) -> None:
        """Collect any final transcription results from both engines."""
        if not self.transcription_engine:
            return
            
        results_dict = self.transcription_engine.get_completed_results()
        realtime_results = results_dict.get('realtime', [])
        batch_results = results_dict.get('batch', [])
        
        if realtime_results:
            self.all_realtime_attempts.extend(realtime_results)
            meaningful_realtime = [r for r in realtime_results if r.text and r.text.strip() and r.text != "[NO_SPEECH_DETECTED]"]
            self.realtime_transcriptions.extend(meaningful_realtime)
            self.combined_transcriptions.extend(meaningful_realtime)
            logger.info(f"Collected {len(meaningful_realtime)} final real-time results")
        
        if batch_results:
            self.all_batch_attempts.extend(batch_results)
            meaningful_batch = [r for r in batch_results if r.text and r.text.strip() and r.text != "[NO_SPEECH_DETECTED]"]
            self.batch_transcriptions.extend(meaningful_batch)
            logger.info(f"Collected {len(meaningful_batch)} final batch results")
    
    def process_audio_chunks(self) -> Dict[str, Any]:
        """Process any pending audio chunks and return new transcription results.
        
        Returns:
            Dictionary with new transcription results and processing stats
        """
        if not self.is_recording or not self.audio_capture or not self.transcription_engine:
            return {
                "new_realtime": [],
                "new_batch": [],
                "chunks_processed": 0
            }
        
        # Send raw audio chunks to dual engine
        raw_chunks_received = 0
        while self.audio_capture.has_audio_data():
            audio_chunk = self.audio_capture.get_audio_chunk()
            if audio_chunk and len(audio_chunk) > 0:
                self.transcription_engine.submit_audio_chunk(audio_chunk, time.time())
                raw_chunks_received += 1
                self.chunks_processed += 1
        
        if raw_chunks_received > 0:
            logger.debug(f"🎤 SERVICE: Sent {raw_chunks_received} raw audio chunks to dual engine")
        
        # Collect completed results
        results_dict = self.transcription_engine.get_completed_results()
        realtime_results = results_dict.get('realtime', [])
        batch_results = results_dict.get('batch', [])
        
        # Process new real-time results
        new_realtime = []
        if realtime_results:
            logger.debug(f"🎯 SERVICE: Received {len(realtime_results)} new real-time results")
            
            # Store ALL attempts for debugging
            self.all_realtime_attempts.extend(realtime_results)
            
            # Filter for meaningful results
            meaningful_realtime = [r for r in realtime_results if r.text and r.text.strip() and r.text != "[NO_SPEECH_DETECTED]"]
            self.realtime_transcriptions.extend(meaningful_realtime)
            self.combined_transcriptions.extend(meaningful_realtime)
            new_realtime = meaningful_realtime
            
            # Log results
            for result in realtime_results:
                if result.text == "[NO_SPEECH_DETECTED]":
                    logger.debug(f"🔇 REALTIME: No speech detected (confidence: {result.confidence:.2f})")
                elif result.text and result.text.strip():
                    logger.info(f"📝 REALTIME: '{result.text}'")
        
        # Process new batch results
        new_batch = []
        if batch_results:
            logger.debug(f"🎯 SERVICE: Received {len(batch_results)} new batch results")
            
            # Store ALL attempts for debugging
            self.all_batch_attempts.extend(batch_results)
            
            # Filter for meaningful results
            meaningful_batch = [r for r in batch_results if r.text and r.text.strip() and r.text != "[NO_SPEECH_DETECTED]"]
            self.batch_transcriptions.extend(meaningful_batch)
            new_batch = meaningful_batch
            
            # Log results
            for result in batch_results:
                if result.text == "[NO_SPEECH_DETECTED]":
                    logger.debug(f"🔇 BATCH: No speech detected (confidence: {result.confidence:.2f})")
                elif result.text and result.text.strip():
                    logger.info(f"📝 BATCH: '{result.text}'")
        
        return {
            "new_realtime": new_realtime,
            "new_batch": new_batch,
            "chunks_processed": raw_chunks_received
        }
    
    def get_recording_stats(self) -> Optional[AudioStats]:
        """Get current recording statistics."""
        if self.audio_capture:
            return self.audio_capture.get_recording_stats()
        return None
    
    def get_transcription_results(self) -> Dict[str, List[TranscriptionResult]]:
        """Get all transcription results.
        
        Returns:
            Dictionary with realtime, batch, and combined results
        """
        return {
            "realtime": self.realtime_transcriptions.copy(),
            "batch": self.batch_transcriptions.copy(),
            "combined": self.combined_transcriptions.copy(),
            "all_realtime_attempts": self.all_realtime_attempts.copy(),
            "all_batch_attempts": self.all_batch_attempts.copy()
        }
    
    def save_audio_file(self, file_path: str) -> bool:
        """Save recorded audio to file.
        
        Args:
            file_path: Path where to save the audio file
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if self.audio_capture:
                self.audio_capture.save_to_file(file_path)
                return True
            return False
        except Exception as e:
            logger.error(f"Error saving audio file: {e}")
            return False
    
    def cleanup(self) -> None:
        """Clean up service resources."""
        try:
            if self.is_recording and self.audio_capture:
                self.audio_capture.stop_recording()
                
            if self.transcription_engine:
                self.transcription_engine.cleanup()
                self.transcription_engine = None
                
            self.audio_capture = None
            self.is_recording = False
            self.current_session_id = None
            
            logger.info("RecordingService cleaned up")
            
        except Exception as e:
            logger.error(f"Error during RecordingService cleanup: {e}")