# Listen2Me - Real-time Voice Transcription

🎙️ **Phase 1 Complete**: Audio capture and real-time transcription interface

Listen2Me is an LLM-powered voice note-taking application that captures audio continuously without interruption and provides real-time transcription feedback.

## Features

- **Continuous Audio Capture**: Records audio in background threads without blocking
- **Real-time Interface**: Live terminal UI showing audio levels and processing status
- **Session Management**: Automatic session creation with unique IDs and metadata
- **Cross-platform**: Works on macOS, Linux, and Windows
- **Professional Testing**: Comprehensive test suite with both mocked and hardware tests

## Installation

### Prerequisites

- Python 3.8 or higher
- Working microphone
- Audio input permissions

### macOS Setup

1. **Install PortAudio** (required for PyAudio):
   ```bash
   brew install portaudio
   ```

2. **Clone and install**:
   ```bash
   git clone <repository-url>
   cd listen-2-me
   python3 -m venv listen2me-env
   source listen2me-env/bin/activate
   pip install -r requirements.txt
   pip install -r requirements-dev.txt
   pip install -e .
   ```

### Linux Setup

1. **Install system dependencies**:
   ```bash
   # Ubuntu/Debian
   sudo apt-get install portaudio19-dev python3-pyaudio
   
   # CentOS/RHEL
   sudo yum install portaudio-devel
   ```

2. **Install Listen2Me**:
   ```bash
   git clone <repository-url>
   cd listen-2-me
   python3 -m venv listen2me-env
   source listen2me-env/bin/activate
   pip install -r requirements.txt
   pip install -r requirements-dev.txt
   pip install -e .
   ```

### Windows Setup

1. **Install Listen2Me**:
   ```cmd
   git clone <repository-url>
   cd listen-2-me
   python -m venv listen2me-env
   listen2me-env\Scripts\activate
   pip install -r requirements.txt
   pip install -r requirements-dev.txt
   pip install -e .
   ```

## Usage

### Basic Usage

Start the real-time transcription interface:
```bash
listen2me
```

### Command Line Options

```bash
listen2me --help
```

Available options:
- `--data-dir DIR`: Directory to store audio files and session data (default: `./data`)
- `--log-level LEVEL`: Set logging level (DEBUG, INFO, WARNING, ERROR)
- `--version`: Show version information

### Keyboard Controls

When running the transcription interface:

| Key | Action |
|-----|--------|
| `SPACE` | Start/stop recording (toggle) |
| `S` | Stop recording |
| `R` | Reset current session |
| `Q` | Quit application |

### Example Usage

```bash
# Basic usage with default settings
listen2me

# Store data in custom directory with debug logging
listen2me --data-dir ~/my-recordings --log-level DEBUG

# Quiet mode with minimal output
listen2me --log-level WARNING
```

## Testing

### Run All Tests

```bash
# Activate virtual environment
source listen2me-env/bin/activate

# Run all tests (excludes hardware tests)
pytest -v

# Run with coverage
pytest -v --cov=listen2me --cov-report=html
```

### Test Categories

1. **Unit Tests** (fast, mocked):
   ```bash
   pytest tests/unit/ -v
   ```

2. **Integration Tests** (medium, mocked):
   ```bash
   pytest tests/integration/ -v
   ```

3. **Hardware Tests** (slow, real microphone):
   ```bash
   pytest tests/hardware/ -v -s -m hardware
   ```

### Hardware Testing

Test with real microphone to verify audio capture:

```bash
# Run hardware tests (requires microphone)
pytest tests/hardware/ -v -s -m hardware
```

The hardware tests will:
- Record 10 seconds of audio from your microphone
- Verify file size and format are correct
- Test real-time audio processing workflow
- Validate session management with actual audio

## Project Structure

```
listen2me/
├── listen2me/
│   ├── audio/
│   │   └── capture.py          # Audio capture with threading
│   ├── storage/
│   │   └── file_manager.py     # Session and file management
│   ├── ui/
│   │   ├── transcription_screen.py  # Real-time terminal UI
│   │   └── keyboard_input.py   # Cross-platform keyboard handling
│   └── main.py                 # CLI entry point
├── tests/
│   ├── unit/                   # Unit tests (mocked)
│   ├── integration/            # Integration tests (mocked)
│   └── hardware/               # Hardware tests (real microphone)
├── requirements.txt            # Core dependencies
├── requirements-dev.txt        # Development dependencies
└── setup.py                   # Package configuration
```

## Architecture

### Audio Capture Flow

1. **Background Recording**: Audio capture runs in separate thread
2. **Queue-based Processing**: Audio chunks placed in thread-safe queue
3. **Real-time Display**: UI updates showing live audio levels and stats
4. **Non-blocking Design**: Audio never stops for processing/transcription

### Session Management

- **Unique Session IDs**: `YYYYMMDD_HHMMSS_XXXX` format with random suffix
- **Metadata Storage**: JSON files with session info, duration, file paths
- **Audio Files**: WAV format with proper headers and validation
- **Directory Structure**: Organized by session with separate audio/metadata files

## Development

### Running Tests

```bash
# Run all tests
pytest -v

# Run specific test category
pytest tests/unit/ -v
pytest tests/integration/ -v
pytest tests/hardware/ -v -s -m hardware

# Run with coverage
pytest --cov=listen2me --cov-report=html
```

### Code Quality

```bash
# Format code
black listen2me/ tests/

# Check style
flake8 listen2me/ tests/

# Sort imports
isort listen2me/ tests/

# Type checking
mypy listen2me/
```

## Troubleshooting

### Audio Issues

**"No audio device found"**:
- Check microphone permissions
- Verify microphone is connected and working
- Try running hardware tests: `pytest tests/hardware/ -v -s -m hardware`

**"PortAudio error"**:
- Install PortAudio: `brew install portaudio` (macOS)
- Check system audio settings

### Installation Issues

**PyAudio installation fails**:
- Install PortAudio first (see platform-specific instructions above)
- On older systems, try: `pip install --upgrade pip setuptools wheel`

**Permission errors**:
- Grant microphone permissions to Terminal/IDE
- Run with appropriate user permissions

### Performance Issues

**High CPU usage**:
- Reduce refresh rate in UI (edit `refresh_per_second` in `transcription_screen.py`)
- Increase chunk size for less frequent processing

**Memory issues**:
- Reduce buffer size in AudioCapture
- Clear old sessions regularly

## Current Status

✅ **Phase 1 Complete**:
- [x] Audio capture with continuous recording
- [x] Real-time terminal interface
- [x] Session management and file storage
- [x] Cross-platform keyboard controls
- [x] Comprehensive test suite
- [x] Hardware verification tests

🚧 **Next Phase**: Real transcription integration (Whisper/OpenAI API)

## License

[License information]

## Contributing

[Contributing guidelines]