"""Simple transcription screen without fancy keyboard handling."""

import time
import logging
import sys
import select
import termios
import tty
from datetime import datetime
from typing import Optional
from dataclasses import dataclass
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich.align import Align

from ..audio.capture import AudioCapture
from ..storage.file_manager import FileManager, SessionInfo


logger = logging.getLogger(__name__)


@dataclass
class TranscriptionStatus:
    """Status information for transcription session."""
    session_id: Optional[str] = None
    is_recording: bool = False
    is_transcribing: bool = False
    duration_seconds: float = 0.0
    total_chunks: int = 0
    chunks_processed: int = 0
    peak_level: float = 0.0
    current_text: str = ""


class SimpleTranscriptionScreen:
    """Simple transcription interface using basic input/output."""
    
    def __init__(self, data_dir: str = "./data"):
        """Initialize simple transcription screen."""
        self.console = Console()
        self.file_manager = FileManager(data_dir)
        self.audio_capture: Optional[AudioCapture] = None
        self.status = TranscriptionStatus()
        self.running = False
        
        logger.info(f"SimpleTranscriptionScreen initialized with data_dir: {data_dir}")
    
    def show_status(self) -> None:
        """Show current status."""
        self.console.clear()
        
        # Header
        self.console.print("🎙️  Listen2Me - Simple Mode", style="bold blue")
        self.console.print("=" * 50)
        
        # Status
        if self.status.is_recording:
            self.console.print("🔴 RECORDING", style="bold red")
        else:
            self.console.print("⏹️  STOPPED", style="bold yellow")
        
        if self.status.session_id:
            self.console.print(f"Session: {self.status.session_id}")
        
        # Audio stats
        if self.audio_capture:
            stats = self.audio_capture.get_recording_stats()
            self.console.print(f"Duration: {stats.duration_seconds:.1f}s")
            self.console.print(f"Chunks: {stats.total_chunks}")
            self.console.print(f"Peak Level: {stats.peak_level:.3f}")
            
            # Visual peak level
            peak_bar = "█" * int(stats.peak_level * 20)
            self.console.print(f"Audio: [{peak_bar:<20}] {stats.peak_level:.3f}")
        
        # Mock transcription
        if self.status.chunks_processed > 0:
            self.console.print(f"\n📝 Processing: {self.status.chunks_processed} chunks")
            confidence = min(0.95, 0.7 + (self.status.chunks_processed * 0.01))
            self.console.print(f"Confidence: {confidence:.1%}")
        
        # Controls
        self.console.print("\n" + "=" * 50)
        self.console.print("Commands:")
        self.console.print("  [bold green]1[/bold green] - Start recording")
        self.console.print("  [bold yellow]2[/bold yellow] - Stop recording") 
        self.console.print("  [bold blue]3[/bold blue] - Reset session")
        self.console.print("  [bold red]q[/bold red] - Quit")
        self.console.print("=" * 50)
    
    def update_status_from_audio(self) -> None:
        """Update status from audio capture."""
        if self.audio_capture:
            stats = self.audio_capture.get_recording_stats()
            self.status.is_recording = stats.is_recording
            self.status.duration_seconds = stats.duration_seconds
            self.status.total_chunks = stats.total_chunks
            self.status.peak_level = stats.peak_level
            
            # Mock processing
            if self.status.is_recording and stats.total_chunks > 0:
                self.status.chunks_processed = min(
                    self.status.total_chunks,
                    self.status.chunks_processed + 1
                )
                self.status.is_transcribing = self.status.chunks_processed < self.status.total_chunks
    
    def start_recording(self) -> None:
        """Start recording."""
        try:
            if self.audio_capture and self.audio_capture.is_recording:
                self.console.print("⚠️  Already recording", style="yellow")
                return
            
            self.audio_capture = AudioCapture(
                sample_rate=16000,
                chunk_size=1024,
                buffer_size=100,
                channels=1
            )
            
            self.status.session_id = self.file_manager.create_session_directory()
            self.audio_capture.start_recording()
            self.status.is_recording = True
            self.status.chunks_processed = 0
            
            self.console.print("✅ Recording started!", style="bold green")
            logger.info(f"Started recording for session: {self.status.session_id}")
            
        except Exception as e:
            self.console.print(f"❌ Error starting recording: {e}", style="bold red")
            logger.error(f"Error starting recording: {e}")
    
    def stop_recording(self) -> None:
        """Stop recording."""
        try:
            if not self.audio_capture or not self.audio_capture.is_recording:
                self.console.print("⚠️  Not recording", style="yellow")
                return
            
            self.audio_capture.stop_recording()
            self.status.is_recording = False
            
            # Save session
            if self.status.session_id:
                audio_filename = f"recording_{self.status.session_id}.wav"
                session_path = self.file_manager.get_session_path(self.status.session_id)
                audio_filepath = session_path / audio_filename
                
                self.audio_capture.save_to_file(str(audio_filepath))
                
                stats = self.audio_capture.get_recording_stats()
                session_info = SessionInfo(
                    session_id=self.status.session_id,
                    start_time=datetime.now(),
                    duration_seconds=stats.duration_seconds,
                    audio_file=audio_filename,
                    file_size_bytes=audio_filepath.stat().st_size if audio_filepath.exists() else 0,
                    sample_rate=self.audio_capture.sample_rate,
                    total_chunks=stats.total_chunks
                )
                self.file_manager.save_session_info(session_info)
                
                self.console.print(f"✅ Recording stopped and saved: {self.status.session_id}", style="bold green")
                logger.info(f"Session saved: {self.status.session_id}")
            
        except Exception as e:
            self.console.print(f"❌ Error stopping recording: {e}", style="bold red")
            logger.error(f"Error stopping recording: {e}")
    
    def reset_session(self) -> None:
        """Reset session."""
        try:
            if self.audio_capture and self.audio_capture.is_recording:
                self.stop_recording()
            
            self.status = TranscriptionStatus()
            self.audio_capture = None
            
            self.console.print("🔄 Session reset", style="bold blue")
            logger.info("Session reset")
            
        except Exception as e:
            self.console.print(f"❌ Error resetting session: {e}", style="bold red")
            logger.error(f"Error resetting session: {e}")
    
    def _get_user_input(self) -> Optional[str]:
        """Get user input in a way that works in all terminals."""
        try:
            if sys.platform != 'win32':
                # Always check if input is available first (non-blocking)
                if select.select([sys.stdin], [], [], 0.0)[0]:
                    # Input is available, try to read it
                    try:
                        # Try reading a line and return first character
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
        self.console.print("Type commands and press Enter (or single keypress if supported).")
        self.console.print("The screen will update automatically while recording.\n")
        
        try:
            loop_count = 0
            while self.running:
                loop_count += 1
                
                # Update status
                self.update_status_from_audio()
                
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
            
            if self.audio_capture and self.audio_capture.is_recording:
                self.stop_recording()
            
            self.console.print("\n👋 Listen2Me session ended", style="bold blue")
            logger.info("SimpleTranscriptionScreen cleanup completed")
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")


def main():
    """Main entry point for simple transcription screen."""
    try:
        screen = SimpleTranscriptionScreen()
        screen.run()
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    main()