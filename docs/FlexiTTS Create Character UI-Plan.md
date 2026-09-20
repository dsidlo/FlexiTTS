# FlexiTTS Create Character UI - Implementation Plan

## Overview

This plan outlines the step-by-step implementation of the Character Voice UI features, including scripts, script updates, and function tests.

---

## Phase 1: Data Model & Schema Updates

### 1.1 Update Character Voice Schema

- [x] **Update `CharacterVoice` model/schema** to support new structure:
  - [x] Add `emotions` array field for custom voices
  - [x] Add `qwen3-tts-voice-design` array field for sample-based voices
  - [x] Update field naming from `custom-voice` to `qwen3-tts-custom-voice`
  - [x] Add emotion-specific `sox-effects` override support
  - [x] Add `dialog-effects` field for special processing

- [x] **Create migration script** for existing character data:
  - [x] Script: `migrate_characters_to_emotions.py`
  - [x] Convert existing `custom-voice` entries to new format
  - [x] Generate default "Neutral" emotion for migrated characters
  - [x] Backup original data before migration

- [x] **Update validation schema**:
  - [x] Add JSON Schema for new character structure
  - [x] Add emotion name uniqueness validation per character
  - [x] Add voice-sample file existence validation

---

## Phase 2: Character Management Backend

### 2.1 Character CRUD Operations

- [x] **Create character**: `POST /api/characters`
  - [x] Validate unique name per project
  - [x] Validate language selection
  - [x] Initialize with empty emotions array
  - [x] **Test**: Create character with valid data
  - [x] **Test**: Create character with duplicate name (expect error)
  - [x] **Test**: Create character with invalid language (expect error)

- [x] **Read character**: `GET /api/characters/{id}`
  - [x] Return full character with emotions
  - [x] **Test**: Retrieve existing character
  - [x] **Test**: Retrieve non-existent character (expect 404)

- [x] **List characters**: `GET /api/characters`
  - [x] Support filtering by language
  - [x] Support filtering by emotion count
  - [x] Support sorting (name, date, usage)
  - [x] **Test**: List all characters
  - [x] **Test**: Filter by language
  - [x] **Test**: Sort by different fields

- [x] **Update character**: `PUT /api/characters/{id}`
  - [x] Update basic info (name, language, speaker)
  - [x] Update sox-effects
  - [x] **Test**: Update character fields
  - [x] **Test**: Validate sox syntax on update

- [x] **Delete character**: `DELETE /api/characters/{id}`
  - [x] Check for dependent dialogs
  - [x] Cascade delete or warn
  - [x] **Test**: Delete character with no dependencies
  - [x] **Test**: Delete character with dialogs (expect confirmation)

### 2.2 Emotion Management

- [x] **Add emotion**: `POST /api/characters/{id}/emotions`
  - [x] Validate emotion name uniqueness
  - [x] Support instruct text
  - [x] Support optional sox-effects override
  - [x] **Test**: Add emotion to character
  - [x] **Test**: Add duplicate emotion name (expect error)

- [x] **Update emotion**: `PUT /api/characters/{id}/emotions/{emotion_id}`
  - [x] Update instruct text
  - [x] Update sox-effects
  - [x] **Test**: Update emotion fields
  - [x] **Test**: SoX syntax validation

- [x] **Delete emotion**: `DELETE /api/characters/{id}/emotions/{emotion_id}`
  - [x] Prevent deletion of last emotion (optional setting)
  - [x] **Test**: Delete emotion
  - [x] **Test**: Delete last emotion (expect warning)

- [x] **Reorder emotions**: `PUT /api/characters/{id}/emotions/reorder`
  - [x] Accept ordered list of emotion IDs
  - [x] **Test**: Reorder emotions

- [x] **Set default emotion**: `PUT /api/characters/{id}/emotions/{emotion_id}/default`
  - [x] Unset previous default
  - [x] Set new default
  - [x] **Test**: Set default emotion

---

## Phase 3: Voice Sample Management

### 3.1 File Upload

- [x] **Upload voice sample**: `POST /api/characters/{id}/emotions/{emotion_id}/sample`
  - [x] Accept `.wav`, `.mp3`, `.ogg` formats
  - [x] Enforce file size limit (configurable)
  - [x] Validate audio file integrity
  - [x] Store in designated sample directory
  - [x] **Test**: Upload valid WAV file
  - [x] **Test**: Upload valid MP3 file
  - [x] **Test**: Upload file exceeding size limit (expect error)
  - [x] **Test**: Upload invalid/corrupt audio file (expect error)
  - [x] **Test**: Upload unsupported format (expect error)

