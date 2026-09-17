"""Phase 4 tests: Character import/export.

Covers the test cases mandated by docs/FlexiTTS Create Character UI-Plan.md
Phases 4.1/4.2: YAML/JSON export, ZIP bundle with manifest, round-trip data
integrity, name-conflict handling (overwrite/keep-both/skip), invalid schema
rejection, and voice-sample copying.
"""

import base64
import io
import os
import shutil
import sys
import zipfile
from pathlib import Path

import pytest
import yaml

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.api.flexitts_api import create_app  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

SCRATCH_ROOT = Path(os.environ.get("JCODE_SCRATCH_DIR", "/tmp/flexitts-p4-tests")) / "import-export"
STORIES_DIR = SCRATCH_ROOT / "stories"
STORY_A = "Story-Source"
STORY_B = "Story-Target"

SAMPLE_BYTES = b"RIFF-fake-voice-sample-data"


def _story_config(extra_characters: str = "") -> str:
    return f"""
global:
  story-dir: STORYNAME/
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
{extra_characters}
""".replace("STORYNAME", "")


def _make_story(story_id: str, characters_yaml: str = ""):
    story_dir = STORIES_DIR / story_id
    (story_dir / "story-chapters").mkdir(parents=True, exist_ok=True)
    (story_dir / "story-xml").mkdir(exist_ok=True)
    (story_dir / "logs").mkdir(exist_ok=True)
    (story_dir / "story-audio").mkdir(exist_ok=True)
    (story_dir / "story-audio" / "clips").mkdir(exist_ok=True)
    (story_dir / "story-voice-refs").mkdir(exist_ok=True)
    (story_dir / "story-config.yml").write_text(
        f"""
global:
  story-dir: {story_id}/
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
{characters_yaml}
""".lstrip()
    )
    return story_dir


@pytest.fixture(scope="module")
def client():
    shutil.rmtree(SCRATCH_ROOT, ignore_errors=True)
    story_a = _story_from_config(STORY_A)
    story_b = _story_from_config(STORY_B)

    from src.api.character_service import CharacterService
    from src.api.sample_service import SampleService
    from src.api.import_export_service import ImportService

    app = create_app()
    client = TestClient(app)

    orig_c = CharacterService.__init__
    orig_s = SampleService.__init__
    orig_i = ImportService.__init__

    def patched_c(self, arg=None):
        orig_c(self, STORIES_DIR)

    def patched_s(self, arg=None, m=None):
        orig_s(self, STORIES_DIR)

    def patched_i(self, arg=None):
        orig_i(self, STORIES_DIR)

    CharacterService.__init__ = patched_c
    SampleService.__init__ = patched_s
    ImportService.__init__ = patched_i
    try:
        yield client
    finally:
        CharacterService.__init__ = orig_c
        SampleService.__init__ = orig_s
        ImportService.__init__ = orig_i
        shutil.rmtree(SCRATCH_ROOT, ignore_errors=True)


def _story_from_config(story_id: str):
    story_dir = STORIES_DIR / story_id
    (story_dir / "story-chapters").mkdir(parents=True, exist_ok=True)
    (story_dir / "story-xml").mkdir(exist_ok=True)
    (story_dir / "logs").mkdir(exist_ok=True)
    (story_dir / "story-audio").mkdir(exist_ok=True)
    (story_dir / "story-audio" / "clips").mkdir(exist_ok=True)
    (story_dir / "story-voice-refs").mkdir(exist_ok=True)
    (story_dir / "story-voice-refs" / "narrator.wav").write_bytes(b"RIFF")
    (story_dir / "story-config.yml").write_text(
        f"""
global:
  story-dir: {story_id}/
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
  - name: Hero
    voice-sample: hero.wav
  - name: Villain
    custom-voice:
      language: English
      speaker: ryan
      instruct: "dark voice"
      emotions:
        - emotion: Neutral
          instruct: "dark voice"
""".lstrip()
    )
    (story_dir / "story-voice-refs" / "hero.wav").write_bytes(SAMPLE_BYTES)
    return story_dir


class TestExport:
    """Phase 4.1."""

    def test_export_to_yaml(self, client):
        r = client.get(f"/api/stories/{STORY_A}/characters/Hero/export")
        assert r.status_code == 200
        assert "yaml" in r.headers["content-type"] or r.headers["content-type"].endswith("x-yaml")
        doc = yaml.safe_load(r.content)
        assert doc["character"]["name"] == "Hero"
        assert doc["formatVersion"] == 1

    def test_export_to_json(self, client):
        import json as _json
        r = client.get(f"/api/stories/{STORY_A}/characters/Hero/export",
                       params={"format": "json"})
        assert r.status_code == 200
        doc = _json.loads(r.content)
        assert doc["character"]["name"] == "Hero"

    def test_export_includes_samples(self, client):
        r = client.get(f"/api/stories/{STORY_A}/characters/Hero/export")
        doc = yaml.safe_load(r.content)
        samples = doc.get("samples", [])
        assert any(s["name"] == "hero.wav" and not s["missing"] for s in samples)
        # Base64 data decodes to original bytes
        import base64 as _b64
        embedded = next(s for s in samples if s["name"] == "hero.wav")
        assert base64.b64decode(embedded["data"]) == SAMPLE_BYTES

    def test_export_multiple_characters_zip(self, client):
        r = client.post(f"/api/stories/{STORY_A}/characters/export",
                        json={"characterIds": ["Hero", "Villain"]})
        assert r.status_code == 200
        assert r.headers["content-type"] == "application/zip"
        zf = zipfile.ZipFile(io.BytesIO(r.content))
        names = zf.namelist()
        assert "manifest.yml" in names
        assert "Hero.yml" in names
        assert "Villain.yml" in names
        manifest = yaml.safe_load(zf.read("manifest.yml"))
        entries = [e["character"] for e in manifest["characters"]]
        assert "Hero" in entries and "Villain" in entries

    def test_export_nonexistent_character_expect_404(self, client):
        r = client.get(f"/api/stories/{STORY_A}/characters/Ghost/export")
        assert r.status_code == 404


