"""Main application entry point for Listen2Me."""

import sys
import argparse
import logging
from pathlib import Path

from .ui.transcription_screen import TranscriptionScreen
from .ui.simple_transcription_screen import SimpleTranscriptionScreen


def setup_logging(level: str = "INFO") -> None:
    """Set up logging configuration."""
    # Create logs directory if it doesn't exist
    import os
    os.makedirs('logs', exist_ok=True)
    
    # Configure logging with both file and console handlers
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            # File handler - always write to file
            logging.FileHandler('logs/listen2me.log'),
            # Console handler - only show warnings and above to keep console clean
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Set console handler to only show warnings and above
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.WARNING)
    
    # Create a more detailed file handler
    file_handler = logging.FileHandler('logs/listen2me.log')
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
    )
    file_handler.setFormatter(file_formatter)
    
    # Clear existing handlers and add our custom ones
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    # Log startup
    logger = logging.getLogger(__name__)
    logger.info("="*50)
    logger.info("Listen2Me application starting up")
    logger.info(f"Log level set to: {level}")
    logger.info("="*50)


def main() -> None:
    """Main entry point for Listen2Me application."""
    parser = argparse.ArgumentParser(
        description="Listen2Me - Real-time voice transcription",
        epilog="Press SPACE to start/stop recording, 'q' to quit"
    )
    
    parser.add_argument(
        "--data-dir",
        type=str,
        default="./data",
        help="Directory to store audio files and session data (default: ./data)"
    )
    
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Set logging level (default: INFO)"
    )
    
    parser.add_argument(
        "--simple",
        action="store_true",
        help="Use simple text-based interface instead of real-time display"
    )
    
    parser.add_argument(
        "--version",
        action="version",
        version="Listen2Me v0.1.0 - Phase 1"
    )
    
    args = parser.parse_args()
    
    # Set up logging
    setup_logging(args.log_level)
    
    # Create data directory if it doesn't exist
    data_dir = Path(args.data_dir)
    data_dir.mkdir(exist_ok=True)
    
    print("🎙️  Listen2Me - Real-time Voice Transcription")
    print("=" * 50)
    print(f"Data directory: {data_dir.absolute()}")
    print(f"Log level: {args.log_level}")
    print("=" * 50)
    
    try:
        # Initialize and run transcription screen
        if args.simple:
            print("Using simple text-based interface...")
            screen = SimpleTranscriptionScreen(str(data_dir))
        else:
            print("Using real-time display interface...")
            screen = TranscriptionScreen(str(data_dir))
        
        screen.run()
        
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"❌ Error: {e}")
        logging.error(f"Application error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()