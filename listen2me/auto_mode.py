"""Auto mode for automated testing and validation of Listen2Me transcription."""

import time
import logging
from typing import Optional, Dict, Any
from datetime import datetime

from .services.notes_service import NotesService
from .models.notes import NotesQuery
from .config import get_config, reload_config

logger = logging.getLogger(__name__)


def run_auto_mode(config_path: Optional[str] = None, duration_seconds: int = 10, batch_overrides: Optional[dict] = None) -> None:
    """Run Listen2Me in automated mode for testing.
    
    This mode:
    1. Initializes services with config
    2. Starts recording automatically  
    3. Records for the specified duration
    4. Stops recording and saves files
    5. Reports results and exits
    
    Args:
        config_path: Optional path to config file
        duration_seconds: How long to record (default: 10 seconds)
        batch_overrides: Optional dict of batch config overrides
    """
    logger.info(f"🤖 Starting auto mode: {duration_seconds}s recording")
    
    recording_service = None
    session_manager = None
    session_id = None
    
    try:
        # Load and configure
        config = _load_and_configure(config_path, batch_overrides, duration_seconds)
        
        # Initialize services
        notes_service = _initialize_services(config)
        
        # Verify system readiness
        if not _check_system_readiness(notes_service):
            return
        
        # Run automated recording workflow
        session_id, results, total_time = _run_recording_workflow(notes_service, duration_seconds)
        
        # Report results
        _report_results(notes_service, session_id, results, total_time)
        
        print("✅ Auto mode completed successfully!")
        logger.info(f"Auto mode completed: {session_id}, {total_time:.1f}s, "
                   f"{len(results['realtime'])} RT, {len(results['batch'])} batch")
        
    except KeyboardInterrupt:
        print("\n🛑 Auto mode interrupted by user")
        logger.info("Auto mode interrupted by KeyboardInterrupt")
        
    except Exception as e:
        print(f"\n❌ Auto mode failed: {e}")
        logger.error(f"Auto mode failed: {e}", exc_info=True)
        raise
        
    finally:
        # Clean up services
        if 'notes_service' in locals():
            print("🧹 Cleaning up...")
            notes_service.cleanup()


def _load_and_configure(config_path: Optional[str], batch_overrides: Optional[dict], duration_seconds: int):
    """Load configuration and apply overrides."""
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
    return config


def _initialize_services(config):
    """Initialize notes service."""
    print("🔧 Initializing services...")
    notes_service = NotesService(config)
    print("✅ Services initialized")
    return notes_service


def _check_system_readiness(notes_service: NotesService) -> bool:
    """Check if system is ready for recording."""
    print("📊 System Status:")
    microphone_ready = notes_service.recording_service.check_microphone_available()
    transcription_ready = notes_service.recording_service.transcription_engine is not None
    
    print(f"   {'✅' if microphone_ready else '❌'} Microphone: {'Ready' if microphone_ready else 'Not Available'}")
    print(f"   {'✅' if transcription_ready else '❌'} Transcription: {'Ready' if transcription_ready else 'Not Ready'}")
    
    if not microphone_ready:
        print("❌ Cannot proceed: Microphone not available")
        return False
        
    if not transcription_ready:
        print("❌ Cannot proceed: Transcription engine not ready")
        return False
    
    return True


