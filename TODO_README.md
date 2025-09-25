# Listen 2 Me: TODO and Project Status

This document outlines the current state of the "Listen 2 Me" project and the immediate next steps required to achieve the goals for Phase 1.

## Current Project Status

The project is currently in **Phase 1: Basic Recording (v0.1)**. The goal of this phase is to create a stable Python terminal application that can record audio and perform real-time transcription.

### What's Working

*   **Audio Capture:** The application can capture audio from a microphone using a pub/sub architecture.
*   **Transcription:** The application uses the Google Cloud Speech-to-Text API to transcribe audio.
*   **Auto Mode:** The `main.py` script can be run in an "auto" mode, which records for a fixed duration and prints transcription results to the console.
*   **Configuration:** The application loads its configuration from a `listen2me.yaml` file.

### What's Not Working or Incomplete

*   **Stability:** The most recent commit (`f9ee21f`) introduced significant changes related to transcription cleanup and has a commit message of "Checkpoint: no idea if this works." This indicates that the current `main` branch is likely unstable.
*   **Error Handling:** The application lacks the "fail-fast" error handling described in the engineering plan. For example, it does not properly validate the configuration file or handle missing Google Cloud credentials at startup.
*   **Interactive UI:** The interactive terminal UI (Phase 4) is not implemented. The application currently exits with a `NotImplementedError` if not run in "auto" mode.
*   **Testing:** The engineering plan mentions that the existing tests need to be fixed. A robust test suite is necessary to ensure the application's stability.
*   **Phase 2 Features:** While some code for Phase 2 (transcription cleanup) has been added, it is not fully integrated and distracts from the primary goal of completing Phase 1.

## Next Steps: A Plan to Complete Phase 1

The following steps are designed to stabilize the project and complete the remaining deliverables for Phase 1.

### 1. Stabilize the Core Application

The immediate priority is to ensure that the core functionality of the application is working reliably.

*   **[ ] Verify "auto" mode:** Run the application in "auto" mode and confirm that it can successfully record audio and produce a transcription.
*   **[ ] Isolate Phase 2 code:** The recently added code for transcription cleanup should be temporarily disabled or moved to a separate feature branch to prevent it from interfering with the Phase 1 deliverables.

### 2. Implement Robust Error Handling

As per the engineering plan, the application must "fail fast" and provide clear error messages.

*   **[ ] Validate configuration at startup:** Add code to `main.py` to validate the `listen2me.yaml` file when the application starts. If the file is invalid or missing required settings, the application should exit with a clear error message.
*   **[ ] Check for Google Cloud credentials:** Before starting the transcription service, verify that the Google Cloud credentials file exists and is valid. If not, the application should exit with an informative error message.
*   **[ ] Improve audio capture error handling:** The `AudioCapture` class should be made more resilient to potential issues with microphone access.

### 3. Refactor and Improve `main.py`

The main application logic needs to be improved to better manage the application's lifecycle.

*   **[ ] Refactor the `Server` class:** The `Server` class in `main.py` should be refactored to better orchestrate the initialization, running, and cleanup of the various services.
*   **[ ] Improve the main loop:** The main application loop should be made more robust, with better handling of application state and user input (once the interactive mode is implemented).

### 4. Fix and Enhance the Test Suite

A working test suite is essential for maintaining code quality and preventing regressions.

*   **[ ] Fix existing tests:** The tests in the `tests` directory need to be updated to work with the current codebase.
*   **[ ] Add tests for new functionality:** New tests should be written to cover the error handling and configuration validation logic.

### 5. Begin Implementation of the Interactive UI (Phase 4)

Once the core application is stable and well-tested, work can begin on the interactive UI.

*   **[ ] Create a basic interactive mode:** Replace the `NotImplementedError` in `main.py` with a basic interactive loop that allows the user to start and stop recording.
*   **[ ] Implement Screen 1a:** As described in the PRD, implement the first screen of the UI, which displays the audio recording status.

By focusing on these steps, we can ensure that Phase 1 of the "Listen 2 Me" project is completed successfully, providing a solid foundation for future development.

## Specific Broken/Incomplete Code

This section details specific parts of the codebase that are currently broken, incomplete, or disconnected from the main application.

### 1. Transcription Cleaning Pipeline is Not Integrated

The functionality for cleaning transcriptions (Phase 2) has been added but is not wired into the main application.

*   **`CleanupAggregator` is unused:** The `main.py` file instantiates `DebugTranscriptionAggregator` which only prints to the console. The `CleanupAggregator`, which is required to batch results for cleaning, is never created or used.
*   **Cleaning services are not instantiated:** There is no code in `main.py` that creates instances of the `ChatGPTCleaningEngine` or `TranscriptionResultCleaner`.
*   **Incorrect Data Flow:** The intended data flow from the engineering plan (`TranscriptionAggregator` -> `TranscriptionCleaningService`) is not implemented. The current flow stops after the `DebugTranscriptionAggregator`.

### 2. UI Code is Orphaned and Non-functional

The code for the user interface is completely disconnected from the application's logic.

*   **`simple_transcription_screen.py` is broken:** This file imports and uses services (`RecordingService`, `SessionManager`) and configuration functions (`get_config`) that do not exist in the current project structure.
*   **Legacy Code:** This UI file appears to be a remnant of a previous design and cannot function without a significant rewrite to integrate with the current service architecture (`AudioCapture`, `TranscriptionService`).

### 3. Full Audio Saving is Not Implemented

There is no mechanism to save the complete audio recording of a session.

*   **`audio_saver.py` is an orphan:** This file contains a `save_to_file` method, but it is not part of a class and is never called. It is effectively dead code.
*   **`AudioCapture` does not save:** The `AudioCapture` service streams audio chunks via its callback but does not accumulate the full recording. To save a session's audio, the main `Server` class would need to be modified to collect all `AudioEvent` data and write it to a file upon completion.

### 4. Data Flow and Message Passing Mismatches

There are logical gaps in how data is passed between components.

*   **Cleaning process is not triggered:** The `main.py` script sets up publishers for `transcription.realtime` and `transcription.batch`, and the `DebugTranscriptionAggregator` subscribes to them. However, the `CleanupAggregator` is never subscribed to these topics, so the cleaning process can never be initiated.
*   **Single Backend Instance:** The `TranscriptionService` creates two consumers (`realtime` and `batch`) that share a single `GoogleSpeechBackend` instance. While this is not strictly an error, it's a point of note that they are not two independent backends, but rather two consumers of the same service with different triggering thresholds.