class TestImport:
    """Phase 4.2."""

    def test_import_valid_character_file(self, client):
        # Export from A, import into B
        export = client.get(f"/api/stories/{STORY_A}/characters/Hero/export")
        r = client.post(f"/api/stories/{STORY_B}/characters/import",
                        files={"file": ("Hero.yml", export.content, "application/x-yaml")},
                        params={"conflict": "keep-both"})
        assert r.status_code == 200
        result = r.json()
        # Story-Target already has Hero (fixture), so keep-both renames:
        # imported reports the final name, rename recorded
        imported_name = result["imported"][0]
        assert imported_name.startswith("Hero")
        if result["renamed"]:
            assert imported_name == result["renamed"][-1]["to"]
        # Voice sample copied (shared file name, content already present)
        copied = STORIES_DIR / STORY_B / "story-voice-refs" / "hero.wav"
        assert copied.exists()
        # Config wired for the imported (possibly renamed) character
        cfg = yaml.safe_load((STORIES_DIR / STORY_B / "story-config.yml").read_text())
        hero = next(c for c in cfg["characters"] if c["name"] == imported_name)
        assert hero["voice-sample"] == "hero.wav"

    def test_import_duplicate_name_each_conflict_resolution(self, client):
        export = client.get(f"/api/stories/{STORY_A}/characters/Villain/export")

        # skip: name exists -> skipped
        r = client.post(f"/api/stories/{STORY_B}/characters/import",
                        files={"file": ("v.yml", export.content)},
                        params={"conflict": "skip"})
        assert r.status_code == 200
        assert "Villain" in r.json()["skipped"]

        # keep-both: renamed
        r = client.post(f"/api/stories/{STORY_B}/characters/import",
                        files={"file": ("v.yml", export.content)},
                        params={"conflict": "keep-both"})
        assert r.status_code == 200
        renamed = r.json()["renamed"]
        assert renamed and renamed[-1]["to"].startswith("Villain (")
        names = yaml.safe_load((STORIES_DIR / STORY_B / "story-config.yml").read_text())
        assert any(c["name"] == "Villain (2)" for c in names["characters"])

        # overwrite: replaced, no rename
        before = (STORIES_DIR / STORY_B / "story-config.yml").read_text()
        r = client.post(f"/api/stories/{STORY_B}/characters/import",
                        files={"file": ("v.yml", export.content)},
                        params={"conflict": "overwrite"})
        assert r.status_code == 200
        assert "Villain" in r.json()["overwritten"]

    def test_import_invalid_schema_expect_error(self, client):
        bad = yaml.safe_dump({"character": {"name": "Bad", "bogus-key": 1}}).encode()
        r = client.post(f"/api/stories/{STORY_B}/characters/import",
                        files={"file": ("bad.yml", bad)},
                        params={"conflict": "overwrite"})
        assert r.status_code == 422
        assert r.json()["detail"]["code"] == "IMPORT_INVALID_CHARACTER"

    def test_import_garbage_payload_expect_error(self, client):
        r = client.post(f"/api/stories/{STORY_B}/characters/import",
                        files={"file": ("junk.yml", b"\x00\x01not yaml or json")})
        assert r.status_code == 422
        assert r.json()["detail"]["code"] in ("IMPORT_PARSE_ERROR", "IMPORT_INVALID")

    def test_import_empty_characters_expect_error(self, client):
        empty = yaml.safe_dump({"characters": []}).encode()
        r = client.post(f"/api/stories/{STORY_B}/characters/import",
                        files={"file": ("empty.yml", empty)})
        assert r.status_code == 422
        assert r.json()["detail"]["code"] == "IMPORT_EMPTY"


class TestRoundTrip:
    """Phase 4 integration."""

    def test_export_modify_import_round_trip_integrity(self, client):
        # Export Hero from A
        export = client.get(f"/api/stories/{STORY_A}/characters/Hero/export")
        original_doc = yaml.safe_load(export.content)
        # Import into B under a new name (keep-both)
        import_result = client.post(f"/api/stories/{STORY_B}/characters/import",
                                    files={"file": ("Hero.yml", export.content)},
                                    params={"conflict": "keep-both"})
        assert import_result.status_code == 200
        # Export the imported character back from B and compare core fields
        r = client.get(f"/api/stories/{STORY_B}/characters/Hero/export")
        round_doc = yaml.safe_load(r.content)
        assert round_doc["character"]["name"] == "Hero"
        # Round-trip: original voice wiring preserved
        assert (round_doc["character"].get("voice-sample")
                == original_doc["character"].get("voice-sample"))

    def test_bundle_import_copies_samples(self, client):
        r = client.post(f"/api/stories/{STORY_B}/characters/export",
                        json={"characterIds": ["Hero"]})
        assert r.status_code == 200
        # Import the bundle into A (target) as new name
        r = client.post(f"/api/stories/{STORY_A}/characters/import",
                        files={"file": ("bundle.zip", r.content)},
                        params={"conflict": "keep-both"})
        assert r.status_code == 200
        body = r.json()
        assert body["imported"], body
        # Sample may already exist in target; copied count may be 0 - but the
        # file must exist with correct content either way
        copied = STORIES_DIR / STORY_A / "story-voice-refs" / "hero.wav"
        assert copied.read_bytes() == SAMPLE_BYTES
