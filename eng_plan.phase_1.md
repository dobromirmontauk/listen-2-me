# Engineering Plan: Phase 1 - Basic Recording (v0.1)

## Overview
Phase 1 focuses on proving core technical feasibility with minimal viable functionality. We'll build a Python terminal application that can record audio, perform real-time transcription, and display results in auto mode.

## Requirements Summary (from PRD)
- Simple Python script that records audio to WAV file
- Basic real-time transcription using Google Cloud Speech-to-Text
- Auto mode for testing and validation
- Save transcription to text file when stopped
- Support for 5+ minutes of continuous recording
- >80% transcription accuracy in quiet environment
- Single Google Speech backend for transcription
- Explicit error handling - fail clearly when credentials or configuration are missing

## Architecture Overview

### High-Level Architecture
```
┌─────────────────────────────────────────────────────────────────┐
│                    Listen2Me Auto Mode App                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────┐  │
│  │   AudioCapture  │    │ Transcription   │    │ FileManager │  │
│  │                 │    │ Service         │    │             │  │
│  │ - record()      │    │ - process()     │    │ - save()    │  │
│  │ - stop()        │    │ - cleanup()     │    │ - cleanup() │  │
│  │ - get_stats()   │    │ - get_results() │    │             │  │
│  └─────────────────┘    └─────────────────┘    └─────────────┘  │
│           │                       │                       │     │
│           └───────────────────────┼───────────────────────┘     │
│                                   │                             │
│  ┌─────────────────────────────────┼─────────────────────────────┐  │
│  │            TranscriptionEngine                              │  │
│  │                                                             │  │
│  │  ┌─────────────────────────────────────────────────────────┐  │  │
│  │  │              GoogleSpeechBackend                      │  │  │
│  │  │                                                       │  │  │
│  │  │ - transcribe()                                        │  │  │
│  │  │ - get_stats()                                         │  │  │
│  │  └─────────────────────────────────────────────────────────┘  │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Design Principles

#### 1. Fail-Fast Error Handling
- **Principle**: Application should fail immediately and clearly when critical components cannot initialize
- **Rationale**: Prevents silent failures that mask configuration or credential issues
- **Implementation**: Validate all dependencies at startup, raise descriptive exceptions

#### 2. Pub/Sub Architecture for Audio Processing
- **Principle**: Use event-driven architecture for audio processing pipeline
- **Rationale**: Enables loose coupling between audio capture and transcription processing
- **Benefits**: Easier testing, extensibility for future features (cleaning, concept extraction)

#### 3. Thread-Safe Audio Capture
- **Principle**: Audio capture runs in background thread with thread-safe data structures
- **Rationale**: Ensures continuous recording without blocking main application flow
- **Implementation**: Use Queue for audio chunks, Event for stop signaling

#### 4. Single Responsibility Components
- **Principle**: Each component has a single, well-defined responsibility
- **AudioCapture**: Only handles audio recording and chunk delivery
- **TranscriptionService**: Only handles transcription processing
- **FileManager**: Only handles file I/O operations

## Package Structure

```
listen2me/
├── main.py                    # Application entry point (auto mode)
├── requirements.txt           # Python dependencies
├── setup.py                   # Package configuration
├── tests/                     # Test suite
├── listen2me/
│   ├── __init__.py
│   ├── app.py                 # Main application orchestrator
│   ├── audio/
│   │   ├── __init__.py
│   │   ├── capture.py         # AudioCapture class
│   │   └── utils.py           # Audio utilities
│   ├── transcription/
│   │   ├── __init__.py
│   │   ├── service.py         # TranscriptionService class
│   │   ├── google_backend.py  # GoogleSpeechBackend class
│   │   └── base.py            # AbstractTranscriptionBackend
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

## Data Flow Architecture

### Audio Processing Pipeline
```
Microphone → AudioCapture → AudioEvent → TranscriptionService → GoogleSpeechBackend
                                                                    ↓
TranscriptionAggregator ← TranscriptionResult ← TranscriptionService
                                ↓
TranscriptionCleaningService ← [batch of TranscriptionResult]
                                ↓
FileManager ← [batch of TranscriptionResult (cleaned)]
```

### Event Flow
1. **Audio Capture**: Continuous background thread captures audio chunks
2. **Event Publishing**: Audio chunks published as AudioEvent objects
3. **Transcription Processing**: TranscriptionService processes events with Google Speech
4. **Result Aggregation**: TranscriptionAggregator collects results and decides when to batch
5. **Cleaning Processing**: TranscriptionCleaningService processes batches of results
6. **File Output**: Cleaned results saved to files at session end

### Threading Model
- **Main Thread**: Application orchestration and user interaction
- **Audio Thread**: Continuous audio capture (daemon thread)
- **Processing Thread**: Transcription processing (synchronous)
- **Aggregation Thread**: Result batching and cleaning coordination (asynchronous)

