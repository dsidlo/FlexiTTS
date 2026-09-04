"""End-to-end render-state test: real chapter_xml_to_audio.main() + stub provider.

This closes the loop the unit tests can't: it drives the actual render pipeline
(provider.generate -> clip write -> inline XML signature update) and then verifies
that after a full render every dialog reads in-sync (green), an edit flags the
dialog stale, and a UI-style selective re-render makes it green again.
"""
import sys
import importlib
import importlib.util
import shutil
import tempfile
from pathlib import Path
from unittest import mock

import numpy as np
import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import chapter_render_state  # noqa: E402
from chapter_render_state import (  # noqa: E402
    get_comprehensive_render_state,
    parse_dialog_states_from_xml,
    update_dialog_timestamp,
)


def _load_real_soundfile():
    """Load the real `soundfile` module from its .py file. The test conftest
    installs a Mock under sys.modules['soundfile'], so a plain `import soundfile`
    (or importlib.import_module) returns the Mock. Loading from the literal file
    path bypasses that so WAVs actually land on disk."""
    candidates = []
    try:
        import numpy as _np  # numpy is always the real module
        candidates.append(Path(_np.__file__).parent / "soundfile.py")
    except Exception:
        pass
    # Search interpreter roots plus any venv on sys.path for site-packages/soundfile.py.
    roots = {Path(sys.base_prefix), Path(sys.prefix), Path(sys.exec_prefix)}
    for entry in sys.path:
        if entry and ".venv" in str(entry):
            roots.add(Path(entry))
    for root in roots:
        candidates += list(root.glob("**/site-packages/soundfile.py"))
    for cand in candidates:
        if cand and cand.exists():
            spec = importlib.util.spec_from_file_location("soundfile_real", cand)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)  # type: ignore[union-attr]
            if callable(getattr(mod, "write", None)) and not isinstance(mod, mock.Mock):
                return mod
    return None


_REAL_SF = _load_real_soundfile()


class StubProvider:
    """Minimal TTS provider: deterministic silent waveform per call."""

    def supports_character(self, char_cfg):  # noqa: ARG002
        return True

    def generate(self, text, speaker, emotion, language, output_path, **kwargs):  # noqa: ARG002
        sr = 24000
        wav = np.zeros(int(sr * 0.05), dtype=np.float32)  # 50ms silence
        return [wav], sr

    def send_alert_sync(self, *a, **k):  # noqa: ARG002
        return False


XML_CONTENT = """<?xml version="1.0" encoding="UTF-8"?>
<chapter name="01-E2E">
  <section seq="1">
    <dialog character="Alice" dlgseq="1" emotion="happy">Hello world.</dialog>
    <dialog character="Alice" dlgseq="2" emotion="sad">Goodbye world.</dialog>
  </section>
</chapter>
"""


@pytest.fixture
def env(monkeypatch):
    """Full story layout + config, run main() with a stub provider.

    Uses a persistent temp dir (not pytest's tmp_path) because main() runs the
    real pipeline; we must be able to observe the written files after it returns.
    Conftest mocks `soundfile` globally, so we restore the real module here to get
    actual WAV writes under the project venv.
    """
    assert _REAL_SF is not None, "could not load the real soundfile module"
    monkeypatch.setitem(sys.modules, "soundfile", _REAL_SF)

    tmp_root = Path(tempfile.mkdtemp(prefix="flexitts_e2e_"))
    story_dir = tmp_root / "Story-E2E"
    xml_dir = story_dir / "story-xml"
    xml_dir.mkdir(parents=True)
    xml_path = xml_dir / "01-E2E.xml"
    xml_path.write_text(XML_CONTENT, encoding="utf-8")

    config = {
        "global": {
            "story-dir": ".",
            "story-xml": "story-xml",
            "story-audio": "story-audio",
            "clips": "story-audio/clips",
            "voices": "refs",
            "clip-separation": 0,
        },
        "characters": [
            {"name": "Alice", "custom-voice": {"language": "English", "speaker": "Ryan", "instruct": "Speak"}}
        ],
    }
    config_path = story_dir / "story-config.yml"
    config_path.write_text(yaml.safe_dump(config), encoding="utf-8")

    monkeypatch.chdir(story_dir)
    monkeypatch.setattr("tts_factory.TTSProviderFactory.create_provider", lambda self, **k: StubProvider())
    mod = chapter_xml_to_audio()
    monkeypatch.setattr(mod, "validate_and_fix_xml", lambda p: True)

    clips_dir = story_dir / "story-audio" / "clips"
    try:
        yield {"xml_path": xml_path, "clips_dir": clips_dir, "stem": "01-E2E"}
    finally:
        monkeypatch.undo()
        shutil.rmtree(tmp_root, ignore_errors=True)


def chapter_xml_to_audio():
    """Import the render module fresh-ish (it logs on import but is importable)."""
    import importlib
    if "chapter_xml_to_audio" in sys.modules:
        return sys.modules["chapter_xml_to_audio"]
    return importlib.import_module("chapter_xml_to_audio")


def _restore_real_soundfile(mod):
    """Conftest mocked the `soundfile` module at import time (so main() bound the
    Mock at module scope). Point the module at the real soundfile so clip writes
    actually land on disk when running under the project venv."""
    if _REAL_SF is not None:
        mod.sf = _REAL_SF
    return mod


