"""Simple transcription screen using the internal service API."""

import time
import logging
import sys
import select
import termios
import tty
from datetime import datetime
from typing import Optional
from ..models.ui import TranscriptionStatus
from rich.console import Console

from ..services.recording_service import RecordingService
from ..services.session_manager import SessionManager
from ..config import get_config

logger = logging.getLogger(__name__)


class SimpleTranscriptionScreen:
    """Simple transcription interface using the internal service API."""
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize simple transcription screen."""
        self.console = Console()
        
        # Load configuration
        if config_path:
            from ..config import reload_config
            self.config = reload_config(config_path)
        else:
            self.config = get_config()
        
        # Initialize services
        logger.info("Initializing services...")
        self.console.print("🔧 Initializing transcription services...", style="blue")
        
        self.recording_service = RecordingService(self.config)
        self.session_manager = SessionManager(self.config)
        
        self.console.print("✅ Transcription engine ready!", style="green")
        logger.info("Services initialized successfully")
        
        # UI state
        self.status = TranscriptionStatus()
        self.running = False
        
        # Cache for display
        self._last_transcription_results = []
        
        logger.info(f"SimpleTranscriptionScreen initialized with config: {self.config.config_file}")
    
    def show_status(self) -> None:
        """Show current status."""
        self.console.clear()
        
        # Header
        self.console.print("🎙️  Listen2Me - Simple Mode", style="bold blue")
        self.console.print("=" * 50)
        
        # Recording status
        if self.status.is_recording:
            self.console.print("🔴 RECORDING", style="bold red")
        else:
            self.console.print("⏹️  STOPPED", style="bold yellow")
        
        if self.status.session_id:
            self.console.print(f"Session: {self.status.session_id}")
        
        # System readiness indicators
        self.console.print()
        microphone_status = "✅ Microphone Ready" if self.recording_service.check_microphone_available() else "❌ Microphone Not Available"
        
        display_info = self.recording_service.get_transcription_info()
        transcription_status = f"✅ Transcription Ready{display_info}"
        
        self.console.print(f"{microphone_status}", style="green" if "✅" in microphone_status else "red")
        self.console.print(f"{transcription_status}", style="green")
        
        # Audio stats
        stats = self.recording_service.get_recording_stats()
        if stats:
            self.console.print(f"Duration: {stats.duration_seconds:.1f}s")
            self.console.print(f"Chunks: {stats.total_chunks}")
            self.console.print(f"Peak Level: {stats.peak_level:.3f}")
            
            # Visual peak level
            peak_bar = "█" * int(stats.peak_level * 20)
            self.console.print(f"Audio: [{peak_bar:<20}] {stats.peak_level:.3f}")
        
        # Transcription results
        if self._last_transcription_results:
            self.console.print(f"\n📝 Transcription:")
            # Show last 3 transcription results
            recent_results = self._last_transcription_results[-3:]
            for i, result in enumerate(recent_results):
                if result.text and result.text.strip():
                    confidence_str = f"({result.confidence:.1%})" if result.confidence > 0 else ""
                    service_str = f"[{result.service}]"
                    self.console.print(f"   {result.text} {confidence_str} {service_str}")
                    
            if len(self._last_transcription_results) > 3:
                self.console.print(f"   ... and {len(self._last_transcription_results) - 3} more results")
        elif self.status.is_recording:
            self.console.print(f"\n📝 Listening for speech... ({self.status.chunks_processed} chunks processed)")
        else:
            self.console.print(f"\n📝 Transcription engine ready - start recording to begin")
        
        # Controls
        self.console.print("\n" + "=" * 50)
        self.console.print("Commands:")
        self.console.print("  [bold green]1[/bold green] - Start recording")
        self.console.print("  [bold yellow]2[/bold yellow] - Stop recording") 
        self.console.print("  [bold blue]3[/bold blue] - Reset session")
        self.console.print("  [bold red]q[/bold red] - Quit")
        self.console.print("=" * 50)
    
    def update_status_from_service(self) -> None:
        """Update status from recording service."""
        # Update recording stats
        stats = self.recording_service.get_recording_stats()
        if stats:
            self.status.is_recording = stats.is_recording
            self.status.duration_seconds = stats.duration_seconds
            self.status.total_chunks = stats.total_chunks
            self.status.peak_level = stats.peak_level
        
        # Process audio chunks and get new transcriptions
        if self.status.is_recording:
            processing_result = self.recording_service.process_audio_chunks()
            self.status.chunks_processed += processing_result["chunks_processed"]
            
            # Update transcription results for display
            new_realtime = processing_result["new_realtime"]
            new_batch = processing_result["new_batch"]
            
            if new_realtime or new_batch:
                # Get all current results for display
                all_results = self.recording_service.get_transcription_results()
                self._last_transcription_results = all_results["combined"]
                
                # Update current text with latest result
                if new_realtime:
                    self.status.current_text = new_realtime[-1].text
                elif new_batch:
                    self.status.current_text = new_batch[-1].text
        
        # Update transcribing status
        self.status.is_transcribing = self.status.chunks_processed > len(self._last_transcription_results)
    
    def start_recording(self) -> None:
        """Start recording."""
        try:
            # Create new session
            session_id = self.session_manager.create_session()
            
            # Start recording via service
            result = self.recording_service.start_recording(session_id)
            
            if result["success"]:
                self.status.session_id = session_id
                self.status.is_recording = True
                self.status.chunks_processed = 0
                self._last_transcription_results = []
                
                self.console.print("✅ Recording and transcription started!", style="bold green")
                logger.info(f"Started recording for session: {session_id}")
            else:
                self.console.print(f"❌ Error starting recording: {result['error']}", style="bold red")
                logger.error(f"Error starting recording: {result['error']}")
                
        except Exception as e:
            self.console.print(f"❌ Error starting recording: {e}", style="bold red")
            logger.error(f"Error starting recording: {e}")
    
    def stop_recording(self) -> None:
        """Stop recording."""
        try:
            if not self.status.is_recording:
                self.console.print("⚠️  Not recording", style="yellow")
                return
            
            self.console.print("📝 Processing final transcriptions...", style="blue")
            
            # Stop recording via service
            result = self.recording_service.stop_recording()
            
            if result["success"]:
                session_id = result["session_id"]
                
                # Save audio file
                session_path = self.session_manager.get_session_path(session_id)
                audio_filename = f"recording_{session_id}.wav"
                audio_filepath = session_path / audio_filename
                
                if self.recording_service.save_audio_file(str(audio_filepath)):
                    # Get all transcription results
                    all_results = self.recording_service.get_transcription_results()
                    
                    # Save session data
                    stats = self.recording_service.get_recording_stats()
                    save_result = self.session_manager.save_session_data(
                        session_id=session_id,
                        audio_file_path=str(audio_filepath),
                        duration_seconds=stats.duration_seconds if stats else 0,
                        sample_rate=stats.sample_rate if stats else 16000,
                        total_chunks=stats.total_chunks if stats else 0,
                        realtime_results=all_results["realtime"],
                        batch_results=all_results["batch"],
                        all_realtime_attempts=all_results["all_realtime_attempts"],
                        all_batch_attempts=all_results["all_batch_attempts"]
                    )
                    
                    if save_result["success"]:
                        self.console.print(f"✅ Recording stopped and saved: {session_id}", style="bold green")
                        logger.info(f"Session saved: {session_id}")
                    else:
                        self.console.print(f"⚠️  Recording stopped but save failed: {save_result['error']}", style="yellow")
                        logger.error(f"Save failed: {save_result['error']}")
                else:
                    self.console.print("⚠️  Recording stopped but audio save failed", style="yellow")
                    
                self.status.is_recording = False
                
            else:
                self.console.print(f"❌ Error stopping recording: {result['error']}", style="bold red")
                logger.error(f"Error stopping recording: {result['error']}")
                
        except Exception as e:
            self.console.print(f"❌ Error stopping recording: {e}", style="bold red")
            logger.error(f"Error stopping recording: {e}")
    
    def reset_session(self) -> None:
        """Reset session."""
        try:
            if self.status.is_recording:
                self.stop_recording()
            
            self.status = TranscriptionStatus()
            self._last_transcription_results = []
            
            self.console.print("🔄 Session reset", style="bold blue")
            logger.info("Session reset")
            
        except Exception as e:
            self.console.print(f"❌ Error resetting session: {e}", style="bold red")
            logger.error(f"Error resetting session: {e}")
    
    def _get_user_input(self) -> Optional[str]:
        """Get user input in a way that works in all terminals."""
        try:
            if sys.platform != 'win32':
                # Non-blocking input check
                if select.select([sys.stdin], [], [], 0.0)[0]:
                    try:
                        line = sys.stdin.readline().strip().lower()
                        logger.debug(f"Line input: '{line}'")
                        return line[:1] if line else None
                    except Exception as e:
                        logger.debug(f"Error reading input line: {e}")
                        return None
            else:
                # Windows - single character input
                import msvcrt
                if msvcrt.kbhit():
                    key = msvcrt.getch().decode('utf-8')
                    logger.debug(f"Single key pressed: '{key}' (ord: {ord(key)})")
                    return key.lower()
        except Exception as e:
            logger.debug(f"Error getting user input: {e}")
        return None

    def run(self) -> None:
        """Run the simple transcription interface."""
        self.running = True
        
        self.console.print("🎙️  Listen2Me - Simple Mode Started", style="bold green")
        self.console.print("✅ Transcription services authenticated and ready", style="green")
        self.console.print("Type commands and press Enter (or single keypress if supported).")
        self.console.print("The screen will update automatically while recording.\n")
        
        try:
            loop_count = 0
            while self.running:
                loop_count += 1
                
                # Update status from services
                self.update_status_from_service()
                
                # Show current status
                self.show_status()
                
                # Check for user input
                command = self._get_user_input()
                
                if command:
                    if command == '1':
                        self.start_recording()
                    elif command == '2':
                        self.stop_recording()
                    elif command == '3':
                        self.reset_session()
                    elif command == 'q':
                        self.running = False
                    else:
                        self.console.print(f"Unknown command: {command}", style="red")
                    
                    # Small delay to show the result
                    time.sleep(1)
                
                # Debug logging every 10 cycles
                if loop_count % 10 == 0:
                    logger.debug(f"Simple mode loop cycle {loop_count}, recording: {self.status.is_recording}")
                
                # Update every 0.5 seconds for smooth real-time display
                time.sleep(0.5)
                    
        except KeyboardInterrupt:
            self.running = False
        except Exception as e:
            self.console.print(f"❌ Error: {e}", style="bold red")
            logger.error(f"Error in main loop: {e}")
        finally:
            self.cleanup()
    
    def cleanup(self) -> None:
        """Clean up resources."""
        try:
            self.running = False
            
            # Stop recording if active
            if self.status.is_recording:
                self.stop_recording()
            
            # Clean up services
            self.recording_service.cleanup()
            
            self.console.print("\n👋 Listen2Me session ended", style="bold blue")
            logger.info("SimpleTranscriptionScreen cleanup completed")
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")