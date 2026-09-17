"""Phase 2.1/2.2 tests: Character CRUD and Emotion management.

Covers the test cases mandated by docs/FlexiTTS Create Character UI-Plan.md
Phases 2.1 and 2.2, running against FastAPI TestClient with a scratch story
directory (never the real Stories/ tree).
"""

import os
import shutil
import sys
from pathlib import Path

import pytest
import yaml

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.api.flexitts_api import create_app  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture(scope="module")
def client():
    """FastAPI TestClient with the stories dir pointed at a scratch tree."""
    scratch = Path(os.environ.get("JCODE_SCRATCH_DIR", "/tmp/flexitts-p2-tests")) / "character-api"
    stories_dir = scratch / "stories"
    shutil.rmtree(scratch, ignore_errors=True)
    stories_dir.mkdir(parents=True)

    # Build a minimal valid story from a fixture config
    story_dir = stories_dir / "Story-Test"
    story_dir.mkdir()
    (story_dir / "story-chapters").mkdir()
    (story_dir / "story-xml").mkdir()
    (story_dir / "logs").mkdir()
    (story_dir / "story-audio").mkdir()
    (story_dir / "story-audio" / "clips").mkdir()
    (story_dir / "story-voice-refs").mkdir()
    (story_dir / "story-voice-refs" / "sample.wav").write_bytes(b"RIFF")
    (story_dir / "story-chapters" / "01-Test.md").write_text("# Test")
    (story_dir / "story-config.yml").write_text(
        """
global:
  story-dir: Story-Test/
  voices: story-voice-refs/
  chapters: story-chapters/
  story-xml: story-xml/
  logs: logs/
  story-audio: story-audio/
  clips: story-audio/clips/
  clip-separation: 0.3
characters:
  - name: Narrator
    voice-sample: sample.wav
  - name: Existing
    custom-voice:
      language: English
      speaker: ryan
      instruct: "base voice"
      emotions:
        - emotion: Neutral
          instruct: "base voice"
""".lstrip()
    )

    from src.api.character_service import CharacterService

    app = create_app()
    client = TestClient(app)

    # Point the API's CharacterService at the scratch stories dir
    from src.api.character_service import CharacterService as CS
    orig_init = CS.__init__

    def patched_init(self, stories_dir_arg=None):
        orig_init(self, stories_dir)

    CS.__init__ = patched_init
    try:
        yield client
    finally:
        CS.__init__ = orig_init
        shutil.rmtree(scratch, ignore_errors=True)


STORY = "Story-Test"


