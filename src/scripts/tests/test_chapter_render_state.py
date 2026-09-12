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


def test_stamped_hash_match_is_green_despite_clip_mtime_race(tmp_path):
    """Regression: in-sync dialogs must be green, not blue (timestamp stale).

    Two real-world cases produced false blues:
    1. A selective re-render + re-stitch leaves the clip milliseconds NEWER
       than the chapter audio (clip writes race the final stitch).
    2. Legacy data carries rendered_at older than the clip mtime (signature
       write skipped/failed after an earlier render).

    In both, the content hash matches and the dialog has a stamped signature,
    so the clip is accounted for and the button must be green. Blue is for
    externally modified clips whose content no longer matches the signature.
    """
    story_dir = tmp_path / "Story-Test"
    xml_dir = story_dir / "story-xml"
    clips_dir = story_dir / "story-audio" / "clips"
    xml_dir.mkdir(parents=True)
    xml_path = xml_dir / "01-Test.xml"
    _write(XML_TEMPLATE, xml_path)

    # Render both dialogs, then stamp signatures inline.
    clip1 = clips_dir / "01-Test" / "chapter_001_001_001_Narrator.wav"
    clip2 = clips_dir / "01-Test" / "chapter_001_001_002_Alice.wav"
    _mk_wav(clip1)
    _mk_wav(clip2)
    first = get_comprehensive_render_state(xml_path, clips_dir, "01-Test", "Test")
    assert first["status"] == "good", first["summary"]

    # Re-render only dialog 2's clip; its mtime lands ~15ms after the chapter
    # audio stitch, and its rendered_at in the XML is NOT refreshed (legacy
    # signature write failure). This is the false-blue scenario.
    import os
    _mk_wav(clip2)
    chapter_audio = story_dir / "story-audio" / "01-Test.wav"
    _mk_wav(chapter_audio)
    os.utime(chapter_audio, (1_700_000_000.0, 1_700_000_000.0))
    os.utime(clip2, (1_700_000_000.017, 1_700_000_000.017))  # 17ms newer
    os.utime(clip1, (1_000_000_000.0, 1_000_000_000.0))  # older render

    # Rewind dialog 2's rendered_at below its clip mtime (case 2).
    states = parse_dialog_states_from_xml(xml_path)
    write_render_signatures_to_xml(
        xml_path,
        {"001_002": {"hash": states["001_002"]["hash"], "rendered_at": 1_690_000_000_000}},
    )

    result = get_comprehensive_render_state(xml_path, clips_dir, "01-Test", "Test")
    dialogs = result["dialogs"]
    assert "001_002" not in dialogs["timestamp_stale"], dialogs
    assert "001_002" in dialogs["good"], dialogs
    assert "001_001" in dialogs["good"], dialogs


def test_unstamped_new_clip_is_timestamp_stale(tmp_path):
    """A clip with no signature after initialization remains unaccounted for.

    Blue/stale semantics: when signatures already exist for other dialogs (so
    first-time discovery does not blanket-stamp) and a clip appears newer than
    the chapter render without a stamped signature, the dialog stays stale so
    the user can re-render it.
    """
    story_dir = tmp_path / "Story-Test"
    xml_dir = story_dir / "story-xml"
    clips_dir = story_dir / "story-audio" / "clips"
    xml_dir.mkdir(parents=True)
    xml_path = xml_dir / "01-Test.xml"
    _write(XML_TEMPLATE, xml_path)

    # Only dialog 1 exists/stamped; dialog 2 has no clip and no signature yet.
    _mk_wav(clips_dir / "01-Test" / "chapter_001_001_001_Narrator.wav")
    states = parse_dialog_states_from_xml(xml_path)
    write_render_signatures_to_xml(
        xml_path,
        {"001_001": {"hash": states["001_001"]["hash"], "rendered_at": 1_700_000_000_000}},
    )

    # Later, a clip for dialog 2 appears newer than the chapter audio.
    import os
    clip2 = clips_dir / "01-Test" / "chapter_001_001_002_Alice.wav"
    _mk_wav(clip2)
    os.utime(clip2, (1_700_000_100.0, 1_700_000_100.0))
    chapter_audio = story_dir / "story-audio" / "01-Test.wav"
    _mk_wav(chapter_audio)
    os.utime(chapter_audio, (1_700_000_000.0, 1_700_000_000.0))

    result = get_comprehensive_render_state(xml_path, clips_dir, "01-Test", "Test")
    dialogs = result["dialogs"]
    assert "001_002" in dialogs["needs_render"], dialogs
    assert "001_001" in dialogs["good"], dialogs