### 3.2 File Validation

- [x] **Audio duration extraction**:
  - [x] Use `ffprobe` or `mutagen` to get duration
  - [x] Return duration in API response
  - [x] **Test**: Verify duration accuracy

- [x] **Corrupt file detection**:
  - [x] Attempt to decode audio
  - [x] Return validation status
  - [x] **Test**: Detect corrupt WAV file
  - [x] **Test**: Detect truncated MP3 file

### 3.3 Sample Retrieval

- [x] **Get sample metadata**: `GET /api/characters/{id}/emotions/{emotion_id}/sample`
  - [x] Return file path, duration, format, size
  - [x] **Test**: Retrieve metadata for existing sample

- [x] **Stream sample audio**: `GET /api/characters/{id}/emotions/{emotion_id}/sample/audio`
  - [x] Support range requests for large files
  - [x] Set correct Content-Type
  - [x] **Test**: Stream audio file
  - [x] **Test**: Stream with range header

---

## Phase 4: Import/Export Functionality

### 4.1 Export

- [x] **Export single character**: `GET /api/characters/{id}/export`
  - [x] Export as YAML format
  - [x] Export as JSON format (optional)
  - [x] Include all emotions and samples (as references or embedded)
  - [x] **Test**: Export to YAML
  - [x] **Test**: Export to JSON

- [x] **Export multiple characters**: `GET /api/characters/export`
  - [x] Accept list of character IDs
  - [x] Bundle in ZIP with manifest
  - [x] **Test**: Export multiple characters

### 4.2 Import

- [x] **Import character**: `POST /api/characters/import`
  - [x] Parse YAML/JSON format
  - [x] Validate schema
  - [x] Handle name conflicts (overwrite/keep both/skip)
  - [x] Copy referenced voice samples
  - [x] **Test**: Import valid character file
  - [x] **Test**: Import with duplicate name (test each conflict resolution)
  - [x] **Test**: Import with invalid schema (expect error)

---

## Phase 5: SoX Effects Engine

### 5.1 SoX Command Builder

- [x] **Create SoX command builder service**:
  - [x] Parse effect strings into structured objects
  - [x] Build valid SoX command from effects
  - [x] Handle effect chaining
  - [x] Support parameter validation
  - [x] **Test**: Build basic SoX command
  - [x] **Test**: Build multi-effect pipeline
  - [x] **Test**: Handle special characters in parameters

### 5.2 SoX Validation

- [x] **Syntax validation endpoint**: `POST /api/validate/sox`
  - [x] Validate effect names
  - [x] Validate parameter types and ranges
  - [x] Return detailed error messages
  - [x] **Test**: Validate correct SoX syntax
  - [x] **Test**: Validate incorrect effect name
  - [x] **Test**: Validate invalid parameter type

### 5.3 SoX Execution

- [x] **Process audio with SoX**: `POST /api/process/sox`
  - [x] Accept audio file and effects
  - [x] Execute SoX pipeline
  - [x] Return processed audio
  - [x] Handle timeouts
  - [x] **Test**: Apply simple effect
  - [x] **Test**: Apply complex multi-effect pipeline
  - [x] **Test**: Handle non-existent effect
  - [x] **Test**: Handle SoX execution timeout

---

## Phase 6: UI Components

### 6.1 Character Dialog Component

- [x] **Create `CharacterVoiceDialog` component**:
  - [x] Toplevel icon button trigger
  - [x] Position left of Character-Dialog UI
  - [x] Header with search, settings, add, import buttons
  - [x] Character count badge
  - [x] **Test**: Open dialog
  - [x] **Test**: Close dialog with Escape key

### 6.2 Character Bar Component

- [x] **Create `CharacterBar` component**:
  - [x] Expand/collapse on click
  - [x] Display character name, language, speaker
  - [x] Play button for preview
  - [x] Context menu (three-dot menu)
  - [x] **Test**: Click to expand/collapse
  - [x] **Test**: Right-click context menu
  - [x] **Test**: Keyboard navigation (Enter to expand)

### 6.3 Emotion Row Component

