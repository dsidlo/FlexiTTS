# FlexiTTS MVP UI - Testing Plan & Feature Checklist

This document serves as the primary UI testing reference for the FlexiTTS MVP. It outlines the subtle UI mechanics implemented, provides a manual testing checklist for immediate validation, and serves as a specification document for the DyTopo coding team to implement automated Playwright E2E tests in the future.

---

## 1. Subtle UI Features Implemented

The MVP contains several underlying UI mechanics designed for stability, data integrity, and user experience:

* **End-to-End Pipeline Initialization**: The app uses `.md` files as the Source of Truth. If the first loaded `.md` chapter lacks a corresponding `.xml` file, an AI pipeline blocking modal appears, retrying up to 3 times to generate the XML structure.
* **Non-Destructive Character Filtering**: Filtering out a character via the Top Bar dropdown shrinks non-matching dialogs into small, italicized placeholders (`...character...`) instead of unmounting them, preserving the storyline's sequential context.
* **Unregistered Character Highlighting**: Characters in the XML that do not exist in `story-config.yml` are visually flagged in bold orange (`#ffb74d`), and `(New)` is appended to their name in the inline-edit dropdown to expose LLM hallucinations.
* **Event Propagation Locks**: Clicking inside `<textarea>` elements or inline attribute inputs explicitly stops event propagation to prevent the parent `<details>` or custom container from accidentally collapsing the Dialog Bar.
* **Absolute State Indexing (`_index`)**: Because XML structures often contain duplicate `id` strings across different `<section>` blocks (e.g., multiple `<dialog dlgseq="1">`), React state mutations are mapped using an absolute `_index` to prevent array collapses or UI reordering bugs.
* **Dynamic Audio State Colors**: Play buttons on Dialog Bars are dynamically colored green if the specific `.wav` file already exists on disk (via IPC checks) and grey if it needs to be generated.
* **Auto-Save on Render**: Clicking "Render Chapter Audio" seamlessly auto-saves the XML to disk first to ensure the Python sub-process reads the exact text currently visible in the UI.
* **Native OS Protection**: Navigating away from a chapter with unsaved changes triggers a native OS confirmation dialog (Save, Discard, Cancel) via Electron's `showMessageBoxSync`, rather than a browser `alert()`.
* **Standardized Disk Formatting**: All UI saves enforce an 80-character word wrap and strict tab (`\t`) indentation to ensure the raw XML remains highly readable in standard text editors.
* **Chapter Markdown Editor**: A dual-pane text editor that allows users to edit the `.md` file directly. Features a "Clean Up (80 chars)" word wrapper tool, and intelligent window resizing (hides UI at <1200px width).
* **Audio-Clip Cleanup**: Rendering a full chapter automatically cleans up orphaned/stale `.wav` clips from the local chapter clip directory to prevent disk bloat.

---

## 2. Manual Testing Checklist

Use this checklist to manually verify the UI functionality. 

### Phase A: Initialization & Generation
- [ ] **Missing XML Edge Case**: Delete `01-Hendrix.xml` (but keep `01-Hendrix.md`). Start the app. Verify that the UI displays a blocking modal/spinner indicating "Generating structure from Markdown", and successfully creates the XML file before loading the UI.
- [ ] **First Chapter Auto-Load**: Verify the app automatically loads the first `.md` chapter found in `story-chapters/` on startup.

### Phase B: Top Bar & Navigation
- [ ] **Chapter Dropdown**: Verify the chapter dropdown displays names cleanly (e.g., `01-Hendrix`) without the `.md` or full file path.
- [ ] **Unsaved Changes Tracker**: Edit any text field. Verify the "Save" button turns orange and displays an asterisk (`Save *`).
- [ ] **Switching Chapters (Unsaved)**: With unsaved changes, attempt to switch chapters using the dropdown. Verify an OS-level warning dialog appears.
- [ ] **Discard Changes**: In the warning dialog, select "Discard" (or Cancel). Verify the changes are reverted or navigation is halted correctly.

### Phase C: Dialog Bars & Editing
- [ ] **Expand/Collapse**: Click the header of a Dialog Bar. Verify it expands to show the text area. Click inside the text area. Verify the bar *does not* collapse.
- [ ] **Text Editing**: Edit the text in a dialog. Verify it correctly updates the internal state (triggering the unsaved warning).
- [ ] **Attribute Editing**: Click on an inline attribute (like `emotion="happy"`). Change the value and press Enter/unfocus. Verify it saves the attribute. Verify the background color is a translucent dark shade, making the white text readable across different colored character headers.
- [ ] **Character Editing**: Click on a character's name. Verify it turns into a `<select>` dropdown populated by `story-config.yml`.
- [ ] **Hallucination Highlighting**: Manually inject a fake character name into the XML (or find one). Verify the name renders in orange text and shows `(New)` in the dropdown.

### Phase D: Filtering & Layout
- [ ] **Character Filter**: Select a specific character from the Top Bar filter dropdown.
- [ ] **Filtered State**: Verify that matching dialogs remain fully visible. Verify that non-matching dialogs shrink to a small, italicized `...CharacterName...` placeholder block with a translucent hashtag ID identifier (`#1.1`).
- [ ] **All Characters Reset**: Select "All Characters" from the dropdown. Verify all placeholders expand back into their full headers.
- [ ] **Maximum Width Check**: Stretch the application window across a large monitor. Verify the Dialog Bars max out at `800px` width and stay horizontally centered to maintain visual readability.

