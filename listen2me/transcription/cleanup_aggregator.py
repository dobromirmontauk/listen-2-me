"""Cleanup aggregation and trigger coordinator.

Coordinates batching of TranscriptionResult objects and triggers cleaning
based on covered audio time (derived from result timestamps), not wall clock.

Trigger policy:
 - First trigger when covered audio >= 10s
 - Subsequent triggers every +5s of covered audio
 - Final trigger on any result with is_final=True

Always sends ALL accumulated results to the cleaning service to provide
growing context.
"""

import logging
import threading
from typing import List, Callable, Optional
from pubsub import pub

from ..models.transcription import TranscriptionResult, CleanedTranscriptionResult

logger = logging.getLogger(__name__)


class CleanupAggregator:
    """Aggregates results and triggers cleaning with growing context."""

    def __init__(
        self,
        topic: str,
        cleaning_callback: Callable[[List[TranscriptionResult]], List[CleanedTranscriptionResult]],
    ) -> None:
        self.topic = topic
        self.cleaning_callback = cleaning_callback

        self.results: List[TranscriptionResult] = []

        self.lock = threading.Lock()
        self.shutdown_event = threading.Event()

        # Trigger thresholds (in seconds of covered audio)
        self.initial_threshold: float = 10.0
        self.increment_threshold: float = 5.0
        self.next_threshold: float = self.initial_threshold

        # Coverage tracking
        self.coverage_start_time: Optional[float] = None
        self.latest_end_time: Optional[float] = None

        # Subscribe
        pub.subscribe(self._on_result, topic)
        logger.info(
            f"CleanupAggregator initialized - subscribed to {topic}; initial={self.initial_threshold}s, step={self.increment_threshold}s"
        )

    def _on_result(self, result: TranscriptionResult) -> None:
        with self.lock:
            self.results.append(result)

            # Update coverage from timestamps if present
            if result.audio_start_time is not None and result.audio_end_time is not None:
                if self.coverage_start_time is None:
                    self.coverage_start_time = result.audio_start_time
                if self.latest_end_time is None or result.audio_end_time > self.latest_end_time:
                    self.latest_end_time = result.audio_end_time

            # Check triggers (time-based off recording timestamps)
            triggered = False
            if self.coverage_start_time is not None and self.latest_end_time is not None:
                covered = self.latest_end_time - self.coverage_start_time
                while covered >= self.next_threshold:
                    self._run_cleanup_locked(reason=f"threshold@{self.next_threshold:.0f}s", covered_seconds=covered)
                    self.next_threshold += self.increment_threshold
                    triggered = True

            # Final trigger
            if result.is_final and not triggered:
                covered = 0.0
                if self.coverage_start_time is not None and self.latest_end_time is not None:
                    covered = self.latest_end_time - self.coverage_start_time
                self._run_cleanup_locked(reason="final", covered_seconds=covered)

    def _run_cleanup_locked(self, reason: str, covered_seconds: float) -> None:
        """Run cleaning on all accumulated results under lock."""
        logger.info(
            f"CleanupAggregator: triggering cleaning ({reason}); total_results={len(self.results)}, covered={covered_seconds:.2f}s"
        )
        try:
            cleaned = self.cleaning_callback(self.results.copy())
            # For prototype, print a short summary
            if cleaned:
                print("\n========== CLEANED TRANSCRIPTION (", reason, ") ==========")
                for i, c in enumerate(cleaned, 1):
                    print(f"{i:2d}. {c.cleaned_text[:200]}")
                print("====================================================\n")
        except Exception as e:
            logger.error(f"CleanupAggregator: cleaning failed: {e}")

    def shutdown(self) -> None:
        logger.info("CleanupAggregator: shutdown")
        self.shutdown_event.set()
        try:
            pub.unsubscribe(self._on_result, self.topic)
        except Exception as e:
            logger.warning(f"CleanupAggregator: unsubscribe error: {e}")



