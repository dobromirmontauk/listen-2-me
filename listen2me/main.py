"""Main application entry point for Listen2Me."""

import sys
import argparse
import logging
from pathlib import Path

from .ui.simple_transcription_screen import SimpleTranscriptionScreen
from .config import get_config


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
    
    try:
        # Load configuration first to set up logging properly
        if args.config:
            from .config import reload_config
            config = reload_config(args.config)
        else:
            config = get_config()
        
        # Set up logging (override config with command line if specified)
        log_level = args.log_level if args.log_level != "INFO" else config.get('logging.level', 'INFO')
        setup_logging(config, log_level)
        
        if args.auto:
            # Auto mode: automated recording for testing
            print("🤖 Listen2Me - Auto Mode")
            print("=" * 50)
            print(f"Configuration: {config.config_file}")
            print(f"Data directory: {config.get_data_directory()}")
            print(f"Recording duration: {args.duration} seconds")
            print(f"Log level: {log_level}")
            print("=" * 50)
            
            # Run auto mode
            from .auto_mode import run_auto_mode
            batch_overrides = {}
            if args.batch_window:
                batch_overrides['window_duration_seconds'] = args.batch_window
            if args.batch_interval:
                batch_overrides['interval_seconds'] = args.batch_interval
            
            run_auto_mode(args.config, args.duration, batch_overrides)
        else:
            # Interactive mode
            print("🎙️  Listen2Me - Real-time Voice Transcription")
            print("=" * 50)
            print(f"Configuration: {config.config_file}")
            print(f"Data directory: {config.get_data_directory()}")
            print(f"Log level: {log_level}")
            print("=" * 50)
            
            # Initialize and run transcription screen
            print("Starting Listen2Me interface...")
            screen = SimpleTranscriptionScreen(args.config)
            screen.run()
        
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"❌ Error: {e}")
        logging.error(f"Application error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()