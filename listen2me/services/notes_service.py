"""Notes service for high-level API to fetch processed chunks and session data."""

import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
from pathlib import Path

from ..models.notes import (
    ProcessingStatus,
    AudioChunk,
    RawTranscription,
    ProcessedChunk,
    SessionNotes,
    NotesQuery,
    NotesResponse,
)
from ..models.transcription import TranscriptionResult
from ..config import Listen2MeConfig
from .recording_service import RecordingService
from .session_manager import SessionManager

logger = logging.getLogger(__name__)


class NotesService:
    """High-level service for accessing processed notes and transcriptions.
    
    This service provides a clean API for clients to:
    1. Start/stop recording sessions
    2. Poll for processed chunks with high watermark
    3. Get session status and metadata
    4. Access different stages of processing (raw, cleaned, annotated)
    
    The service abstracts away the internal audio processing pipeline.
    """
    
    def __init__(self, config: Listen2MeConfig):
        """Initialize notes service.
        
        Args:
            config: Application configuration
        """
        self.config = config
        self.recording_service = RecordingService(config)
        self.session_manager = SessionManager(config)
        
        # Track client high watermarks per session
        self._client_watermarks: Dict[str, Optional[datetime]] = {}
        
        logger.info("NotesService initialized")
    
    def start_recording_session(self) -> Dict[str, Any]:
        """Start a new recording session.
        
        Returns:
            Dict with session_id and success status
        """
        try:
            # Create new session
            session_id = self.session_manager.create_session()
            
            # Start recording via recording service
            result = self.recording_service.start_recording(session_id)
            
            if result["success"]:
                # Initialize watermark for this session
                self._client_watermarks[session_id] = None
                
                logger.info(f"Started recording session: {session_id}")
                return {
                    "success": True,
                    "session_id": session_id,
                    "started_at": result.get("started_at")
                }
            else:
                return {
                    "success": False,
                    "error": result["error"]
                }
                
        except Exception as e:
            logger.error(f"Error starting recording session: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def stop_recording_session(self, session_id: str) -> Dict[str, Any]:
        """Stop recording session and save all data.
        
        Args:
            session_id: Session to stop
            
        Returns:
            Dict with success status and final session data
        """
        try:
            # Stop recording
            result = self.recording_service.stop_recording()
            
            if not result["success"]:
                return {
                    "success": False,
                    "error": result["error"]
                }
            
            # Save audio file
            session_path = self.session_manager.get_session_path(session_id)
            audio_filename = f"recording_{session_id}.wav"
            audio_filepath = session_path / audio_filename
            
            if not self.recording_service.save_audio_file(str(audio_filepath)):
                return {
                    "success": False,
                    "error": "Failed to save audio file"
                }
            
            # Get final results and save session data
            final_results = self.recording_service.get_transcription_results()
            stats = self.recording_service.get_recording_stats()
            
            save_result = self.session_manager.save_session_data(
                session_id=session_id,
                audio_file_path=str(audio_filepath),
                duration_seconds=stats.duration_seconds if stats else 0,
                sample_rate=stats.sample_rate if stats else 16000,
                total_chunks=stats.total_chunks if stats else 0,
                realtime_results=final_results["realtime"],
                batch_results=final_results["batch"],
                all_realtime_attempts=final_results["all_realtime_attempts"],
                all_batch_attempts=final_results["all_batch_attempts"]
            )
            
            if not save_result["success"]:
                return {
                    "success": False,
                    "error": f"Failed to save session data: {save_result['error']}"
                }
            
            logger.info(f"Stopped recording session: {session_id}")
            return {
                "success": True,
                "session_id": session_id,
                "stopped_at": result.get("stopped_at"),
                "duration_seconds": result.get("duration_seconds"),
                "total_chunks": result.get("total_chunks"),
                "transcription_counts": {
                    "realtime": len(final_results["realtime"]),
                    "batch": len(final_results["batch"]),
                    "total_attempts": {
                        "realtime": len(final_results["all_realtime_attempts"]),
                        "batch": len(final_results["all_batch_attempts"])
                    }
                }
            }
            
        except Exception as e:
            logger.error(f"Error stopping recording session {session_id}: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_session_status(self, session_id: str) -> SessionNotes:
        """Get current status of a recording session.
        
        Args:
            session_id: Session to check
            
        Returns:
            SessionNotes with current status
        """
        try:
            # Get session info from file system
            session_info = self.session_manager.load_session_info(session_id)
            
            # Check if currently recording
            is_recording = (
                self.recording_service.is_recording and 
                self.recording_service.current_session_id == session_id
            )
            
            # Get current recording stats if active
            stats = None
            if is_recording:
                stats = self.recording_service.get_recording_stats()
            
            # Create SessionNotes
            session_notes = SessionNotes(
                session_id=session_id,
                start_time=session_info.start_time if session_info else datetime.now(),
                duration_seconds=stats.duration_seconds if stats else (session_info.duration_seconds if session_info else None),
                is_recording=is_recording,
                is_processing=is_recording,  # Simplified - processing happens during recording
                is_complete=not is_recording and session_info is not None,
                total_chunks=stats.total_chunks if stats else (session_info.total_chunks if session_info else 0),
                audio_file_path=str(self.session_manager.get_session_path(session_id) / f"recording_{session_id}.wav") if session_info else None,
                session_file_path=str(self.session_manager.get_session_path(session_id) / "session_info.json") if session_info else None
            )
            
            return session_notes
            
        except Exception as e:
            logger.error(f"Error getting session status for {session_id}: {e}")
            # Return minimal session info on error
            return SessionNotes(
                session_id=session_id,
                start_time=datetime.now(),
                is_recording=False,
                is_processing=False,
                is_complete=False
            )
    
    def get_processed_chunks(self, query: NotesQuery) -> NotesResponse:
        """Get processed chunks for a session with high watermark support.
        
        Args:
            query: Query parameters including session_id and high_watermark
            
        Returns:
            NotesResponse with processed chunks newer than high watermark
        """
        try:
            session_id = query.session_id
            
            # Get current session status
            session_status = self.get_session_status(session_id)
            
            # Get transcription results from recording service
            if self.recording_service.current_session_id == session_id:
                # Session is active - process any pending audio chunks first
                self.recording_service.process_audio_chunks()
                
                # Then get live results
                results = self.recording_service.get_transcription_results()
                all_transcriptions = results["all_realtime_attempts"] + results["all_batch_attempts"]
            else:
                # Session is completed - would need to load from files
                # For now, return empty results for completed sessions
                # TODO: Implement loading completed session transcriptions
                all_transcriptions = []
            
            # Filter transcriptions by high watermark
            high_watermark = query.high_watermark or self._client_watermarks.get(session_id)
            filtered_transcriptions = []
            
            if high_watermark:
                filtered_transcriptions = [
                    t for t in all_transcriptions 
                    if t.timestamp > high_watermark
                ]
            else:
                filtered_transcriptions = all_transcriptions
            
            # Apply limit if specified
            if query.limit:
                filtered_transcriptions = filtered_transcriptions[:query.limit]
            
            # Convert TranscriptionResults to ProcessedChunks
            processed_chunks = []
            for i, transcription in enumerate(filtered_transcriptions):
                # Create AudioChunk (simplified - we don't have actual audio bytes here)
                audio_chunk = AudioChunk(
                    chunk_id=transcription.chunk_id or f"chunk_{i}",
                    session_id=session_id,
                    start_time=transcription.audio_start_time or 0.0,
                    end_time=transcription.audio_end_time or 0.0,
                    audio_data=b"",  # Not included unless specifically requested
                    sample_rate=16000,  # Default
                    timestamp=transcription.timestamp,
                    processing_status=ProcessingStatus.COMPLETED
                )
                
                # Create RawTranscription
                raw_transcription = RawTranscription(
                    transcription_id=f"raw_{transcription.chunk_id or i}",
                    chunk_id=transcription.chunk_id or f"chunk_{i}",
                    session_id=session_id,
                    text=transcription.text,
                    confidence=transcription.confidence,
                    service=transcription.service,
                    language=transcription.language,
                    processing_time=transcription.processing_time,
                    timestamp=transcription.timestamp,
                    transcription_mode=transcription.transcription_mode,
                    alternatives=transcription.alternatives,
                    batch_id=getattr(transcription, 'batch_id', None)
                )
                
                # Create ProcessedChunk
                processed_chunk = ProcessedChunk(
                    chunk_id=transcription.chunk_id or f"chunk_{i}",
                    session_id=session_id,
                    audio=audio_chunk,
                    raw_transcriptions=[raw_transcription],
                    raw_transcription_status=ProcessingStatus.COMPLETED,
                    processed_transcription_status=ProcessingStatus.PENDING,  # Not yet implemented
                    annotation_status=ProcessingStatus.PENDING,  # Not yet implemented
                    created_at=transcription.timestamp,
                    updated_at=transcription.timestamp
                )
                
                processed_chunks.append(processed_chunk)
            
            # Calculate new high watermark
            new_high_watermark = None
            if processed_chunks:
                new_high_watermark = max(chunk.updated_at for chunk in processed_chunks)
                # Update client watermark
                self._client_watermarks[session_id] = new_high_watermark
            
            # Create response
            response = NotesResponse(
                session_id=session_id,
                chunks=processed_chunks,
                new_high_watermark=new_high_watermark,
                total_chunks_available=len(all_transcriptions),
                has_more=query.limit is not None and len(filtered_transcriptions) >= query.limit,
                session_status=session_status
            )
            
            logger.debug(f"Returning {len(processed_chunks)} processed chunks for session {session_id}")
            return response
            
        except Exception as e:
            logger.error(f"Error getting processed chunks for session {query.session_id}: {e}")
            # Return empty response on error
            return NotesResponse(
                session_id=query.session_id,
                chunks=[],
                new_high_watermark=query.high_watermark,
                total_chunks_available=0,
                has_more=False,
                session_status=self.get_session_status(query.session_id)
            )
    
    def list_sessions(self) -> List[SessionNotes]:
        """List all available sessions.
        
        Returns:
            List of SessionNotes for all sessions
        """
        try:
            sessions_metadata = self.session_manager.list_sessions()
            session_notes = []
            
            for session_meta in sessions_metadata:
                session_id = session_meta["session_id"]
                session_status = self.get_session_status(session_id)
                session_notes.append(session_status)
            
            return session_notes
            
        except Exception as e:
            logger.error(f"Error listing sessions: {e}")
            return []
    
    def cleanup(self) -> None:
        """Clean up service resources."""
        try:
            self.recording_service.cleanup()
            self._client_watermarks.clear()
            logger.info("NotesService cleaned up")
        except Exception as e:
            logger.error(f"Error during NotesService cleanup: {e}")