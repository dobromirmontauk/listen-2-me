"""Debug transcription aggregator that periodically prints accumulated results.

This component is intended for console debugging. It subscribes to a
transcription topic, accumulates all incoming `TranscriptionResult`s and
prints a summary every ~5 seconds of covered audio time (based on
TranscriptionResult.audio_start_time/audio_end_time), and also once on
shutdown.
"""

import logging
import threading
from typing import List, Dict, Optional
from pubsub import pub
from ..models.transcription import TranscriptionResult

logger = logging.getLogger(__name__)


class DebugTranscriptionAggregator:
    """Aggregates transcription results and prints them periodically and on shutdown."""
    
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
        self.lock = threading.RLock()
        self.shutdown_event = threading.Event()

        # Debug printing policy (~5 seconds of covered audio)
        self.print_interval_seconds: float = 5.0
        self.coverage_start_time: Optional[float] = None
        self.latest_end_time: Optional[float] = None
        self.next_print_threshold_seconds: float = self.print_interval_seconds
        
        # Subscribe to transcription topic
        pub.subscribe(self._on_result, topic)
        
        logger.info(f"TranscriptionAggregator '{name}' initialized - subscribed to {topic}")

    def _on_result(self, result: TranscriptionResult) -> None:
        """Handle transcription result."""
        logger.debug(f"_on_result for {self.name} is GETTING LOCK")

        prints_to_do = 0
        with self.lock:
            self.results.append(result)
            logger.debug(
                f"Aggregated {self.name} result: {result.text[:50]}...")
            # Update covered audio window using recording timestamps
            if result.audio_start_time is not None and result.audio_end_time is not None:
                if self.coverage_start_time is None:
                    self.coverage_start_time = result.audio_start_time
                if self.latest_end_time is None or result.audio_end_time > self.latest_end_time:
                    self.latest_end_time = result.audio_end_time

                covered = self.latest_end_time - self.coverage_start_time
                # If we've crossed one or more print thresholds, record how many
                # prints we need to do.
                while covered >= self.next_print_threshold_seconds:
                    prints_to_do += 1
                    self.next_print_threshold_seconds += self.print_interval_seconds
        logger.debug(f"_on_result for {self.name} is RELEASING LOCK")

        # Now, outside the lock, do the printing. This prevents holding the
        # lock during I/O.
        for _ in range(prints_to_do):
            self.print_transcription_summary()

    def get_results_summary(self) -> Dict[str, any]:
        """Get summary of aggregated results.
        
        Returns:
            Dictionary with result counts and statistics
        """
        logger.debug(f"Getting LOCK for results summary for {self.name}")
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
        if self.coverage_start_time is not None and self.latest_end_time is not None:
            covered = self.latest_end_time - self.coverage_start_time
            print(f"Covered audio (s): {covered:.2f}")
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
        logger.debug(f"_get_full_transcription for {self.name} is GETTING LOCK")
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
        logger.info("Shutting down DebugTranscriptionAggregator...")
        self.shutdown_event.set()

        # Unsubscribe from topic
        try:
            pub.unsubscribe(self._on_result, self.topic)
        except Exception as e:
            logger.warning(f"Error during unsubscribe: {e}")

        # Print transcription summary
        self.print_transcription_summary()

        logger.info("DebugTranscriptionAggregator shutdown complete")
        return True
