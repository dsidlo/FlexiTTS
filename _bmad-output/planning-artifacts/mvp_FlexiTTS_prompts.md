# File: mvp_FlexiTTS_prompt.md

## FlexiTTS Resources

### Background data

  - _bmad-output/brainstorming/brainstorming-session-2026-02-20.md
  - "_bmad-output/planning-artifacts/*.md" 
  - Python programs in this project are run using "uv run python <script>,,,"

### Chapter XML definition

  - src/scripts/chapter_validate_xml.py

## MVP Definition

  - Read the story-config.yml
    - Before reading the story-config.yml the script src/scripts/validate_config.py is run at the project root directory.
      - If the .yml config file is invalid, an ERROR dialog modal display to show the error output from the script, and the program exist.

    - This file contains all of the configuration for the FlexiTTS application, and the current Story that the App is processing, including the chapter files, character definitions, and other settings.
    - The data should be stored to the Story-Config data-structure variable.
    - Test are written for each type script function where possible.

## Prompts toward a product...

### Done: App Startup

- An Electron App that contains a "Chapter" window.
  - UI Components are written in typescript.
  - Non-UI actions are written in python.
- The first chapter is loaded from the story-config.yml file, for rendering to the Chapter window.
  - Before the file is loaded, the script src/scripts/chapter_validate_xml.py is run to validate that the XML is valid.
    - If the XML file is invalid, an ERROR dialog modal display to show the error output from the script, and the app will try to load the data as is.

### Done: Top of App
  - "Chapter Name: [<That Chapter's Name>]"
  - "Characters [<Character Count>]"
    - Number of characters in the chapter
  - Drop down of characters in the chapter
  - "Dialogs [<Dialog Count>]"
  - A save button
    - When pressed, save the contents of the chapter elements in the chapter window as XML to the given Chapter file, in the Story-config.story-xml directory.
    - After the file is saved, the script src/scripts/chapter_validate_xml.py is run to validate that the XML is valid.
      - If the XML file is invalid, an ERROR dialog modal display to show the error output from the script 

### Done:  Window Body
  - The window body consists of dialog bars
    - Each Dialog bar represents a dialog section of the chapter for a given character.
    - Each Dialog bar contains the content of a dialog section in the chapter for a given character.
    - Dialog bars are consistently colored based on the character's location in the Story-config data structure. But, the dialog bar for the narrator is always grey.
    - Each Dialog bar can expand to show a text area for editing the dialog content.
    - Rich-Click on a Dialog bar shows a drop-down of XML attributes for that dialog section except for the text content and the character name.
    - Left-Click on an attribute value allows the user to edit the value.
    - Right-Click on the Chapter, shows a drop-down of the Chapter .XML files in Story-config.story-xml directory.
  
### Done: Save Functionality
  - When the user presses the save button in the Top Bar, the application converts the current chapter UI state into an XML string.
  - The text within each `<dialog>` and `<narration>` block is word-wrapped at an 80-character boundary with proper tab (`\t`) and double space indentation to ensure it matches standard text editor reading formats.
  - The XML is written to the source `.xml` file using the `window.api.writeFile` IPC command in Electron.
  - It automatically runs `chapter_validate_xml.py` on the newly written file and pops up an error dialog if the resulting file contains invalid XML structure.

### Done: Render and Play a Dialog

  - When the play icon is pressed, the following command is executed "chapter_xml_to_audio.py <chapter-file-name> --section <section-num> --dlgseq <dlgseq-num>" 
    - While generating/playing, the play button transforms into a square "stop" icon that allows the user to kill the background process early.
    - After generation finishes, the file generated (output to stdout: i.e. "Applying character effects to chapter_004_004_001_narrator.wav") is played natively. The full path to the file is resolved in "Story-Entanglement/story-audio/clips/...".

### Done: Render Chapter

  - The Top Bar contains a "Render Chapter" button.
  - When pressed, the UI executes `chapter_xml_to_audio.py <chapter-name> --create-missing-clips` to generate any missing clips for the entire chapter and construct the final chapter `.wav` file.
  - It plays the final `.wav` file automatically once complete.
  - While running, the button changes to a red "Stop" button that can kill the underlying python or audio background processes.


- Delete dialog.
- Add Empty Dialog.

