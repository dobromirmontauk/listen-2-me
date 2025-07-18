# Engineering Plan: Phase 1 - Basic Recording (v0.1)

## Overview
Phase 1 focuses on proving core technical feasibility with minimal viable functionality. We'll build a Python terminal application that can record audio, perform real-time transcription, and display results in a simple terminal interface.

## Requirements Summary (from PRD)
- Simple Python script that records audio to WAV file
- Basic real-time transcription using OpenAI Whisper or similar
- Terminal output showing transcription as it happens
- Save transcription to text file when stopped
- Support for 5+ minutes of continuous recording
- >80% transcription accuracy in quiet environment
- Two transcription backends for comparison

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    Listen2Me Terminal App                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────┐  │
│  │   AudioCapture  │    │ TranscriptionUI │    │ FileManager │  │
│  │                 │    │                 │    │             │  │
│  │ - record()      │    │ - display()     │    │ - save()    │  │
│  │ - stop()        │    │ - refresh()     │    │ - cleanup() │  │
│  │ - get_data()    │    │ - show_stats()  │    │             │  │
│  └─────────────────┘    └─────────────────┘    └─────────────┘  │
│           │                       │                       │     │
│           └───────────────────────┼───────────────────────┘     │
│                                   │                             │
│  ┌─────────────────────────────────┼─────────────────────────────┐  │
│  │            TranscriptionEngine                              │  │
│  │                                                             │  │
│  │  ┌─────────────────┐    ┌─────────────────┐               │  │
│  │  │  WhisperBackend │    │  GoogleBackend  │               │  │
│  │  │                 │    │                 │               │  │
│  │  │ - transcribe()  │    │ - transcribe()  │               │  │
│  │  │ - get_stats()   │    │ - get_stats()   │               │  │
│  │  └─────────────────┘    └─────────────────┘               │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Package Structure

```
listen2me/
├── main.py                    # Application entry point
├── requirements.txt           # Python dependencies
├── setup.py                   # Package configuration
├── tests/
│   ├── __init__.py
│   ├── test_audio_capture.py
│   ├── test_transcription.py
│   └── test_integration.py
├── listen2me/
│   ├── __init__.py
│   ├── app.py                 # Main application class
│   ├── audio/
│   │   ├── __init__.py
│   │   ├── capture.py         # AudioCapture class
│   │   └── utils.py           # Audio utilities
│   ├── transcription/
│   │   ├── __init__.py
│   │   ├── engine.py          # TranscriptionEngine class
│   │   ├── whisper_backend.py # WhisperBackend class
│   │   ├── google_backend.py  # GoogleBackend class
│   │   └── base.py            # AbstractTranscriptionBackend
│   ├── ui/
│   │   ├── __init__.py
│   │   ├── terminal.py        # TranscriptionUI class
│   │   └── screens.py         # Screen 1a/1b implementations
│   ├── storage/
│   │   ├── __init__.py
│   │   └── file_manager.py    # FileManager class
│   └── config/
│       ├── __init__.py
│       └── settings.py        # Configuration management
└── data/                      # Runtime data directory
    ├── audio/
    ├── transcriptions/
    └── logs/
```

## Core Classes and Interfaces

