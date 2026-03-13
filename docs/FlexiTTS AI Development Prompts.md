# FlexiTTS AI Development Prompts

## Configuration Refactoring

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

## Render Chapter Callout on Changes...
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

## Additional MVP Features needed.

### Create New Story

### Create New Chapter

### Rename Story

### Rename Chapter