### Phase E: Audio Rendering & State
- [ ] **Audio Button Colors**: Verify that play buttons for existing audio clips are green. Dialogs missing audio should have grey buttons.
- [ ] **Individual Clip Generation**: Click a grey play button. Verify it turns into a loading spinner, generates the clip, turns green, and plays the audio.
- [ ] **Chapter Audio Render (Auto-Save)**: Make an unsaved text edit. Click "Render Chapter Audio". Verify the UI automatically saves the file (Save button turns grey) before the rendering spinner starts.
- [ ] **Render Cancellation**: During a long render, click the "Stop" button. Verify the Python process is killed and the UI state resets properly without crashing.

### Phase F: Data Integrity
- [ ] **XML Validation**: Manually corrupt the XML syntax in the raw file and hit Save in the UI (if possible) or generate invalid XML. Verify the UI pops up an Error Dialog regarding schema validation.
- [ ] **File Formatting**: Save a chapter in the UI. Open the `.xml` file in VS Code. Verify it is indented with tabs and the text is wrapped at 80 characters.

### Phase G: Markdown Editor
- [ ] **Dual Pane UI**: Expand the window width beyond `1200px` and click "Edit Text" in the Top Bar. Verify the Markdown Editor appears on the left, and the Dialogs shift to the right.
- [ ] **Single Pane UI**: Shrink the window width below `1200px` and click "Edit Text". Verify the Text Editor replaces the Dialog UI completely.
- [ ] **Clean Up Formatter**: Type a long string of text on a single line in the editor. Click "Clean Up (80 chars)". Verify the text wraps to 80 characters per line without cutting any words in half.
- [ ] **Markdown Saving**: Make a text edit in the editor pane. Notice the Top Bar "Save" button activates. Switch chapters. Verify the Electron native OS save dialog correctly traps the unsaved `.md` state and writes it to disk.

---

## 3. Automated Testing Spec (For DyTopo Coding Team)

When the DyTopo team shifts to implementing E2E tests (e.g., using **Playwright**), they should use this specification.

### Environment Setup
* Tests must be run against the compiled Electron app using Playwright's `_electron.launch()` API.
* Mock the filesystem for deterministic test states (or strictly manage a `tests/fixtures/` directory containing `.md`, `.xml`, and `.yml` files).

### Core Test Suites to Implement

#### Suite 1: Initialization Pipelines
1. **Test**: `loads_first_chapter_automatically`
   * *Action*: Launch app.
   * *Assert*: The Top Bar dropdown value matches the first alphabetical `.md` file in the fixtures directory.
2. **Test**: `generates_xml_if_missing`
   * *Setup*: Provide an `.md` fixture but delete its `.xml` counterpart.
   * *Action*: Launch app.
   * *Assert*: Expect the `.loading-modal` to be visible with text containing "Generating". Wait for modal to detach. Expect the new `.xml` file to exist on the filesystem.

#### Suite 2: State & Navigation Defenses
1. **Test**: `tracks_unsaved_changes`
   * *Action*: Type into a `<textarea>` inside a Dialog Bar.
   * *Assert*: Top Bar Save button has class/style indicating orange color and text includes `*`.
2. **Test**: `prevents_navigation_with_unsaved_changes`
   * *Action*: Trigger unsaved changes. Attempt to select a different chapter from the `<select>` dropdown.
   * *Assert*: Playwright intercepts the Electron `dialog.showMessageBoxSync`. Mock the response to "Cancel". Expect the active chapter *not* to change.

#### Suite 3: UI Interactions & Rendering
1. **Test**: `non_destructive_character_filtering`
   * *Action*: Select "Hendrix" from the character filter dropdown.
   * *Assert*: Dialog elements belonging to "Narrator" have a `.filtered-out` CSS class applied. They are visible in the DOM but their height/text matches the placeholder parameters.
2. **Test**: `identifies_unregistered_characters`
   * *Setup*: Load an XML fixture containing `<dialog character="Bob">` where Bob is not in the YAML config.
   * *Assert*: The character label for Bob contains the specific orange hex color (`#ffb74d`) and text includes `(New)`.
3. **Test**: `auto_saves_before_chapter_render`
   * *Action*: Type into a text area. Click "Render Chapter Audio".
   * *Assert*: The unsaved changes indicator disappears *before* the render spinner appears. The mocked filesystem receives the updated text.

#### Suite 4: Component Isolation
1. **Test**: `event_propagation_locked_on_inputs`
   * *Action*: Click the header to expand a Dialog Bar. Click inside the nested `<textarea>`.
   * *Assert*: The Dialog Bar remains expanded (class `.expanded` remains true).
2. **Test**: `duplicate_id_state_stability`
   * *Setup*: Load XML with two `<dialog dlgseq="1">` elements in different `<section>` blocks.
   * *Action*: Edit the text of the *second* element.
   * *Assert*: Only the second element's text changes. The arrays do not swap or overwrite the first element. (Validates absolute `_index` usage).
3. **Test**: `markdown_editor_responsive_layout`
   * *Setup*: Launch Playwright browser with a viewport width of `800px`.
   * *Action*: Click the `Edit Text` button.
   * *Assert*: Expect the markdown `<textarea>` to be visible, but expect the `<main>` dialog container to be completely hidden. Resize window to `1200px` and verify both elements become simultaneously visible.