## Component Interfaces

### AudioCapture Interface
```python
class AudioCapture:
    def __init__(self, sample_rate: int, chunk_size: int, channels: int)
    def start_recording(self) -> None
    def stop_recording(self) -> None
    def get_recording_stats(self) -> AudioStats
    def set_audio_event_callback(self, callback: Callable[[AudioEvent], None]) -> None
```

**Key Design Decisions:**
- Uses callback-based event publishing for audio chunks
- Thread-safe recording with background thread
- Non-blocking audio chunk delivery

### TranscriptionService Interface
```python
class TranscriptionService:
    def __init__(self, backend: AbstractTranscriptionBackend)
    def process_audio_chunk(self, audio_chunk: bytes) -> None
    def get_results(self) -> List[TranscriptionResult]
    def get_stats(self) -> Dict[str, Any]
    def cleanup(self) -> None
```

**Key Design Decisions:**
- Single backend design (Google Speech only)
- Synchronous processing for simplicity
- Raw transcription results (uncleaned)

### TranscriptionAggregator Interface
```python
class TranscriptionAggregator:
    def __init__(self, batch_size: int, batch_timeout: float)
    def add_transcription_result(self, result: TranscriptionResult) -> None
    def get_ready_batches(self) -> List[List[TranscriptionResult]]
    def get_all_results(self) -> List[TranscriptionResult]
    def cleanup(self) -> None
```

**Key Design Decisions:**
- Batches raw transcription results based on size or time
- Provides ready batches to cleaning service
- Maintains all results for final aggregation

### TranscriptionCleaningService Interface
```python
class TranscriptionCleaningService:
    def __init__(self, cleaning_engine: CleaningEngine)
    def clean_transcription_batch(self, raw_results: List[TranscriptionResult]) -> List[TranscriptionResult]
    def get_cleaning_stats(self) -> Dict[str, Any]
    def cleanup(self) -> None
```

**Key Design Decisions:**
- Takes batches of raw transcription results
- Returns cleaned transcription results
- Uses pluggable cleaning engine (ChatGPT, Claude, etc.)

### GoogleSpeechBackend Interface
```python
class GoogleSpeechBackend(AbstractTranscriptionBackend):
    def __init__(self, credentials_path: str, language: str)
    def initialize(self) -> bool
    def transcribe_chunk(self, audio_chunk: bytes) -> TranscriptionResult
    def get_stats(self) -> Dict[str, Any]
    def cleanup(self) -> None
```

**Key Design Decisions:**
- Credentials validation at initialization
- Connection testing before accepting requests
- Clear error messages for configuration issues

### Listen2MeApp Interface
```python
class Listen2MeApp:
    def __init__(self, config: Dict[str, Any])
    def start_auto_mode(self, duration: int) -> None
    def _initialize_components(self) -> None
    def _cleanup(self) -> None
```

**Key Design Decisions:**
- Configuration validation at startup
- Component lifecycle management
- Clear error propagation to caller

## Data APIs (Interfaces and Schemas)

### AudioEvent (pub/sub payload)
```python
@dataclass
class AudioEvent:
    chunk_id: str
    audio_data: bytes
    timestamp: float            # Unix timestamp when chunk was captured
    sequence_number: int
    sample_rate: int = 16000
    channels: int = 1
    chunk_duration_ms: Optional[int] = None
    final: bool = False
```
- Derived field: `chunk_duration_ms` computed from audio length if not provided
- Semantics: `final=True` indicates last chunk in a session

### TranscriptionResult (raw transcription)
```python
@dataclass
class TranscriptionResult:
    text: str
    confidence: float
    processing_time: float
    timestamp: datetime
    service: str                # e.g. "google_speech"
    language: str = "en-US"
    alternatives: Optional[list] = None
    is_final: bool = True
    chunk_id: Optional[str] = None
    audio_start_time: Optional[float] = None
    audio_end_time: Optional[float] = None
    transcription_mode: str = "realtime"    # "realtime" | "batch"
    batch_id: Optional[str] = None
```
- Produced by: `TranscriptionService` (GoogleSpeechBackend)
- Consumed by: `TranscriptionAggregator`, `TranscriptionCleaningService`

### CleanedTranscriptionResult (cleaning output)
```python
@dataclass
class CleanedTranscriptionResult:
    original_chunk_ids: List[str]
    cleaned_text: str
    cleaning_timestamp: datetime
    cleaning_service: str       # e.g. "ChatGPT", "Claude"
    cleaning_model: str         # e.g. "gpt-4o-mini"
    cleaning_confidence: Optional[float] = None
    original_texts: Optional[List[str]] = None
    cleaning_notes: Optional[str] = None
    cleaning_batch_id: Optional[str] = None
    sequence_number: Optional[int] = None
```
- Produced by: `TranscriptionCleaningService`
- Consumed by: `FileManager` (and later UI)