### 1. AudioCapture (`listen2me/audio/capture.py`)
```python
from queue import Queue
from threading import Thread, Event
import pyaudio
import wave

class AudioCapture:
    def __init__(self, sample_rate: int = 16000, chunk_size: int = 1024, buffer_size: int = 100):
        """Initialize audio capture with specified parameters.
        
        Args:
            sample_rate: Audio sample rate (16kHz for Whisper)
            chunk_size: Size of each audio chunk in samples
            buffer_size: Maximum number of chunks to buffer
        """
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.audio_queue = Queue(maxsize=buffer_size)
        self.recording_thread = None
        self.stop_event = Event()
        self.is_recording = False
        
    def start_recording(self) -> None:
        """Start continuous recording in background thread."""
        if self.is_recording:
            return
            
        self.stop_event.clear()
        self.recording_thread = Thread(target=self._record_continuously)
        self.recording_thread.daemon = True
        self.recording_thread.start()
        self.is_recording = True
        
    def stop_recording(self) -> None:
        """Stop recording and clean up resources."""
        if not self.is_recording:
            return
            
        self.stop_event.set()
        if self.recording_thread:
            self.recording_thread.join(timeout=2.0)
        self.is_recording = False
        
    def _record_continuously(self) -> None:
        """Internal method: continuous recording loop in background thread."""
        audio = pyaudio.PyAudio()
        stream = audio.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=self.sample_rate,
            input=True,
            frames_per_buffer=self.chunk_size
        )
        
        try:
            while not self.stop_event.is_set():
                # Read audio chunk from microphone
                audio_chunk = stream.read(self.chunk_size, exception_on_overflow=False)
                
                # Put chunk in queue for transcription (non-blocking)
                if not self.audio_queue.full():
                    self.audio_queue.put(audio_chunk)
                else:
                    # Drop oldest chunk if buffer is full
                    try:
                        self.audio_queue.get_nowait()
                        self.audio_queue.put(audio_chunk)
                    except:
                        pass
                        
        finally:
            stream.stop_stream()
            stream.close()
            audio.terminate()
        
    def get_audio_chunk(self) -> Optional[bytes]:
        """Get next audio chunk for processing (non-blocking).
        
        Returns:
            Audio chunk bytes or None if no data available
        """
        try:
            return self.audio_queue.get_nowait()
        except:
            return None
            
    def has_audio_data(self) -> bool:
        """Check if audio data is available for processing."""
        return not self.audio_queue.empty()
        
    def get_buffer_size(self) -> int:
        """Get current number of buffered chunks."""
        return self.audio_queue.qsize()
        
    def save_to_file(self, filepath: str) -> None:
        """Save recorded audio to WAV file."""
        # Implementation will save accumulated audio data
        pass
        
    def get_recording_stats(self) -> Dict[str, Any]:
        """Get current recording statistics."""
        return {
            "is_recording": self.is_recording,
            "buffer_size": self.get_buffer_size(),
            "sample_rate": self.sample_rate,
            "chunk_size": self.chunk_size
        }
```

### 2. AbstractTranscriptionBackend (`listen2me/transcription/base.py`)
```python
from abc import ABC, abstractmethod

class AbstractTranscriptionBackend(ABC):
    @abstractmethod
    def transcribe_chunk(self, audio_chunk: bytes) -> TranscriptionResult:
        """Transcribe audio chunk and return result."""
        
    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        """Get backend performance statistics."""
        
    @abstractmethod
    def initialize(self) -> bool:
        """Initialize backend resources."""
        
    @abstractmethod
    def cleanup(self) -> None:
        """Clean up backend resources."""

@dataclass
class TranscriptionResult:
    text: str
    confidence: float
    processing_time: float
    timestamp: datetime
    service: str
```

### 3. WhisperBackend (`listen2me/transcription/whisper_backend.py`)
```python
class WhisperBackend(AbstractTranscriptionBackend):
    def __init__(self, model_name: str = "base"):
        """Initialize Whisper backend with specified model."""
        
    def transcribe_chunk(self, audio_chunk: bytes) -> TranscriptionResult:
        """Transcribe using local Whisper model."""
        
    def get_stats(self) -> Dict[str, Any]:
        """Return Whisper-specific statistics."""
```

### 4. GoogleBackend (`listen2me/transcription/google_backend.py`)
```python
class GoogleBackend(AbstractTranscriptionBackend):
    def __init__(self, credentials_path: str = None):
        """Initialize Google Speech-to-Text backend."""
        
    def transcribe_chunk(self, audio_chunk: bytes) -> TranscriptionResult:
        """Transcribe using Google Cloud Speech API."""
        
    def get_stats(self) -> Dict[str, Any]:
        """Return Google-specific statistics."""
```

