# FlexiTTS Create Character UI - Implementation Plan

## Overview

This plan outlines the step-by-step implementation of the Character Voice UI features, including scripts, script updates, and function tests.

---

## Phase 1: Data Model & Schema Updates

### 1.1 Update Character Voice Schema

- [ ] **Update `CharacterVoice` model/schema** to support new structure:
  - [ ] Add `emotions` array field for custom voices
  - [ ] Add `qwen3-tts-voice-design` array field for sample-based voices
  - [ ] Update field naming from `custom-voice` to `qwen3-tts-custom-voice`
  - [ ] Add emotion-specific `sox-effects` override support
  - [ ] Add `dialog-effects` field for special processing

- [ ] **Create migration script** for existing character data:
  - [ ] Script: `migrate_characters_to_emotions.py`
  - [ ] Convert existing `custom-voice` entries to new format
  - [ ] Generate default "Neutral" emotion for migrated characters
  - [ ] Backup original data before migration

- [ ] **Update validation schema**:
  - [ ] Add JSON Schema for new character structure
  - [ ] Add emotion name uniqueness validation per character
  - [ ] Add voice-sample file existence validation

---

## Phase 2: Character Management Backend

### 2.1 Character CRUD Operations

- [ ] **Create character**: `POST /api/characters`
  - [ ] Validate unique name per project
  - [ ] Validate language selection
  - [ ] Initialize with empty emotions array
  - [ ] **Test**: Create character with valid data
  - [ ] **Test**: Create character with duplicate name (expect error)
  - [ ] **Test**: Create character with invalid language (expect error)

- [ ] **Read character**: `GET /api/characters/{id}`
  - [ ] Return full character with emotions
  - [ ] **Test**: Retrieve existing character
  - [ ] **Test**: Retrieve non-existent character (expect 404)

- [ ] **List characters**: `GET /api/characters`
  - [ ] Support filtering by language
  - [ ] Support filtering by emotion count
  - [ ] Support sorting (name, date, usage)
  - [ ] **Test**: List all characters
  - [ ] **Test**: Filter by language
  - [ ] **Test**: Sort by different fields

- [ ] **Update character**: `PUT /api/characters/{id}`
  - [ ] Update basic info (name, language, speaker)
  - [ ] Update sox-effects
  - [ ] **Test**: Update character fields
  - [ ] **Test**: Validate sox syntax on update

- [ ] **Delete character**: `DELETE /api/characters/{id}`
  - [ ] Check for dependent dialogs
  - [ ] Cascade delete or warn
  - [ ] **Test**: Delete character with no dependencies
  - [ ] **Test**: Delete character with dialogs (expect confirmation)

### 2.2 Emotion Management

- [ ] **Add emotion**: `POST /api/characters/{id}/emotions`
  - [ ] Validate emotion name uniqueness
  - [ ] Support instruct text
  - [ ] Support optional sox-effects override
  - [ ] **Test**: Add emotion to character
  - [ ] **Test**: Add duplicate emotion name (expect error)

- [ ] **Update emotion**: `PUT /api/characters/{id}/emotions/{emotion_id}`
  - [ ] Update instruct text
  - [ ] Update sox-effects
  - [ ] **Test**: Update emotion fields
  - [ ] **Test**: SoX syntax validation

- [ ] **Delete emotion**: `DELETE /api/characters/{id}/emotions/{emotion_id}`
  - [ ] Prevent deletion of last emotion (optional setting)
  - [ ] **Test**: Delete emotion
  - [ ] **Test**: Delete last emotion (expect warning)

- [ ] **Reorder emotions**: `PUT /api/characters/{id}/emotions/reorder`
  - [ ] Accept ordered list of emotion IDs
  - [ ] **Test**: Reorder emotions

- [ ] **Set default emotion**: `PUT /api/characters/{id}/emotions/{emotion_id}/default`
  - [ ] Unset previous default
  - [ ] Set new default
  - [ ] **Test**: Set default emotion

---

## Phase 3: Voice Sample Management

### 3.1 File Upload

