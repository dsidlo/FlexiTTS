# FlexiTTS AI Development Prompts

## [Done] Configuration Refactoring

/dytopo
- story-config.yml is no-longer the main configuration file.
- story-config.yml is specific to a given story and exists with a given Story-* directory.
- FlexiTTS configuration exists in ~/.config/FlexiTTS/FlexiTTS.yaml
- Incorporate the use of FlexiTTS.yaml for configuration management.
- Incorporate the use of FlexiTTS.yaml stories-dir identify where the Story-* directories exist.
- Add a Story drop-down in the Chapter dialog UI.
- Stories in the dropdown are found by scanning the strories-dir for "Story-*" directories.
- The dropdown should display the name of the story directory, less the story-dir-prefix.
- Current Implementations
- Scripts in src/scripts
- App UI in src/ui
- Goal: Implement these features and associated tests. All tests pass with no failures.

/dytopo
- Verify that UI and python script follow and respect the config files ~/.config/FlexiTTS/FlexiTTS.yaml (which indicates where the stories are located) and Story-<story_name>/story-config.yml (which indicates where the soy's resources are located).
- The UI should reference the current-story based on the FlexiTTS.yml config file.

** Note: gpt-5.4 was required to debug and correct the config file refactoring. Kimi-k2.5 was simply incapable of handling the breadth of the changes across UI code and python scripts and various logs for clues to handling the issues resulting from the refactor.


/dytopo
- story-config has some slight changes.
- "story-dir:" removed './' in front of the path, leaving only the directory name of the story directory.
- "voice-sample:" removed the path the file voice reference audio file. The path should be derived using the "voices:" directory property.
Given these changes, update App UI code and python scripts to reflect the config file changes.

(Fixed & Features added)
- When rendering chapter, voice dialoge alerts should be generated as they are passed to tts-service for rendering.
- Perform checks before voice generation.
- Need better error handling for missing reference voice.
- Incorrect speaker for custom voice.
  - (New Features)
    - When Character is assigned to a dialog either through the population of the Character-Dialog UI given the chapter's .xml file, or when chosen or modified via the dialog-bar character dropdown... If the character does not exists, or if something is missing or off in the characters voice configuration, a '!' character appears in front of the character name, which when clicked or hovered on, a dialog indicating the voice configuration issue(s) are described.

## [Done]  Render Chapter Callout on Changes...
 1. Fast checks: keep everything in-memory up front—read .chapter_rendered once, map dialog IDs to their recorded hashes/timestamps, and compare against a lightweight snapshot (e.g., the memoized dialog hashes  
 you already compute when the chapter loads). Avoid re-reading large WAVs unless a mismatch is already detected; hash the XML/dialog text only when the editor flags them dirty. That keeps the “needs rerender?”  
 check to just string comparisons and timestamp lookups.
 2. Selective rendering: when “Render Chapter” executes, walk only the dialogs flagged as stale/missing. Your renderer already supports per-dialog invocation, so drive it with the filtered list. Once a dialog   
 finishes successfully, update its entry in .chapter_rendered immediately (temp file + atomic rename) so repeated button presses skip it.                  
 3. Force re-render on stale clips: if a dialog’s hash differs but a WAV still exists, delete (or move to a .trash folder) that clip before you enqueue the render job. That guarantees the renderer can’t skip it 
 due to leftover files, and your “missing file → render” fast path stays valid.                    
 4. Missing-only rerenders: when a clip is absent but hashes match, just re-render that dialog. No need to touch others, so the overall chapter process remains efficient.                                         
 5. Batch bookkeeping: after the selective pass completes, regenerate the chapter-level summary (XML hash + per-dialog hashes/timestamps) and overwrite .chapter_rendered. That way, the green/yellow state always 
 reflects the latest render, even if only a subset ran.

 With these adjustments, the UI does constant-time checks (hash comparisons), “Render Chapter” only spends time on dialogs that truly need work, and any stale clip is proactively removed so the next render      
 can’t skip it.


 ### [Done] Re-Render Status Issues

 What scripts and exists that update the state of .chapter_rendered.json?
 Based on my analysis, here are the only scripts that update .chapter_rendered.json:
 Scripts That Update .chapter_rendered.json

 ### 1. src/scripts/chapter_render_state.py (The ONLY updater)

 This is the only script that writes to .chapter_rendered.json. It has two functions that call save_render_state():

| Function                             | Line | When Called                | What It Does                                  |
|--------------------------------------|------|----------------------------|-----------------------------------------------|
| check_render_state()                 | 362  | Every time UI checks state | Computes hashes, detects stale, saves state |
| update_render_state_with_new_clips() | 435  | Never called (dead code)   | Would update after render, but not used     |

 ### 2. TypeScript Callers (Trigger the Python script)

 These TypeScript files execute chapter_render_state.py as a subprocess, which then updates .chapter_rendered.json:

| File                                    | Function                  | When Called                       |
|-----------------------------------------|---------------------------|-----------------------------------|
| src/ui/src/services/pythonBridge.ts:616 | checkChapterRenderState() | UI checks if chapter needs render |
| src/ui/electron/main.ts:1195            | IPC handler               | Electron main process handler     |

 ### Entry Point Flow

 ```
  TypeScript: checkChapterRenderState()                                             
       │                                                                                  
       ▼                                                                                  
   Executes: chapter_render_state.py <xml_path> <story_dir> <chapter_stem>            
       │                                                                                  
       ▼                                                                                  
   Python: get_render_state_json()  (line 480)                                        
       │                                                                                  
       ▼                                                                                  
   Python: check_render_state()  (line 322)                                           
       │                                                                                  
       ▼                                                                                  
   Python: save_render_state()  (line 362)  ◄─── WRITES .chapter_rendered.json        
 ```           

## Character UI Design

### Current Character Voice Structure

```yaml
  - name: Narrator-cv
    # This version of the narrator voice uses Qwen3-TTS voice customization.
    # It customizes one of Qwen3-TTS's 9 internal voices using sox post-processing
    # to make it deeper and rougher.
    custom-voice:
      language: English
      speaker: ryan
      instruct: "Deep manly voice. Speech is moderately fast, slightly hushed."
    sox-effects:
      - treble -5 5000 0.7 compand 0.3,1 6:-70,-60,-20 -4 -90 0.1 gain -3
  - name: Hendrix
    custom-voice:
      language: English
      speaker: ryan
      instruct: "Deep manly voice with a rough texture. Speech is calm and calculating, moderately fast."
    sox-effects:
      - overdrive 15 30 gain -8
  - name: Yamato
    custom-voice:
      language: English
      speaker: ryan
      instruct: "An mature man. Speech is gruff and abrupt with a hit of frustration."
    sox-effects:
      - pitch -250 equalizer 1800 +4 1.8 equalizer 3200 +3 2.2 bass +2 120 gain -n -1.5
  - name: Ayana
    voice-sample: Ayana-voice.wav
```

### New Character Voice Structure

For custom voices, the structure is as follows:
Emotions are added to the dialog dropdown.
- The idea is that the available emotions are used to control the voice's emotional tone and style dynamically during dialog playback. And these available as emotions-dropdown are available in the Chapter-Dialog UI Dialog-Bar.

```yaml
  - name: Narrator-cv
    description: "The Narrator's voice."
    qwen3-tts-custom-voice:
      language: English
      speaker: ryan
      instruct: "Deep manly voice. Speech is moderately fast, slightly hushed."
    sox-effects:
      - treble -5 5000 0.7 compand 0.3,1 6:-70,-60,-20 -4 -90 0.1 gain -3
      - description: ""
    emotions:
      - name: Neutral
        description: ""
        instruct: "Calm Focused Deep Voice"
  - name: Hendrix
    description: "Ryan is the male protagonist of the story. He is young handsome, mature, and generally good natured and has a high sense of protection for himself and those he cares for."
    qwen3-tts-custom-voice:
      language: English
      speaker: ryan
      sox-effects:
        - overdrive 15 30 gain -8
      emotions:
        - emotion: Default
          description: ""
          instruct: "Deep manly voice with a rough texture. Speech is calm and calculating, moderately fast."
        - emotion: Excited
          description: ""
          instruct: "Excited and enthusiastic, Fast and energetic speech"
        - emotion: Calm
          description: ""
          instruct: "Calm Focused Deep Voice"
        - emotion: Sad
          description: ""
          instruct: "Lowered slow voice, deeply sad"
          sox-effects:
            # This would override the default sox effects
            - overdrive 15 30 gain -4
        - emotion: Angry
          instruct: "Gritted teeth, aggressive tone"
        - emotion: Happy
          instruct: "Light Happy, Cordial"
    sox-effects:
      - overdrive 15 30 gain -8
      - description: ""
  - name: Ayana
    description: "Ayana is a woman in her late 20's. She is smart and has endured many health issues in her recent past, until symbiosis with AI has given here a new lease on life. She is was very depressed in the past and will be coming to grips with her new found abilities."
    sox-effects:
      - overdrive 15 30 gain -8
    quen3-tts-voice-design:
      - emotion: Normal
        description: ""
        voice-sample: Ayana-voice.wav
      - emotion: Sand
        description: ""
        voice-sample: Ayana-voice-sad.wav
        sox-effects:
          # This is an override of the default sox effects
          - overdrive 15 30 gain -4
      - emotion: Pain
        voice-sample: Ayana-voice-pain.wav
        dialog-effects:
          - cave

```

#### Character Voice UI

- Create a toplevel Icon button that opens the Character-Voice UI Dialog (to the left of the Character-Dialog UI)
- The Character-Voice UI dialog shows the list if Character-Bars

##### Character uses Voice references (qwen3-tts-voice-design)

- When the Character-Bar is clicked, it expands to list the emotions.
- Each emotion is based on a voice sample.
- The emotion bar has the properties...
  - emotion-name (The emotions main value)
  - voice-sample: The wave file to clone (voice reference)
  - sox-effects: The sox effects (post-processing) pipe-line

##### Character uses Custom Voice with Cloned-Voice (quen-tts-voice-design)

- When the Character-Bar is clicked, it expands to list the emotions.
- The Character is associated to 1 of 9 possible quen2-tts built-in voices.
- Each emotion is based on a voice "instruct" prompt.

## TODO...

- Add Create Chapter
- Move Chapter
- Rather than 
- Create Dialog
- Move Dialog