### 5. TranscriptionEngine (`listen2me/transcription/engine.py`)
```python
from concurrent.futures import ThreadPoolExecutor, Future
from queue import Queue
from typing import List, Dict, Any, Optional
import threading

class TranscriptionEngine:
    def __init__(self, backends: List[AbstractTranscriptionBackend]):
        """Initialize engine with multiple backends."""
        self.backends = backends
        self.executor = ThreadPoolExecutor(max_workers=len(backends))
        self.result_queue = Queue()
        self.pending_futures = []
        self.lock = threading.Lock()
        
    def submit_chunk(self, audio_chunk: bytes) -> None:
        """Submit audio chunk for asynchronous transcription.
        
        Args:
            audio_chunk: Raw audio data to transcribe
        """
        with self.lock:
            # Submit to all backends concurrently
            for backend in self.backends:
                future = self.executor.submit(self._transcribe_with_backend, backend, audio_chunk)
                self.pending_futures.append(future)
                
    def _transcribe_with_backend(self, backend: AbstractTranscriptionBackend, audio_chunk: bytes) -> TranscriptionResult:
        """Internal method: transcribe with specific backend."""
        try:
            result = backend.transcribe_chunk(audio_chunk)
            self.result_queue.put(result)
            return result
        except Exception as e:
            # Handle transcription errors gracefully
            error_result = TranscriptionResult(
                text=f"[ERROR: {backend.__class__.__name__}]",
                confidence=0.0,
                processing_time=0.0,
                timestamp=datetime.now(),
                service=backend.__class__.__name__
            )
            self.result_queue.put(error_result)
            return error_result
            
    def get_completed_results(self) -> List[TranscriptionResult]:
        """Get all completed transcription results (non-blocking).
        
        Returns:
            List of completed transcription results
        """
        results = []
        
        # Clean up completed futures
        with self.lock:
            self.pending_futures = [f for f in self.pending_futures if not f.done()]
            
        # Get all available results from queue
        while not self.result_queue.empty():
            try:
                result = self.result_queue.get_nowait()
                results.append(result)
            except:
                break
                
        return results
        
    def get_comparison_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get performance comparison between backends."""
        stats = {}
        for backend in self.backends:
            stats[backend.__class__.__name__] = backend.get_stats()
        return stats
        
    def cleanup(self) -> None:
        """Clean up engine resources."""
        self.executor.shutdown(wait=True)
        for backend in self.backends:
            backend.cleanup()
```

### 6. TranscriptionUI (`listen2me/ui/terminal.py`)
```python
class TranscriptionUI:
    def __init__(self):
        """Initialize terminal UI."""
        
    def display_screen_1a(self, audio_stats: Dict[str, Any]) -> None:
        """Display Screen 1a: Audio Recording Status."""
        
    def display_screen_1b(self, transcription_results: List[TranscriptionResult]) -> None:
        """Display Screen 1b: Real-time Transcription."""
        
    def handle_keyboard_input(self) -> Optional[str]:
        """Handle keyboard input for commands."""
        
    def refresh_display(self) -> None:
        """Refresh the current display."""
```

### 7. FileManager (`listen2me/storage/file_manager.py`)
```python
class FileManager:
    def __init__(self, data_dir: str = "./data"):
        """Initialize file manager with data directory."""
        
    def save_audio_file(self, audio_data: bytes, filename: str) -> str:
        """Save audio data to file and return path."""
        
    def save_transcription(self, results: List[TranscriptionResult], filename: str) -> str:
        """Save transcription results to JSON file."""
        
    def create_session_directory(self) -> str:
        """Create new session directory with timestamp."""
        
    def cleanup_old_files(self, max_age_days: int = 30) -> None:
        """Clean up old session files."""
```

### 8. Listen2MeApp (`listen2me/app.py`)
```python
class Listen2MeApp:
    def __init__(self):
        """Initialize the main application."""
        
    def start(self) -> None:
        """Start the application main loop."""
        
    def stop(self) -> None:
        """Stop the application and clean up resources."""
        
    def handle_keyboard_commands(self, command: str) -> None:
        """Handle keyboard commands (P, S, 1a, 1b, etc.)."""
```

## Component Interfaces

### Audio → Transcription Interface
```python
# Continuous audio streaming with non-blocking interface
while app.is_running:
    # Audio capture runs in background thread, filling queue
    if audio_capture.has_audio_data():
        audio_chunk: bytes = audio_capture.get_audio_chunk()
        
        # Submit for async transcription (non-blocking)
        transcription_engine.submit_chunk(audio_chunk)
        
    # Get completed results (non-blocking)
    results: List[TranscriptionResult] = transcription_engine.get_completed_results()
```

