# Listen 2 Me: An LLM-powered notetaking & idea organizer app

## Executive Summary

Listen 2 Me is a hands-free, voice-controlled note-taking application that captures and organizes ideas in real-time. The app uses continuous voice recording with AI-powered transcription to extract key concepts as you speak, making it ideal for capturing thoughts while driving, walking, or in any hands-free scenario. Unlike traditional note-taking apps, Listen 2 Me is designed for noisy environments and maintains context through pauses, creating a seamless thought-capture experience.

**Core Value Proposition:** Transform scattered thoughts into organized, searchable knowledge without interrupting your flow or requiring manual input.

## Platform & Scope

* Target platform: Python terminal app (initial implementation)
* Future platforms: MacOS desktop app, then Android app (long-term goal)
* Hands-free mode is primary. Typing mode is secondary.
* Voice controlled & activated. Voice interface is primary.
* Should work in noisy environments, e.g. driving with AC on, walking around with a dog, etc.
* Should be in a "continuous listening" mode. Once activated, it should be resilient to pauses as I think. It should ideally be resilient to other noise, including other people speaking. 

## Technical Requirements

### Performance Requirements
* Real-time transcription with <2 second latency
* Minimum 15 minutes continuous recording without interruption
* Efficient resource usage for extended recording sessions
* Works offline for basic recording (transcription can be processed later)

### Audio Requirements
* Basic noise filtering for common environments (office, home)
* Voice activity detection to distinguish user speech from background noise
* Support for built-in microphone and external audio devices
* Automatic gain control for consistent audio levels

### Platform Requirements
* Python 3.8+
* Cross-platform compatibility (MacOS, Linux, Windows)
* Basic terminal interface with text-based output
* Microphone access via Python audio libraries (pyaudio, sounddevice)
* Internet connection for AI processing (optional for basic recording)
* File-based data storage (JSON/SQLite)

## Core Workflow
    * When started, it goes straight to note capturing mode. The entire conversation is always recorded, RAW, so it can be replayed later if needed.
    * As capture happens, real-time transcription is occurring. 
    * The transcription will be creating a "real-time summary" of key concepts in the note. These should be short descriptions that can fit on a phone screen single line. Every time a new "key concept" is generated, it gets added to the list. This can happen every 10-30s or so.
    * The transcription should be annotated with what "key concepts" are touched upon in that part of the conversation. Later, when the transcription is saved, it should be saved with these annotations. This will be a key part of our data structured.
    * As more capture happens, the "key concepts" previously generated and full conversation is included. *Key concepts* should be reused whenever possible. If a new key concept is applied, it should have a timestamp of when it shows up.

## Data Structures

### Note Structure
```json
{
  "id": "uuid",
  "timestamp": "2024-01-01T12:00:00Z",
  "title": "Auto-generated or user-provided title",
  "status": "recording|processing|completed",
  "duration_seconds": 1800,
  "raw_audio_path": "/path/to/audio.wav",
  "transcription": [
    {
      "sentence": "This is the first sentence I spoke about project planning.",
      "start_time": 0.0,
      "end_time": 5.2,
      "confidence": 0.95,
      "key_concepts": ["concept_id_1", "concept_id_2"]
    },
    {
      "sentence": "Then I mentioned the budget constraints we're facing.",
      "start_time": 5.2,
      "end_time": 8.7,
      "confidence": 0.89,
      "key_concepts": ["concept_id_3"]
    }
  ],
  "key_concepts": ["concept_id_1", "concept_id_2", "concept_id_3"]
}
```

### Key Concept Structure
```json
{
  "id": "uuid",
  "name": "Short concept name",
  "description": "Brief description fitting on one line",
  "first_mentioned": "2024-01-01T12:05:30Z",
  "last_mentioned": "2024-01-01T12:15:45Z",
  "mention_count": 3,
  "related_concepts": ["concept_id_4", "concept_id_5"],
  "notes": ["note_id_1", "note_id_2"]
}
```

### Implementation Data Structures

**Note:** The JSON structures above are for documentation. In implementation, use more efficient formats:

#### Transcription Matrix (Pandas DataFrame or Array-of-Arrays)
```python
# Column indices
SENTENCE = 0
START_TIME = 1  
END_TIME = 2
CONFIDENCE = 3
KEY_CONCEPTS = 4  # List of concept IDs

# Example as array-of-arrays
transcription_matrix = [
    ["This is the first sentence I spoke about project planning.", 0.0, 5.2, 0.95, ["concept_id_1", "concept_id_2"]],
    ["Then I mentioned the budget constraints we're facing.", 5.2, 8.7, 0.89, ["concept_id_3"]],
    ["We need to consider the timeline as well.", 8.7, 12.1, 0.92, ["concept_id_1", "concept_id_4"]]
]

# Or as Pandas DataFrame
import pandas as pd
transcription_df = pd.DataFrame(transcription_matrix, 
                              columns=['sentence', 'start_time', 'end_time', 'confidence', 'key_concepts'])
```

### Storage Strategy
* **Transcription**: Pandas DataFrame saved as Parquet/Pickle for efficiency
* **Metadata**: JSON files for note metadata and key concept definitions
* **Audio**: WAV files stored separately, referenced by path
* **Index**: SQLite database for fast searching and relationships
* **Backup**: Automatic daily backup of all data files

## User Personas & Use Cases

### Primary Persona: "The Busy Professional"
**Background:** Knowledge worker who generates many ideas throughout the day but struggles to capture them without interrupting their workflow.

**Use Cases:**
- Capturing project ideas during commute
- Recording meeting follow-ups while walking between offices
- Brainstorming solutions while exercising
- Documenting insights during focused work sessions

### Secondary Persona: "The Creative Thinker"
**Background:** Writer, designer, or entrepreneur who needs to capture creative bursts whenever they occur.

**Use Cases:**
- Recording story ideas while doing household chores
- Capturing design inspiration during nature walks
- Documenting business concepts during late-night thinking sessions
- Building upon previous ideas through voice notes

### Key Scenarios:
1. **Hands-free capture:** User is driving and wants to record project thoughts
2. **Noisy environment:** User is in a coffee shop but needs to capture an important idea
3. **Continuation:** User resumes a previous thinking session and builds on past concepts
4. **Review & organize:** User wants to find all notes related to a specific concept

## Voice Commands

### Core Commands
- **"Listen 2 Me, start recording"** - Begin a new note capture session
- **"Listen 2 Me, stop recording"** - End current recording and save note
- **"Listen 2 Me, pause"** - Temporarily pause recording (maintains session)
- **"Listen 2 Me, resume"** - Resume paused recording
- **"Listen 2 Me, new note"** - Start a completely new note (saves current if active)

### Navigation Commands
- **"Listen 2 Me, show concepts"** - Display current key concepts being tracked
- **"Listen 2 Me, open previous note"** - Load and display the last recorded note
- **"Listen 2 Me, find [concept name]"** - Search for notes containing specific concept
- **"Listen 2 Me, organize mode"** - Switch to organization/review mode (future feature)

### Meta Commands
- **"Listen 2 Me, replay last"** - Play back the last 30 seconds of audio
- **"Listen 2 Me, title this [custom title]"** - Set custom title for current note
- **"Listen 2 Me, help"** - Show available commands

### Command Recognition
- Commands must start with "Listen 2 Me" wake phrase
- 2-second timeout after wake phrase to execute command
- If no valid command detected, return to normal recording mode
- Commands work during recording without stopping the session

## Implementation Phases

### Phase 1: "Crawl" - Basic Recording (v0.1)
**Goal:** Prove core concept with minimal viable functionality

**Features:**
- Simple Python script that records audio to WAV file
- Basic real-time transcription using OpenAI Whisper or similar
- Terminal output showing transcription as it happens
- Save transcription to text file when stopped

**Success Criteria:**
- Can record 5+ minutes of continuous audio
- Transcription accuracy >80% in quiet environment
- Terminal shows real-time text output

### Phase 2: "Walk" - Key Concept Extraction (v0.2)
**Goal:** Add AI-powered concept identification

**Features:**
- LLM integration (OpenAI GPT-4 or Claude) for concept extraction
- Display key concepts in terminal as they're identified
- Save concepts with timestamps in matrix format
- Basic concept reuse detection

**Success Criteria:**
- Identifies 3-5 relevant concepts per 10-minute session
- Concepts are human-readable and relevant
- Can reuse concepts from previous sessions

### Phase 3: "Run" - Full Voice Control (v0.3)
**Goal:** Complete hands-free operation

**Features:**
- Voice command recognition and execution
- Session management (start/stop/pause)
- Note organization and retrieval
- Persistent storage with SQLite indexing

