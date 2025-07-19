# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Listen2Me is an LLM-powered voice note-taking application that provides real-time transcription with dual-mode processing. The application captures audio continuously and provides both real-time (2-second chunks) and batch (configurable windows with overlap) transcription modes running simultaneously for quality comparison.

**Current Status:** Recently refactored to separate UI from application logic in preparation for HTTP API integration. The application now uses a service layer architecture.

## Development Commands

### Environment Setup
```bash
# Set up development environment
python3 -m venv listen2me-env
source listen2me-env/bin/activate  # Linux/Mac
# listen2me-env\Scripts\activate   # Windows
pip install -r requirements.txt
pip install -r requirements-dev.txt
pip install -e .
```

### Testing
```bash
# Run all tests (excludes hardware tests by default)
pytest -v

# Run specific test categories
pytest tests/unit/ -v                    # Unit tests only
pytest tests/integration/ -v             # Integration tests only  
pytest tests/hardware/ -v -s -m hardware # Hardware tests (requires microphone)

# Run with coverage
pytest -v --cov=listen2me --cov-report=html
```

### Running the Application
```bash
# Interactive mode (default)
listen2me

# Auto mode for testing (record N seconds, save, exit)
listen2me --auto --duration 15

# Auto mode with batch transcription overrides
listen2me --auto --duration 15 --batch-window 10 --batch-interval 8

# Custom config and logging
listen2me --config path/to/config.yaml --log-level DEBUG
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

## Architecture Overview

### Service Layer Architecture (Recently Refactored)

The application uses a **service layer pattern** to separate UI from business logic:

- **`RecordingService`** (`listen2me/services/recording_service.py`): Core application logic managing recording lifecycle, dual transcription engines, and audio processing
- **`SessionManager`** (`listen2me/services/session_manager.py`): Handles file operations, session metadata, and data persistence
- **`SimpleTranscriptionScreen`** (`listen2me/ui/simple_transcription_screen.py`): UI layer that uses the services via internal API

This architecture enables future HTTP API integration (Sanic) where the same internal services can be exposed as REST endpoints.

### Dual Transcription System

**Real-time Mode**: 2-second audio chunks processed immediately for instant feedback
**Batch Mode**: Configurable windows (default 60s) processed every 45s with 15s overlap for higher quality

Both modes run simultaneously, with results stored separately for quality comparison:
- `realtime_transcription_[session].json/txt`  
- `batch_transcription_[session].json/txt`
- `combined_transcription_[session].json` (meaningful results only)

### Key Components

#### Audio Processing
- **`AudioCapture`** (`listen2me/audio/capture.py`): Thread-safe audio recording with PyAudio
- **`RollingAudioBuffer`** (`listen2me/audio/buffer.py`): 75-second rolling buffer for batch processing

#### Transcription
- **`DualTranscriptionEngine`** (`listen2me/transcription/dual_engine.py`): Manages both real-time and batch engines
- **`GoogleSpeechBackend`** (`listen2me/transcription/google_backend.py`): Google Cloud Speech-to-Text integration
- **`AbstractTranscriptionBackend`** (`listen2me/transcription/base.py`): Base interface for transcription backends

#### Data Models
All dataclasses are organized in `listen2me/models/`:
- **`TranscriptionResult`** (`models/transcription.py`): Core transcription data with timestamps and metadata
- **`AudioStats`** (`models/audio.py`): Audio capture statistics
- **`SessionInfo`** (`models/session.py`): Session metadata
- **`TranscriptionStatus`** (`models/ui.py`): UI state management

### Configuration

**Primary config**: `listen2me.yaml` with sections for:
- `google_cloud`: Speech-to-Text API settings
- `audio`: Sample rates, buffer sizes, audio processing
- `transcription.realtime`: 2-second chunk settings
- `transcription.batch`: Configurable window/interval/overlap settings
- `storage`: Data directory and file format settings
- `logging`: File paths and verbosity levels

**Runtime overrides**: Command-line arguments can override batch transcription parameters for testing.

### Session Management

Sessions use timestamp-based IDs: `YYYYMMDD_HHMMSS_XXXX`

**Directory structure**:
```
data/sessions/[session_id]/
├── recording_[session_id].wav           # Audio recording
├── session_info.json                    # Session metadata
├── realtime_transcription_[session_id].json/.txt  # Real-time results
├── batch_transcription_[session_id].json/.txt     # Batch results
└── combined_transcription_[session_id].json       # Combined meaningful results
```

**File types saved**:
- **Audio**: WAV format with proper headers
- **Transcription**: Both JSON (machine-readable) and TXT (human-readable) formats
- **Debug data**: ALL transcription attempts including "no speech detected" for debugging

## Key Implementation Details

### Thread Safety
- Audio capture runs in background threads with thread-safe queues
- Transcription processing uses ThreadPoolExecutor for concurrent backend processing
- UI updates via non-blocking status polling from services

### Error Handling
- Graceful degradation when transcription backends fail
- All transcription attempts logged (including failures) for debugging
- Resource cleanup on exceptions or keyboard interrupts

### Memory Management
- Rolling audio buffers prevent memory leaks during long recordings
- Periodic cleanup of completed transcription futures
- Proper resource disposal in all service cleanup methods

## Testing Strategy

### Test Categories
- **Unit tests** (`tests/unit/`): Fast, mocked component tests
- **Integration tests** (`tests/integration/`): Cross-component workflow tests  
- **Hardware tests** (`tests/hardware/`): Real microphone/audio tests (use `-m hardware`)

### Test Configuration
- **pytest.ini**: Configured with coverage requirements (80% minimum)
- **Fixtures**: Audio samples, mock backends, temporary directories
- **Markers**: `unit`, `integration`, `performance`, `hardware`, `slow`

## Recent Changes

**Architecture Refactoring** (Latest): Separated UI from application logic by creating service layer:
- Created `RecordingService` and `SessionManager` services
- Refactored `SimpleTranscriptionScreen` to use internal service API instead of managing business logic
- Removed ~340 lines of business logic from UI layer
- Fixed hasattr() usage throughout codebase with proper polymorphism

## Development Notes

### Code Style
- No comments in code unless explicitly requested
- Use proper polymorphism instead of hasattr() introspection
- Follow existing patterns for service-oriented architecture
- Maintain separation between UI and business logic

### Common Tasks
- **Adding new transcription backends**: Inherit from `AbstractTranscriptionBackend`
- **Modifying transcription behavior**: Update `DualTranscriptionEngine` or specific backend implementations
- **UI changes**: Work with `SimpleTranscriptionScreen` which uses service APIs
- **Storage changes**: Modify `SessionManager` or `FileManager`
- **Configuration changes**: Update `listen2me.yaml` and corresponding config classes

### Important Files for Future API Integration
- `listen2me/services/recording_service.py`: Core recording and transcription logic ready for HTTP exposure
- `listen2me/services/session_manager.py`: File operations and session management ready for HTTP exposure
- `listen2me/config/`: Configuration management that can be shared between CLI and HTTP API