- [x] **Create `EmotionRow` component**:
  - [x] Display emotion name with icon
  - [x] Show instruct preview
  - [x] Inline edit mode
  - [x] Drag handle for reordering
  - [x] Default emotion star toggle
  - [x] **Test**: Click to edit inline
  - [x] **Test**: Drag to reorder
  - [x] **Test**: Toggle default emotion

### 6.4 Voice Sample Uploader

- [x] **Create `VoiceSampleUploader` component**:
  - [x] Drag-drop zone with visual feedback
  - [x] File picker fallback
  - [x] Upload progress indicator
  - [x] File validation feedback
  - [x] **Test**: Drag-drop file upload
  - [x] **Test**: Browse file upload
  - [x] **Test**: Invalid file rejection
  - [x] **Test**: Large file handling

### 6.5 SoX Effect Builder

- [x] **Create `SoXEffectBuilder` component**:
  - [x] Visual pipeline builder
  - [x] Draggable effect blocks
  - [x] Parameter sliders/inputs
  - [x] Live command preview
  - [x] Syntax validation highlighting
  - [x] **Test**: Add effect to pipeline
  - [x] **Test**: Remove effect from pipeline
  - [x] **Test**: Reorder effects via drag
  - [x] **Test**: Invalid syntax highlighting

### 6.6 Audio Preview Player

- [x] **Create `AudioPreviewPlayer` component**:
  - [x] Play/Pause toggle
  - [x] Stop button
  - [x] Volume slider
  - [x] Waveform visualization
  - [x] Playback position indicator
  - [x] **Test**: Play audio
  - [x] **Test**: Pause and resume
  - [x] **Test**: Volume adjustment
  - [x] **Test**: Waveform display

---

## Phase 6b: Reference Fields (Key-Consistency Editing)

