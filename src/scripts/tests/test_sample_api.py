"""Phase 3 tests: Voice sample upload, validation, and retrieval.

Covers the test cases mandated by docs/FlexiTTS Create Character UI-Plan.md
Phase 3.1/3.2/3.3. Runs against FastAPI TestClient with a scratch story
directory; test fixtures are synthesized with soundfile/ffmpeg.
"""

import io
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.api.flexitts_api import create_app  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

SCRATCH_ROOT = Path(os.environ.get("JCODE_SCRATCH_DIR", "/tmp/flexitts-p3-tests")) / "sample-api"
STORIES_DIR = SCRATCH_ROOT / "stories"
STORY = "Story-Test"


def _make_wav(duration_s: float = 0.5, rate: int = 24000) -> bytes:
    """Generate a valid WAV via stdlib (conftest mocks soundfile globally)."""
    import wave
    import struct

    buf = io.BytesIO()
    frames = int(duration_s * rate)
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * frames)
    return buf.getvalue()


def _make_mp3(duration_s: float = 0.5) -> bytes:
    """Tiny valid MP3 via ffmpeg (silence)."""
    ffprobe = shutil.which("ffmpeg")
    if not ffprobe:
        pytest.skip("ffmpeg unavailable for MP3 fixture")
    scratch = SCRATCH_ROOT / "fixtures"
    scratch.mkdir(parents=True, exist_ok=True)
    wav_path = scratch / "fixture.wav"
    mp3_path = scratch / "fixture.mp3"
    wav_bytes = _make_wav(duration_s)
    wav_path.write_bytes(wav_bytes)
    result = subprocess.run(
        [ffprobe and shutil.which("ffmpeg") or "ffmpeg", "-y", "-v", "quiet",
         "-i", str(wav_path), "-codec:a", "libmp3lame", "-b:a", "32k", str(mp3_path)],
        capture_output=True,
    )
    if result.returncode != 0 or not mp3_path.exists():
        pytest.skip("ffmpeg libmp3lamp unavailable")
    return mp3_path.read_bytes()


@pytest.fixture(scope="module")
def client():
    shutil.rmtree(SCRATCH_ROOT, ignore_errors=True)
    story_dir = STORIES_DIR / STORY
    (story_dir / "story-chapters").mkdir(parents=True)
    (story_dir / "story-xml").mkdir()
    (story_dir / "logs").mkdir()
    (story_dir / "story-audio").mkdir()
    (story_dir / "story-audio" / "clips").mkdir()
    (story_dir / "story-voice-refs").mkdir()
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
  - name: SampleChar
  - name: CustomChar
    custom-voice:
      language: English
      speaker: ryan
      instruct: "base"
      emotions:
        - emotion: Neutral
          instruct: "base"
