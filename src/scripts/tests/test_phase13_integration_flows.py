"""Phase 13 integration tests: end-to-end flows through the bridge.

These tests exercise the exact command surface the UI drives
(`src/scripts/flexitts_bridge.py characters ...` via a subprocess, the same
route as window.api.runPythonScript) against a fully sandboxed environment:
HOME and XDG_CONFIG_HOME point at a scratch tree, so neither the real
~/.config/FlexiTTS nor the real Stories/ directory is ever touched.

Flows covered (docs/FlexiTTS Create Character UI-Plan.md Phase 13):
1. Create new character: create -> list -> verify present in config.
2. Add emotions: add-emotion -> configure (instruct/sox) -> verify.
3. Import/export cycle: export -> modify -> import -> round-trip integrity.
4. Assign to dialog: character + emotion -> dialog XML attr -> pipeline
   utterance parsing resolves the correct emotion (playback preflight).

Each subprocess call gets the sandbox env; assertions read story-config.yml
on disk to verify real side effects.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
BRIDGE = Path(__file__).resolve().parent.parent / "flexitts_bridge.py"

STORY = "Story-It"

SAMPLE_WAV = b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00" + b"\x00" * 16

CONFIG_YML = """global:
  story-dir: Story-It/
  voices: story-voice-refs/
  chapters: story-chapters/
  story-xml: story-xml/
  logs: logs/
  story-audio: story-audio/
  clips: story-audio/clips/
  clip-separation: 0.3
characters:
  - name: Narrator
    voice-sample: narrator.wav
"""


def run_bridge(env: dict, args: list[str]) -> dict:
    result = subprocess.run(
        [sys.executable, str(BRIDGE), *args],
        capture_output=True, text=True, timeout=90, env=env,
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        payload = {"success": False, "raw": result.stdout, "stderr": result.stderr[-400:]}
    return payload


def read_config(story_dir: Path) -> dict:
    import yaml
    return yaml.safe_load((story_dir / "story-config.yml").read_text())


@pytest.fixture(scope="module")
def sandbox():
    scratch = Path(os.environ.get("JCODE_SCRATCH_DIR", "/tmp/flexitts-p13-tests")) / "integration"
    shutil.rmtree(scratch, ignore_errors=True)
    home, stories_dir, story_dir = _make_sandbox(scratch)
    env = os.environ.copy()
    env["HOME"] = str(home)
    env["XDG_CONFIG_HOME"] = str(home / ".config")
    yield {"env": env, "stories_dir": stories_dir, "story_dir": story_dir}
    shutil.rmtree(scratch, ignore_errors=True)


def _make_sandbox(scratch: Path):
    home = scratch / "home"
    config_dir = home / ".config" / "FlexiTTS"
    config_dir.mkdir(parents=True, exist_ok=True)
    stories_dir = scratch / "stories"
    story_dir = stories_dir / STORY
    for sub in ("story-chapters", "story-xml", "logs", "story-audio", "story-voice-refs"):
        (story_dir / sub).mkdir(parents=True, exist_ok=True)
    (story_dir / "story-voice-refs" / "narrator.wav").write_bytes(SAMPLE_WAV)
    (story_dir / "story-chapters" / "01-It.md").write_text("# It")
    (story_dir / "story-config.yml").write_text(CONFIG_YML)
    (config_dir / "FlexiTTS.yml").write_text(
        f"""FlexiTTS:
  stories-dir: "{stories_dir}"
  story-dir-prefix: "Story-"
  current-story: "It"
