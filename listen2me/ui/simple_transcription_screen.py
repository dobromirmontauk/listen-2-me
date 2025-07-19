"""Simple transcription screen without fancy keyboard handling."""

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
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich.align import Align

from ..audio.capture import AudioCapture
from ..storage.file_manager import FileManager
from ..models.session import SessionInfo
from ..transcription import TranscriptionEngine, GoogleSpeechBackend, TranscriptionResult
from ..transcription.dual_engine import DualTranscriptionEngine
from ..config import get_config


logger = logging.getLogger(__name__)




class SimpleTranscriptionScreen:
    """Simple transcription interface using basic input/output."""
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize simple transcription screen."""
        self.console = Console()
        
        # Load configuration from YAML file
        if config_path:
            from ..config import reload_config
            self.config = reload_config(config_path)
        else:
            self.config = get_config()
        
        # Get data directory from config
        data_dir = self.config.get_data_directory()
        
        self.file_manager = FileManager(data_dir)
        self.audio_capture: Optional[AudioCapture] = None
        self.transcription_engine: Optional[DualTranscriptionEngine] = None
        self.status = TranscriptionStatus()
        self.running = False
        
        # Dual transcription results storage
        self.realtime_transcriptions = []
        self.batch_transcriptions = []
        
        # Debug: ALL transcription attempts (including no speech)
        self.all_realtime_attempts = []
        self.all_batch_attempts = []
        
        logger.info(f"SimpleTranscriptionScreen initialized with config: {self.config.config_file}")
        
        # Initialize transcription engine immediately on startup
        logger.info("Setting up transcription engine on startup...")
        self.console.print("🔧 Initializing transcription services...", style="blue")
        self._setup_transcription()
        self.console.print("✅ Transcription engine ready!", style="green")
        logger.info("Transcription engine ready!")
    
    def _check_microphone_available(self) -> bool:
        """Check if microphone is available for recording."""
        try:
            # Try to create a temporary AudioCapture instance to test microphone
            from ..audio.capture import AudioCapture
            temp_capture = AudioCapture(
                sample_rate=16000,
                chunk_size=1024,
                buffer_size=10,
                channels=1
            )
            # AudioCapture creation will fail if no microphone is available
            return True
        except Exception as e:
            logger.debug(f"Microphone not available: {e}")
            return False
    
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
        
        # System readiness indicators
        self.console.print()
        microphone_status = "✅ Microphone Ready" if self._check_microphone_available() else "❌ Microphone Not Available"
        
        if self.transcription_engine:
            # Get display info from backends
            display_info = ""
            for backend in self.transcription_engine.backends:
                info = backend.get_display_info()
                if info:
                    display_info = info
                    break
            transcription_status = f"✅ Transcription Ready{display_info}"
        else:
            transcription_status = "❌ Transcription Not Ready"
        
        self.console.print(f"{microphone_status}", style="green" if "✅" in microphone_status else "red")
        self.console.print(f"{transcription_status}", style="green" if "✅" in transcription_status else "red")
        
        # Audio stats
        if self.audio_capture:
            stats = self.audio_capture.get_recording_stats()
            self.console.print(f"Duration: {stats.duration_seconds:.1f}s")
            self.console.print(f"Chunks: {stats.total_chunks}")
            self.console.print(f"Peak Level: {stats.peak_level:.3f}")
            
            # Visual peak level
            peak_bar = "█" * int(stats.peak_level * 20)
            self.console.print(f"Audio: [{peak_bar:<20}] {stats.peak_level:.3f}")
        
        # Transcription results
        if self.status.transcription_results:
            self.console.print(f"\n📝 Transcription:")
            # Show last 3 transcription results
            recent_results = self.status.transcription_results[-3:]
            for i, result in enumerate(recent_results):
                if result.text and result.text.strip():
                    confidence_str = f"({result.confidence:.1%})" if result.confidence > 0 else ""
                    service_str = f"[{result.service}]"
                    self.console.print(f"   {result.text} {confidence_str} {service_str}")
                    
            if len(self.status.transcription_results) > 3:
                self.console.print(f"   ... and {len(self.status.transcription_results) - 3} more results")
        elif self.status.is_recording:
            self.console.print(f"\n📝 Listening for speech... ({self.status.chunks_processed} chunks processed)")
        else:
            if self.transcription_engine:
                self.console.print(f"\n📝 Transcription engine ready - start recording to begin")
        
        # Controls
        self.console.print("\n" + "=" * 50)
        self.console.print("Commands:")
        self.console.print("  [bold green]1[/bold green] - Start recording")
        self.console.print("  [bold yellow]2[/bold yellow] - Stop recording") 
        self.console.print("  [bold blue]3[/bold blue] - Reset session")
        self.console.print("  [bold red]q[/bold red] - Quit")
        self.console.print("=" * 50)
    
    def update_status_from_audio(self) -> None:
        """Update status from audio capture and process transcription."""
        if self.audio_capture:
            stats = self.audio_capture.get_recording_stats()
            self.status.is_recording = stats.is_recording
            self.status.duration_seconds = stats.duration_seconds
            self.status.total_chunks = stats.total_chunks
            self.status.peak_level = stats.peak_level
            
            # Process audio chunks for dual-mode transcription
            if self.status.is_recording and self.transcription_engine:
                # Send raw audio chunks directly to dual engine
                raw_chunks_received = 0
                while self.audio_capture.has_audio_data():
                    audio_chunk = self.audio_capture.get_audio_chunk()
                    if audio_chunk and len(audio_chunk) > 0:
                        # Send to dual transcription engine with timestamp
                        self.transcription_engine.submit_audio_chunk(audio_chunk, time.time())
                        raw_chunks_received += 1
                        self.status.chunks_processed += 1
                
                if raw_chunks_received > 0:
                    logger.debug(f"🎤 UI: Sent {raw_chunks_received} raw audio chunks to dual engine")
                
                # Collect completed transcription results from both modes
                results_dict = self.transcription_engine.get_completed_results()
                realtime_results = results_dict.get('realtime', [])
                batch_results = results_dict.get('batch', [])
                
                # Process real-time results
                if realtime_results:
                    logger.debug(f"🎯 UI: Received {len(realtime_results)} new real-time results")
                    
                    # Store ALL attempts for debugging
                    self.all_realtime_attempts.extend(realtime_results)
                    
                    # Filter for meaningful results (non-empty speech)
                    meaningful_realtime = [r for r in realtime_results if r.text and r.text.strip() and r.text != "[NO_SPEECH_DETECTED]"]
                    self.realtime_transcriptions.extend(meaningful_realtime)
                    self.status.transcription_results.extend(meaningful_realtime)
                    
                    # Log all attempts (including no speech)
                    for result in realtime_results:
                        if result.text == "[NO_SPEECH_DETECTED]":
                            logger.debug(f"🔇 REALTIME: No speech detected (confidence: {result.confidence:.2f}, time: {result.processing_time:.3f}s)")
                        elif result.text and result.text.strip():
                            logger.debug(f"🎯 REALTIME: '{result.text}' (confidence: {result.confidence:.2f})")
                            logger.info(f"📝 REALTIME: '{result.text}'")
                    
                    # Update display with latest meaningful result
                    if meaningful_realtime:
                        latest_result = meaningful_realtime[-1]
                        self.status.current_text = latest_result.text
                
                # Process batch results
                if batch_results:
                    logger.debug(f"🎯 UI: Received {len(batch_results)} new batch results")
                    
                    # Store ALL attempts for debugging
                    self.all_batch_attempts.extend(batch_results)
                    
                    # Filter for meaningful results (non-empty speech)
                    meaningful_batch = [r for r in batch_results if r.text and r.text.strip() and r.text != "[NO_SPEECH_DETECTED]"]
                    self.batch_transcriptions.extend(meaningful_batch)
                    
                    # Log all attempts (including no speech)
                    for result in batch_results:
                        if result.text == "[NO_SPEECH_DETECTED]":
                            logger.debug(f"🔇 BATCH: No speech detected (confidence: {result.confidence:.2f}, time: {result.processing_time:.3f}s)")
                        elif result.text and result.text.strip():
                            logger.debug(f"🎯 BATCH: '{result.text}' (confidence: {result.confidence:.2f})")
                            logger.info(f"📝 BATCH: '{result.text}'")
                
                # Update transcribing status
                self.status.is_transcribing = self.status.chunks_processed > len(self.status.transcription_results)
    
    def _setup_transcription(self) -> bool:
        """Set up dual-mode transcription engine with available backends."""
        logger.info("Starting dual-mode transcription setup...")
        backends = []
        
        # Get configuration values
        credentials_path = self.config.get_google_credentials_path()
        language = self.config.get('google_cloud.language', 'en-US')
        use_enhanced = self.config.get('google_cloud.use_enhanced_model', True)
        enable_punctuation = self.config.get('google_cloud.enable_automatic_punctuation', True)
        
        logger.info(f"Google credentials path: {credentials_path}")
        logger.debug(f"Config: language={language}, use_enhanced={use_enhanced}, punctuation={enable_punctuation}")
        
        # Initialize Google Speech backend - will CRASH if setup fails (by design)
        logger.info("Initializing Google Speech backend...")
        google_backend = GoogleSpeechBackend(
            credentials_path=credentials_path,
            language=language,
            use_enhanced=use_enhanced,
            enable_automatic_punctuation=enable_punctuation
        )
        
        logger.info("Testing Google Speech backend initialization...")
        if google_backend.initialize():
            backends.append(google_backend)
            logger.info("✅ Google Speech backend initialized successfully")
        else:
            raise RuntimeError("Google Speech backend failed to initialize")
        
        # Get transcription configuration
        realtime_config = self.config.get('transcription.realtime', {})
        batch_config = self.config.get('transcription.batch', {})
        
        logger.info(f"Dual transcription config:")
        logger.info(f"  Real-time: {realtime_config}")
        logger.info(f"  Batch: {batch_config}")
        
        # Initialize dual transcription engine
        logger.info(f"Initializing dual transcription engine with {len(backends)} backends...")
        self.transcription_engine = DualTranscriptionEngine(
            backends=backends,
            realtime_config=realtime_config,
            batch_config=batch_config
        )
        
        if self.transcription_engine.initialize():
            logger.info("✅ Dual transcription engine initialized successfully")
            return True
        else:
            raise RuntimeError("Failed to initialize dual transcription engine")
    
    def start_recording(self) -> None:
        """Start recording."""
        try:
            if self.audio_capture and self.audio_capture.is_recording:
                self.console.print("⚠️  Already recording", style="yellow")
                return
            
            # Transcription engine should already be ready from startup
            if not self.transcription_engine:
                raise RuntimeError("Transcription engine not initialized - this should not happen")
            
            # Initialize audio capture with config values
            self.audio_capture = AudioCapture(
                sample_rate=self.config.get('audio.sample_rate', 16000),
                chunk_size=self.config.get('audio.chunk_size', 1024),
                buffer_size=self.config.get('audio.buffer_size', 100),
                channels=self.config.get('audio.channels', 1)
            )
            
            # Create session
            self.status.session_id = self.file_manager.create_session_directory()
            
            # Clear previous transcription results
            self.status.transcription_results = []
            self.status.chunks_processed = 0
            self.realtime_transcriptions = []
            self.batch_transcriptions = []
            
            # Start recording
            self.audio_capture.start_recording()
            self.status.is_recording = True
            
            self.console.print("✅ Recording and transcription started!", style="bold green")
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
            
            # Collect any final transcription results from dual engine
            logger.info("Collecting final transcription results from both engines...")
            if self.transcription_engine:
                results_dict = self.transcription_engine.get_completed_results()
                realtime_results = results_dict.get('realtime', [])
                batch_results = results_dict.get('batch', [])
                
                if realtime_results:
                    meaningful_realtime = [r for r in realtime_results if r.text and r.text.strip()]
                    self.realtime_transcriptions.extend(meaningful_realtime)
                    self.status.transcription_results.extend(meaningful_realtime)
                    logger.info(f"Collected {len(meaningful_realtime)} final real-time results")
                
                if batch_results:
                    meaningful_batch = [r for r in batch_results if r.text and r.text.strip()]
                    self.batch_transcriptions.extend(meaningful_batch)
                    logger.info(f"Collected {len(meaningful_batch)} final batch results")
            
            # Wait for pending transcriptions of recorded audio to complete
            logger.info("Waiting for pending transcriptions...")
            self.console.print("📝 Processing final transcriptions...", style="blue")
            time.sleep(3)  # Give transcription engine time to process recorded audio
            
            # Collect any final transcription results
            if self.transcription_engine:
                final_results_dict = self.transcription_engine.get_completed_results()
                final_realtime = final_results_dict.get('realtime', [])
                final_batch = final_results_dict.get('batch', [])
                
                if final_realtime:
                    meaningful_realtime = [r for r in final_realtime if r.text and r.text.strip()]
                    self.realtime_transcriptions.extend(meaningful_realtime)
                    self.status.transcription_results.extend(meaningful_realtime)
                    logger.info(f"Collected {len(meaningful_realtime)} final real-time results")
                
                if final_batch:
                    meaningful_batch = [r for r in final_batch if r.text and r.text.strip()]
                    self.batch_transcriptions.extend(meaningful_batch)
                    logger.info(f"Collected {len(meaningful_batch)} final batch results")
            
            # Save session
            if self.status.session_id:
                audio_filename = f"recording_{self.status.session_id}.wav"
                session_path = self.file_manager.get_session_path(self.status.session_id)
                audio_filepath = session_path / audio_filename
                
                self.audio_capture.save_to_file(str(audio_filepath))
                
                # Save transcription results in multiple formats (both real-time and batch)
                try:
                    import json
                    
                    # Save real-time transcription results (including debug data)
                    if self.realtime_transcriptions or self.all_realtime_attempts:
                        realtime_json_filename = f"realtime_transcription_{self.status.session_id}.json"
                        realtime_json_filepath = session_path / realtime_json_filename
                        realtime_txt_filename = f"realtime_transcription_{self.status.session_id}.txt"
                        realtime_txt_filepath = session_path / realtime_txt_filename
                        
                        # JSON format for real-time (use all attempts for debugging)
                        realtime_data = {
                            "session_id": self.status.session_id,
                            "transcription_mode": "realtime",
                            "generated_at": datetime.now().isoformat(),
                            "total_results": len(self.all_realtime_attempts),
                            "meaningful_results": len(self.realtime_transcriptions),
                            "audio_file": audio_filename,
                            "transcription_segments": []
                        }
                        
                        for i, result in enumerate(self.all_realtime_attempts):
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
                            realtime_data["transcription_segments"].append(segment)
                        
                        with open(realtime_json_filepath, 'w', encoding='utf-8') as f:
                            json.dump(realtime_data, f, indent=2, ensure_ascii=False)
                        
                        # Text format for real-time (use all attempts for debugging)
                        with open(realtime_txt_filepath, 'w', encoding='utf-8') as f:
                            f.write(f"REAL-TIME Transcription for session: {self.status.session_id}\n")
                            f.write(f"Generated at: {datetime.now().isoformat()}\n")
                            f.write(f"Total attempts: {len(self.all_realtime_attempts)} (meaningful: {len(self.realtime_transcriptions)})\n")
                            f.write("=" * 60 + "\n\n")
                            
                            for i, result in enumerate(self.all_realtime_attempts):
                                audio_time = f"Audio: {result.audio_start_time:.1f}-{result.audio_end_time:.1f}s" if result.audio_start_time else ""
                                f.write(f"[RT-{i+1:03d}] {result.timestamp.strftime('%H:%M:%S')} {audio_time}\n")
                                f.write(f"         Confidence: {result.confidence:.1%} via {result.service}\n")
                                f.write(f"         {result.text}\n\n")
                        
                        logger.info(f"Saved {len(self.all_realtime_attempts)} real-time transcription attempts ({len(self.realtime_transcriptions)} meaningful)")
                        logger.info(f"Saved real-time JSON: {realtime_json_filepath}")
                        logger.info(f"Saved real-time text: {realtime_txt_filepath}")
                    
                    # Save batch transcription results (including debug data)
                    if self.batch_transcriptions or self.all_batch_attempts:
                        batch_json_filename = f"batch_transcription_{self.status.session_id}.json"
                        batch_json_filepath = session_path / batch_json_filename
                        batch_txt_filename = f"batch_transcription_{self.status.session_id}.txt"
                        batch_txt_filepath = session_path / batch_txt_filename
                        
                        # JSON format for batch (use all attempts for debugging)
                        batch_data = {
                            "session_id": self.status.session_id,
                            "transcription_mode": "batch",
                            "generated_at": datetime.now().isoformat(),
                            "total_results": len(self.all_batch_attempts),
                            "meaningful_results": len(self.batch_transcriptions),
                            "audio_file": audio_filename,
                            "transcription_segments": []
                        }
                        
                        for i, result in enumerate(self.all_batch_attempts):
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
                                "batch_id": result.batch_id,
                                "chunk_id": result.chunk_id,
                                "alternatives": result.alternatives
                            }
                            batch_data["transcription_segments"].append(segment)
                        
                        with open(batch_json_filepath, 'w', encoding='utf-8') as f:
                            json.dump(batch_data, f, indent=2, ensure_ascii=False)
                        
                        # Text format for batch (use all attempts for debugging)
                        with open(batch_txt_filepath, 'w', encoding='utf-8') as f:
                            f.write(f"BATCH Transcription for session: {self.status.session_id}\n")
                            f.write(f"Generated at: {datetime.now().isoformat()}\n")
                            f.write(f"Total attempts: {len(self.all_batch_attempts)} (meaningful: {len(self.batch_transcriptions)})\n")
                            f.write("=" * 60 + "\n\n")
                            
                            for i, result in enumerate(self.all_batch_attempts):
                                audio_time = f"Audio: {result.audio_start_time:.1f}-{result.audio_end_time:.1f}s" if result.audio_start_time else ""
                                f.write(f"[BATCH-{i+1:03d}] {result.timestamp.strftime('%H:%M:%S')} {audio_time}\n")
                                f.write(f"           Batch ID: {result.batch_id}\n")
                                f.write(f"           Confidence: {result.confidence:.1%} via {result.service}\n")
                                f.write(f"           {result.text}\n\n")
                        
                        logger.info(f"Saved {len(self.all_batch_attempts)} batch transcription attempts ({len(self.batch_transcriptions)} meaningful)")
                        logger.info(f"Saved batch JSON: {batch_json_filepath}")
                        logger.info(f"Saved batch text: {batch_txt_filepath}")
                    
                    # Also save combined transcription for compatibility
                    if self.status.transcription_results:
                        combined_json_filename = f"combined_transcription_{self.status.session_id}.json"
                        combined_json_filepath = session_path / combined_json_filename
                        
                        combined_data = {
                            "session_id": self.status.session_id,
                            "transcription_mode": "combined",
                            "generated_at": datetime.now().isoformat(),
                            "total_results": len(self.status.transcription_results),
                            "audio_file": audio_filename,
                            "realtime_count": len(self.realtime_transcriptions),
                            "batch_count": len(self.batch_transcriptions),
                            "transcription_segments": []
                        }
                        
                        for i, result in enumerate(self.status.transcription_results):
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
                        
                        with open(combined_json_filepath, 'w', encoding='utf-8') as f:
                            json.dump(combined_data, f, indent=2, ensure_ascii=False)
                        
                        logger.info(f"Saved combined transcription JSON: {combined_json_filepath}")
                    
                except Exception as e:
                    logger.error(f"Failed to save transcription results: {e}")
                
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
        self.console.print("✅ Transcription services authenticated and ready", style="green")
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
            
            # Clean up transcription engine
            if self.transcription_engine:
                try:
                    self.transcription_engine.cleanup()
                    logger.debug("Transcription engine cleaned up")
                except Exception as e:
                    logger.error(f"Error cleaning up transcription engine: {e}")
                finally:
                    self.transcription_engine = None
            
            self.console.print("\n👋 Listen2Me session ended", style="bold blue")
            logger.info("SimpleTranscriptionScreen cleanup completed")
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")


# Entry point is now in listen2me.main - this file only contains the UI class