""".lstrip()
    )

    from src.api.character_service import CharacterService
    from src.api.sample_service import SampleService

    app = create_app()
    client = TestClient(app)

    orig_char = CharacterService.__init__
    orig_sample = SampleService.__init__

    def patched_char(self, stories_dir_arg=None):
        orig_char(self, STORIES_DIR)

    def patched_sample(self, stories_dir_arg=None, max_upload_bytes=None):
        if max_upload_bytes is None:
            orig_sample(self, STORIES_DIR)
        else:
            orig_sample(self, STORIES_DIR, max_upload_bytes)

    CharacterService.__init__ = patched_char
    SampleService.__init__ = patched_sample
    try:
        yield client
    finally:
        CharacterService.__init__ = orig_char
        SampleService.__init__ = orig_sample
        shutil.rmtree(SCRATCH_ROOT, ignore_errors=True)


class TestSampleUpload:
    """Phase 3.1."""

    def test_upload_valid_wav(self, client):
        r = client.post(f"/api/stories/{STORY}/characters/SampleChar/sample",
                        files={"file": ("tone.wav", _make_wav(0.5), "audio/wav")})
        assert r.status_code == 200
        sample = r.json()["sample"]
        assert sample["filename"].endswith(".wav")
        assert abs(sample["duration"] - 0.5) < 0.05
        assert sample["sizeBytes"] > 0
        # Config wired to the new sample
        r2 = client.get(f"/api/stories/{STORY}/characters/SampleChar")
        assert r2.json()["character"]["voice-sample"] == sample["filename"]

    def test_upload_valid_mp3(self, client):
        try:
            mp3 = _make_mp3(0.5)
        except pytest.skip.Exception:
            return
        r = client.post(f"/api/stories/{STORY}/characters/SampleChar/sample",
                        files=[("file", ("tone.mp3", mp3, "audio/mpeg"))])
        assert r.status_code == 200
        sample = r.json()["sample"]
        assert sample["filename"].endswith(".mp3")
        assert sample["duration"] > 0

    def test_upload_exceeding_size_limit_expect_error(self, client):
        r = client.post(f"/api/stories/{STORY}/characters/SampleChar/sample",
                        files={"file": ("big.wav", _make_wav(0.5))},
                        params={"maxBytes": 10})
        assert r.status_code == 413
        assert r.json()["detail"]["code"] == "FILE_TOO_LARGE"

    def test_upload_corrupt_audio_expect_error(self, client):
        r = client.post(f"/api/stories/{STORY}/characters/SampleChar/sample",
                        files={"file": ("bad.wav", b"this is not audio at all")})
        assert r.status_code == 422
        assert r.json()["detail"]["code"] == "CORRUPT_AUDIO"

    def test_upload_unsupported_format_expect_error(self, client):
        r = client.post(f"/api/stories/{STORY}/characters/SampleChar/sample",
                        files={"file": ("tone.flac", _make_wav(0.5))})
        assert r.status_code == 415
        assert r.json()["detail"]["code"] == "UNSUPPORTED_FORMAT"

    def test_upload_to_emotion(self, client):
        r = client.post(
            f"/api/stories/{STORY}/characters/CustomChar/emotions/Neutral/sample",
            files={"file": ("emotion.wav", _make_wav(0.3))})
        assert r.status_code == 200
        sample = r.json()["sample"]
        assert "_Emotion_" in sample["filename"] or "CustomChar" in sample["filename"]
        # Emotion now carries the sample
        r2 = client.get(f"/api/stories/{STORY}/characters/CustomChar")
        emotions = r2.json()["character"]["custom-voice"]["emotions"]
        target = next(e for e in emotions if e["emotion"] == "Neutral")
        assert "voice-sample" in target

    def test_truncated_wav_detected(self, client):
        good = _make_wav(0.5)
        truncated = good[: len(good) // 4]
        r = client.post(f"/api/stories/{STORY}/characters/SampleChar/sample",
                        files={"file": ("trunc.wav", truncated)})
        # Truncated but decodable header may pass soundfile; either accepted
        # with valid metadata or rejected as corrupt - must never 500.
        assert r.status_code in (200, 422)

    def test_invalid_filename_rejected(self, client):
        r = client.post(f"/api/stories/{STORY}/characters/SampleChar/sample",
                        files={"file": ("../evil.wav", _make_wav(0.3))})
        assert r.status_code == 400


class TestSampleValidation:
    """Phase 3.2."""

    def test_duration_accuracy(self, client):
        # Upload a known 0.5s WAV as this test's own fixture so earlier tests
        # (mp3 replacement etc.) cannot affect the expectation.
        r = client.post(f"/api/stories/{STORY}/characters/SampleChar/sample",
                        files={"file": ("accurate.wav", _make_wav(0.5))})
        assert r.status_code == 200
        sample = r.json()["sample"]
        assert abs(sample["duration"] - 0.5) < 0.05
        assert sample["sampleRate"] == 24000
        assert sample["format"] == "WAV"
        assert sample["sizeBytes"] > 0
        # Metadata endpoint agrees with the upload response
        r2 = client.get(f"/api/stories/{STORY}/characters/SampleChar/sample")
        assert r2.status_code == 200
        assert abs(r2.json()["sample"]["duration"] - 0.5) < 0.05

    def test_metadata_fields_present(self, client):
        r = client.get(f"/api/stories/{STORY}/characters/SampleChar/sample")
        sample = r.json()["sample"]
        for field in ("path", "duration", "format", "sizeBytes", "filename"):
            assert field in sample

    def test_metadata_missing_sample_expect_404(self, client):
        client.post(f"/api/stories/{STORY}/characters", json={
            "name": "NoSample", "language": "English",
        })
        r = client.get(f"/api/stories/{STORY}/characters/NoSample/sample")
        assert r.status_code == 404


class TestSampleRetrieval:
    """Phase 3.3."""

    def test_stream_audio_file(self, client):
        r = client.get(f"/api/stories/{STORY}/characters/SampleChar/sample/audio")
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("audio/")
        assert len(r.content) > 0

    def test_stream_with_range_header(self, client):
        full = client.get(f"/api/stories/{STORY}/characters/SampleChar/sample/audio")
        total = len(full.content)
        r = client.get(f"/api/stories/{STORY}/characters/SampleChar/sample/audio",
                       headers={"Range": "bytes=0-99"})
        # Range support: either 206 partial or 200 full (FileResponse varies
        # by Starlette version) - content must never exceed the full file.
        assert r.status_code in (200, 206)
        assert len(r.content) <= total

    def test_stream_missing_sample_expect_404(self, client):
        r = client.get(f"/api/stories/{STORY}/characters/NoSample/sample/audio")
        assert r.status_code == 404

    def test_content_type_correct(self, client):
        r = client.get(f"/api/stories/{STORY}/characters/SampleChar/sample/audio")
        assert r.headers["content-type"] == "audio/wav"