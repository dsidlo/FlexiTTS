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

### App Startup

- An Electron App that contains a "Chapter" window.
  - UI Components are written in typescript.
  - Non-UI actions are written in python.
- The first chapter is loaded from the story-config.yml file, for rendering to the Chapter window.
  - Before the file is loaded, the script src/scripts/chapter_validate_xml.py is run to validate that the XML is valid.
    - If the XML file is invalid, an ERROR dialog modal display to show the error output from the script, and the app will try to load the data as is.

### Top of App
  - "Chapter Name: [<That Chapter's Name>]"
  - "Characters [<Character Count>]"
    - Number of characters in the chapter
  - Drop down of characters in the chapter
  - "Dialogs [<Dialog Count>]"
  - A save button
    - When pressed, save the contents of the chapter elements in the chapter window as XML to the given Chapter file, in the Story-config.story-xml directory.
    - After the file is saved, the script src/scripts/chapter_validate_xml.py is run to validate that the XML is valid.
      - If the XML file is invalid, an ERROR dialog modal display to show the error output from the script 

### Window Body
  - The window body consists of dialog bars
    - Each Dialog bar represents a dialog section of the chapter for a given character.
    - Each Dialog bar contains the content of a dialog section in the chapter for a given character.
    - Dialog bars are consistently colored based on the character's location in the Story-config data structure. But, the dialog bar for the narrator is always grey.
    - Each Dialog bar can expand to show a text area for editing the dialog content.
    - Rich-Click on a Dialog bar shows a drop-down of XML attributes for that dialog section except for the text content and the character name.
    - Left-Click on an attribute value allows the user to edit the value.
    - Right-Click on the Chapter, shows a drop-down of the Chapter .XML files in Story-config.story-xml directory.
  
### Save Functionality
  - When the user presses the save button in the Top Bar, the application converts the current chapter UI state into an XML string.
  - The text within each `<dialog>` and `<narration>` block is word-wrapped at an 80-character boundary with proper tab (`\t`) and double space indentation to ensure it matches standard text editor reading formats.
  - The XML is written to the source `.xml` file using the `window.api.writeFile` IPC command in Electron.
  - It automatically runs `chapter_validate_xml.py` on the newly written file and pops up an error dialog if the resulting file contains invalid XML structure.

### Render and Play a Dialog

  - When the play icon is pressed, the following command is executed "chapter_xml_to_audio.py <chapter-file-name> --section <section-num> --dlgseq <dlgseq-num>" 
    - While generating/playing, the play button transforms into a square "stop" icon that allows the user to kill the background process early.
    - After generation finishes, the file generated (output to stdout: i.e. "Applying character effects to chapter_004_004_001_narrator.wav") is played natively. The full path to the file is resolved in "Story-Entanglement/story-audio/clips/...".

### Render Chapter

  - The Top Bar contains a "Render Chapter" button.
  - When pressed, the UI executes `chapter_xml_to_audio.py <chapter-name> --create-missing-clips` to generate any missing clips for the entire chapter and construct the final chapter `.wav` file.
  - It plays the final `.wav` file automatically once complete.
  - While running, the button changes to a red "Stop" button that can kill the underlying python or audio background processes.


### TODO / Future Optimizations

  - **Persistent Model Backend (DyTopo Manager):** Currently, `chapter_xml_to_audio.py` is executed from scratch via `spawn` on every play button press. This forces Hugging Face Hub to verify the cache and PyTorch to reload the 1.7B parameter Qwen3-TTS model into VRAM every single time, which is slow. We should migrate the audio generation to a persistent backend service (e.g. FastAPI worker managed by DyTopo) that loads the PyTorch models exactly once on boot. The React UI would then send generation requests to this persistent server for near-instantaneous audio generation.