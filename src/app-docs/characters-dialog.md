# Characters Dialog

Open with the **🎭 Characters** button. The dialog has three tabs:
**🎭 Characters**, **🔊 Dialog Effects**, and **📊 Post-Process**.

## Characters tab

Each character is a row: name, language, speaker/sample, and an **⇥ Assign**
button (assigns this character to the selected dialog lines). Expand a row
to edit:

- **Voice**: either a *voice sample* (uploaded WAV/MP3/OGG reference) or a
  *custom voice* (built-in Qwen3-TTS speaker + language + instruct text).
  The uploader's **Browse Files** opens the story's voice-reference
  directory.
- **Emotions**: per-emotion samples or instruct presets. Each emotion can
  override the character's SoX chain.
- **Dialog effects**: chips with ✕ to unlink a shared effect from this
  character.

Toolbar: **↩ Undo / ↪ Redo** (last 50 edits), all edits auto-save to
`story-config.yml` with validation; on failure the change rolls back and a
timestamped backup (`story-config.YYYYMMDD_HHMMSS.bak`) is kept.

Right-click a character row for the menu: 📋 Duplicate, and delete
(blocked while other config still references the character).

## Dialog Effects tab

Story-level SoX effect chains shared by characters (e.g. `cave-echo`).
The builder validates effect names and parameters; invalid entries are
flagged with a one-click fix when possible.

## Post-Process tab

Chains applied to the whole chapter after per-line rendering. This tab uses
an explicit **Save** button instead of auto-save.

## Import / Export

Characters can be exported to YAML/JSON (samples embedded base64) or a ZIP
bundle, and imported with conflict handling: overwrite, keep-both, or skip.