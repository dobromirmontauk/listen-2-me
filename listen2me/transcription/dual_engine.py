"""Dual-mode transcription engine handling both real-time and batch processing."""

import time
import logging
import threading
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor

from .base import AbstractTranscriptionBackend
from ..models.transcription import TranscriptionResult
from .engine import TranscriptionEngine
from ..audio.buffer import RollingAudioBuffer

logger = logging.getLogger(__name__)


class DualTranscriptionEngine:
    """Manages both real-time and batch transcription modes simultaneously."""
    
    def __init__(self, 
                 backends: List[AbstractTranscriptionBackend],
                 realtime_config: Dict[str, Any],
                 batch_config: Dict[str, Any]):
        """Initialize dual transcription engine.
        
        Args:
            backends: List of transcription backends to use
            realtime_config: Configuration for real-time transcription
            batch_config: Configuration for batch transcription
        """
        self.backends = backends
        self.realtime_config = realtime_config
        self.batch_config = batch_config
        
        # Real-time transcription engine
        self.realtime_engine = TranscriptionEngine(backends)
        
        # Batch transcription engine (separate instance to avoid conflicts)
        self.batch_engine = TranscriptionEngine(backends)
        
        # Rolling audio buffer for batch processing
        buffer_duration = batch_config.get('buffer_duration_seconds', 75.0)
        self.audio_buffer = RollingAudioBuffer(buffer_duration)
        
        # Batch processing state
        self.batch_enabled = batch_config.get('enabled', True)
        self.batch_window_duration = batch_config.get('window_duration_seconds', 60.0)
        self.batch_interval = batch_config.get('interval_seconds', 45.0)
        self.batch_overlap = batch_config.get('overlap_seconds', 15.0)
        
        # Batch scheduling
        self.batch_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="BatchTranscription")
        self.batch_scheduler_thread = None
        self.batch_running = False
        self.last_batch_time = 0
        self.batch_counter = 0
        
        # Result storage
        self.realtime_results = []
        self.batch_results = []
        self.results_lock = threading.Lock()
        
        # Real-time buffering state
        self.realtime_buffer = bytearray()
        self.realtime_chunk_size = int(16000 * 2 * realtime_config.get('chunk_duration_seconds', 2.0))
        self.realtime_max_interval = realtime_config.get('max_chunk_interval_seconds', 2.5)
        self.last_realtime_submit = time.time()
        self._pending_realtime_timing = None  # Properly initialize timing state
        
        logger.info(f"DualTranscriptionEngine initialized:")
        logger.info(f"  Real-time: {realtime_config.get('chunk_duration_seconds', 2.0)}s chunks")
        logger.info(f"  Batch: {self.batch_window_duration}s windows every {self.batch_interval}s")
        logger.info(f"  Buffer: {buffer_duration}s capacity")
    
    def initialize(self) -> bool:
        """Initialize both transcription engines."""
        logger.info("Initializing dual transcription engines...")
        
        # Initialize real-time engine
        if not self.realtime_engine.initialize():
            logger.error("Failed to initialize real-time transcription engine")
            return False
        
        # Initialize batch engine
        if not self.batch_engine.initialize():
            logger.error("Failed to initialize batch transcription engine")
            return False
        
        # Start batch scheduler if enabled
        if self.batch_enabled:
            self._start_batch_scheduler()
        
        logger.info("Dual transcription engines initialized successfully")
        return True
    
    def submit_audio_chunk(self, audio_chunk: bytes, audio_timestamp: Optional[float] = None) -> None:
        """Submit audio chunk for both real-time and batch processing."""
        if not audio_chunk:
            return
            
        if audio_timestamp is None:
            audio_timestamp = time.time()
        
        # Add to rolling buffer for batch processing
        self.audio_buffer.add_audio_chunk(audio_chunk)
        
        # Process for real-time transcription (with buffering)
        self._process_realtime_audio(audio_chunk, audio_timestamp)
    
    def _process_realtime_audio(self, audio_chunk: bytes, audio_timestamp: float) -> None:
        """Process audio for real-time transcription with buffering."""
        self.realtime_buffer.extend(audio_chunk)
        
        current_time = time.time()
        time_since_last_submit = current_time - self.last_realtime_submit
        
        # Send buffered audio when we have enough or time interval exceeded
        if (len(self.realtime_buffer) >= self.realtime_chunk_size or 
            time_since_last_submit >= self.realtime_max_interval):
            
            if len(self.realtime_buffer) > 0:
                # Calculate audio duration and timestamps
                bytes_per_second = 16000 * 2  # 16kHz, 16-bit
                audio_duration = len(self.realtime_buffer) / bytes_per_second
                audio_end_time = audio_timestamp
                audio_start_time = audio_end_time - audio_duration
                
                # Submit to real-time engine
                buffer_copy = bytes(self.realtime_buffer)
                logger.debug(f"🎯 REALTIME: Submitting {len(buffer_copy)} bytes "
                           f"({audio_duration:.1f}s audio, {audio_start_time:.1f}-{audio_end_time:.1f})")
                
                # Submit with enhanced metadata
                self._submit_to_realtime_engine(buffer_copy, audio_start_time, audio_end_time)
                
                # Clear buffer and update timing
                self.realtime_buffer.clear()
                self.last_realtime_submit = current_time
    
    def _submit_to_realtime_engine(self, audio_data: bytes, start_time: float, end_time: float) -> None:
        """Submit audio to real-time engine with timestamp metadata."""
        # We need to modify the transcription result after it's created
        # For now, submit normally and we'll enhance the result when we collect it
        self.realtime_engine.submit_chunk(audio_data, sample_rate=16000)
        
        # Store timing info for the next result we collect
        self._pending_realtime_timing = {
            'start_time': start_time,
            'end_time': end_time,
            'submitted_at': time.time()
        }
    
    def _start_batch_scheduler(self) -> None:
        """Start the batch transcription scheduler."""
        self.batch_running = True
        self.batch_scheduler_thread = threading.Thread(
            target=self._batch_scheduler_loop,
            name="BatchScheduler",
            daemon=True
        )
        self.batch_scheduler_thread.start()
        logger.info("Batch transcription scheduler started")
    
    def _batch_scheduler_loop(self) -> None:
        """Main loop for batch transcription scheduling."""
        while self.batch_running:
            try:
                current_time = time.time()
                
                # Check if it's time for batch processing
                if current_time - self.last_batch_time >= self.batch_interval:
                    self._schedule_batch_transcription()
                    self.last_batch_time = current_time
                
                # Sleep for a short interval
                time.sleep(1.0)  # Check every second
                
            except Exception as e:
                logger.error(f"Error in batch scheduler: {e}")
                time.sleep(5.0)  # Back off on error
    
    def _schedule_batch_transcription(self) -> None:
        """Schedule a batch transcription job."""
        # Get audio window from buffer
        audio_window = self.audio_buffer.get_audio_window(
            duration_seconds=self.batch_window_duration,
            start_offset_seconds=0.0  # From current time
        )
        
        if audio_window is None:
            logger.debug("Insufficient audio data for batch transcription")
            return
        
        audio_data, start_timestamp, end_timestamp = audio_window
        self.batch_counter += 1
        batch_id = f"batch_{self.batch_counter}_{int(time.time())}"
        
        logger.info(f"🔄 BATCH: Scheduling batch transcription {batch_id}")
        logger.info(f"   Audio: {len(audio_data)} bytes, {end_timestamp - start_timestamp:.1f}s")
        logger.info(f"   Time range: {start_timestamp:.1f} - {end_timestamp:.1f}")
        
        # Submit to batch executor (fire-and-forget)
        self.batch_executor.submit(
            self._process_batch_transcription,
            audio_data, start_timestamp, end_timestamp, batch_id
        )
    
    def _process_batch_transcription(self, audio_data: bytes, start_time: float, 
                                   end_time: float, batch_id: str) -> None:
        """Process batch transcription in background thread."""
        try:
            logger.debug(f"🎯 BATCH: Processing batch {batch_id}")
            
            # Submit to batch engine
            self.batch_engine.submit_chunk(audio_data, sample_rate=16000)
            
            # Wait for result with timeout
            max_wait_time = 30.0  # 30 second timeout
            start_wait = time.time()
            
            while time.time() - start_wait < max_wait_time:
                results = self.batch_engine.get_completed_results()
                if results:
                    # Enhance result with batch metadata
                    for result in results:
                        result.audio_start_time = start_time
                        result.audio_end_time = end_time
                        result.transcription_mode = "batch"
                        result.batch_id = batch_id
                        result.chunk_id = batch_id  # Use batch_id as chunk_id
                    
                    # Store batch results
                    with self.results_lock:
                        self.batch_results.extend(results)
                    
                    logger.info(f"✅ BATCH: Completed batch {batch_id}")
                    for result in results:
                        if result.text and result.text.strip():
                            logger.info(f"📝 BATCH: '{result.text}' (confidence: {result.confidence:.2f})")
                    break
                
                time.sleep(0.1)  # Check every 100ms
            else:
                logger.warning(f"⏰ BATCH: Timeout waiting for batch {batch_id} result")
                
        except Exception as e:
            logger.error(f"❌ BATCH: Error processing batch {batch_id}: {e}")
    
    def get_completed_results(self) -> Dict[str, List[TranscriptionResult]]:
        """Get all completed transcription results, separated by mode."""
        # Collect real-time results
        realtime_results = self.realtime_engine.get_completed_results()
        
        # Enhance real-time results with timing info if available
        if self._pending_realtime_timing is not None and realtime_results:
            timing = self._pending_realtime_timing
            for result in realtime_results:
                result.audio_start_time = timing['start_time']
                result.audio_end_time = timing['end_time']
                result.transcription_mode = "realtime"
            self._pending_realtime_timing = None
        
        # Collect batch results
        batch_results = []
        with self.results_lock:
            batch_results = self.batch_results.copy()
            self.batch_results.clear()  # Clear after collecting
        
        return {
            'realtime': realtime_results,
            'batch': batch_results
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics for both engines."""
        buffer_stats = self.audio_buffer.get_buffer_stats()
        
        return {
            'realtime_engine': self.realtime_engine.get_engine_stats(),
            'batch_engine': self.batch_engine.get_engine_stats(),
            'audio_buffer': buffer_stats,
            'batch_enabled': self.batch_enabled,
            'batch_counter': self.batch_counter,
            'last_batch_time': self.last_batch_time
        }
    
    def cleanup(self) -> None:
        """Clean up both engines and resources."""
        logger.info("Shutting down dual transcription engine...")
        
        # Stop batch scheduler
        if self.batch_scheduler_thread:
            self.batch_running = False
            self.batch_scheduler_thread.join(timeout=5.0)
        
        # Shutdown batch executor
        try:
            self.batch_executor.shutdown(wait=True)
        except Exception as e:
            logger.error(f"Error shutting down batch executor: {e}")
        
        # Clean up engines
        try:
            self.realtime_engine.cleanup()
        except Exception as e:
            logger.error(f"Error cleaning up real-time engine: {e}")
        
        try:
            self.batch_engine.cleanup()
        except Exception as e:
            logger.error(f"Error cleaning up batch engine: {e}")
        
        # Clear buffer
        self.audio_buffer.clear()
        
        logger.info("Dual transcription engine shutdown completed")