### Transcription → UI Interface
```python
# Transcription results are displayed in real-time
results: List[TranscriptionResult] = transcription_engine.get_recent_results()
ui.display_screen_1b(results)
```

### Audio → Storage Interface
```python
# Audio data is saved to files for persistence
audio_data: bytes = audio_capture.get_recorded_data()
filepath: str = file_manager.save_audio_file(audio_data, "session_001.wav")
```

### UI → App Interface
```python
# UI commands are handled by main application
command: str = ui.handle_keyboard_input()
app.handle_keyboard_commands(command)
```

## Application Execution

### Startup Sequence
1. **Configuration Loading**: Load settings from `config/settings.py`
2. **Backend Initialization**: Initialize Whisper and Google backends
3. **Audio System Setup**: Initialize audio capture with appropriate parameters
4. **UI Initialization**: Set up terminal UI and screen management
5. **File System Setup**: Create session directory and prepare storage

### Main Loop
```python
def main_loop():
    # Start continuous audio recording in background thread
    audio_capture.start_recording()
    
    while app.is_running:
        # 1. Check for new audio chunks (non-blocking)
        if audio_capture.has_audio_data():
            audio_chunk = audio_capture.get_audio_chunk()
            
            # 2. Process with transcription backends (async)
            if audio_chunk:
                transcription_engine.submit_chunk(audio_chunk)
        
        # 3. Get completed transcription results
        completed_results = transcription_engine.get_completed_results()
        
        # 4. Update UI display with new results
        if completed_results:
            ui.update_transcription_display(completed_results)
        ui.refresh_display()
        
        # 5. Handle keyboard input (non-blocking)
        command = ui.handle_keyboard_input()
        if command:
            app.handle_keyboard_commands(command)
            
        # 6. Save periodic checkpoints
        if should_checkpoint():
            file_manager.save_checkpoint()
            
        # 7. Small sleep to prevent busy waiting
        time.sleep(0.01)  # 10ms sleep
        
    # Stop recording when exiting
    audio_capture.stop_recording()
```

### Shutdown Sequence
1. **Stop Recording**: Gracefully stop audio capture
2. **Save Final Data**: Save all audio and transcription data
3. **Backend Cleanup**: Clean up transcription backend resources
4. **File System Cleanup**: Ensure all files are properly saved
5. **Resource Cleanup**: Release audio system and UI resources

## Testing Strategy

### Unit Tests

#### Audio Capture Tests (`tests/test_audio_capture.py`)
```python
def test_audio_capture_initialization()
def test_start_stop_recording()
def test_audio_chunk_generation()
def test_wav_file_saving()
def test_recording_statistics()
def test_resource_cleanup()
```

#### Transcription Tests (`tests/test_transcription.py`)
```python
def test_whisper_backend_initialization()
def test_google_backend_initialization()
def test_transcription_accuracy()
def test_performance_statistics()
def test_error_handling()
def test_backend_comparison()
```

#### UI Tests (`tests/test_ui.py`)
```python
def test_screen_1a_display()
def test_screen_1b_display()
def test_keyboard_input_handling()
def test_screen_transitions()
def test_ui_refresh()
```

### Integration Tests (`tests/test_integration.py`)
```python
def test_end_to_end_recording_flow()
def test_real_time_transcription_pipeline()
def test_file_saving_and_loading()
def test_multi_backend_comparison()
def test_error_recovery()
def test_long_recording_sessions()
```

### Performance Tests
```python
def test_5_minute_continuous_recording()
def test_transcription_latency()
def test_memory_usage_over_time()
def test_cpu_usage_monitoring()
def test_disk_space_management()
```

### Pytest Configuration (`pytest.ini`)
```ini
[tool:pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = 
    -v
    --strict-markers
    --tb=short
    --cov=listen2me
    --cov-report=html
    --cov-report=term-missing
    --cov-fail-under=80
markers =
    unit: Unit tests
    integration: Integration tests
    performance: Performance tests
    slow: Slow tests that take >1 second
```

