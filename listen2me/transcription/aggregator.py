"""Transcription aggregator that collects and prints all transcription results."""

import logging
import threading
from typing import List, Dict
from pubsub import pub
from ..models.transcription import TranscriptionResult

logger = logging.getLogger(__name__)


class TranscriptionAggregator:
    """Aggregates transcription results and prints them upon shutdown."""
    
    def __init__(self, topic: str, name: str):
        """Initialize transcription aggregator.
        
        Args:
            topic: Topic for transcription results
            name: Name for this aggregator (e.g., "realtime", "batch")
        """
        self.topic = topic
        self.name = name
        
        # Store transcription results
        self.results: List[TranscriptionResult] = []
        
        # Thread safety
        self.lock = threading.Lock()
        self.shutdown_event = threading.Event()
        
        # Subscribe to transcription topic
        pub.subscribe(self._on_result, topic)
        
        logger.info(f"TranscriptionAggregator '{name}' initialized - subscribed to {topic}")
    
    def _on_result(self, result: TranscriptionResult) -> None:
        """Handle transcription result."""
        with self.lock:
            self.results.append(result)
            logger.debug(f"Aggregated {self.name} result: {result.text[:50]}...")
    
    def get_results_summary(self) -> Dict[str, any]:
        """Get summary of aggregated results.
        
        Returns:
            Dictionary with result counts and statistics
        """
        with self.lock:
            return {
                "count": len(self.results),
                "results": self.results.copy(),
                "name": self.name
            }
    
    def print_transcription_summary(self) -> None:
        """Print a summary of all transcription results."""
        summary = self.get_results_summary()
        
        print(f"\n{'='*60}")
        print(f"🎙️  {self.name.upper()} TRANSCRIPTION SUMMARY")
        print(f"{'='*60}")
        print(f"Total transcriptions: {summary['count']}")
        print()
        
        if summary['count'] > 0:
            print(f"📝 {self.name.upper()} TRANSCRIPTIONS:")
            print("-" * 40)
            for i, result in enumerate(summary['results'], 1):
                confidence_str = f"({result.confidence:.1%})" if result.confidence > 0 else ""
                print(f"{i:2d}. {result.text} {confidence_str}")
            print()
            
            # Print full transcription
            print("📄 FULL TRANSCRIPTION:")
            print("-" * 40)
            full_text = self._get_full_transcription()
            print(full_text)
            print("-" * 40)
        
        print(f"{'='*60}")
    
    def _get_full_transcription(self) -> str:
        """Get the full transcription text combining all results.
        
        Returns:
            Combined transcription text
        """
        with self.lock:
            # Filter out no-speech detections and combine text
            valid_results = []
            for result in self.results:
                if result.text and result.text != "[NO_SPEECH_DETECTED]":
                    valid_results.append(result.text)
            
            # Combine text
            full_text = " ".join(valid_results)
            return full_text
    
    def shutdown(self, timeout: float = 5.0) -> bool:
        """Shutdown the aggregator and print results.
        
        Args:
            timeout: Maximum time to wait for shutdown
            
        Returns:
            True if shutdown completed successfully
        """
        logger.info("Shutting down TranscriptionAggregator...")
        self.shutdown_event.set()
        
        # Unsubscribe from topic
        try:
            pub.unsubscribe(self._on_result, self.topic)
        except Exception as e:
            logger.warning(f"Error during unsubscribe: {e}")
        
        # Print transcription summary
        self.print_transcription_summary()
        
        logger.info("TranscriptionAggregator shutdown complete")
        return True 