- [ ] **Upload voice sample**: `POST /api/characters/{id}/emotions/{emotion_id}/sample`
  - [ ] Accept `.wav`, `.mp3`, `.ogg` formats
  - [ ] Enforce file size limit (configurable)
  - [ ] Validate audio file integrity
  - [ ] Store in designated sample directory
  - [ ] **Test**: Upload valid WAV file
  - [ ] **Test**: Upload valid MP3 file
  - [ ] **Test**: Upload file exceeding size limit (expect error)
  - [ ] **Test**: Upload invalid/corrupt audio file (expect error)
  - [ ] **Test**: Upload unsupported format (expect error)

### 3.2 File Validation

- [ ] **Audio duration extraction**:
  - [ ] Use `ffprobe` or `mutagen` to get duration
  - [ ] Return duration in API response
  - [ ] **Test**: Verify duration accuracy

- [ ] **Corrupt file detection**:
  - [ ] Attempt to decode audio
  - [ ] Return validation status
  - [ ] **Test**: Detect corrupt WAV file
  - [ ] **Test**: Detect truncated MP3 file

### 3.3 Sample Retrieval

- [ ] **Get sample metadata**: `GET /api/characters/{id}/emotions/{emotion_id}/sample`
  - [ ] Return file path, duration, format, size
  - [ ] **Test**: Retrieve metadata for existing sample

- [ ] **Stream sample audio**: `GET /api/characters/{id}/emotions/{emotion_id}/sample/audio`
  - [ ] Support range requests for large files
  - [ ] Set correct Content-Type
  - [ ] **Test**: Stream audio file
  - [ ] **Test**: Stream with range header

---

## Phase 4: Import/Export Functionality

### 4.1 Export

- [ ] **Export single character**: `GET /api/characters/{id}/export`
  - [ ] Export as YAML format
  - [ ] Export as JSON format (optional)
  - [ ] Include all emotions and samples (as references or embedded)
  - [ ] **Test**: Export to YAML
  - [ ] **Test**: Export to JSON

- [ ] **Export multiple characters**: `GET /api/characters/export`
  - [ ] Accept list of character IDs
  - [ ] Bundle in ZIP with manifest
  - [ ] **Test**: Export multiple characters

### 4.2 Import

- [ ] **Import character**: `POST /api/characters/import`
  - [ ] Parse YAML/JSON format
  - [ ] Validate schema
  - [ ] Handle name conflicts (overwrite/keep both/skip)
  - [ ] Copy referenced voice samples
  - [ ] **Test**: Import valid character file
  - [ ] **Test**: Import with duplicate name (test each conflict resolution)
  - [ ] **Test**: Import with invalid schema (expect error)

---

## Phase 5: SoX Effects Engine

### 5.1 SoX Command Builder

- [ ] **Create SoX command builder service**:
  - [ ] Parse effect strings into structured objects
  - [ ] Build valid SoX command from effects
  - [ ] Handle effect chaining
  - [ ] Support parameter validation
  - [ ] **Test**: Build basic SoX command
  - [ ] **Test**: Build multi-effect pipeline
  - [ ] **Test**: Handle special characters in parameters

### 5.2 SoX Validation

- [ ] **Syntax validation endpoint**: `POST /api/validate/sox`
  - [ ] Validate effect names
  - [ ] Validate parameter types and ranges
  - [ ] Return detailed error messages
  - [ ] **Test**: Validate correct SoX syntax
  - [ ] **Test**: Validate incorrect effect name
  - [ ] **Test**: Validate invalid parameter type

### 5.3 SoX Execution

- [ ] **Process audio with SoX**: `POST /api/process/sox`
  - [ ] Accept audio file and effects
  - [ ] Execute SoX pipeline
  - [ ] Return processed audio
  - [ ] Handle timeouts
  - [ ] **Test**: Apply simple effect
  - [ ] **Test**: Apply complex multi-effect pipeline
  - [ ] **Test**: Handle non-existent effect
  - [ ] **Test**: Handle SoX execution timeout

---

## Phase 6: UI Components

### 6.1 Character Dialog Component

- [ ] **Create `CharacterVoiceDialog` component**:
  - [ ] Toplevel icon button trigger
  - [ ] Position left of Character-Dialog UI
  - [ ] Header with search, settings, add, import buttons
  - [ ] Character count badge
  - [ ] **Test**: Open dialog
  - [ ] **Test**: Close dialog with Escape key

### 6.2 Character Bar Component