### Automated Test Execution
```bash
# Set up virtual environment and install dependencies
python -m venv listen2me-env
source listen2me-env/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
pip install -e .

# Run all tests with coverage
pytest

# Run specific test categories
pytest -m unit                    # Unit tests only
pytest -m integration             # Integration tests only
pytest -m performance             # Performance tests only
pytest -m "not slow"              # Skip slow tests

# Run tests with parallel execution
pytest -n auto                    # Use all CPU cores
pytest -n 4                       # Use 4 processes

# Run tests with verbose output
pytest -v --tb=long

# Run specific test file
pytest tests/test_audio_capture.py

# Run tests and generate HTML coverage report
pytest --cov=listen2me --cov-report=html

# Run tests in watch mode (install pytest-watch)
ptw -- --testmon
```

### Test Project Structure
```
tests/
├── conftest.py                   # Pytest configuration and fixtures
├── fixtures/                     # Test fixtures and sample data
│   ├── audio_samples/
│   │   ├── test_audio_16khz.wav
│   │   ├── test_audio_noisy.wav
│   │   └── test_audio_silent.wav
│   └── transcription_samples/
│       ├── expected_results.json
│       └── mock_responses.json
├── unit/
│   ├── test_audio_capture.py
│   ├── test_transcription_backends.py
│   ├── test_transcription_engine.py
│   ├── test_ui_terminal.py
│   └── test_file_manager.py
├── integration/
│   ├── test_audio_to_transcription.py
│   ├── test_end_to_end_workflow.py
│   └── test_ui_integration.py
└── performance/
    ├── test_long_recording.py
    ├── test_transcription_latency.py
    └── test_memory_usage.py
```

### Test Configuration (`conftest.py`)
```python
import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, MagicMock

@pytest.fixture
def temp_data_dir():
    """Create temporary directory for test data."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir

@pytest.fixture
def mock_audio_capture():
    """Mock AudioCapture for testing."""
    mock = Mock()
    mock.is_recording = False
    mock.get_audio_chunk.return_value = b'\x00' * 1024  # Silent audio
    mock.has_audio_data.return_value = True
    mock.get_recording_stats.return_value = {
        "is_recording": True,
        "buffer_size": 10,
        "sample_rate": 16000,
        "chunk_size": 1024
    }
    return mock

@pytest.fixture
def mock_whisper_backend():
    """Mock WhisperBackend for testing."""
    from listen2me.transcription.base import TranscriptionResult
    from datetime import datetime
    
    mock = Mock()
    mock.transcribe_chunk.return_value = TranscriptionResult(
        text="test transcription",
        confidence=0.9,
        processing_time=0.1,
        timestamp=datetime.now(),
        service="whisper"
    )
    mock.get_stats.return_value = {
        "total_requests": 1,
        "avg_latency": 0.1,
        "error_count": 0
    }
    return mock

@pytest.fixture
def sample_audio_file():
    """Path to sample audio file for testing."""
    return Path(__file__).parent / "fixtures" / "audio_samples" / "test_audio_16khz.wav"

@pytest.fixture(scope="session")
def test_config():
    """Test configuration settings."""
    return {
        "audio": {
            "sample_rate": 16000,
            "chunk_size": 1024,
            "buffer_size": 10
        },
        "transcription": {
            "whisper_model": "base",
            "timeout": 30
        }
    }
```

### Development Workflow Commands
```bash
# Complete development setup
make setup                        # Set up virtual env and install deps
make test                         # Run all tests
make test-unit                    # Run unit tests only
make test-integration             # Run integration tests only
make test-performance             # Run performance tests only
make coverage                     # Generate coverage report
make lint                         # Run code linting
make format                       # Format code with black
make type-check                   # Run mypy type checking
make clean                        # Clean up generated files

# Continuous development
make watch-tests                  # Run tests on file changes
make dev                          # Start development server
```

### Makefile for Development
```makefile
.PHONY: setup test test-unit test-integration test-performance coverage lint format type-check clean

VENV = listen2me-env
PYTHON = $(VENV)/bin/python
PIP = $(VENV)/bin/pip
PYTEST = $(VENV)/bin/pytest

setup:
	python -m venv $(VENV)
	$(PIP) install -r requirements.txt
	$(PIP) install -r requirements-dev.txt
	$(PIP) install -e .

test:
	$(PYTEST)

test-unit:
	$(PYTEST) -m unit

test-integration:
	$(PYTEST) -m integration

test-performance:
	$(PYTEST) -m performance

coverage:
	$(PYTEST) --cov=listen2me --cov-report=html --cov-report=term

lint:
	$(VENV)/bin/flake8 listen2me tests
	$(VENV)/bin/isort --check-only listen2me tests

format:
	$(VENV)/bin/black listen2me tests
	$(VENV)/bin/isort listen2me tests

type-check:
	$(VENV)/bin/mypy listen2me

clean:
	rm -rf $(VENV)
	rm -rf htmlcov
	rm -rf .coverage
	rm -rf .pytest_cache
	rm -rf __pycache__
	find . -name "*.pyc" -delete
	find . -name "*.pyo" -delete
```

