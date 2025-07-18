"""Terminal-based transcription screen with real-time audio display."""

import sys
import time
import threading
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from dataclasses import dataclass
from rich.console import Console
from rich.panel import Panel
from rich.layout import Layout
from rich.live import Live
from rich.text import Text
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.align import Align

from ..audio.capture import AudioCapture, AudioStats
from ..storage.file_manager import FileManager, SessionInfo
from .keyboard_input import create_input_handler


logger = logging.getLogger(__name__)


@dataclass
class TranscriptionStatus:
    """Current status of transcription process."""
    is_recording: bool = False
    is_transcribing: bool = False
    chunks_processed: int = 0
    total_chunks: int = 0
    current_text: str = ""
    session_id: Optional[str] = None
    duration_seconds: float = 0.0
    peak_level: float = 0.0


class TranscriptionScreen:
    """Terminal-based transcription interface with real-time display."""
    
    def __init__(self, data_dir: str = "./data"):
        """Initialize transcription screen.
        
        Args:
            data_dir: Directory for storing audio and session data
        """
        self.console = Console()
        self.file_manager = FileManager(data_dir)
        self.audio_capture: Optional[AudioCapture] = None
        self.status = TranscriptionStatus()
        
        # UI update thread
        self.ui_thread: Optional[threading.Thread] = None
        self.stop_ui_event = threading.Event()
        self.running = False
        
        # Keyboard input handler - will be initialized in run()
        self.input_handler = None
        
        logger.info(f"TranscriptionScreen initialized with data_dir: {data_dir}")
    
    def create_layout(self) -> Layout:
        """Create the main UI layout."""
        layout = Layout()
        
        # Split into header, main content, and footer
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="main", ratio=1),
            Layout(name="footer", size=3)
        )
        
        # Split main content into left and right panels
        layout["main"].split_row(
            Layout(name="audio_panel", ratio=1),
            Layout(name="transcription_panel", ratio=2)
        )
        
        return layout
    
    def update_header(self, layout: Layout) -> None:
        """Update the header panel."""
        title = Text("🎙️  Listen2Me - Real-time Transcription", style="bold blue")
        status_text = "🔴 RECORDING" if self.status.is_recording else "⏹️  STOPPED"
        status_style = "bold red" if self.status.is_recording else "bold yellow"
        
        header_text = Text.assemble(
            title, "  |  ", 
            (status_text, status_style),
            "  |  ",
            f"Session: {self.status.session_id or 'None'}"
        )
        
        layout["header"].update(Panel(
            Align.center(header_text),
            style="bright_blue"
        ))
    
    def update_audio_panel(self, layout: Layout) -> None:
        """Update the audio monitoring panel."""
        audio_table = Table(title="🎵 Audio Monitor", show_header=True, header_style="bold magenta")
        audio_table.add_column("Metric", style="cyan")
        audio_table.add_column("Value", style="white")
        
        # Add audio statistics
        audio_table.add_row("Duration", f"{self.status.duration_seconds:.1f}s")
        audio_table.add_row("Chunks Captured", str(self.status.total_chunks))
        audio_table.add_row("Chunks Processed", str(self.status.chunks_processed))
        
        # Peak level visualization
        peak_bar = "█" * int(self.status.peak_level * 20)
        peak_text = f"{peak_bar:<20} {self.status.peak_level:.3f}"
        audio_table.add_row("Peak Level", peak_text)
        
        # Recording status
        recording_status = "🔴 Active" if self.status.is_recording else "⏹️ Stopped"
        audio_table.add_row("Recording", recording_status)
        
        layout["audio_panel"].update(Panel(audio_table, border_style="green"))
    
    def update_transcription_panel(self, layout: Layout) -> None:
        """Update the transcription display panel."""
        # Mock transcription for now
        if self.status.is_transcribing:
            transcription_text = Text("🔄 Transcribing audio...", style="yellow italic")
        elif self.status.current_text:
            transcription_text = Text(self.status.current_text, style="white")
        else:
            transcription_text = Text(
                "Press SPACE to start recording, 's' to stop, 'q' to quit",
                style="dim white italic"
            )
        
        # Add some mock transcription status
        if self.status.chunks_processed > 0:
            mock_confidence = min(0.95, 0.7 + (self.status.chunks_processed * 0.01))
            status_text = Text.assemble(
                "\n\n",
                ("Transcription Status: ", "bold"),
                ("✅ Processing", "green"),
                f"\nConfidence: {mock_confidence:.1%}",
                f"\nProcessed: {self.status.chunks_processed}/{self.status.total_chunks} chunks"
            )
            transcription_text = Text.assemble(transcription_text, status_text)
        
        layout["transcription_panel"].update(Panel(
            transcription_text,
            title="📝 Transcription Output",
            border_style="blue"
        ))
    
    def update_footer(self, layout: Layout) -> None:
        """Update the footer with controls."""
        controls = Text.assemble(
            ("Controls: ", "bold"),
            ("SPACE", "bold green"), " Start/Stop Recording  ",
            ("S", "bold yellow"), " Stop Recording  ",
            ("Q", "bold red"), " Quit  ",
            ("R", "bold blue"), " Reset Session  ",
            ("Ctrl+C", "bold red"), " Force Quit"
        )
        
        layout["footer"].update(Panel(
            Align.center(controls),
            style="bright_black"
        ))
    
    def update_status_from_audio(self) -> None:
        """Update status from current audio capture state."""
        if self.audio_capture:
            stats = self.audio_capture.get_recording_stats()
            self.status.is_recording = stats.is_recording
            self.status.duration_seconds = stats.duration_seconds
            self.status.total_chunks = stats.total_chunks
            self.status.peak_level = stats.peak_level
            
            # Mock processing of chunks (simulate transcription)
            if self.status.is_recording and stats.total_chunks > 0:
                # Process chunks with slight delay to simulate real transcription
                self.status.chunks_processed = min(
                    self.status.total_chunks,
                    self.status.chunks_processed + 1
                )
                self.status.is_transcribing = self.status.chunks_processed < self.status.total_chunks
    
    def update_display(self, layout: Layout) -> None:
        """Update all display components."""
        try:
            # Update status from audio capture
            self.update_status_from_audio()
            
            # Update all UI panels
            self.update_header(layout)
            self.update_audio_panel(layout)
            self.update_transcription_panel(layout)
            self.update_footer(layout)
            
        except Exception as e:
            logger.error(f"Error updating display: {e}")
    
    def start_recording(self) -> None:
        """Start audio recording and create new session."""
        try:
            if self.audio_capture and self.audio_capture.is_recording:
                logger.warning("Recording already in progress")
                return
            
            # Create new audio capture instance
            self.audio_capture = AudioCapture(
                sample_rate=16000,
                chunk_size=1024,
                buffer_size=100,
                channels=1
            )
            
            # Create new session
            self.status.session_id = self.file_manager.create_session_directory()
            
            # Start recording
            self.audio_capture.start_recording()
            self.status.is_recording = True
            self.status.chunks_processed = 0
            
            logger.info(f"Started recording for session: {self.status.session_id}")
            
        except Exception as e:
            logger.error(f"Error starting recording: {e}")
            self.console.print(f"❌ Error starting recording: {e}", style="bold red")
    
    def stop_recording(self) -> None:
        """Stop audio recording and save session."""
        try:
            if not self.audio_capture or not self.audio_capture.is_recording:
                logger.warning("No recording in progress")
                return
            
            # Stop recording
            self.audio_capture.stop_recording()
            self.status.is_recording = False
            
            # Save audio file and session info
            if self.status.session_id:
                audio_filename = f"recording_{self.status.session_id}.wav"
                session_path = self.file_manager.get_session_path(self.status.session_id)
                audio_filepath = session_path / audio_filename
                
                # Save audio to file
                self.audio_capture.save_to_file(str(audio_filepath))
                
                # Create and save session info
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
                
                self.console.print(f"✅ Session saved: {self.status.session_id}", style="bold green")
                logger.info(f"Session saved: {self.status.session_id}")
            
        except Exception as e:
            logger.error(f"Error stopping recording: {e}")
            self.console.print(f"❌ Error stopping recording: {e}", style="bold red")
    
    def reset_session(self) -> None:
        """Reset current session and clear display."""
        try:
            if self.audio_capture and self.audio_capture.is_recording:
                self.stop_recording()
            
            # Reset status
            self.status = TranscriptionStatus()
            self.audio_capture = None
            
            self.console.print("🔄 Session reset", style="bold blue")
            logger.info("Session reset")
            
        except Exception as e:
            logger.error(f"Error resetting session: {e}")
            self.console.print(f"❌ Error resetting session: {e}", style="bold red")
    
    def handle_key_input(self, key: str) -> bool:
        """Handle keyboard input. Returns True to continue, False to quit."""
        try:
            logger.info(f"Handling key input: '{key}' (ord: {ord(key)})")
            if key == 'q':
                logger.info("Quit key pressed")
                return False
            elif key == ' ' or key == '\n':  # Space or Enter
                logger.info(f"Space/Enter key pressed, currently recording: {self.status.is_recording}")
                if self.status.is_recording:
                    self.stop_recording()
                else:
                    self.start_recording()
            elif key == 's':
                logger.info("Stop key pressed")
                self.stop_recording()
            elif key == 'r':
                logger.info("Reset key pressed")
                self.reset_session()
            else:
                logger.info(f"Unhandled key: '{key}'")
        except Exception as e:
            logger.error(f"Error handling key input: {e}")
        
        return True
    
    def run(self) -> None:
        """Run the transcription screen interface."""
        try:
            self.running = True
            layout = self.create_layout()
            
            # Start keyboard input handler
            self.input_handler = create_input_handler(self.handle_key_input)
            self.input_handler.start()
            
            self.console.print("🎙️  Listen2Me Transcription Screen Started", style="bold green")
            self.console.print("Press SPACE to start recording, 'q' to quit, Ctrl+C to force quit", style="yellow")
            
            with Live(layout, refresh_per_second=10, screen=True) as live:
                while self.running:
                    try:
                        # Update display
                        self.update_display(layout)
                        
                        # Sleep briefly to avoid excessive CPU usage
                        time.sleep(0.1)
                        
                    except KeyboardInterrupt:
                        logger.info("Keyboard interrupt received")
                        break
                    except Exception as e:
                        logger.error(f"Error in main loop: {e}")
                        break
            
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt during startup")
        except Exception as e:
            logger.error(f"Error running transcription screen: {e}")
            self.console.print(f"❌ Error: {e}", style="bold red")
        finally:
            self.cleanup()
    
    def cleanup(self) -> None:
        """Clean up resources."""
        try:
            self.running = False
            
            # Stop input handler
            if self.input_handler:
                self.input_handler.stop()
            
            if self.audio_capture and self.audio_capture.is_recording:
                self.stop_recording()
            
            self.console.print("👋 Listen2Me session ended", style="bold blue")
            logger.info("TranscriptionScreen cleanup completed")
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")


def main():
    """Main entry point for transcription screen."""
    try:
        screen = TranscriptionScreen()
        screen.run()
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    main()