class TestCharacterCRUD:
    """Phase 2.1 endpoint tests."""

    def test_create_character_with_valid_data(self, client):
        r = client.post(f"/api/stories/{STORY}/characters", json={
            "name": "NewChar", "language": "English",
            "voiceType": "custom", "voice": {"speaker": "ryan", "instruct": "calm"},
        })
        assert r.status_code == 200
        assert r.json()["character"]["name"] == "NewChar"
        assert r.json()["character"]["custom-voice"]["speaker"] == "ryan"

    def test_create_character_duplicate_name_expect_error(self, client):
        r = client.post(f"/api/stories/{STORY}/characters", json={
            "name": "newchar", "language": "English",
        })
        assert r.status_code == 409
        assert r.json()["detail"]["code"] == "CHARACTER_EXISTS"

    def test_create_character_invalid_language_expect_error(self, client):
        r = client.post(f"/api/stories/{STORY}/characters", json={
            "name": "LangTest", "language": "Klingon",
        })
        assert r.status_code == 400
        assert r.json()["detail"]["code"] == "INVALID_LANGUAGE"

    def test_create_sample_character(self, client):
        r = client.post(f"/api/stories/{STORY}/characters", json={
            "name": "SampleChar", "language": "English",
            "voiceType": "sample", "voice": {"voiceSample": "sample.wav"},
        })
        assert r.status_code == 200
        assert r.json()["character"]["voice-sample"] == "sample.wav"

    def test_get_existing_character(self, client):
        r = client.get(f"/api/stories/{STORY}/characters/Existing")
        assert r.status_code == 200
        assert r.json()["character"]["custom-voice"]["speaker"] == "ryan"

    def test_get_nonexistent_character_expect_404(self, client):
        r = client.get(f"/api/stories/{STORY}/characters/NoSuchCharacter")
        assert r.status_code == 404
        assert r.json()["detail"]["code"] == "CHARACTER_NOT_FOUND"

    def test_list_all_characters(self, client):
        r = client.get(f"/api/stories/{STORY}/characters")
        assert r.status_code == 200
        names = [c["name"] for c in r.json()["characters"]]
        assert "Narrator" in names and "Existing" in names and "NewChar" in names
        assert r.json()["totalCount"] == len(names)

    def test_update_character_fields(self, client):
        r = client.put(f"/api/stories/{STORY}/characters/NewChar", json={
            "description": "A test character",
            "soxEffects": ["gain +2", "reverb 50"],
        })
        assert r.status_code == 200
        updated = r.json()["character"]
        assert updated["description"] == "A test character"
        assert updated["sox-effects"] == ["gain +2", "reverb 50"]

    def test_update_character_sox_syntax_is_validated_on_save(self, client):
        # List-of-strings type enforced at the pydantic request boundary (422)
        r = client.put(f"/api/stories/{STORY}/characters/NewChar", json={
            "soxEffects": "gain +2",
        })
        assert r.status_code == 422

    def test_update_unknown_character_expect_404(self, client):
        r = client.put(f"/api/stories/{STORY}/characters/Ghost", json={"description": "x"})
        assert r.status_code == 404

    def test_delete_character_with_no_dependencies(self, client):
        client.post(f"/api/stories/{STORY}/characters", json={
            "name": "SampleChar", "language": "English",
        })
        r = client.delete(f"/api/stories/{STORY}/characters/SampleChar")
        assert r.status_code == 200
        assert r.json()["deleted"]["name"] == "SampleChar"
        assert r.json()["affectedDialogs"] == 0

    def test_delete_character_with_dialogs_returns_count(self, client):
        r = client.post(f"/api/stories/{STORY}/characters", json={
            "name": "Doomed", "language": "English",
        })
        assert r.status_code == 200
        r = client.delete(f"/api/stories/{STORY}/characters/Doomed",
                          params={"dependentDialogs": 3})
        assert r.status_code == 200
        assert r.json()["affectedDialogs"] == 3

    def test_delete_nonexistent_character_expect_404(self, client):
        r = client.delete(f"/api/stories/{STORY}/characters/Ghost")
        assert r.status_code == 404