def _run_recording_workflow(notes_service: NotesService, duration_seconds: int) -> tuple[str, Dict[str, Any], float]:
    """Run the core recording workflow using the notes service API."""
    print()
    print("🎙️  Starting automated recording...")
    
    # Start recording session via notes service
    start_time = time.time()
    start_result = notes_service.start_recording_session()
    
    if not start_result["success"]:
        raise RuntimeError(f"Failed to start recording: {start_result['error']}")
    
    session_id = start_result["session_id"]
    print(f"📼 Recording session: {session_id}")
    print(f"   Started at: {datetime.now().strftime('%H:%M:%S')}")
    print(f"   Duration: {duration_seconds} seconds")
    print()
    
    # Record with progress updates
    print("🔴 Recording in progress...")
    high_watermark = None
    
    for i in range(duration_seconds):
        elapsed = i + 1
        remaining = duration_seconds - elapsed
        
        # Poll for new processed chunks
        query = NotesQuery(
            session_id=session_id,
            high_watermark=high_watermark,
            include_audio=False,
            limit=100
        )
        
        response = notes_service.get_processed_chunks(query)
        high_watermark = response.new_high_watermark
        
        # Count transcriptions by mode
        realtime_count = sum(1 for chunk in response.chunks 
                           for raw in chunk.raw_transcriptions 
                           if raw.transcription_mode == "realtime")
        batch_count = sum(1 for chunk in response.chunks 
                        for raw in chunk.raw_transcriptions 
                        if raw.transcription_mode == "batch")
        
        # Show progress
        progress_bar = "█" * elapsed + "░" * remaining
        print(f"   [{progress_bar}] {elapsed:2d}/{duration_seconds}s - "
              f"RT: {realtime_count}, Batch: {batch_count}", end="\r")
        
        time.sleep(1)
    
    print()  # New line after progress
    print()
    
    # Stop recording
    print("⏹️  Stopping recording...")
    stop_result = notes_service.stop_recording_session(session_id)
    
    if not stop_result["success"]:
        raise RuntimeError(f"Failed to stop recording: {stop_result['error']}")
    
    # Get final results
    final_query = NotesQuery(
        session_id=session_id,
        high_watermark=None,  # Get all chunks
        include_audio=False
    )
    final_response = notes_service.get_processed_chunks(final_query)
    
    # Convert to compatible format for reporting
    final_results = {
        "realtime": [raw for chunk in final_response.chunks 
                    for raw in chunk.raw_transcriptions 
                    if raw.transcription_mode == "realtime"],
        "batch": [raw for chunk in final_response.chunks 
                 for raw in chunk.raw_transcriptions 
                 if raw.transcription_mode == "batch"],
        "all_realtime_attempts": [raw for chunk in final_response.chunks 
                                for raw in chunk.raw_transcriptions 
                                if raw.transcription_mode == "realtime"],
        "all_batch_attempts": [raw for chunk in final_response.chunks 
                             for raw in chunk.raw_transcriptions 
                             if raw.transcription_mode == "batch"],
        "combined": [raw for chunk in final_response.chunks 
                    for raw in chunk.raw_transcriptions]
    }
    
    total_time = time.time() - start_time
    return session_id, final_results, total_time


def _report_results(notes_service: NotesService, session_id: str, results: Dict[str, Any], total_time: float):
    """Report the results of the auto mode recording."""
    print(f"✅ Recording completed")
    print(f"   Session ID: {session_id}")
    print(f"   Total time: {total_time:.1f} seconds")
    print(f"   Real-time transcriptions: {len(results['realtime'])}")
    print(f"   Batch transcriptions: {len(results['batch'])}")
    print()
    
    # Show sample transcriptions if available
    if results["realtime"]:
        print("📝 Sample Real-time Transcriptions:")
        for i, result in enumerate(results["realtime"][:3]):  # Show first 3
            confidence_str = f"({result.confidence:.1%})" if result.confidence > 0 else ""
            print(f"   RT-{i+1}: {result.text} {confidence_str}")
        if len(results["realtime"]) > 3:
            print(f"   ... and {len(results['realtime']) - 3} more real-time results")
        print()
    
    if results["batch"]:
        print("📝 Sample Batch Transcriptions:")
        for i, result in enumerate(results["batch"][:3]):  # Show first 3
            confidence_str = f"({result.confidence:.1%})" if result.confidence > 0 else ""
            batch_id_str = f"[{result.batch_id}]" if result.batch_id else ""
            print(f"   BATCH-{i+1}: {result.text} {confidence_str} {batch_id_str}")
        if len(results["batch"]) > 3:
            print(f"   ... and {len(results['batch']) - 3} more batch results")
        print()
    
    if not results["realtime"] and not results["batch"]:
        print("⚠️  No transcriptions were generated")
        print("   This might be due to:")
        print("   - No speech detected during recording")
        print("   - Microphone input level too low")
        print("   - Transcription service issues")
        print()
    
    # Show file outputs
    session_path = notes_service.session_manager.get_session_path(session_id)
    print("📁 Output Files Generated:")
    print(f"   Session directory: {session_path}")
    
    # List expected files
    expected_files = [
        f"recording_{session_id}.wav",
        f"session_info.json"
    ]
    
    if results["realtime"] or results["all_realtime_attempts"]:
        expected_files.extend([
            f"realtime_transcription_{session_id}.json",
            f"realtime_transcription_{session_id}.txt"
        ])
    
    if results["batch"] or results["all_batch_attempts"]:
        expected_files.extend([
            f"batch_transcription_{session_id}.json",
            f"batch_transcription_{session_id}.txt"
        ])
    
    if results.get("combined"):
        expected_files.append(f"combined_transcription_{session_id}.json")
    
    for filename in expected_files:
        filepath = session_path / filename
        if filepath.exists():
            size = filepath.stat().st_size
            print(f"   ✅ {filename} ({size:,} bytes)")
        else:
            print(f"   ❌ {filename} (missing)")
    print()