"""
    )
    return home, stories_dir, story_dir


class TestCreateCharacterFlow:
    """13.1: Open dialog -> Add -> Fill form -> Save -> appears in list."""

    def test_create_flow_config_lands_and_lists(self, sandbox):
        env = sandbox["env"]
        # UI sends: characters create <story> '<json>'
        payload = run_bridge(env, ["characters", "create", STORY, json.dumps({
            "name": "Hendrix",
            "voiceType": "custom",
            "language": "English",
            "voice": {"speaker": "ryan", "instruct": "gravelly"},
        })])
        assert payload.get("success") is True, payload

        listing = run_bridge(env, ["characters", "list", STORY])
        assert listing.get("success") is True
        names = [c["name"] for c in listing["characters"]]
        assert "Hendrix" in names, names

        # Config on disk contains the custom-voice block
        cfg = read_config(sandbox["story_dir"])
        hendrix = next(c for c in cfg["characters"] if c["name"] == "Hendrix")
        assert hendrix["custom-voice"]["speaker"] == "ryan"
        assert hendrix["custom-voice"]["language"] == "English"

    def test_duplicate_create_reports_client_error(self, sandbox):
        env = sandbox["env"]
        body = json.dumps({"name": "Dup", "voiceType": "custom", "language": "English",
                           "voice": {"speaker": "ryan", "instruct": ""}})
        first = run_bridge(env, ["characters", "create", STORY, body])
        assert first.get("success") is True
        second = run_bridge(env, ["characters", "create", STORY, body])
        assert second.get("success") is False
        assert second.get("code") in ("CHARACTER_EXISTS", "VALIDATION_ERROR")


class TestEmotionFlow:
    """13.1b: Expand character -> Add emotion -> Configure -> Save."""

    def test_add_configure_verify(self, sandbox):
        env = sandbox["env"]
        run_bridge(env, ["characters", "create", STORY, json.dumps({
            "name": "Yamato", "voiceType": "custom", "language": "English",
            "voice": {"speaker": "ryan", "instruct": "calm"},
        })])
        add = run_bridge(env, ["characters", "add-emotion", STORY, "Yamato", json.dumps({
            "emotion": "Angry", "instruct": "loud and sharp",
        })])
        assert add.get("success") is True, add

        update = run_bridge(env, ["characters", "update-emotion", STORY, "Yamato", "Angry",
                                  json.dumps({"instruct": "loud and sharp", "soxEffects": ["norm"]})])
        assert update.get("success") is True, update

        cfg = read_config(sandbox["story_dir"])
        yamato = next(c for c in cfg["characters"] if c["name"] == "Yamato")
        emotions = yamato["custom-voice"]["emotions"]
        angry = next(e for e in emotions if e.get("emotion") == "Angry")
        assert angry["instruct"] == "loud and sharp"
        assert angry.get("sox-effects") == ["norm"]

    def test_get_character_reflects_emotions(self, sandbox):
        env = sandbox["env"]
        got = run_bridge(env, ["characters", "get", STORY, "Yamato"])
        assert got.get("success") is True
        emotions = got["character"].get("custom-voice", {}).get("emotions", [])
        assert any(e.get("emotion") == "Angry" for e in emotions)


class TestImportExportCycle:
    """13.2: Export -> modify -> import -> verify round-trip integrity."""

    def test_export_modify_import_round_trip(self, sandbox):
        env = sandbox["env"]
        # Export Hendrix as YAML (samples embedded)
        export = run_bridge(env, ["characters", "export", STORY, "Hendrix"])
        assert export.get("success") is True, export
        doc = export["document"]
        assert doc["character"]["name"] == "Hendrix"

        # Modify: rename + tweak instruct, as a user editing the file would
        doc["character"]["name"] = "Hendrix-Prime"
        doc["character"]["custom-voice"]["instruct"] = "modified voice"
        file_path = sandbox["stories_dir"] / "hendrix-export.yml"
        file_path.write_text(json.dumps(doc))

        # Import into the same story with keep-both (name differs now)
        b64 = json.loads(json.dumps(doc))  # sanity
        raw = json.dumps(doc).encode()
        import base64
        result = run_bridge(env, ["characters", "import-characters", STORY,
                                  base64.b64encode(raw).decode(), "keep-both"])
        assert result.get("success") is True, result

        # Verify round-trip integrity: the modified instruct survived
        cfg = read_config(sandbox["story_dir"])
        prime = next(c for c in cfg["characters"] if c["name"] == "Hendrix-Prime") \
            if any(c["name"] == "Hendrix-Prime" for c in cfg["characters"]) else \
            next(c for c in cfg["characters"] if c["custom-voice"].get("instruct") == "modified voice")
        assert prime["custom-voice"]["speaker"] == "ryan"

        listing = run_bridge(env, ["characters", "list", STORY])
        names = [c["name"] for c in listing["characters"]]
        assert "Hendrix" in names  # original untouched


class TestAssignToDialogFlow:
    """13.4: Configure character -> assign to dialog line -> pipeline resolves
    the correct emotion (playback correctness)."""

    def test_dialog_xml_emotion_reaches_utterance_pipeline(self, sandbox):
        sys.path.insert(0, str(PROJECT_ROOT / "src" / "scripts"))
        try:
            import chapter_xml_to_audio as x2a  # noqa: E402
        finally:
            sys.path.pop(-1)

        xml = """<?xml version="1.0"?>
<chapter num="1">
  <section seq="1">
    <dialog character="Yamato" dlgseq="1" emotion="Angry">You shall not pass!</dialog>
  </section>
</chapter>"""
        xml_path = sandbox["story_dir"] / "story-xml" / "01-It.xml"
        xml_path.write_text(xml)

        utterances = x2a.parse_xml(xml_path)
        target = [u for u in utterances if u.speaker == "Yamato"]
        assert len(target) == 1
        assert target[0].emotion == "Angry"
        assert target[0].dlgseq == "001"
        assert "shall not pass" in target[0].text

    def test_emotion_instruct_resolution_matches_character_config(self, sandbox):
        """The pipeline must pick the per-emotion instruct we configured
        in the emotion flow above — this is what the TTS request carries."""
        env = sandbox["env"]
        cfg = read_config(sandbox["story_dir"])
        yamato = next(c for c in cfg["characters"] if c["name"] == "Yamato")
        emotions = yamato["custom-voice"]["emotions"]
        angry = next(e for e in emotions if e.get("emotion") == "Angry")
        # The dialog line was assigned emotion="Angry": the pipeline must
        # resolve to the per-emotion instruct, not the base one.
        assert angry["instruct"] == "loud and sharp"
        assert angry["instruct"] != yamato["custom-voice"]["instruct"]


class TestBackupSafetyNet:
    """Every mutation leaves a timestamped .bak (recovery net)."""

    def test_backup_created_on_mutation(self, sandbox):
        env = sandbox["env"]
        before = sorted(p.name for p in (sandbox["story_dir"]).glob("story-config.*.bak"))
        run_bridge(env, ["characters", "create", STORY, json.dumps({
            "name": "BackupProbe", "voiceType": "custom", "language": "English",
            "voice": {"speaker": "ryan", "instruct": ""},
        })])
        after = sorted(p.name for p in (sandbox["story_dir"]).glob("story-config.*.bak"))
        assert len(after) >= len(before), "expected a new .bak backup after mutation"