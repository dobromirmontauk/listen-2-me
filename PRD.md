# Listen 2 Me: An LLM-powered notetaking & idea organizer app

* Eventually an Android app
* Hands-free mode is primary. Typing mode is secondary.
* Voice controlled & activated. Voice interface is primary.
* Should work in noisy environments, e.g. driving with AC on, walking around with a dog, etc.
* Should be in a "continuous listening" mode. Once activated, it should be resilient to pauses as I think. It should ideally be resilient to other noise, including other people speaking. 
* The workflow of the app should be:
    * When started, it goes straight to note capturing mode. The entire conversation is always recorded, RAW, so it can be replayed later if needed.
    * As capture happens, real-time transcription is occurring. 
    * The transcription will be creating a "real-time summary" of key concepts in the note. These should be short descriptions that can fit on a phone screen single line. Every time a new "key concept" is generated, it gets added to the list. This can happen every 10-30s or so.
    * The transcription should be annotated with what "key concepts" are touched upon in that part of the conversation. Later, when the transcription is saved, it should be saved with these annotations. This will be a key part of our data structured.
    * As more capture happens, the "key concepts" previously generated and full conversation is included. *Key concepts* should be reused whenever possible. If a new key concept is applied, it should have a timestamp of when it shows up.
* It should have special voice commands that trigger certain actions. For example:
    * Start a new note. 
    * Stop capturing entirely; go into organization mode (which will not be defined yet)
    * Open previous note


Instructions:
* Crawl/walk/run. Let's break this PRD down into small, incremental steps we can implement. Each step should have a name or version numer.
* Start with just the backend system. Should turn on voice recording, show real-time transcription, show generated "key concepts" as they show up on the sidde.
* Generate the user flows, from a user perspective
* Define the data structures that will be saved
* Research what voice transcription services can be used. Propose 2-3 alternatives, with pros/cons of each.