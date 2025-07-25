"""Main application entry point for Listen2Me."""

import sys
import time
import argparse
import logging
from pathlib import Path

from listen2me.audio.audio_pub import AudioPublisher
from listen2me.audio.capture import AudioCapture
from listen2me.services.transcription_service import TranscriptionService
from listen2me.transcription.aggregator import TranscriptionAggregator

from .config import Listen2MeConfig 

logger = logging.getLogger(__name__)

class Server:

    def __init__(self, config_path: str):
       # Load configuration
        self.config = Listen2MeConfig(config_path)
        # Set up logging (override config with command line if specified)
        log_level = self.config.get('logging.level', 'INFO')
        setup_logging(self.config, log_level)
        self.should_exit = False


    def init(self):
        # Initialize services
        logger.info("Initializing services...")
        
        # Get audio settings from config
        sample_rate = self.config.get('audio.sample_rate', 16000)
        chunk_size = self.config.get('audio.chunk_size', 1024)
        channels = self.config.get('audio.channels', 1)
        
        # Calculate chunks per second for transcription timing
        chunks_per_second = sample_rate / chunk_size
        
        logger.info(f"Audio settings: {sample_rate}Hz, {chunk_size} samples/chunk, {channels} channels")
        logger.info(f"Chunks per second: {chunks_per_second:.1f}")
        
        self.audio_publisher = AudioPublisher("audio.frame")
        self.audio_capture = AudioCapture(
            callback=self.audio_publisher.publish_audio_event,
            sample_rate=sample_rate,
            chunk_size=chunk_size,
            channels=channels
        )
        self.transcription_service = TranscriptionService(self.config, "audio.frame")
        self.transcription_service.start_transcription_consumers(chunks_per_second)
        
        # Create transcription aggregators
        self.realtime_aggregator = TranscriptionAggregator("transcription.realtime", "realtime")
        self.batch_aggregator = TranscriptionAggregator("transcription.batch", "batch")

    def run(self, duration: int):
        try:
            self.audio_capture.start_recording()
            if duration:
                time.sleep(duration)
            else:
                while not self.should_exit:
                    time.sleep(1)
        except Exception as e:
            logger.error(f"Error in run: {e}")
        finally:
            self.cleanup()

    def cleanup(self):
        self.audio_capture.stop_recording()
        self.transcription_service.shutdown_transcription()
        
        # Shutdown aggregators and print results
        self.realtime_aggregator.shutdown()
        self.batch_aggregator.shutdown()



def setup_logging(config, level: str = "INFO") -> None:

    """Set up logging configuration from YAML config."""
    # Get log file path from config
    log_file_path = config.get('logging.file_path', 'data/logs/listen2me.log')
    console_output = config.get('logging.console_output', True)
    
    # Create logs directory if it doesn't exist
    import os
    log_dir = Path(log_file_path).parent
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Set up handlers
    handlers = []
    
    # File handler - always write to file
    file_handler = logging.FileHandler(log_file_path)
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
    )
    file_handler.setFormatter(file_formatter)
    handlers.append(file_handler)
    
    # Console handler - only if enabled in config
    if console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.WARNING)  # Only show warnings and above on console
        console_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        console_handler.setFormatter(console_formatter)
        handlers.append(console_handler)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(getattr(logging, level.upper()))
    for handler in handlers:
        root_logger.addHandler(handler)
    
    # Log startup
    logger = logging.getLogger(__name__)
    logger.info("="*50)
    logger.info("Listen2Me application starting up")
    logger.info(f"Log file: {log_file_path}")
    logger.info(f"Log level set to: {level}")
    logger.info("="*50)


def main() -> None:
    """Main entry point for Listen2Me application."""
    parser = argparse.ArgumentParser(
        description="Listen2Me - Real-time voice transcription",
        epilog="Commands: 1=Start recording, 2=Stop recording, 3=Reset session, q=Quit"
    )
    
    parser.add_argument(
        "--config",
        type=str,
        help="Path to configuration YAML file (default: looks for listen2me.yaml)"
    )
    
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Set logging level (default: INFO)"
    )
    
    parser.add_argument(
        "--auto",
        action="store_true",
        help="Run in automatic mode: start recording, record for specified duration, then stop and exit"
    )
    
    parser.add_argument(
        "--duration",
        type=int,
        default=10,
        help="Duration in seconds for auto mode recording (default: 10)"
    )
    
    parser.add_argument(
        "--batch-window",
        type=int,
        help="Batch transcription window duration in seconds (overrides config)"
    )
    
    parser.add_argument(
        "--batch-interval",
        type=int,
        help="Batch transcription interval in seconds (overrides config)"
    )
    
    parser.add_argument(
        "--version",
        action="version",
        version="Listen2Me v0.1.0 - Phase 1"
    )
    
    args = parser.parse_args()

    server = Server(args.config)
    try:
        server.init()
        if args.auto:
            server.run(args.duration)
        else:
            raise NotImplementedError("Interactive mode not implemented yet")
    except KeyboardInterrupt:
        server.cleanup()
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"❌ Error: {e}")
        logging.error(f"Application error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()