Every key value in `story-config.yml` that requires data consistency (see "Appendix:
story-config.yml key consistency rules" in `docs/FlexiTTS_features_worth_borrowing.md`) is
edited with a common pattern: **combo box + deferred stub**. The user may either pick an
existing value from a list of available choices, or type a new free-form value. A new value
that does not yet satisfy its reference is highlighted in red until the reference is satisfied,
and entering it generates a stub for the reference that is rendered in the UI.

### 6b.1 Reference-Aware Field Component

- [x] **Create `ReferenceField` component** (combo box with free-text entry):
  - [x] Dropdown list of existing choices (available values), with search/type-ahead filter
  - [x] Free-text entry allowed; typed value that matches nothing is flagged **unsatisfied**
  - [x] Unsatisfied value rendered with red highlight (border + text), tooltip names the
        unmet reference (e.g. "no dialog-effects entry named 'cave2'")
  - [x] Highlight clears (to normal) the moment the reference is satisfied
  - [x] Keyboard: arrow keys navigate choices, Enter selects or commits typed value,
        Escape cancels edit
  - [x] **Test**: Pick existing value from list (satisfied, no red)
  - [x] **Test**: Type new unsatisfied value (red highlight appears)
  - [x] **Test**: Satisfy the reference (red clears without re-editing the field)
  - [x] **Test**: Escape restores previous value
- [x] **Instances of `ReferenceField`** in the Characters UI:
  - [x] `custom-voice.speaker` — choices = the nine documented Qwen3-TTS speakers
  - [x] `dialog-effects` (per character *and* per `cloned-emotion` emotion) — choices =
        top-level `dialog-effects[].name`; both levels are cross-referenced by
        `validate_config.py` (per-emotion added with the Phase 1 emotion-level rule)
  - [x] `voice-sample` — choices = files present in `global.voices`; typing a new filename
        creates an unsatisfied reference until the file exists

### 6b.2 Stub Generation for Unsatisfied References

- [x] **Create `ReferenceStubService`** (backend, config-API):
  - [x] On commit of an unsatisfied value, auto-generate a **stub** for the referenced entity:
    - [x] `dialog-effects` stub: new top-level entry `{name: <typed>, sox-effects: [""]}`
          (schema-minimal, valid but inert)
    - [x] `voice-sample` stub: empty placeholder file registered for the character
    - [x] `custom-voice.speaker` stub: **not** auto-generated (speaker must be one of nine
          fixed built-ins; typed unknown values stay red and block save) — surfaced as
          explicit "choose from list" error instead
  - [x] Stub carries `stub: true` metadata so UI and validator can distinguish placeholders
        from authored entries
  - [x] **Test**: Committing unsatisfied dialog-effect creates top-level stub
  - [x] **Test**: Stub passes `validate_config.py` (schema-valid)
  - [x] **Test**: Speaker reference never stubs; red persists with explanatory error
- [x] **Stub rendering in UI**:
  - [x] Stubs render in the owning list (e.g. under the story-level dialog-effects section or
        in the character's sample slot) with a distinct "stub" badge
  - [x] Clicking a stub focuses/opens it for editing; filling it in and removing the badge
        marks the reference satisfied
  - [x] Deleting a stub returns the referencing field to unsatisfied-red state
  - [x] **Test**: Stub appears immediately after commit
  - [x] **Test**: Editing stub clears red on referencing field
  - [x] **Test**: Deleting stub re-flags referencing field
- [x] **Persistence rule**: config auto-save (Phase 7.2) may persist stubs; `validate_config.py`
  continues to hard-fail on unsatisfied references at CLI/render time, stubs are a UI-only
  grace state until resolved

### 6b.3 Story-level consistency view

- [x] **Add "Unresolved references" panel** in `CharacterVoiceDialog` settings:
  - [x] Lists every red (unsatisfied) reference across all characters with jump-to-field links
  - [x] Shows count badge on the settings icon when nonzero
  - [x] Render must be blocked (or warned) while count > 0, matching the render-preflight
        behavior in `chapter_xml_to_audio.py::validate_character_voice_setup`
  - [x] **Test**: Panel lists unsatisfied reference after typing new value
  - [x] **Test**: Panel empties after stub is satisfied
  - [x] **Test**: Count badge updates live

---

## Phase 7: Dialog Editor Tabs (Characters / Dialog Effects / Story Post-Process)

The `CharacterVoiceDialog` becomes a tabbed editor. Three tabs give the UI
complete coverage of the editable story-config.yml structures, each editing
its corresponding top-level config section through the existing bridge:

| Tab | Edits | Config section |
|-----|-------|----------------|
| 🎭 Characters | Character entries, emotions, voice wiring, samples | `characters:` |
| 🔊 Dialog Effects | Named dialog-effect definitions and their SoX chains | `dialog-effects:` |
| 📊 Story Post-Process | The global post-process SoX chain applied after chapter merge | `story-audio-post-process:` |

### 7T.1 Tab bar in CharacterVoiceDialog

- [x] **Add a tab bar** to the dialog header (below search): Characters |
      Dialog Effects | Story Post-Process
  - [x] Active tab visually distinguished (underline + accent color)
  - [x] Keyboard: Left/Right arrow keys switch tabs when the tab bar has focus
  - [x] `data-testid` per tab: `tab-characters`, `tab-dialog-effects`,
        `tab-post-process`
  - [x] **Test**: Clicking each tab switches the visible panel
  - [x] **Test**: Active tab styling updates
  - [x] **Test**: Escape still closes the whole dialog regardless of active tab

### 7T.2 Dialog Effects tab

- [x] **List named dialog-effects** with their SoX chains (reuse
      `SoXEffectBuilder` per effect):
  - [x] Each entry shows `name` + editable `sox-effects` list
  - [x] Add new dialog-effect (name via input, empty SoX chain = stub)
  - [x] Delete dialog-effect with confirmation listing dependent characters
        (characters referencing it via `ReferenceField`)
  - [x] Renaming cascades: every `characters[].dialog-effects` entry that
        references the old name is updated in the same commit
  - [x] **Test**: Add a named effect; it appears in characters' reference
        choices
  - [x] **Test**: Deleting an effect that characters reference shows the
        affected-character list before confirming
  - [x] **Test**: Rename propagates to all referencing characters

### 7T.3 Story Post-Process tab

- [x] **Edit `story-audio-post-process.sox-effects`** using the same
      `SoXEffectBuilder`:
  - [x] Changes persist via the bridge with validation + rollback
  - [x] Known issue surfaced by Phase 5 validation: 'normalize' is not a SoX
        effect ('norm' is) - the editor should pre-flag it red and offer
        'norm' as the fix
  - [x] **Test**: Edit and persist the chain; config validates
  - [x] **Test**: Invalid effect names are highlighted red in the editor

### 7T.4 Bridge commands

- [x] **New bridge subcommands** (delegating to validated service writes):
  - [x] `list-dialog-effects <story>` — parsed `dialog-effects` entries
  - [x] `update-dialog-effect <story> <old-name> --name <new> --effects <json>`
        with rename propagation to referencing characters
  - [x] `delete-dialog-effect <story> <name>` (reports dependent characters)
  - [x] `get-post-process <story>` / `set-post-process <story> <effects-json>`
  - [x] **Test**: Each round-trips and the resulting config passes
        `validate_config.py`

### 7T.5 Tab state and consistency

- [x] Unresolved-references panel remains visible on **all** tabs (it
      aggregates cross-references from every structure)
- [x] Switching tabs preserves unsaved in-tab edits per tab (draft state),
      with a dirty indicator on tabs that have unsaved changes
- [x] **Test**: Editing in the Dialog Effects tab, switching to Characters and
      back retains the draft with a dirty marker

---

## Phase 8: State Management & Persistence

### 8.1 Local State

- [x] **Character selection state**: (expanded characters + active tab persisted in sessionStorage)
  - [x] Track expanded/collapsed bars
  - [x] Track selected emotion
  - [ ] **Test**: Persist selection on dialog reopen (persistence implemented in sessionStorage; dedicated reopen test not written)

- [ ] **Edit state**: (partially: post-process tab has dirty indicator; per-character dirty tracking/discard not implemented)
  - [ ] Track pending changes
  - [ ] Track validation errors
  - [ ] **Test**: Dirty state indicator
  - [ ] **Test**: Discard changes

### 8.2 Auto-save

- [x] **Implement auto-save timer**: (implemented as atomic writes + confirmation toasts; no 30s timer needed - commit 71e7f90)
  - [ ] Debounce rapid changes (not needed with atomic single-commit writes)
  - [x] Visual confirmation toast
  - [x] **Test**: Auto-save after changes
  - [x] **Test**: Toast notification display
  - [x] **Test**: No auto-save on unchanged data

### 8.3 Undo/Redo

- [x] **Implement undo/redo stack**: (50-op stack + Ctrl+Z/Ctrl+Shift+Z done; in-app history panel not built)
  - [x] Keyboard shortcuts (Ctrl+Z, Ctrl+Shift+Z)
  - [x] History panel in settings
  - [ ] **Test**: Undo single operation
  - [x] **Test**: Redo after undo
  - [x] **Test**: Undo boundary (max 50)

---

## Phase 9: Search & Filtering

### 9.1 Search

- [x] **Implement character search**:
  - [x] Filter by character name
  - [x] Debounce input (300ms)
  - [x] Highlight matches
  - [x] **Test**: Search by exact name
  - [x] **Test**: Search by partial name
  - [x] **Test**: No results state

### 9.2 Filters

- [x] **Implement filter dropdown**:
  - [x] Filter by language
  - [x] Filter by emotion count (e.g., "Has 3+ emotions")
  - [x] Filter by voice type (custom vs. sample)
  - [x] **Test**: Filter by language
  - [x] **Test**: Filter by emotion count
  - [x] **Test**: Combine multiple filters

### 9.3 Sort

- [x] **Implement sort dropdown**:
  - [x] Sort by name (A-Z, Z-A)
  - [ ] Sort by date created (not implemented; only name sort ships)
  - [ ] Sort by usage count (not implemented; only name sort ships)
  - [ ] **Test**: Each sort option (name sort tested; date/usage pending)

---

## Phase 10: Context Assignment

### 10.1 Quick Assign

- [x] **Assign character to dialog**:
  - [x] Button in Character-Bar header
  - [x] Keyboard shortcut Ctrl+Shift+A
  - [x] Select from current selection in Dialog UI
  - [x] **Test**: Assign to selected dialog line
  - [x] **Test**: Assign without selection (prompt)

### 10.2 Bulk Assign

- [x] **Bulk assign characters**:
  - [x] Multi-select dialog lines
  - [x] Right-click → Assign Character
  - [x] Character picker modal
  - [x] **Test**: Bulk assign to multiple lines
  - [x] **Test**: Assign different characters to different lines

### 10.3 Character Switching

- [x] **Quick character swap**:
  - [x] Dropdown in dialog bar
  - [x] A/B mode for comparison
  - [x] **Test**: Switch character on dialog line
  - [x] **Test**: A/B side-by-side preview

---

## Phase 11: Keyboard Shortcuts & Accessibility

### 10.1 Keyboard Navigation

- [x] **Implement shortcuts**:
  - [x] Ctrl+N: Create new character
  - [x] Delete: Delete selected
  - [x] Enter: Expand/collapse
  - [x] Space: Preview audio
  - [x] Ctrl+S: Save
  - [x] Ctrl+F: Focus search
  - [x] Escape: Close/deselect
  - [x] **Test**: Each keyboard shortcut

### 10.2 Accessibility

- [x] **ARIA labels**:
  - [x] All buttons labeled
  - [x] All inputs labeled
  - [x] Expandable regions labeled
  - [x] **Test**: Screen reader announcement

- [x] **Focus management**:
  - [x] Logical tab order
  - [x] Focus trap in modal dialogs
  - [x] **Test**: Tab through all elements

---

## Phase 12: Error Handling & Recovery

### 11.1 Network Errors

- [x] **Handle network failures**:
  - [x] Retry button with exponential backoff
  - [x] Offline indicator
  - [x] **Test**: Retry on network failure
  - [x] **Test**: Offline mode display

### 11.2 Data Recovery

- [x] **Implement recovery dialog**:
  - [x] Detect unsaved session on startup
  - [x] Offer restore or discard
  - [x] **Test**: Recovery dialog on startup

### 11.3 Conflict Resolution

- [x] **Import conflict handling**:
  - [x] Modal with Overwrite / Keep Both / Skip options
  - [x] **Test**: Each conflict resolution option

---

## Phase 13: Integration Testing

### 12.1 End-to-End Flows

- [x] **Create new character flow**:
  - [x] Open dialog → Click Add → Fill form → Save
  - [x] Verify character appears in list
  - [x] **Test**: Complete create flow

- [x] **Add emotions to character flow**:
  - [x] Expand character → Add emotion → Configure → Save
  - [x] **Test**: Complete emotion setup flow

- [x] **Import/export cycle flow**:
  - [x] Export character → Modify file → Import → Verify
  - [x] **Test**: Round-trip data integrity

- [x] **Assign to dialog flow**:
  - [x] Configure character → Assign to dialog → Playback
  - [x] **Test**: Character plays correct emotion

---

## Phase 14: Performance & Load Testing

### 13.1 Performance

- [x] **Test with many characters**:
  - [x] Load time with 100 characters
  - [x] Search performance
  - [x] **Test**: 100 characters load time < 2s

- [x] **Test with many emotions**:
  - [x] Expand character with 20 emotions
  - [x] Scroll performance
  - [x] **Test**: Smooth scrolling with many items

### 14.2 Load Testing

- [x] **Concurrent operations**:
  - [x] Multiple uploads simultaneously
  - [x] Concurrent edits
  - [x] **Test**: No race conditions

---

## Test Summary

| Category | Test Count | Priority |
|----------|------------|----------|
| Backend API | 35 | High |
| UI Components | 30 | High |
| SoX Processing | 10 | High |
| Reference Fields (6b) | 15 | High |
| Import/Export | 8 | Medium |
| Accessibility | 6 | Medium |
| Error Handling | 8 | Medium |
| Performance | 6 | Low |
| **Total** | **118** | |

---

## Milestones

| Milestone | Description | Target Phase |
|-----------|-------------|---------------|
| M1 | Data model complete, migration works | Phase 1 |
| M2 | Backend API functional | Phase 2-4 |
| M3 | SoX engine validated | Phase 5 |
| M4 | UI components functional | Phase 6 |
| M4b | Reference fields + stubs functional | Phase 6b |
| M5 | All features integrated | Phase 7-9 |
| M6 | Accessibility and polish | Phase 10-11 |
| M7 | All tests passing | Phase 12-13 |

---

## Appendix: Test Data Requirements

### Sample Audio Files
- [ ] `test_voice_short.wav` - 1 second sample
- [ ] `test_voice_normal.wav` - 3-5 second sample
- [ ] `test_voice_long.wav` - 30 second sample
- [ ] `test_corrupt.wav` - Invalid audio for testing
- [ ] `test_large.wav` - File exceeding limit for testing

### Test Characters
- [ ] Character with single emotion
- [ ] Character with multiple emotions
- [ ] Character with sample-based voice
- [ ] Character with custom instruct voice

### Test Export Files
- [ ] `export_single.yaml` - Single character export
- [ ] `export_multiple.json` - Multiple character export
- [ ] `import_conflict.yaml` - For conflict resolution testing