### Done: Some visual ergonomic changes...
- The render dialog is a yellow icon containing a white large dot and should be a green 
  with a large white dot if the audio exists and grey with a large white dot if audio does not exist.
  - I like that the play botton is not rendered if the audio does not exist as well. This is good.
- The Render Chapter button should be green if the audio already exists and grey if not.
  - It should also have a play button next to it if the audio for the chapter exists.

### Done: Some visual ergonomic changes...
- When chapter is being rendered Change "Stop" Button to "Stop Chapter Render" and should have some sort of progress animation that feels like the system is doing something.
Save Check...
- Add a warning that the file has been changed, and if the user want to save or cancel or discard changes.
Thoughts...
- I realized that I made you do the work of creating the cool down. Because with the TTS service, a cool down is not necessary, so we can remove that logic when we add that feature. Sorry about that.
- Otherwise, looking good!

### Done: Bug...
- I was making a small change to chapter 02-Tech.xml, and as soon as I change the dialog the UI
  reacted and placed dialog #2.1 before dialog #1.2 and dialog #1.1 disappeared.
  - Changing #3.2 cause it to re-order to between #1.1 and #1.2.

### Done: Excelent! Excelent! You are doing a great job... 
Change the character of a dialog...
- If the character is clicked on, a drop down presents the list of the characters in the story (from the config file)
  to choose from.

### Done: A case of sensitivity...
- There is a case sensitivity issues with the Narrator, as the Narrator is upper cased in the UI
  but all lower case in the config file. I think that we should keep the case sensitivity and make
  change the narrator in the config file to Narrator.
