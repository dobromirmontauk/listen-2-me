"""Auto mode for automated testing and validation of Listen2Me transcription."""

import time
import logging
from typing import Optional
from datetime import datetime

from .ui.simple_transcription_screen import SimpleTranscriptionScreen
from .config import get_config, reload_config

logger = logging.getLogger(__name__)


def run_auto_mode(config_path: Optional[str] = None, duration_seconds: int = 10, batch_overrides: Optional[dict] = None) -> None:
    """Run Listen2Me in automated mode for testing.
    
    This mode:
    1. Initializes the transcription system
    2. Starts recording automatically
    3. Records for the specified duration
    4. Stops recording automatically
    5. Saves all transcription files
    6. Exits cleanly
    
    Args:
        config_path: Optional path to config file
        duration_seconds: How long to record (default: 10 seconds)
        batch_overrides: Optional dict of batch config overrides
    """
    logger.info(f"🤖 Starting auto mode: {duration_seconds}s recording")
    
    try:
        # Load configuration
        if config_path:
            config = reload_config(config_path)
        else:
            config = get_config()
        
        print(f"📋 Auto mode initialized")
        print(f"   Duration: {duration_seconds} seconds")
        print(f"   Config: {config.config_file}")
        print(f"   Data directory: {config.get_data_directory()}")
        
        # Apply batch overrides if provided
        if batch_overrides:
            for key, value in batch_overrides.items():
                config_key = f"transcription.batch.{key}"
                old_value = config.get(config_key)
                config.set(config_key, value)
                print(f"   Batch override: {key} = {value} (was {old_value})")
        
        print()
        
        # Initialize transcription screen (but don't run the interactive loop)
        print("🔧 Initializing transcription system...")
        screen = SimpleTranscriptionScreen(config_path)
        
        # Show system status
        print("📊 System Status:")
        microphone_ready = screen._check_microphone_available()
        transcription_ready = screen.transcription_engine is not None
        
        print(f"   {'✅' if microphone_ready else '❌'} Microphone: {'Ready' if microphone_ready else 'Not Available'}")
        print(f"   {'✅' if transcription_ready else '❌'} Transcription: {'Ready' if transcription_ready else 'Not Ready'}")
        
        if not microphone_ready:
            print("❌ Cannot proceed: Microphone not available")
            return
            
        if not transcription_ready:
            print("❌ Cannot proceed: Transcription engine not ready")
            return
        
        print()
        print("🎙️  Starting automated recording...")
        
        # Start recording
        start_time = time.time()
        screen.start_recording()
        
        if not screen.status.is_recording:
            print("❌ Failed to start recording")
            return
        
        session_id = screen.status.session_id
        print(f"📼 Recording session: {session_id}")
        print(f"   Started at: {datetime.now().strftime('%H:%M:%S')}")
        print(f"   Duration: {duration_seconds} seconds")
        print()
        
        # Record for specified duration with progress updates
        print("🔴 Recording in progress...")
        for i in range(duration_seconds):
            elapsed = i + 1
            remaining = duration_seconds - elapsed
            
            # Update transcription status
            screen.update_status_from_audio()
            
            # Show progress
            progress_bar = "█" * elapsed + "░" * remaining
            realtime_count = len(screen.realtime_transcriptions)
            batch_count = len(screen.batch_transcriptions)
            
            print(f"   [{progress_bar}] {elapsed:2d}/{duration_seconds}s - "
                  f"RT: {realtime_count}, Batch: {batch_count}", end="\r")
            
            time.sleep(1)
        
        print()  # New line after progress
        print()
        
        # Stop recording
        print("⏹️  Stopping recording...")
        screen.stop_recording()
        
        # Final status update
        screen.update_status_from_audio()
        total_time = time.time() - start_time
        
        print(f"✅ Recording completed")
        print(f"   Session ID: {session_id}")
        print(f"   Total time: {total_time:.1f} seconds")
        print(f"   Real-time transcriptions: {len(screen.realtime_transcriptions)}")
        print(f"   Batch transcriptions: {len(screen.batch_transcriptions)}")
        print()
        
        # Show sample transcriptions if available
        if screen.realtime_transcriptions:
            print("📝 Sample Real-time Transcriptions:")
            for i, result in enumerate(screen.realtime_transcriptions[:3]):  # Show first 3
                confidence_str = f"({result.confidence:.1%})" if result.confidence > 0 else ""
                print(f"   RT-{i+1}: {result.text} {confidence_str}")
            if len(screen.realtime_transcriptions) > 3:
                print(f"   ... and {len(screen.realtime_transcriptions) - 3} more real-time results")
            print()
        
        if screen.batch_transcriptions:
            print("📝 Sample Batch Transcriptions:")
            for i, result in enumerate(screen.batch_transcriptions[:3]):  # Show first 3
                confidence_str = f"({result.confidence:.1%})" if result.confidence > 0 else ""
                batch_id_str = f"[{result.batch_id}]" if result.batch_id else ""
                print(f"   BATCH-{i+1}: {result.text} {confidence_str} {batch_id_str}")
            if len(screen.batch_transcriptions) > 3:
                print(f"   ... and {len(screen.batch_transcriptions) - 3} more batch results")
            print()
        
        if not screen.realtime_transcriptions and not screen.batch_transcriptions:
            print("⚠️  No transcriptions were generated")
            print("   This might be due to:")
            print("   - No speech detected during recording")
            print("   - Microphone input level too low")
            print("   - Transcription service issues")
            print()
        
        # Show file outputs
        if screen.status.session_id:
            session_path = screen.file_manager.get_session_path(screen.status.session_id)
            print("📁 Output Files Generated:")
            print(f"   Session directory: {session_path}")
            
            # List expected files
            expected_files = [
                f"recording_{session_id}.wav",
                f"session_info.json"
            ]
            
            if screen.realtime_transcriptions:
                expected_files.extend([
                    f"realtime_transcription_{session_id}.json",
                    f"realtime_transcription_{session_id}.txt"
                ])
            
            if screen.batch_transcriptions:
                expected_files.extend([
                    f"batch_transcription_{session_id}.json",
                    f"batch_transcription_{session_id}.txt"
                ])
            
            if screen.status.transcription_results:
                expected_files.append(f"combined_transcription_{session_id}.json")
            
            for filename in expected_files:
                filepath = session_path / filename
                if filepath.exists():
                    size = filepath.stat().st_size
                    print(f"   ✅ {filename} ({size:,} bytes)")
                else:
                    print(f"   ❌ {filename} (missing)")
            print()
        
        # Clean up
        print("🧹 Cleaning up...")
        screen.cleanup()
        
        print("✅ Auto mode completed successfully!")
        logger.info(f"Auto mode completed: {session_id}, {total_time:.1f}s, "
                   f"{len(screen.realtime_transcriptions)} RT, {len(screen.batch_transcriptions)} batch")
        
    except KeyboardInterrupt:
        print("\n🛑 Auto mode interrupted by user")
        logger.info("Auto mode interrupted by KeyboardInterrupt")
        
        # Try to clean up if screen exists
        if 'screen' in locals():
            try:
                screen.cleanup()
            except Exception as cleanup_error:
                logger.error(f"Error during cleanup: {cleanup_error}")
                
    except Exception as e:
        print(f"\n❌ Auto mode failed: {e}")
        logger.error(f"Auto mode failed: {e}", exc_info=True)
        
        # Try to clean up if screen exists
        if 'screen' in locals():
            try:
                screen.cleanup()
            except Exception as cleanup_error:
                logger.error(f"Error during cleanup: {cleanup_error}")
        
        raise  # Re-raise for debugging