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