An interesting conundrum...
- If the the user changes the Character of a dialog and renders it, it renders based on the character in the
  underlying XML because the XML has not changed yet. Then aplay tries to play the have of the new character
  but does not find the wave file, because it was rendered using a different name. thus plays nothing.
  - So if the character is changed, we either have to block the ability to render that dialog's audio
    and prompt the user to save the XML file so that the appropriate voice is rendered and played.
    Or, add a character override to chapter_xml_to_voice.py that allows the character for that
    --section and --dlgseq to be over-ridden.
  - If we choose the last option, we would have to track that the character had changed and
    delete the wav of the orgininal section/dlgseq/character (to ensure that it is not captured to the full
    chapter audio render.
    - But this allows the user to experiment.
    - We would also have to track if the user decides not to save the XML. And if the user had
      experimented with a different voice character, the wav files for those experimental change
      have to be tracked and deleted on discard of the changes.
  - What do you think? Simplicity or ease of use? 
Give me you opinion on this before coding.

### Done: Make sense, and that actually makes this change I've been holding off on worth while...

- Chapter Name should be based on the .md file in the story-chapters directory.
  - Chapter Name should display without an extention.
  - If the .xml file does not already exist, one is created using chapter_to_xml.py and 
    then run through with chapter_seq_xml.py and finally chapter_validate_xml.py to validate it.
    - A modal dialog display (explaining what is happening) while this process is happening.
    - The process repeats and retries 3 times if any part of the process breaks down.
Let me know you thoughts before making changes.

  
### Done: Chapter to XML Bug...
- When running the app myself...
  - I first deleted the 01-Hendrix.xml file then started the app.
    I saw the system attempt to convert the .md file to xml, but then it errored and gave me this message...
    Error initializing app: Error invoking remote method 'show-error-dialog': Error: No handler registered for 'show-error-dialog'
  - Errors in the logs...
[1] [IPC] run-python-script called: src/scripts/chapter_to_xml.py --chapter 01-Hendrix.md
[1] [IPC] run-python-script called: src/scripts/chapter_to_xml.py --chapter 01-Hendrix.md
[1] [Python stderr] usage: chapter_to_xml.py [-h] [--all-chapters] [--llm LLM] [file_path]
[1] chapter_to_xml.py: error: unrecognized arguments: --chapter
[1] 
[1] [Python stderr] usage: chapter_to_xml.py [-h] [--all-chapters] [--llm LLM] [file_path]
[1] chapter_to_xml.py: error: unrecognized arguments: --chapter
[1] 
[1] [Python] Process exited with code 2 signal null
[1] Error occurred in handler for 'run-python-script': Error: usage: chapter_to_xml.py [-h] [--all-chapters] [--llm LLM] [file_path]
[1] chapter_to_xml.py: error: unrecognized arguments: --chapter
[1] 
[1]     at ChildProcess.<anonymous> (/home/dsidlo/workspace/FlexiTTS/src/ui/dist-electron/main.cjs:132:28)
[1]     at ChildProcess.emit (node:events:508:28)
[1]     at maybeClose (node:internal/child_process:1101:16)
[1]     at Socket.<anonymous> (node:internal/child_process:457:11)
[1]     at Socket.emit (node:events:508:28)
[1]     at Pipe.<anonymous> (node:net:346:12)
[1] [Python] Process exited with code 2 signal null
[1] Error occurred in handler for 'run-python-script': Error: usage: chapter_to_xml.py [-h] [--all-chapters] [--llm LLM] [file_path]
[1] chapter_to_xml.py: error: unrecognized arguments: --chapter
[1] 
[1]     at ChildProcess.<anonymous> (/home/dsidlo/workspace/FlexiTTS/src/ui/dist-electron/main.cjs:132:28)
[1]     at ChildProcess.emit (node:events:508:28)
[1]     at maybeClose (node:internal/child_process:1101:16)
[1]     at Socket.<anonymous> (node:internal/child_process:457:11)
[1]     at Socket.emit (node:events:508:28)
[1]     at Pipe.<anonymous> (node:net:346:12)
[1] [IPC] run-python-script called: src/scripts/chapter_to_xml.py --chapter 01-Hendrix.md
[1] [IPC] run-python-script called: src/scripts/chapter_to_xml.py --chapter 01-Hendrix.md
[1] [Python stderr] usage: chapter_to_xml.py [-h] [--all-chapters] [--llm LLM] [file_path]
[1] chapter_to_xml.py: error: unrecognized arguments: --chapter
[1] 
[1] [Python stderr] usage: chapter_to_xml.py [-h] [--all-chapters] [--llm LLM] [file_path]
[1] chapter_to_xml.py: error: unrecognized arguments: --chapter
[1] 
[1] [Python] Process exited with code 2 signal null
[1] Error occurred in handler for 'run-python-script': Error: usage: chapter_to_xml.py [-h] [--all-chapters] [--llm LLM] [file_path]
[1] chapter_to_xml.py: error: unrecognized arguments: --chapter
[1] 
[1]     at ChildProcess.<anonymous> (/home/dsidlo/workspace/FlexiTTS/src/ui/dist-electron/main.cjs:132:28)
[1]     at ChildProcess.emit (node:events:508:28)
[1]     at maybeClose (node:internal/child_process:1101:16)
[1]     at Socket.<anonymous> (node:internal/child_process:457:11)
[1]     at Socket.emit (node:events:508:28)
[1]     at Pipe.<anonymous> (node:net:346:12)
[1] [IPC] run-python-script called: src/scripts/chapter_to_xml.py --chapter 01-Hendrix.md
[1] [Python] Process exited with code 2 signal null
[1] Error occurred in handler for 'run-python-script': Error: usage: chapter_to_xml.py [-h] [--all-chapters] [--llm LLM] [file_path]
[1] chapter_to_xml.py: error: unrecognized arguments: --chapter
[1] 
[1]     at ChildProcess.<anonymous> (/home/dsidlo/workspace/FlexiTTS/src/ui/dist-electron/main.cjs:132:28)
[1]     at ChildProcess.emit (node:events:508:28)
[1]     at maybeClose (node:internal/child_process:1101:16)
[1]     at Socket.<anonymous> (node:internal/child_process:457:11)
[1]     at Socket.emit (node:events:508:28)
[1]     at Pipe.<anonymous> (node:net:346:12)
[1] [IPC] run-python-script called: src/scripts/chapter_to_xml.py --chapter 01-Hendrix.md
[1] [Python stderr] usage: chapter_to_xml.py [-h] [--all-chapters] [--llm LLM] [file_path]
[1] chapter_to_xml.py: error: unrecognized arguments: --chapter
[1] 
[1] [Python stderr] usage: chapter_to_xml.py [-h] [--all-chapters] [--llm LLM] [file_path]
[1] chapter_to_xml.py: error: unrecognized arguments: --chapter
[1] 
[1] [Python] Process exited with code 2 signal null
[1] Error occurred in handler for 'run-python-script': Error: usage: chapter_to_xml.py [-h] [--all-chapters] [--llm LLM] [file_path]
[1] chapter_to_xml.py: error: unrecognized arguments: --chapter
[1] 
[1]     at ChildProcess.<anonymous> (/home/dsidlo/workspace/FlexiTTS/src/ui/dist-electron/main.cjs:132:28)
[1]     at ChildProcess.emit (node:events:508:28)
[1]     at maybeClose (node:internal/child_process:1101:16)
[1]     at Socket.<anonymous> (node:internal/child_process:457:11)
[1]     at Socket.emit (node:events:508:28)
[1]     at Pipe.<anonymous> (node:net:346:12)
[1] Error occurred in handler for 'show-error-dialog': Error: No handler registered for 'show-error-dialog'
[1]     at Session.<anonymous> (node:electron/js2c/browser_init:2:116556)
[1]     at Session.emit (node:events:508:28)
[1] [Python] Process exited with code 2 signal null
[1] Error occurred in handler for 'run-python-script': Error: usage: chapter_to_xml.py [-h] [--all-chapters] [--llm LLM] [file_path]
[1] chapter_to_xml.py: error: unrecognized arguments: --chapter
[1] 
[1]     at ChildProcess.<anonymous> (/home/dsidlo/workspace/FlexiTTS/src/ui/dist-electron/main.cjs:132:28)
[1]     at ChildProcess.emit (node:events:508:28)
[1]     at maybeClose (node:internal/child_process:1101:16)
[1]     at Socket.<anonymous> (node:internal/child_process:457:11)
[1]     at Socket.emit (node:events:508:28)
[1]     at Pipe.<anonymous> (node:net:346:12)
[1] Error occurred in handler for 'show-error-dialog': Error: No handler registered for 'show-error-dialog'
[1]     at Session.<anonymous> (node:electron/js2c/browser_init:2:116556)
[1]     at Session.emit (node:events:508:28)
[1] [304725:0225/080452.567210:ERROR:ui/events/platform/wayland/wayland_event_watcher.cc:47] libwayland: warning: queue 0x3efc0084ce00 destroyed while proxies still attached:
[1] 
[1] [304725:0225/080452.567278:ERROR:ui/events/platform/wayland/wayland_event_watcher.cc:47] libwayland:   zwp_tablet_pad_group_v2#4278190085 still attached
[1] 
[1] [304725:0225/080452.567298:ERROR:ui/events/platform/wayland/wayland_event_watcher.cc:47] libwayland:   zwp_tablet_pad_v2#4278190084 still attached

### Done: Nice! Nice!...
- The .md to xml is working well!
- I like the new Chapter Audio Render spinner, Nice asthetic!
Audio clip cleanup...
- To keep things in the audio clips dirs clean...
  - We when the chapter is rendered...
  - All audio-clips that are not associated to a dialog in the chapter should be deleted
    before the missing clips are rendered and the chapter audio is spliced together.
  - We should use the avaiable Trash folder system for the given host if possible.
    - So the user can find a clip that they really liked but accidently deleted.

### Done: Please continue with...
Please review the code...
- To ensure that the audo-clip cleanup is isolated to the directory for that chapter's audio-clips.
- Also make sure that when creating new audio clips, the dir exist for them to be placed it.
  As I am not sure that the chapter_xml_to_audio.py script already does that.
  If it already handles the mkdir, then need to do that in the app.

### Done: Feature...
- Create a text button that allows the user to read and edit the test of a chapter.
- Pressing the text button Changes the screen from the Test to Audio Chapter UI to a simple
  work processor.
- The Chapter word processor should include a Save button that acts like the save button in the 
  Chapter dialog to Audion UI.
- It should have a cleanup button to re-format the text to 80 chars much like you do with the Chapter dialog UI
  when a document is saved. Keeping things neat for the user.
- Long lines should word wrap without splitting a word.
- If the main window is large enough, both the simple Chapter word processor and the Chapter dialog to audio UI
  can be placed side by side with the Chapter work processor on the right hand side, other wise
  only the Chapter word processor is visible.
  
### Done: UI touches...
- Place the edit text button to the right of the chapter name being viewed.
- Make the text in that button darker, currently very hard to see.
- Please place the Chapter word processor to the on the left side.
- When both dialogs are side by side, allow to combine width of the dialogs to come much closer to the edges of the 
  main window.

### Done: More tweaks...
- Place the edit text button to the left of the chapter name being viewed.
- When a file is being edited, the edit text button disappears, and place the "Close Chapter Text" 
  button to the right of the Save button on the Chapter Word Processor.
  - Make the "Close Chapter Text" button blue. 
  


### Done: Perform a Refactor of the Python Scripts in src/scripty

- Ensure that existing functionality is not lost.
- Refactor calls the calls to TTS and SoX Audio generation (in chapter_xml_to_audio.py)
  so that they can continue to be used as is or with a TTS service if -tts-service option
  is specified with a web-sockets url.
- Create a tts-service that accepts the parameters require tperform TTS 
  operations as they are currently performed by the chapter_xml_to_audio.py script.
- Create tests for function to achieve high test coverage.

### Done: Test Scripts on the command line.

Spawn a background dt-manager and have it apply DyTopo agent coordination on the following task...
- Create tests in src/scripts/tests that run the scripts in src/scripts via subprocess
  to ensure that more of the scrip logic is covered.

Spawn a background dt-manager and have it apply DyTopo agent coordination on the following task:
Ran tests from src/scripts using `pytest tests/ -v --cov=../scripts/ --cov-report=html`...
- 4 tests failed of 124
- The script chapter_seq_xml.py has 0 coverage. (Add more tests)
- chapter_to_xml.py 0 coverage. (Add more tests)
- chapter_validate_xml.py 0 coverage.
- Coverage Report in src/scripts/htmlcov
- Test Report in src/scripts/html-test-report.html

## Done: Create and agent with the /skill:dt-developer to do the following:
- Correction...
- Change script-code, and DyTopo dt-manager and dt-worker agent-scripts, so that the
  - Redis key component Task-<YYYYMMDD>-<hhmmss> is changed to Task-<YYYYMMDD>.
  - Redis key component Task-<YYYYMMDD> is changed to Request-<YYYYMMDD>-<hhmmss>.

## Done: Manual Testing Issue:
Done: Have a the dt-manager use DyTopo the resolve this issue...
- When I try to render a single dialog or a whole chapter, things look like they are working, 
  But no actual audio files are rendered.
- It looks like the TTS service is not running and using the GPU.
- The process to start up the TTS service may not be implemented.
- If the TTS service is not started, and a call to use it does not find the TTS service available,
  the app should make attempts to start it up and then validate that it is running.
- If the TTS service fails to start after a few attempts, the app should log the failure and
  provide a user-friendly message.
- Each time the user attempt to use an audio rendering service, the app should first test
  to ensure that the services is up and running, before running scripts that use it.
- Test should be added to test this feature.

Done: Have a the dt-manager use DyTopo the resolve this issue...
I seems that one test is failing...
- generateAudio
```text
TypeError: PythonBridgeService.showErrorDialog is not a function
    at Object.generateAudio (/home/dsidlo/workspace/FlexiTTS/src/ui/src/hooks/useAudio.ts:169:35)
    at /home/dsidlo/workspace/FlexiTTS/src/ui/src/__tests__/useAudio.test.ts:287:46
    at file:///home/dsidlo/workspace/FlexiTTS/src/ui/node_modules/@vitest/runner/dist/chunk-hooks.js:155:11
    at file:///home/dsidlo/workspace/FlexiTTS/src/ui/node_modules/@vitest/runner/dist/chunk-hooks.js:752:26
    at file:///home/dsidlo/workspace/FlexiTTS/src/ui/node_modules/@vitest/runner/dist/chunk-hooks.js:1897:20
    at new Promise (<anonymous>)
    at runWithTimeout (file:///home/dsidlo/workspace/FlexiTTS/src/ui/node_modules/@vitest/runner/dist/chunk-hooks.js:1863:10)
    at runTest (file:///home/dsidlo/workspace/FlexiTTS/src/ui/node_modules/@vitest/runner/dist/chunk-hooks.js:1574:12)
    at runSuite (file:///home/dsidlo/workspace/FlexiTTS/src/ui/node_modules/@vitest/runner/dist/chunk-hooks.js:1729:8)
    at runSuite (file:///home/dsidlo/workspace/FlexiTTS/src/ui/node_modules/@vitest/runner/dist/chunk-hooks.js:1729:8)
```

Done: As the dt-manager use DyTopo the resolve this issue...
- When I try to render a single dialog or a whole chapter, things look like they are working, 
  But no actual audio files are rendered.
- I am not seeing GPU activity so I don't think that the tts-server.py process is running at all.
- Run ps shows me that the tts service is not runnin, and should have been started when the app started.
- This the error in the logs...
```
[1] ********
[1] Warning: flash-attn is not installed. Will only run the manual PyTorch version. Please install flash-attn for faster inference.
[1] ********
[1]  
[1] Validating Story-Entanglement/story-xml/01-Hendrix.xml...
[1] Success: Story-Entanglement/story-xml/01-Hendrix.xml is valid against the schema.
[1] Processing Story-Entanglement/story-xml/01-Hendrix.xml...
[1] Generating audio for narrator...
[1]   Generating chapter_001_001_001_narrator...
[1]     [Dry-run] Would generate: chapter_001_001_001_narrator
[1] Error applying sox effects: sox FAIL formats: can't open input file `Story-Entanglement/story-audio/clips/01-Hendrix/chapter_001_001_001_narrator.wav': No such file or directory
```
- Additionally, if chapter_xml_to_auto.py is run in --tts mode, the code to load and use any GPU services should not be invoked, including imports of such libaries
  at the import alone may performGPU oriented initialization, (but I might be wrong here).

## Resolve Test Reporting Config Confusions

- I move the pytest configuration to pyproject.toml to reduce confusion and verified that unit-test and coverage reports are generated in src/scripts/test-results.
- Tests are run from src/scripts/tests to test-reports refers to src/scripts/test-reports.
Do these actions set-by-step
- I have verified that pytest unit-tests results are written to src/scripts/test-results/pytests-report.html
- I have verified that pytest coverage results are written to src/scripts/test-results/htmlcov/
- I want the CSS injection script for the unit-tests separated into its own file and placed into src/test-scripts/add-css.py
- add-css.py should read in src/scripts/test-reports/pytests-report.html and output src/scripts/test-results/unit-tests-report.html with the css injected.
- I want run-tests.sh and run-tests-fast.sh to call on add-css.py to update the unit-test report html file.
- I need conftest.py to run add-css.py in the very last hook.
- I need generate-dashboard.py to extract the correct values fro src/scripts/test-results/pytest-report.html

## TODO List...

### UI Stuff...

  - Add a new chapter
  - Create a Story
    - Create Story-<StoryName> Directory
    - Populate Base Story Config and Base Story Folders
    - Import Story
      - Import a document
        - Strip document down to text
        - Separate out chapters and prep them as .md files
        - Drop the stories into the story-chapters directory
  - Add Chapter UI
    - This is a small UI or dialog that will spawn a new chapter in the story.
    - Here we can name the chapter and add a brief summary.
  - We need a way to re-order chapters.

### TODO / Future Optimizations

  - **Persistent Model Backend (DyTopo Manager):** Currently, `chapter_xml_to_audio.py` is executed from scratch via `spawn` on every play button press. This forces Hugging Face Hub to verify the cache and PyTorch to reload the 1.7B parameter Qwen3-TTS model into VRAM every single time, which is slow. We should migrate the audio generation to a persistent backend service (e.g. FastAPI worker managed by DyTopo) that loads the PyTorch models exactly once on boot. The React UI would then send generation requests to this persistent server for near-instantaneous audio generation.

### TODO / Additional UIs

 - A UI for editing the Config file.
   - Config files for every story.
   - The story directory should contain all of the asseets and metadata for a given story.
 - A UI for voice creation.
 - A UI for Character assets
   - Assets by Emotion
   - Assets by Chapter
   - Assets by Location
   - Character Summary and story arc.
 - A UI for Story Assets
 - A Ui for music generation
 - A UI for Background and foreground foley
 - Writer's Block Tool