## Development Environment Setup

### Virtual Environment Setup
```bash
# Create virtual environment
python -m venv listen2me-env

# Activate virtual environment (macOS/Linux)
source listen2me-env/bin/activate

# Activate virtual environment (Windows)
listen2me-env\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Install package in development mode
pip install -e .
```

### Dependencies

#### Production Dependencies (`requirements.txt`)
```
# Core dependencies
pyaudio>=0.2.11
numpy>=1.21.0
scipy>=1.7.0

# Whisper backend
openai-whisper>=20230314
torch>=1.13.0

# Google backend
google-cloud-speech>=2.16.0
google-auth>=2.10.0

# UI and utilities
rich>=12.5.0
click>=8.1.0
pydantic>=1.10.0
```

#### Development Dependencies (`requirements-dev.txt`)
```
# Testing framework
pytest>=7.1.0
pytest-cov>=4.0.0
pytest-mock>=3.10.0
pytest-asyncio>=0.21.0
pytest-xdist>=3.0.0

# Code quality
black>=22.0.0
flake8>=5.0.0
isort>=5.10.0
mypy>=1.0.0

# Development tools
pre-commit>=2.20.0
tox>=4.0.0
```

### Setup Configuration (`setup.py`)
```python
from setuptools import setup, find_packages

setup(
    name="listen2me",
    version="0.1.0",
    description="LLM-powered notetaking & idea organizer app",
    author="Your Name",
    python_requires=">=3.8",
    packages=find_packages(),
    install_requires=[
        "pyaudio>=0.2.11",
        "numpy>=1.21.0",
        "scipy>=1.7.0",
        "openai-whisper>=20230314",
        "torch>=1.13.0",
        "google-cloud-speech>=2.16.0",
        "google-auth>=2.10.0",
        "rich>=12.5.0",
        "click>=8.1.0",
        "pydantic>=1.10.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.1.0",
            "pytest-cov>=4.0.0",
            "pytest-mock>=3.10.0",
            "pytest-asyncio>=0.21.0",
            "black>=22.0.0",
            "flake8>=5.0.0",
            "isort>=5.10.0",
            "mypy>=1.0.0",
        ]
    },
    entry_points={
        "console_scripts": [
            "listen2me=listen2me.main:main",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
)
```

## Success Criteria Verification

### Automated Checks
1. **5+ minute recording test**: Integration test that records for 5 minutes and verifies file integrity
2. **Transcription accuracy test**: Use known audio samples to verify >80% accuracy
3. **Real-time display test**: Verify UI updates within acceptable latency
4. **Backend comparison test**: Ensure both Whisper and Google backends function correctly
5. **Resource cleanup test**: Verify no memory leaks or resource exhaustion

### Manual Verification
1. **Terminal display**: Visual confirmation of Screen 1a and 1b displays
2. **Audio quality**: Listen to saved WAV files for quality verification
3. **Transcription review**: Manual review of transcription accuracy
4. **Performance monitoring**: Monitor CPU/memory usage during operation

## Risk Mitigation

### Technical Risks
1. **Audio driver issues**: Include fallback audio backends and comprehensive error handling
2. **Whisper model loading**: Implement retry logic and model caching
3. **Google API failures**: Include offline fallback and rate limiting
4. **Resource exhaustion**: Implement memory monitoring and cleanup

### Deliverable Checkpoints
1. **Deliverable 1**: Basic audio recording and file saving
2. **Deliverable 2**: Screen 1a implementation with audio visualization
3. **Deliverable 3**: Dual backend transcription with statistics
4. **Deliverable 4**: Screen 1b implementation with real-time display

Each deliverable includes its own test suite and success criteria verification.