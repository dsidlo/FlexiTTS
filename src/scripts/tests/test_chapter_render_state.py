"""Unit tests for inline-XML render signature storage in chapter_render_state.

Covers the design change that moves per-dialog render metadata out of
.chapter_rendered.json and into the chapter XML as render_hash/rendered_at attrs.
"""
import sys
import time
import wave
from pathlib import Path
from xml.etree import ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from chapter_render_state import (  # noqa: E402
    compute_dialog_hash,
    get_comprehensive_render_state,
    parse_dialog_states_from_xml,
    update_dialog_timestamp,
    write_render_signatures_to_xml,
)

XML_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<chapter name="01-Test">
  <section seq="1">
    <narration dlgseq="1" emotion="neutral">The night sky bled into neon.</narration>
    <dialog dlgseq="2" character="Alice" emotion="happy">Hello world.</dialog>
  </section>
</chapter>
"""


def _write(xml: str, path: Path) -> None:
    path.write_text(xml, encoding="utf-8")


def _mk_wav(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(24000)
        w.writeframes(b"\x00\x00" * 2400)  # 0.1s of silence


def _edit_dialog_text(xml_path: Path, old: str, new: str) -> None:
    """Simulate a user editing one dialog's text, touching only that element."""
    text = xml_path.read_text(encoding="utf-8")
    assert old in text
    xml_path.write_text(text.replace(old, new, 1), encoding="utf-8")


def test_signature_round_trip_via_xml(tmp_path):
    xml_path = tmp_path / "story-xml" / "01-Test.xml"
    xml_path.parent.mkdir(parents=True)
    _write(XML_TEMPLATE, xml_path)

    states = parse_dialog_states_from_xml(xml_path)
    assert set(states) == {"001_001", "001_002"}
    assert states["001_001"]["stored_hash"] == ""  # not yet stored
    assert states["001_001"]["hash"]  # computed current hash present

    # Persist signatures inline.
    write_render_signatures_to_xml(
        xml_path,
        {
            "001_001": {"hash": states["001_001"]["hash"], "rendered_at": 1700000001000},
            "001_002": {"hash": states["001_002"]["hash"], "rendered_at": 1700000002000},
        },
    )

    reread = parse_dialog_states_from_xml(xml_path)
    assert reread["001_001"]["stored_hash"] == states["001_001"]["hash"]
    assert reread["001_001"]["rendered_at"] == 1700000001000
    assert reread["001_002"]["stored_hash"] == states["001_002"]["hash"]

    # The hash function must not include render bookkeeping (would self-invalidate).
    tree = ET.parse(xml_path)
    node = [n for n in tree.iter() if n.tag == "dialog"][0]
    assert compute_dialog_hash(node) == states["001_002"]["hash"]


def test_stale_then_green_after_render(tmp_path):
    story_dir = tmp_path / "Story-Test"
    xml_dir = story_dir / "story-xml"
    clips_dir = story_dir / "story-audio" / "clips"
    xml_dir.mkdir(parents=True)
    xml_path = xml_dir / "01-Test.xml"
    _write(XML_TEMPLATE, xml_path)

    # Create a clip for each dialog so both exist on disk.
    _mk_wav(clips_dir / "01-Test" / "chapter_001_001_001_Narrator.wav")
    _mk_wav(clips_dir / "01-Test" / "chapter_001_001_002_Alice.wav")

    # First check initializes inline signatures; everything in sync.
    first = get_comprehensive_render_state(xml_path, clips_dir, "01-Test", "Test")
    assert first["metadata"]["xml_hash"]
    assert "001_001" in first["dialog_hashes"]
    assert first["needs_render"] is False, first

    # Edit dialog 001_002 text -> it becomes content-stale (only that tag changes).
    _edit_dialog_text(xml_path, "Hello world.", "Hello there, world!")
    after_edit = get_comprehensive_render_state(xml_path, clips_dir, "01-Test", "Test")
    assert "001_002" in after_edit["dialogs"]["needs_render"]
    assert "001_001" in after_edit["dialogs"]["good"]

    # Re-render dialog 001_002: write a fresh clip and update its timestamp + hash.
    clip = clips_dir / "01-Test" / "chapter_001_001_002_Alice.wav"
    _mk_wav(clip)
    updated = update_dialog_timestamp(xml_path, clips_dir, "01-Test", "Test", "001_002")
    assert "001_002" not in updated["dialogs"]["needs_render"], updated["dialogs"]

    # And the XML now carries the fresh signature for 001_002.
    final_states = parse_dialog_states_from_xml(xml_path)
    assert final_states["001_002"]["hash"] == final_states["001_002"]["stored_hash"]


def test_no_sidecar_written(tmp_path):
    """Storing signatures inline must not (re)create the legacy sidecar file."""
    story_dir = tmp_path / "Story-Test"
    xml_dir = story_dir / "story-xml"
    clips_dir = story_dir / "story-audio" / "clips"
    xml_dir.mkdir(parents=True)
    xml_path = xml_dir / "01-Test.xml"
    _write(XML_TEMPLATE, xml_path)
    _mk_wav(clips_dir / "01-Test" / "chapter_001_001_001_Narrator.wav")

    get_comprehensive_render_state(xml_path, clips_dir, "01-Test", "Test", refresh_dialog_hashes=True)
    assert not (clips_dir / "01-Test" / ".chapter_rendered.json").exists()


def test_chapter_audio_file_drives_chapter_timestamp(tmp_path):
    story_dir = tmp_path / "Story-Test"
    xml_dir = story_dir / "story-xml"
    audio_dir = story_dir / "story-audio"
    clips_dir = audio_dir / "clips"
    xml_dir.mkdir(parents=True)
    xml_path = xml_dir / "01-Test.xml"
    _write(XML_TEMPLATE, xml_path)
    _mk_wav(clips_dir / "01-Test" / "chapter_001_001_001_Narrator.wav")
    _mk_wav(clips_dir / "01-Test" / "chapter_001_001_002_Alice.wav")

    chapter_audio = audio_dir / "01-Test.wav"
    _mk_wav(chapter_audio)

    state = get_comprehensive_render_state(xml_path, clips_dir, "01-Test", "Test")
    expected = int(chapter_audio.stat().st_mtime * 1000)
    assert abs(state["chapter_rendered_at"] - expected) < 5000