def _run_main(argv_extra):
    mod = _restore_real_soundfile(chapter_xml_to_audio())
    argv = ["chapter_xml_to_audio.py", "story-xml/01-E2E.xml"] + argv_extra
    with mock.patch.object(sys, "argv", argv):
        mod.main()


def _chapter_clips_dir(clips_dir: Path, stem: str) -> Path:
    """The render_state signature write proved the path; resolve it from disk rather
    than assuming a layout, so the test is not brittle to config base resolution."""
    direct = clips_dir / stem
    if direct.exists():
        return direct
    # Fall back to searching beneath the story dir.
    for p in clips_dir.parent.parent.rglob(stem):
        if p.is_dir() and p.parent.name == "clips":
            return p
    return direct


def test_full_render_then_edit_then_selective_green(env):
    xml_path = env["xml_path"]
    clips_dir = env["clips_dir"]
    stem = env["stem"]

    # --- Full chapter render through the real pipeline -----------------------
    _run_main([])

    # The render pipeline signed both dialogs inline in the XML.
    states = parse_dialog_states_from_xml(xml_path)
    assert set(states) == {"001_001", "001_002"}
    assert all(s["stored_hash"] for s in states.values()), states
    assert all(s["stored_hash"] == s["hash"] for s in states.values()), states

    # Clips were really written (soundfile is the real module here, not the
    # conftest mock, so WAVs land on disk under the project venv).
    chap_clips = _chapter_clips_dir(clips_dir, stem)
    clip1 = chap_clips / "chapter_001_001_001_Alice.wav"
    clip2 = chap_clips / "chapter_001_001_002_Alice.wav"
    assert clip1.exists(), list(chap_clips.glob("*"))
    assert clip2.exists()

    base_clips = chap_clips.parent

    # After a full render, everything reads in-sync (green).
    state = get_comprehensive_render_state(xml_path, base_clips, stem, "Story-E2E", refresh_dialog_hashes=True)
    assert state["dialogs"]["needs_render"] == [], state["dialogs"]
    assert sorted(state["dialogs"]["good"]) == ["001_001", "001_002"], state["dialogs"]

    # --- Edit one dialog: it becomes stale, the other stays green -----------
    text = xml_path.read_text(encoding="utf-8")
    xml_path.write_text(text.replace("Hello world.", "Hello there, brave world!", 1), encoding="utf-8")
    after_edit = get_comprehensive_render_state(xml_path, base_clips, stem, "Story-E2E")
    assert "001_001" in after_edit["dialogs"]["needs_render"], after_edit["dialogs"]
    assert "001_001" not in after_edit["dialogs"]["good"]
    assert "001_002" in after_edit["dialogs"]["good"]

    # --- UI-style selective re-render of the edited dialog -> green ---------
    upd = update_dialog_timestamp(xml_path, base_clips, stem, "Story-E2E", "001_001")
    assert "001_001" not in upd["dialogs"]["needs_render"], upd["dialogs"]
    st = parse_dialog_states_from_xml(xml_path)
    assert st["001_001"]["stored_hash"] == st["001_001"]["hash"]


def test_selective_render_via_main_then_green(env):
    """The real UI flow: full render, edit, selective main() render (which must NOT
    touch state), then the UI's update_dialog_timestamp to turn the dialog green."""
    xml_path = env["xml_path"]
    clips_dir = env["clips_dir"]
    stem = env["stem"]

    # Full render baseline -> all green.
    _run_main([])
    chap_clips = _chapter_clips_dir(clips_dir, stem)
    base_clips = chap_clips.parent
    base = get_comprehensive_render_state(xml_path, base_clips, stem, "Story-E2E", refresh_dialog_hashes=True)
    assert base["dialogs"]["needs_render"] == [], base["dialogs"]

    # Edit dialog 001_001 -> stale.
    text = xml_path.read_text(encoding="utf-8")
    xml_path.write_text(text.replace("Hello world.", "Hello there, brave new world!", 1), encoding="utf-8")
    after_edit = get_comprehensive_render_state(xml_path, base_clips, stem, "Story-E2E")
    assert "001_001" in after_edit["dialogs"]["needs_render"], after_edit["dialogs"]

    # Selective render through the real pipeline: generates the new clip but (per
    # design) returns early without touching the render state.
    _run_main(["--section", "1", "--dlgseq", "1", "--tts-service", "ws://stub"])
    clip1 = chap_clips / "chapter_001_001_001_Alice.wav"
    assert clip1.exists()

    # State is unchanged by the selective render until the UI stamps it.
    mid = get_comprehensive_render_state(xml_path, base_clips, stem, "Story-E2E")
    assert "001_001" in mid["dialogs"]["needs_render"], mid["dialogs"]

    # UI stamps the fresh timestamp/hash -> green.
    upd = update_dialog_timestamp(xml_path, base_clips, stem, "Story-E2E", "001_001")
    assert "001_001" not in upd["dialogs"]["needs_render"], upd["dialogs"]
    st = parse_dialog_states_from_xml(xml_path)
    assert st["001_001"]["stored_hash"] == st["001_001"]["hash"]
