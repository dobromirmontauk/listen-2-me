"""Transcription engine that orchestrates multiple backends."""

import time
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from queue import Queue, Empty
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime

from .base import AbstractTranscriptionBackend
from ..models.transcription import TranscriptionResult

logger = logging.getLogger(__name__)


class TranscriptionEngine:
    """Manages multiple transcription backends and orchestrates processing."""
    
    def __init__(self, backends: List[AbstractTranscriptionBackend], max_workers: Optional[int] = None):
        """Initialize transcription engine.
        
        Args:
            backends: List of transcription backends to use
            max_workers: Maximum number of worker threads (defaults to number of backends)
        """
        self.backends = backends
        self.max_workers = max_workers or len(backends)
        self.executor = ThreadPoolExecutor(max_workers=self.max_workers)
        self.result_queue = Queue()
        self.pending_futures = []
        self.lock = threading.Lock()
        self.is_initialized = False
        self.callbacks = []  # Result callbacks
        
        # Statistics
        self.stats = {
            "total_chunks_submitted": 0,
            "total_results_received": 0,
            "avg_processing_time": 0.0,
            "backend_count": len(backends),
            "start_time": None
        }
    
    def initialize(self) -> bool:
        """Initialize all backends."""
        logger.info(f"Initializing transcription engine with {len(self.backends)} backends")
        
        successful_backends = []
        for backend in self.backends:
            try:
                logger.info(f"Initializing {backend.__class__.__name__}...")
                if backend.initialize():
                    successful_backends.append(backend)
                    logger.info(f"✅ {backend.__class__.__name__} initialized successfully")
                else:
                    logger.warning(f"❌ {backend.__class__.__name__} failed to initialize")
            except Exception as e:
                logger.error(f"❌ {backend.__class__.__name__} initialization error: {e}")
        
        if not successful_backends:
            logger.error("No transcription backends could be initialized")
            return False
        
        # Update backends list to only include successful ones
        self.backends = successful_backends
        self.stats["backend_count"] = len(self.backends)
        self.stats["start_time"] = datetime.now()
        self.is_initialized = True
        
        logger.info(f"Transcription engine initialized with {len(self.backends)} active backends")
        return True
    
    def submit_chunk(self, audio_chunk: bytes, sample_rate: int = 16000) -> None:
        """Submit audio chunk for asynchronous transcription.
        
        Args:
            audio_chunk: Raw audio data to transcribe
            sample_rate: Sample rate of the audio in Hz
        """
        logger.debug(f"🔄 ENGINE: submit_chunk called with {len(audio_chunk) if audio_chunk else 0} bytes")
        
        if not self.is_initialized:
            logger.warning("Transcription engine not initialized, skipping chunk")
            return
        
        if not audio_chunk or len(audio_chunk) == 0:
            logger.debug("Empty audio chunk, skipping transcription")
            return
        
        with self.lock:
            self.stats["total_chunks_submitted"] += 1
            current_chunk_id = self.stats["total_chunks_submitted"]
            
            logger.debug(f"📤 ENGINE: Submitting chunk #{current_chunk_id} to {len(self.backends)} backends")
            
            # Submit to all available backends concurrently
            submitted_count = 0
            for backend in self.backends:
                if backend.is_healthy():
                    future = self.executor.submit(
                        self._transcribe_with_backend, 
                        backend, 
                        audio_chunk, 
                        sample_rate
                    )
                    self.pending_futures.append(future)
                    submitted_count += 1
                    logger.debug(f"✅ ENGINE: Submitted chunk #{current_chunk_id} to {backend.__class__.__name__}")
                else:
                    logger.warning(f"❌ ENGINE: Skipping unhealthy backend: {backend.__class__.__name__}")
            
            logger.debug(f"📊 ENGINE: Chunk #{current_chunk_id} submitted to {submitted_count}/{len(self.backends)} backends")
    
    def _transcribe_with_backend(self, 
                               backend: AbstractTranscriptionBackend, 
                               audio_chunk: bytes, 
                               sample_rate: int) -> TranscriptionResult:
        """Internal method: transcribe with specific backend."""
        try:
            result = backend.transcribe_chunk(audio_chunk, sample_rate)
            
            # Put result in queue for retrieval
            self.result_queue.put(result)
            
            # Update engine stats
            with self.lock:
                self.stats["total_results_received"] += 1
                
                # Update average processing time
                total_results = self.stats["total_results_received"]
                current_avg = self.stats["avg_processing_time"]
                self.stats["avg_processing_time"] = (
                    (current_avg * (total_results - 1) + result.processing_time) / total_results
                )
            
            # Call registered callbacks
            for callback in self.callbacks:
                try:
                    callback(result)
                except Exception as e:
                    logger.error(f"Error in result callback: {e}")
            
            logger.debug(f"Transcription completed by {backend.__class__.__name__}: "
                        f"'{result.text[:50]}...' (confidence: {result.confidence:.2f})")
            
            return result
            
        except Exception as e:
            logger.error(f"Transcription failed in {backend.__class__.__name__}: {e}")
            
            # Create error result
            error_result = TranscriptionResult(
                text=f"[ERROR: {backend.__class__.__name__}]",
                confidence=0.0,
                processing_time=0.0,
                timestamp=datetime.now(),
                service=backend.__class__.__name__,
                chunk_id=f"error_{int(time.time() * 1000)}"
            )
            
            self.result_queue.put(error_result)
            return error_result
    
    def get_completed_results(self) -> List[TranscriptionResult]:
        """Get all completed transcription results (non-blocking).
        
        Returns:
            List of completed transcription results
        """
        logger.debug(f"📥 ENGINE: get_completed_results called")
        
        results = []
        
        # Clean up completed futures
        with self.lock:
            initial_pending = len(self.pending_futures)
            self.pending_futures = [f for f in self.pending_futures if not f.done()]
            completed_futures = initial_pending - len(self.pending_futures)
            
            if completed_futures > 0:
                logger.debug(f"🧹 ENGINE: Cleaned up {completed_futures} completed futures, {len(self.pending_futures)} still pending")
        
        # Get all available results from queue
        queue_size = self.result_queue.qsize()
        logger.debug(f"📊 ENGINE: Result queue size: {queue_size}")
        
        while True:
            try:
                result = self.result_queue.get_nowait()
                results.append(result)
                logger.debug(f"📨 ENGINE: Retrieved result: '{result.text}' (confidence: {result.confidence:.2f})")
            except Empty:
                break
        
        logger.debug(f"📋 ENGINE: Retrieved {len(results)} transcription results total")
        
        return results
    
    def get_latest_result(self) -> Optional[TranscriptionResult]:
        """Get the most recent transcription result.
        
        Returns:
            Most recent TranscriptionResult or None
        """
        results = self.get_completed_results()
        if not results:
            return None
        
        # Return result with highest confidence, or most recent if tied
        return max(results, key=lambda r: (r.confidence, r.timestamp.timestamp()))
    
    def add_result_callback(self, callback: Callable[[TranscriptionResult], None]) -> None:
        """Add callback to be called when new results are available.
        
        Args:
            callback: Function that takes TranscriptionResult as argument
        """
        self.callbacks.append(callback)
        logger.debug(f"Added result callback: {callback.__name__}")
    
    def get_comparison_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get performance comparison between backends.
        
        Returns:
            Dictionary with backend names as keys and their stats as values
        """
        comparison = {}
        
        for backend in self.backends:
            backend_stats = backend.get_stats()
            backend_stats["health_status"] = "healthy" if backend.is_healthy() else "unhealthy"
            comparison[backend.__class__.__name__] = backend_stats
        
        return comparison
    
    def get_engine_stats(self) -> Dict[str, Any]:
        """Get overall engine statistics.
        
        Returns:
            Dictionary with engine performance metrics
        """
        stats = self.stats.copy()
        
        # Add current queue size
        stats["pending_results"] = self.result_queue.qsize()
        stats["pending_futures"] = len(self.pending_futures)
        
        # Add uptime if started
        if stats["start_time"]:
            uptime = datetime.now() - stats["start_time"]
            stats["uptime_seconds"] = uptime.total_seconds()
        
        # Add processing rate
        if stats["uptime_seconds"] and stats["uptime_seconds"] > 0:
            stats["chunks_per_second"] = stats["total_chunks_submitted"] / stats["uptime_seconds"]
            stats["results_per_second"] = stats["total_results_received"] / stats["uptime_seconds"]
        
        return stats
    
    def stop_processing(self) -> None:
        """Stop processing new chunks and cancel pending futures (for recording stop)."""
        logger.info("Stopping transcription processing...")
        
        with self.lock:
            # Cancel all pending futures
            cancelled_count = 0
            for future in self.pending_futures:
                if not future.done():
                    if future.cancel():
                        cancelled_count += 1
            
            logger.info(f"Cancelled {cancelled_count} pending transcription futures")
            self.pending_futures.clear()
            
            # Clear result queue to prevent stale results
            try:
                while not self.result_queue.empty():
                    self.result_queue.get_nowait()
                logger.debug("Cleared result queue")
            except:
                pass
        
        logger.info("Transcription processing stopped")
    
    def cleanup(self) -> None:
        """Clean up engine resources."""
        logger.info("Shutting down transcription engine...")
        
        # Stop processing first
        self.stop_processing()
        
        # Shutdown executor
        try:
            self.executor.shutdown(wait=True)
            logger.debug("Executor shutdown completed")
        except Exception as e:
            logger.error(f"Error shutting down executor: {e}")
        
        # Clean up all backends
        for backend in self.backends:
            try:
                backend.cleanup()
                logger.debug(f"Cleaned up {backend.__class__.__name__}")
            except Exception as e:
                logger.error(f"Error cleaning up {backend.__class__.__name__}: {e}")
        
        # Clear queues
        try:
            while not self.result_queue.empty():
                self.result_queue.get_nowait()
        except:
            pass
        
        self.is_initialized = False
        logger.info("Transcription engine shutdown completed")
    
    def __enter__(self):
        """Context manager entry."""
        if not self.initialize():
            raise RuntimeError("Failed to initialize transcription engine")
        return self
    
    def __exit__(self, _exc_type, _exc_val, _exc_tb):
        """Context manager exit."""
        self.cleanup()