**Success Criteria:**
- All core voice commands work reliably
- Can navigate previous notes using voice only
- Data persists across sessions and can be searched


# APPENDIX
Raw notes as I work on this PRD. Do not touch this section.
* We should be saving 3 versions of the text transcription
    * Raw transcription from the service
    * "Cleaned up" transcription, from an LLM call, that puts in proper punctuation/removes filler words/etc.
    * Annotated transcription, with the key concepts extracted.
    * We may want to "re-run" the processing steps of audio -> transcription -> cleanup -> annotated. So we want to save the outputs of each step, with "pointers" to what section of the previous one the "processed" one refers to.
    * We need a good data structure that takes this requirements into account.
* We probably want a "transcribe mode" and a "command mode"
    * If I say "Listen 2 Me", it should say "Waiting for command"
    * Commands can only be issued in "command mode". This is to minimize accidentally going into "Commands" while transcribing. Transcribing should be VERY sticky, because it would be super annoying if the app kept trying to do other things instead of transcribe.
* We should add a Mermaid graph of the UX flows (based on voice commands).
    * What screens let you go to other screens
    * What commands/buttons take you to other screens (maybe labeled edges?)
    * 
* Rough user experience screens that we want. For each of these, we should create a simple visual mockup. For the Markdown PRD, it can be using ASCII art.
    * Screen 1: Transcribing screens
        * 1a: Shows recording stats + a "wave function" showing the audio input, so we have a visual feedback if audio is being picked up. Includes a timer of how much has been captured so far, and a MB file size?
        * 1b: Shows live transcription, as it gets generated from the backend.
        * 1c: Shows cleaned up transcription, which gets batched and processed every ~10s or so.
        * 1d: Shows "annotated" transcription, which has the key concepts attached.
        * 1e: Shows list of raw audio files that were captured, with paths to disk
        * These screens should still work if data is missing; e.g. if we managed to record audio, but not run transcription / cleanup / etc, they should simply say "no data".
        * They should have an option to "rerun step" that reprocesses that step. This will be useful as we change our code and want to see what the latest version does against the previously saved data.
        * Each screen should have a "pause/start" button (also with voice control) and "save" button (also with voice control)
    * Screen 2: current note key concepts screen
        * Word-cloud like approach to key concepts. They should be listed in order of when they showed up on the conversation. We should have a 'weight' float for how much the key concept has showed up in the conversation.
        * Display: key concept (<5 words), timestamp (first occurence), float representing weight
    * Screen 3: all notes screen
        * List of notes, with titles if they were given some. Date/time when the note was taken. Top 3 key concepts of the note. Assign a number to the note so they are easy to refer to verbally like "Open note #3" or "Open yesterday's note"
    * Screen 4: All key concepts screen
        * 4a: List the top 10 key concepts (the ones with the most content). Have them numbered so it is easy to refer to them, e.g. "Open #1"
        * 4b: List key concepts at a particular "level" from the hierarchy. This will make it so we can easily "open" that concept and see what other key concepts (or notes) are below it.
* Key concepts should be a hierarchical, linked set of nodes, like Wikipedia
    * The App should keep track of the taxonomy of key concepts. E.g. "History > World History > World War II > Western Front" or "Engineering > Software > Quality > Factoring > Design Patterns"
    * Each key concept can have one parent, multiple children, and infinite links to other key concepts. Each key concept has a unique ID, separate from it's English definition, to allow for later renaming of the key concept (without losing the links).
    * Parents, children, and links will be able to be changed. 
* To keep things human-readable and a version-history, the primary source of data will be markdown files stored in Git. 
    * Files should link to each other using hyperlinks.
    * Filepaths should be used for parent/children nodes.
    * Our app should read-in all of the files and convert them into internal data representations for faster processing.
    * When saving notes, key concepts, etc it should write back to the Markdown format in the Git repo.
* Review flow.
    * After taking a note, and having the app generate the transcriptions / key concepts, we'll want to save them. This should kick off a new git branch and a Merge Request. That way, if the app is messing up major parts of transcription / annotation / or creating key concepts, they can be caught before they are fully merged back into the "main branch".


# FUTURE WORK
Do not touch this section. Ignore it for everything we are doing right now.
* "Conversation mode" --> I should be able to have a conversation with the LLM about a concept. Save the responses from the LLM (don't re-transcribe them), but don't include any of their ideas / key concepts in the final output. All of the ideas saved should be the note taker. OK if they are repeating the ideas that the LLM had.