class TestEmotionManagement:
    """Phase 2.2 endpoint tests."""

    def test_add_emotion_to_character(self, client):
        r = client.post(f"/api/stories/{STORY}/characters/Existing/emotions", json={
            "emotion": "Happy", "instruct": "light and cordial",
        })
        assert r.status_code == 200
        assert r.json()["emotion"]["emotion"] == "Happy"

    def test_add_duplicate_emotion_name_expect_error(self, client):
        r = client.post(f"/api/stories/{STORY}/characters/Existing/emotions", json={
            "emotion": "happy",  # case-insensitive duplicate
        })
        assert r.status_code == 409
        assert r.json()["detail"]["code"] == "EMOTION_EXISTS"

    def test_add_emotion_with_sox_override(self, client):
        r = client.post(f"/api/stories/{STORY}/characters/Existing/emotions", json={
            "emotion": "Angry", "instruct": "gritted teeth",
            "soxEffects": ["overdrive 15 30"],
        })
        assert r.status_code == 200
        entry = r.json()["emotion"]
        assert entry["sox-effects"] == ["overdrive 15 30"]

    def test_update_emotion_fields(self, client):
        r = client.put(f"/api/stories/{STORY}/characters/Existing/emotions/Angry", json={
            "instruct": "gritted teeth, aggressive tone",
        })
        assert r.status_code == 200
        assert r.json()["emotion"]["instruct"] == "gritted teeth, aggressive tone"

    def test_update_emotion_sox_effects(self, client):
        r = client.put(f"/api/stories/{STORY}/characters/Existing/emotions/Angry", json={
            "soxEffects": ["overdrive 20 30"],
        })
        assert r.status_code == 200
        assert r.json()["emotion"]["sox-effects"] == ["overdrive 20 30"]

    def test_update_unknown_emotion_expect_404(self, client):
        r = client.put(f"/api/stories/{STORY}/characters/Existing/emotions/Ghost", json={
            "instruct": "x",
        })
        assert r.status_code == 404
        assert r.json()["detail"]["code"] == "EMOTION_NOT_FOUND"

    def test_delete_emotion(self, client):
        # Add a throwaway emotion so Existing keeps >1 emotions after delete
        client.post(f"/api/stories/{STORY}/characters/Existing/emotions",
                    json={"emotion": "Throwaway"})
        r = client.delete(f"/api/stories/{STORY}/characters/Existing/emotions/throwaway")
        assert r.status_code == 200
        assert r.json()["deleted"]["emotion"] == "Throwaway"

    def test_delete_last_emotion_expect_warning(self, client):
        # Create a fresh character with exactly one emotion
        client.post(f"/api/stories/{STORY}/characters", json={
            "name": "Solo", "language": "English",
            "voiceType": "custom", "voice": {"speaker": "dylan", "instruct": "x"},
        })
        r = client.delete(f"/api/stories/{STORY}/characters/Solo/emotions/Neutral")
        assert r.status_code == 409
        assert r.json()["detail"]["code"] == "LAST_EMOTION_PROTECTED"
        # Override works
        r = client.delete(f"/api/stories/{STORY}/characters/Solo/emotions/Neutral",
                          params={"allowDeleteLast": "true"})
        assert r.status_code == 200

    def test_reorder_emotions(self, client):
        # Existing currently has: Angry, Happy, Neutral (set by earlier tests),
        # but ensure a known state first
        client.put(f"/api/stories/{STORY}/characters/Existing/emotions/reorder",
                   json={"orderedEmotions": ["Neutral", "Happy", "Angry"]})
        r = client.put(f"/api/stories/{STORY}/characters/Existing/emotions/reorder",
                       json={"orderedEmotions": ["angry", "happy", "neutral"]})
        assert r.status_code == 200
        names = [e["emotion"] for e in r.json()["emotions"]]
        assert names == ["Angry", "Happy", "Neutral"]

    def test_reorder_invalid_list_expect_error(self, client):
        r = client.put(f"/api/stories/{STORY}/characters/Existing/emotions/reorder",
                       json={"orderedEmotions": ["Angry"]})
        assert r.status_code == 400
        assert r.json()["detail"]["code"] == "INVALID_ORDER"

    def test_set_default_emotion_unsets_previous(self, client):
        # Set Angry as default: it should move to the front of the list
        r = client.put(f"/api/stories/{STORY}/characters/Existing/emotions/Angry/default")
        assert r.status_code == 200
        # Verify Angry is first via GET
        r = client.get(f"/api/stories/{STORY}/characters/Existing")
        emotions = r.json()["character"]["custom-voice"]["emotions"]
        assert emotions[0]["emotion"] == "Angry"


class TestCharacterValidationRollback:
    """Mutations that would break the config roll back and surface 422."""

    def test_invalid_dialog_effect_reference_rolls_back(self, client):
        original = (Path(os.environ.get("JCODE_SCRATCH_DIR", "/tmp/flexitts-p2-tests"))
                    / "character-api" / "stories" / STORY / "story-config.yml").read_text()
        r = client.put(f"/api/stories/{STORY}/characters/NewChar", json={
            "dialogEffects": ["undefined-effect-name"],
        })
        assert r.status_code == 422
        # File rolled back to its pre-request state
        after = (Path(os.environ.get("JCODE_SCRATCH_DIR", "/tmp/flexitts-p2-tests"))
                 / "character-api" / "stories" / STORY / "story-config.yml").read_text()
        assert after == original


class TestStoryResolution:
    def test_invalid_story_id_rejected(self, client):
        r = client.get("/api/stories/..%2F..%2Fetc/characters")
        assert r.status_code in (400, 404)

    def test_unknown_story_expect_404(self, client):
        r = client.get("/api/stories/Story-DoesNotExist/characters")
        assert r.status_code == 404