### AudioStats (telemetry)
```python
@dataclass
class AudioStats:
    is_recording: bool
    duration_seconds: float
    buffer_size: int
    sample_rate: int
    chunk_size: int
    total_chunks: int
```
- Produced by: `AudioCapture`
- Consumed by: diagnostics and logs

## Configuration Management

### Configuration Structure
```yaml
google_cloud:
  credentials_path: "path/to/credentials.json"
  language: "en-US"
  
audio:
  sample_rate: 16000
  chunk_size: 1024
  channels: 1
  
storage:
  data_directory: "data"
  
logging:
  level: "INFO"
  file_path: "data/logs/listen2me.log"
```

### Configuration Validation
- **Required Fields**: Validate all required configuration at startup
- **File Existence**: Check credentials file exists before initialization
- **Type Validation**: Ensure configuration values are correct types
- **Clear Errors**: Provide descriptive error messages for missing/invalid config

## Error Handling Strategy

### Error Categories
1. **Configuration Errors**: Missing or invalid configuration
2. **Credential Errors**: Missing or invalid Google Cloud credentials
3. **Network Errors**: Google Speech API connectivity issues
4. **Audio Errors**: Microphone access or audio format issues
5. **Resource Errors**: File system or memory issues

### Error Handling Principles
- **Fail Fast**: Stop immediately when critical dependencies fail
- **Clear Messages**: Provide actionable error messages
- **No Silent Failures**: All errors should be logged and reported
- **Graceful Degradation**: Not applicable for Phase 1 (core functionality required)

### Error Propagation
- **Configuration Errors**: Raise ValueError with clear description
- **Credential Errors**: Raise FileNotFoundError or ValueError
- **Runtime Errors**: Raise RuntimeError with context
- **Application Level**: Catch and re-raise with additional context

## Testing Strategy

### Test Categories
1. **Unit Tests**: Individual component testing
2. **Integration Tests**: Component interaction testing
3. **Hardware Tests**: Real microphone testing
4. **Error Tests**: Configuration and credential error scenarios

### Test Coverage Requirements
- **Audio Capture**: Thread safety, buffer management, resource cleanup
- **Transcription Service**: Google Speech integration, error handling
- **Configuration**: Validation, error scenarios
- **File Management**: Audio and transcription file saving

### Test Data
- **Mock Audio**: Generated test audio for unit tests
- **Real Audio**: Actual microphone recording for hardware tests
- **Error Scenarios**: Missing credentials, invalid config, network failures

## Performance Requirements

### Audio Processing
- **Latency**: <2 seconds from audio capture to transcription result
- **Throughput**: Support continuous recording without buffer overflow
- **Memory**: Efficient audio chunk processing without memory leaks

### Resource Management
- **CPU**: Minimal impact during recording
- **Memory**: Bounded memory usage for long recording sessions
- **Disk**: Efficient audio file storage and cleanup

## Success Criteria

### Functional Requirements
- ✅ Record 5+ minutes of continuous audio
- ✅ Transcribe with >80% accuracy in quiet environment
- ✅ Save audio and transcription files correctly
- ✅ Handle configuration errors gracefully

### Non-Functional Requirements
- ✅ Clear error messages for missing credentials
- ✅ Thread-safe audio processing
- ✅ Proper resource cleanup
- ✅ Configurable recording parameters

## Risk Mitigation

### Technical Risks
1. **Google Speech API Limits**: Monitor usage and handle rate limiting
2. **Audio Driver Issues**: Test with multiple audio devices
3. **Configuration Complexity**: Provide clear documentation and examples
4. **Resource Leaks**: Comprehensive cleanup in all error paths

### Mitigation Strategies
- **API Monitoring**: Track API usage and errors
- **Hardware Testing**: Test with real microphones
- **Documentation**: Clear setup and configuration guides
- **Error Logging**: Comprehensive error tracking and reporting

## Deliverables

### Deliverable 1: Basic Audio Recording ✅ **MOSTLY COMPLETE**
- Audio capture with pub/sub architecture
- File saving works
- Need to fix tests to match new API

### Deliverable 2: Auto Mode with Transcription ❌ **NEEDS WORK**
- Auto mode exists but needs enhancement
- Need to integrate transcription results display
- Need to add proper error handling

### Deliverable 3: Google Speech Backend ❌ **PARTIAL**
- Google Speech backend works
- Need to add explicit error handling for missing credentials
- Need to add configuration validation

### Deliverable 4: Explicit Error Handling ❌ **NEEDS WORK**
- Need clear error messages when credentials are missing
- Need validation of configuration before starting
- Need to fail fast when critical components can't initialize