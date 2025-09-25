"""Generic transcription result cleaner that works with different backend engines."""

import logging
from typing import List, Optional, Dict, Any, Protocol
from datetime import datetime
from abc import ABC, abstractmethod

from ..models.transcription import TranscriptionResult, CleanedTranscriptionResult

logger = logging.getLogger(__name__)


class CleaningEngine(Protocol):
    """Protocol for cleaning engines that can process text."""
    
    async def send_prompt(self, prompt: str, **kwargs) -> str:
        """Send a prompt to the engine and get response."""
        ...


class TranscriptionResultCleaner:
    """Cleans transcription results using any compatible cleaning engine."""
    
    def __init__(self, engine: CleaningEngine):
        """Initialize transcription result cleaner.
        
        Args:
            engine: Cleaning engine that implements the CleaningEngine protocol
        """
        self.engine = engine
        
        # Track cleaning history for context
        self.cleaning_history: List[Dict[str, Any]] = []
        self.previously_cleaned_results: List[CleanedTranscriptionResult] = []
        
        logger.info("TranscriptionResultCleaner initialized")
    
    async def clean_transcriptions(
        self, 
        transcriptions: List[TranscriptionResult],
        prompt: str,
        original_input: Optional[str] = None,
        include_history: bool = True,
        cleaning_batch_id: Optional[str] = None
    ) -> List[CleanedTranscriptionResult]:
        """Clean a list of transcription results using the cleaning engine.
        
        Args:
            transcriptions: List of transcription results to clean
            prompt: Instructions for cleaning the transcriptions
            original_input: Original raw input text (for context)
            include_history: Whether to include previously cleaned results for context
            
        Returns:
            List of cleaned transcription results
        """
        if not transcriptions:
            logger.warning("No transcriptions provided for cleaning")
            return []
        
        # Prepare the input text from transcriptions
        input_text = self._prepare_input_text(transcriptions)
        
        # Get previously cleaned text for context
        previously_cleaned = None
        if include_history and self.previously_cleaned_results:
            previously_cleaned = self._prepare_cleaned_input_text(self.previously_cleaned_results)
        
        # Build the full prompt with context
        full_prompt = self._build_prompt(
            prompt, input_text, original_input, previously_cleaned
        )
        
        # Call the cleaning engine
        cleaned_text = await self.engine.send_prompt(full_prompt)
        
        # Parse the cleaned text back into individual results
        cleaned_results = self._parse_cleaned_results(
            transcriptions, cleaned_text, cleaning_batch_id
        )
        
        # Record this cleaning operation in history
        self._record_cleaning_operation(
            input_text, cleaned_text, prompt, original_input, previously_cleaned
        )
        
        # Update previously cleaned results
        self.previously_cleaned_results.extend(cleaned_results)
        
        logger.info(f"Successfully cleaned {len(transcriptions)} transcriptions")
        return cleaned_results
            
    
    def _prepare_cleaned_input_text(self, cleaned_transcriptions: List[CleanedTranscriptionResult]) -> str:
        """Prepare input text from cleaned transcription results.
        
        Args:
            cleaned_transcriptions: List of cleaned transcription results
            
        Returns:
            Formatted input text
        """
        lines = []
        for i, result in enumerate(cleaned_transcriptions, 1):
            # Include cleaning service and model for context
            service_str = f"[{result.cleaning_service}]" if result.cleaning_service else ""
            confidence_str = f"({result.cleaning_confidence:.1%})" if result.cleaning_confidence else ""
            
            line = f"{i}. {result.cleaned_text} {confidence_str} {service_str}"
            lines.append(line)
        
        return "\n".join(lines)

    def _prepare_input_text(self, transcriptions: List[TranscriptionResult]) -> str:
        """Prepare input text from transcription results.
        
        Args:
            transcriptions: List of transcription results
            
        Returns:
            Formatted input text
        """
        lines = []
        for i, result in enumerate(transcriptions, 1):
            # Include confidence and mode for context
            confidence_str = f"({result.confidence:.1%})" if result.confidence > 0 else ""
            mode_str = f"[{result.transcription_mode}]" if result.transcription_mode else ""
            
            line = f"{i}. {result.text} {confidence_str} {mode_str}"
            lines.append(line)
        
        return "\n".join(lines)
    
    def _build_prompt(
        self, 
        prompt: str, 
        input_text: str, 
        original_input: Optional[str] = None,
        previously_cleaned: Optional[str] = None
    ) -> str:
        """Build the full prompt with context.
        
        Args:
            prompt: Base cleaning instructions
            input_text: Current input text to clean
            original_input: Original raw input (for context)
            previously_cleaned: Previously cleaned text (for context)
            
        Returns:
            Complete prompt with context
        """
        full_prompt = f"""You are a transcription cleaning assistant. Your task is to clean up transcription results to make them more readable and accurate.

{prompt}

Current transcription results to clean:
{input_text}

"""
        
        if original_input:
            full_prompt += f"Original raw input (for reference):\n{original_input}\n\n"
        
        if previously_cleaned:
            full_prompt += f"Previously cleaned text (for context and consistency):\n{previously_cleaned}\n\n"
        
        full_prompt += """Please clean up the transcription results above. Return the cleaned text in the same numbered format, but with improved readability, grammar, and accuracy. Maintain the same number of items and their order.

Cleaned transcription results:"""
        
        return full_prompt
    
    def _parse_cleaned_results(
        self, 
        original_transcriptions: List[TranscriptionResult], 
        cleaned_text: str,
        cleaning_batch_id: Optional[str] = None
    ) -> List[CleanedTranscriptionResult]:
        """Parse cleaned text into a single CleanedTranscriptionResult object.
        
        Args:
            original_transcriptions: Original transcription results
            cleaned_text: Cleaned text from the engine
            cleaning_batch_id: Optional batch ID for grouping
            
        Returns:
            List containing a single cleaned transcription result
        """
        # Extract chunk IDs from original transcriptions
        chunk_ids = [result.chunk_id for result in original_transcriptions if result.chunk_id]
        
        # Get original texts for comparison
        original_texts = [result.text for result in original_transcriptions]
        
        # Create a single cleaned transcription result
        cleaned_result = CleanedTranscriptionResult(
            original_chunk_ids=chunk_ids,
            cleaned_text=cleaned_text.strip(),
            cleaning_timestamp=datetime.now(),
            cleaning_service=getattr(self.engine, 'model', 'Unknown'),
            cleaning_model=getattr(self.engine, 'model', 'Unknown'),
            original_texts=original_texts,
            cleaning_batch_id=cleaning_batch_id,
            sequence_number=len(self.previously_cleaned_results) + 1
        )
        
        return [cleaned_result]
    
    def _extract_text_from_line(self, line: str) -> str:
        """Extract cleaned text from a numbered line.
        
        Args:
            line: Line like "1. Hello world (95%) [realtime]"
            
        Returns:
            Extracted text "Hello world"
        """
        # Remove numbering and metadata
        parts = line.split('.', 1)
        if len(parts) > 1:
            text_part = parts[1].strip()
            # Remove confidence and mode info
            text_part = text_part.split('(')[0].strip()
            text_part = text_part.split('[')[0].strip()
            return text_part
        return line.strip()
    
    def _record_cleaning_operation(
        self, 
        input_text: str, 
        cleaned_text: str, 
        prompt: str,
        original_input: Optional[str] = None,
        previously_cleaned: Optional[str] = None
    ) -> None:
        """Record a cleaning operation in history.
        
        Args:
            input_text: Input text that was cleaned
            cleaned_text: Resulting cleaned text
            prompt: Prompt used for cleaning
            original_input: Original input (if any)
            previously_cleaned: Previously cleaned text (if any)
        """
        operation = {
            "timestamp": datetime.now(),
            "input_text": input_text,
            "cleaned_text": cleaned_text,
            "prompt": prompt,
            "original_input": original_input,
            "previously_cleaned": previously_cleaned
        }
        
        self.cleaning_history.append(operation)
        logger.debug(f"Recorded cleaning operation {len(self.cleaning_history)}")
    
    def get_cleaning_history(self) -> List[Dict[str, Any]]:
        """Get the history of cleaning operations.
        
        Returns:
            List of cleaning operation records
        """
        return self.cleaning_history.copy()
    
    def get_previously_cleaned_results(self) -> List[CleanedTranscriptionResult]:
        """Get previously cleaned transcription results.
        
        Returns:
            List of previously cleaned transcription results
        """
        return self.previously_cleaned_results.copy()
    
    def clear_history(self) -> None:
        """Clear the cleaning history and previously cleaned results."""
        self.cleaning_history.clear()
        self.previously_cleaned_results.clear()
        logger.info("Cleared cleaning history and previously cleaned results")
    
    def clear_previously_cleaned_results(self) -> None:
        """Clear only the previously cleaned results."""
        self.previously_cleaned_results.clear()
        logger.info("Cleared previously cleaned results") 