"""Session manager for handling recording sessions and file operations."""

import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path

from ..storage.file_manager import FileManager
from ..models.session import SessionInfo
from ..models.transcription import TranscriptionResult
from ..config import Listen2MeConfig

logger = logging.getLogger(__name__)


class SessionManager:
    """Manages recording sessions, file storage, and session metadata."""
    
    def __init__(self, config: Listen2MeConfig):
        """Initialize session manager.
        
        Args:
            config: Application configuration
        """
        self.config = config
        self.file_manager = FileManager(config.get_data_directory())
        logger.info(f"SessionManager initialized with data dir: {config.get_data_directory()}")
    
    def create_session(self) -> str:
        """Create a new recording session.
        
        Returns:
            New session ID
        """
        session_id = self.file_manager.create_session_directory()
        logger.info(f"Created new session: {session_id}")
        return session_id
    
    def save_session_data(self, 
                         session_id: str, 
                         audio_file_path: str,
                         duration_seconds: float,
                         sample_rate: int,
                         total_chunks: int,
                         realtime_results: List[TranscriptionResult],
                         batch_results: List[TranscriptionResult],
                         all_realtime_attempts: List[TranscriptionResult],
                         all_batch_attempts: List[TranscriptionResult]) -> Dict[str, Any]:
        """Save complete session data including audio and transcription results.
        
        Args:
            session_id: Session identifier
            audio_file_path: Path to saved audio file
            duration_seconds: Recording duration
            sample_rate: Audio sample rate
            total_chunks: Total audio chunks processed
            realtime_results: Meaningful real-time transcription results
            batch_results: Meaningful batch transcription results
            all_realtime_attempts: ALL real-time attempts (including no speech)
            all_batch_attempts: ALL batch attempts (including no speech)
            
        Returns:
            Dictionary with saved file paths and metadata
        """
        try:
            session_path = self.file_manager.get_session_path(session_id)
            audio_filename = f"recording_{session_id}.wav"
            saved_files = []
            
            # Save session info
            file_size = Path(audio_file_path).stat().st_size if Path(audio_file_path).exists() else 0
            session_info = SessionInfo(
                session_id=session_id,
                start_time=datetime.now(),
                duration_seconds=duration_seconds,
                audio_file=audio_filename,
                file_size_bytes=file_size,
                sample_rate=sample_rate,
                total_chunks=total_chunks
            )
            self.file_manager.save_session_info(session_info)
            saved_files.append("session_info.json")
            
            # Save real-time transcription results (including debug data)
            if realtime_results or all_realtime_attempts:
                realtime_files = self._save_transcription_results(
                    session_id=session_id,
                    session_path=session_path,
                    mode="realtime",
                    meaningful_results=realtime_results,
                    all_attempts=all_realtime_attempts,
                    audio_filename=audio_filename
                )
                saved_files.extend(realtime_files)
            
            # Save batch transcription results (including debug data)
            if batch_results or all_batch_attempts:
                batch_files = self._save_transcription_results(
                    session_id=session_id,
                    session_path=session_path,
                    mode="batch",
                    meaningful_results=batch_results,
                    all_attempts=all_batch_attempts,
                    audio_filename=audio_filename
                )
                saved_files.extend(batch_files)
            
            # Save combined transcription for compatibility
            combined_results = realtime_results + batch_results
            if combined_results:
                combined_file = self._save_combined_transcription(
                    session_id=session_id,
                    session_path=session_path,
                    combined_results=combined_results,
                    realtime_count=len(realtime_results),
                    batch_count=len(batch_results),
                    audio_filename=audio_filename
                )
                saved_files.append(combined_file)
            
            logger.info(f"Saved session data for {session_id}: {len(saved_files)} files")
            
            return {
                "success": True,
                "session_id": session_id,
                "session_path": str(session_path),
                "saved_files": saved_files,
                "file_count": len(saved_files)
            }
            
        except Exception as e:
            logger.error(f"Error saving session data: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _save_transcription_results(self,
                                  session_id: str,
                                  session_path: Path,
                                  mode: str,
                                  meaningful_results: List[TranscriptionResult],
                                  all_attempts: List[TranscriptionResult],
                                  audio_filename: str) -> List[str]:
        """Save transcription results in both JSON and text format.
        
        Args:
            session_id: Session identifier
            session_path: Path to session directory
            mode: Transcription mode ("realtime" or "batch")
            meaningful_results: Results with actual speech
            all_attempts: All transcription attempts including no speech
            audio_filename: Name of audio file
            
        Returns:
            List of saved filenames
        """
        json_filename = f"{mode}_transcription_{session_id}.json"
        txt_filename = f"{mode}_transcription_{session_id}.txt"
        json_filepath = session_path / json_filename
        txt_filepath = session_path / txt_filename
        
        # JSON format (use all attempts for debugging)
        transcription_data = {
            "session_id": session_id,
            "transcription_mode": mode,
            "generated_at": datetime.now().isoformat(),
            "total_results": len(all_attempts),
            "meaningful_results": len(meaningful_results),
            "audio_file": audio_filename,
            "transcription_segments": []
        }
        
        for i, result in enumerate(all_attempts):
            segment = {
                "segment_id": i + 1,
                "timestamp": result.timestamp.isoformat(),
                "audio_start_time": result.audio_start_time,
                "audio_end_time": result.audio_end_time,
                "text": result.text,
                "confidence": result.confidence,
                "service": result.service,
                "language": result.language,
                "processing_time": result.processing_time,
                "transcription_mode": result.transcription_mode,
                "chunk_id": result.chunk_id,
                "alternatives": result.alternatives
            }
            
            # Add batch-specific fields
            if hasattr(result, 'batch_id') and result.batch_id:
                segment["batch_id"] = result.batch_id
                
            transcription_data["transcription_segments"].append(segment)
        
        # Save JSON
        with open(json_filepath, 'w', encoding='utf-8') as f:
            json.dump(transcription_data, f, indent=2, ensure_ascii=False)
        
        # Text format (use all attempts for debugging)
        with open(txt_filepath, 'w', encoding='utf-8') as f:
            mode_upper = mode.upper()
            f.write(f"{mode_upper} Transcription for session: {session_id}\n")
            f.write(f"Generated at: {datetime.now().isoformat()}\n")
            f.write(f"Total attempts: {len(all_attempts)} (meaningful: {len(meaningful_results)})\n")
            f.write("=" * 60 + "\n\n")
            
            for i, result in enumerate(all_attempts):
                audio_time = f"Audio: {result.audio_start_time:.1f}-{result.audio_end_time:.1f}s" if result.audio_start_time else ""
                prefix = f"[{mode_upper[:2]}-{i+1:03d}]" if mode == "realtime" else f"[{mode_upper}-{i+1:03d}]"
                
                f.write(f"{prefix} {result.timestamp.strftime('%H:%M:%S')} {audio_time}\n")
                
                if hasattr(result, 'batch_id') and result.batch_id:
                    f.write(f"{' ' * len(prefix)} Batch ID: {result.batch_id}\n")
                    
                f.write(f"{' ' * len(prefix)} Confidence: {result.confidence:.1%} via {result.service}\n")
                f.write(f"{' ' * len(prefix)} {result.text}\n\n")
        
        logger.info(f"Saved {len(all_attempts)} {mode} transcription attempts ({len(meaningful_results)} meaningful)")
        
        return [json_filename, txt_filename]
    
    def _save_combined_transcription(self,
                                   session_id: str,
                                   session_path: Path,
                                   combined_results: List[TranscriptionResult],
                                   realtime_count: int,
                                   batch_count: int,
                                   audio_filename: str) -> str:
        """Save combined transcription results for compatibility.
        
        Args:
            session_id: Session identifier
            session_path: Path to session directory
            combined_results: All meaningful transcription results
            realtime_count: Number of real-time results
            batch_count: Number of batch results
            audio_filename: Name of audio file
            
        Returns:
            Saved filename
        """
        combined_filename = f"combined_transcription_{session_id}.json"
        combined_filepath = session_path / combined_filename
        
        combined_data = {
            "session_id": session_id,
            "transcription_mode": "combined",
            "generated_at": datetime.now().isoformat(),
            "total_results": len(combined_results),
            "audio_file": audio_filename,
            "realtime_count": realtime_count,
            "batch_count": batch_count,
            "transcription_segments": []
        }
        
        for i, result in enumerate(combined_results):
            segment = {
                "segment_id": i + 1,
                "timestamp": result.timestamp.isoformat(),
                "audio_start_time": getattr(result, 'audio_start_time', None),
                "audio_end_time": getattr(result, 'audio_end_time', None),
                "text": result.text,
                "confidence": result.confidence,
                "service": result.service,
                "transcription_mode": getattr(result, 'transcription_mode', 'unknown'),
                "batch_id": getattr(result, 'batch_id', None)
            }
            combined_data["transcription_segments"].append(segment)
        
        with open(combined_filepath, 'w', encoding='utf-8') as f:
            json.dump(combined_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Saved combined transcription: {combined_filename}")
        return combined_filename
    
    def get_session_path(self, session_id: str) -> Path:
        """Get path to session directory.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Path to session directory
        """
        return self.file_manager.get_session_path(session_id)
    
    def list_sessions(self) -> List[Dict[str, Any]]:
        """List all available sessions.
        
        Returns:
            List of session metadata dictionaries
        """
        return self.file_manager.list_sessions()
    
    def load_session_info(self, session_id: str) -> Optional[SessionInfo]:
        """Load session information.
        
        Args:
            session_id: Session identifier
            
        Returns:
            SessionInfo object or None if not found
        """
        return self.file_manager.load_session_info(session_id)