- [ ] **Create `CharacterBar` component**:
  - [ ] Expand/collapse on click
  - [ ] Display character name, language, speaker
  - [ ] Play button for preview
  - [ ] Context menu (three-dot menu)
  - [ ] **Test**: Click to expand/collapse
  - [ ] **Test**: Right-click context menu
  - [ ] **Test**: Keyboard navigation (Enter to expand)

### 6.3 Emotion Row Component

- [ ] **Create `EmotionRow` component**:
  - [ ] Display emotion name with icon
  - [ ] Show instruct preview
  - [ ] Inline edit mode
  - [ ] Drag handle for reordering
  - [ ] Default emotion star toggle
  - [ ] **Test**: Click to edit inline
  - [ ] **Test**: Drag to reorder
  - [ ] **Test**: Toggle default emotion

### 6.4 Voice Sample Uploader

- [ ] **Create `VoiceSampleUploader` component**:
  - [ ] Drag-drop zone with visual feedback
  - [ ] File picker fallback
  - [ ] Upload progress indicator
  - [ ] File validation feedback
  - [ ] **Test**: Drag-drop file upload
  - [ ] **Test**: Browse file upload
  - [ ] **Test**: Invalid file rejection
  - [ ] **Test**: Large file handling

### 6.5 SoX Effect Builder

- [ ] **Create `SoXEffectBuilder` component**:
  - [ ] Visual pipeline builder
  - [ ] Draggable effect blocks
  - [ ] Parameter sliders/inputs
  - [ ] Live command preview
  - [ ] Syntax validation highlighting
  - [ ] **Test**: Add effect to pipeline
  - [ ] **Test**: Remove effect from pipeline
  - [ ] **Test**: Reorder effects via drag
  - [ ] **Test**: Invalid syntax highlighting

### 6.6 Audio Preview Player

- [ ] **Create `AudioPreviewPlayer` component**:
  - [ ] Play/Pause toggle
  - [ ] Stop button
  - [ ] Volume slider
  - [ ] Waveform visualization
  - [ ] Playback position indicator
  - [ ] **Test**: Play audio
  - [ ] **Test**: Pause and resume
  - [ ] **Test**: Volume adjustment
  - [ ] **Test**: Waveform display

---

## Phase 6b: Reference Fields (Key-Consistency Editing)

