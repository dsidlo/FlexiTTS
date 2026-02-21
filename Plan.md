# FlexiTTS MVP UI Plan

## Analysis
Reviewed PRD/product brief: Core features include doc import (MD upload/parse), XML CRUD (load/edit/reorder dlgseq/emotion/post-effects via tree/grid), char metadata YAML CRUD (forms for voices/summaries/effects), audio gen/preview/export (clips + Reaper .rpp zip). Constraints: Local-first, integrate brownfield CLI (subprocess calls to chapter_to_xml.py, chapter_xml_to_audio.py, validate_config.py). Use lxml for XML, yaml for config, pydub/soundfile for audio, streamlit-aggrid for editable/reorder grids. Test with 01-Hendrix.md/xml/WAVs. Edge cases: Invalid XML (use validate_and_fix_xml), missing clips (--create-missing-clips), silence buffers (0.3s). No cloud deps; GPU for TTS previews.

## High-Level Mapping
- **Backend Logic**: Modular functions in ui.py: load_config() (yaml), parse_xml() (lxml to DataFrame), edit_xml(df) (aggrid → ET write), gen_audio(xml_path) (subprocess chapter_xml_to_audio.py), zip_export(clips_dir, xml, rpp_stub).
- **Streamlit Structure**: Tabs via st.tabs: "1. MD → XML" (upload → subprocess → display), "2. XML Editor" (select file → aggrid reorder/edit → save), "3. Char Config" (load YAML → st.data_editor → validate/save), "4. Audio Gen/Export" (select XML → subprocess → st.audio previews → download zip with .rpp: simple text stub like "TRACK 1 chapter_001.wav").
- **Wireframe (Text-Based)**:
  - Sidebar: Config JSON viewer (st.json), buttons (Re-run All, Validate).
  - Main: Tabs as above.
    - Tab1: File uploader → "Generate XML" button → st.code(xml_tree).
    - Tab2: File selector → aggrid (cols: dlgseq, char, emotion, text, post_effects; sortable/reorder) → "Save XML" button.
    - Tab3: YAML editor (st.data_editor on characters list) → "Validate & Save" (subprocess validate_config.py).
    - Tab4: XML selector → "Generate Audio" → expander with st.audio per clip → "Export Zip" (clips + XML + .rpp).
- **Integration Points**: Subprocess for CLI (capture stdout/stderr for errors). Reactive updates via st.session_state. Global queue: Button chains tabs 1-4.
- **Testing**: End-to-end on 01-Hendrix: MD→XML edit (e.g., reorder dlgseq=1)→audio gen→zip. Unit: Mock subprocess for dry-run.

Next: Implement ui.py prototype (step 2).