Every key value in `story-config.yml` that requires data consistency (see "Appendix:
story-config.yml key consistency rules" in `docs/FlexiTTS_features_worth_borrowing.md`) is
edited with a common pattern: **combo box + deferred stub**. The user may either pick an
existing value from a list of available choices, or type a new free-form value. A new value
that does not yet satisfy its reference is highlighted in red until the reference is satisfied,
and entering it generates a stub for the reference that is rendered in the UI.

### 6b.1 Reference-Aware Field Component

- [ ] **Create `ReferenceField` component** (combo box with free-text entry):
  - [ ] Dropdown list of existing choices (available values), with search/type-ahead filter
  - [ ] Free-text entry allowed; typed value that matches nothing is flagged **unsatisfied**
  - [ ] Unsatisfied value rendered with red highlight (border + text), tooltip names the
        unmet reference (e.g. "no dialog-effects entry named 'cave2'")
  - [ ] Highlight clears (to normal) the moment the reference is satisfied
  - [ ] Keyboard: arrow keys navigate choices, Enter selects or commits typed value,
        Escape cancels edit
  - [ ] **Test**: Pick existing value from list (satisfied, no red)
  - [ ] **Test**: Type new unsatisfied value (red highlight appears)
  - [ ] **Test**: Satisfy the reference (red clears without re-editing the field)
  - [ ] **Test**: Escape restores previous value
- [ ] **Instances of `ReferenceField`** in the Characters UI:
  - [ ] `custom-voice.speaker` — choices = the nine documented Qwen3-TTS speakers
  - [ ] `dialog-effects` (per character *and* per `cloned-emotion` emotion) — choices =
        top-level `dialog-effects[].name`; both levels are cross-referenced by
        `validate_config.py` (per-emotion added with the Phase 1 emotion-level rule)
  - [ ] `voice-sample` — choices = files present in `global.voices`; typing a new filename
        creates an unsatisfied reference until the file exists

### 6b.2 Stub Generation for Unsatisfied References

- [ ] **Create `ReferenceStubService`** (backend, config-API):
  - [ ] On commit of an unsatisfied value, auto-generate a **stub** for the referenced entity:
    - [ ] `dialog-effects` stub: new top-level entry `{name: <typed>, sox-effects: [""]}`
          (schema-minimal, valid but inert)
    - [ ] `voice-sample` stub: empty placeholder file registered for the character
    - [ ] `custom-voice.speaker` stub: **not** auto-generated (speaker must be one of nine
          fixed built-ins; typed unknown values stay red and block save) — surfaced as
          explicit "choose from list" error instead
  - [ ] Stub carries `stub: true` metadata so UI and validator can distinguish placeholders
        from authored entries
  - [ ] **Test**: Committing unsatisfied dialog-effect creates top-level stub
  - [ ] **Test**: Stub passes `validate_config.py` (schema-valid)
  - [ ] **Test**: Speaker reference never stubs; red persists with explanatory error
- [ ] **Stub rendering in UI**:
  - [ ] Stubs render in the owning list (e.g. under the story-level dialog-effects section or
        in the character's sample slot) with a distinct "stub" badge
  - [ ] Clicking a stub focuses/opens it for editing; filling it in and removing the badge
        marks the reference satisfied
  - [ ] Deleting a stub returns the referencing field to unsatisfied-red state
  - [ ] **Test**: Stub appears immediately after commit
  - [ ] **Test**: Editing stub clears red on referencing field
  - [ ] **Test**: Deleting stub re-flags referencing field
- [ ] **Persistence rule**: config auto-save (Phase 7.2) may persist stubs; `validate_config.py`
  continues to hard-fail on unsatisfied references at CLI/render time, stubs are a UI-only
  grace state until resolved

### 6b.3 Story-level consistency view

- [ ] **Add "Unresolved references" panel** in `CharacterVoiceDialog` settings:
  - [ ] Lists every red (unsatisfied) reference across all characters with jump-to-field links
  - [ ] Shows count badge on the settings icon when nonzero
  - [ ] Render must be blocked (or warned) while count > 0, matching the render-preflight
        behavior in `chapter_xml_to_audio.py::validate_character_voice_setup`
  - [ ] **Test**: Panel lists unsatisfied reference after typing new value
  - [ ] **Test**: Panel empties after stub is satisfied
  - [ ] **Test**: Count badge updates live

---

## Phase 7: State Management & Persistence

### 7.1 Local State

- [ ] **Character selection state**:
  - [ ] Track selected character ID
  - [ ] Track expanded/collapsed bars
  - [ ] Track selected emotion
  - [ ] **Test**: Persist selection on dialog reopen

- [ ] **Edit state**:
  - [ ] Track dirty state per character
  - [ ] Track pending changes
  - [ ] Track validation errors
  - [ ] **Test**: Dirty state indicator
  - [ ] **Test**: Discard changes

### 7.2 Auto-save

- [ ] **Implement auto-save timer**:
  - [ ] Save every 30 seconds
  - [ ] Debounce rapid changes
  - [ ] Visual confirmation toast
  - [ ] **Test**: Auto-save after changes
  - [ ] **Test**: Toast notification display
  - [ ] **Test**: No auto-save on unchanged data

### 7.3 Undo/Redo

- [ ] **Implement undo/redo stack**:
  - [ ] Track last 50 operations
  - [ ] Keyboard shortcuts (Ctrl+Z, Ctrl+Shift+Z)
  - [ ] History panel in settings
  - [ ] **Test**: Undo single operation
  - [ ] **Test**: Redo after undo
  - [ ] **Test**: Undo boundary (max 50)

---

## Phase 8: Search & Filtering

### 8.1 Search

- [ ] **Implement character search**:
  - [ ] Filter by character name
  - [ ] Debounce input (300ms)
  - [ ] Highlight matches
  - [ ] **Test**: Search by exact name
  - [ ] **Test**: Search by partial name
  - [ ] **Test**: No results state

### 8.2 Filters

- [ ] **Implement filter dropdown**:
  - [ ] Filter by language
  - [ ] Filter by emotion count (e.g., "Has 3+ emotions")
  - [ ] Filter by voice type (custom vs. sample)
  - [ ] **Test**: Filter by language
  - [ ] **Test**: Filter by emotion count
  - [ ] **Test**: Combine multiple filters

### 8.3 Sort

- [ ] **Implement sort dropdown**:
  - [ ] Sort by name (A-Z, Z-A)
  - [ ] Sort by date created
  - [ ] Sort by usage count
  - [ ] **Test**: Each sort option

---

## Phase 9: Context Assignment

### 9.1 Quick Assign

- [ ] **Assign character to dialog**:
  - [ ] Button in Character-Bar header
  - [ ] Keyboard shortcut Ctrl+Shift+A
  - [ ] Select from current selection in Dialog UI
  - [ ] **Test**: Assign to selected dialog line
  - [ ] **Test**: Assign without selection (prompt)

### 9.2 Bulk Assign

- [ ] **Bulk assign characters**:
  - [ ] Multi-select dialog lines
  - [ ] Right-click → Assign Character
  - [ ] Character picker modal
  - [ ] **Test**: Bulk assign to multiple lines
  - [ ] **Test**: Assign different characters to different lines

### 9.3 Character Switching

- [ ] **Quick character swap**:
  - [ ] Dropdown in dialog bar
  - [ ] A/B mode for comparison
  - [ ] **Test**: Switch character on dialog line
  - [ ] **Test**: A/B side-by-side preview

---

## Phase 10: Keyboard Shortcuts & Accessibility

### 10.1 Keyboard Navigation

- [ ] **Implement shortcuts**:
  - [ ] Ctrl+N: Create new character
  - [ ] Delete: Delete selected
  - [ ] Enter: Expand/collapse
  - [ ] Space: Preview audio
  - [ ] Ctrl+S: Save
  - [ ] Ctrl+F: Focus search
  - [ ] Escape: Close/deselect
  - [ ] **Test**: Each keyboard shortcut

### 10.2 Accessibility

- [ ] **ARIA labels**:
  - [ ] All buttons labeled
  - [ ] All inputs labeled
  - [ ] Expandable regions labeled
  - [ ] **Test**: Screen reader announcement

- [ ] **Focus management**:
  - [ ] Logical tab order
  - [ ] Focus trap in modal dialogs
  - [ ] **Test**: Tab through all elements

---

## Phase 11: Error Handling & Recovery

### 11.1 Network Errors

- [ ] **Handle network failures**:
  - [ ] Retry button with exponential backoff
  - [ ] Offline indicator
  - [ ] **Test**: Retry on network failure
  - [ ] **Test**: Offline mode display

### 11.2 Data Recovery

- [ ] **Implement recovery dialog**:
  - [ ] Detect unsaved session on startup
  - [ ] Offer restore or discard
  - [ ] **Test**: Recovery dialog on startup

### 11.3 Conflict Resolution

- [ ] **Import conflict handling**:
  - [ ] Modal with Overwrite / Keep Both / Skip options
  - [ ] **Test**: Each conflict resolution option

---

## Phase 12: Integration Testing

### 12.1 End-to-End Flows

- [ ] **Create new character flow**:
  - [ ] Open dialog → Click Add → Fill form → Save
  - [ ] Verify character appears in list
  - [ ] **Test**: Complete create flow

- [ ] **Add emotions to character flow**:
  - [ ] Expand character → Add emotion → Configure → Save
  - [ ] **Test**: Complete emotion setup flow

- [ ] **Import/export cycle flow**:
  - [ ] Export character → Modify file → Import → Verify
  - [ ] **Test**: Round-trip data integrity

- [ ] **Assign to dialog flow**:
  - [ ] Configure character → Assign to dialog → Playback
  - [ ] **Test**: Character plays correct emotion

---

## Phase 13: Performance & Load Testing

### 13.1 Performance

- [ ] **Test with many characters**:
  - [ ] Load time with 100 characters
  - [ ] Search performance
  - [ ] **Test**: 100 characters load time < 2s

- [ ] **Test with many emotions**:
  - [ ] Expand character with 20 emotions
  - [ ] Scroll performance
  - [ ] **Test**: Smooth scrolling with many items

### 13.2 Load Testing

- [ ] **Concurrent operations**:
  - [ ] Multiple uploads simultaneously
  - [ ] Concurrent edits
  - [ ] **Test**: No race conditions

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
