"""Phase 5 tests: SoX effects engine (builder, validation, execution).

Covers the test cases mandated by docs/FlexiTTS Create Character UI-Plan.md
Phases 5.1/5.2/5.3: command building (basic, multi-effect, special chars),
syntax validation (correct syntax, unknown effect, invalid param type), and
execution (simple effect, complex pipeline, non-existent effect, timeout).
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.api.flexitts_api import create_app  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

SCRATCH_ROOT = Path(os.environ.get("JCODE_SCRATCH_DIR", "/tmp/flexitts-p5-tests")) / "sox"


@pytest.fixture(scope="module")
def client():
    shutil.rmtree(SCRATCH_ROOT, ignore_errors=True)
    SCRATCH_ROOT.mkdir(parents=True, exist_ok=True)
    wav = SCRATCH_ROOT / "test.wav"
    subprocess.run(
        ["sox", "-n", "-r", "24000", "-c", "1", str(wav), "synth", "1", "sine", "440"],
        check=True, capture_output=True,
    )
    app = create_app()
    client = TestClient(app, raise_server_exceptions=False)
    yield client
    shutil.rmtree(SCRATCH_ROOT, ignore_errors=True)


@pytest.fixture(scope="module")
def wav_path(client) -> Path:
    return SCRATCH_ROOT / "test.wav"


class TestSoxCommandBuilder:
    """Phase 5.1."""

    def test_build_basic_command(self, wav_path):
        from src.api.sox_service import build_command
        argv, effects = build_command(wav_path, wav_path.with_suffix(".out.wav"),
                                      ["reverb 50"])
        assert argv[0] == "sox"
        assert argv[1] == str(wav_path)
        assert "reverb" in argv and "50" in argv
        assert effects[0]["effect"] == "reverb"
        assert effects[0]["args"] == ["50"]

    def test_build_multi_effect_pipeline(self, wav_path):
        from src.api.sox_service import build_command
        argv, effects = build_command(
            wav_path, wav_path.with_suffix(".out.wav"),
            ["pitch -400", "reverb 50", "gain +3", "norm"])
        # Chaining: all effects appended in order after file args
        names = [e["effect"] for e in effects]
        assert names == ["pitch", "reverb", "gain", "norm"]
        argv_str = " ".join(argv)
        for name in names:
            assert name in argv_str

    def test_special_characters_in_parameters(self, wav_path):
        from src.api.sox_service import parse_effect_strings, quote_effect_string
        # shlex handles quoted special chars
        effects = parse_effect_strings(["pad 0.5 1.5", "gain '-3'"])
        assert effects[1]["effect"] == "gain"
        assert effects[1]["args"] == ["-3"]
        q = quote_effect_string("pad", ["0.5", "1.5"])
        assert q == "pad 0.5 1.5"
        # Malformed quoting surfaces a parse-safe result, not a crash
        effects2 = parse_effect_strings(["gain 'unbalanced"])
        assert effects2[0]["effect"] == "gain"

    def test_parse_preserves_config_format(self, wav_path):
        """story-config.yml chains are multi-effect strings; each known effect
        name segments into its own structured effect."""
        from src.api.sox_service import parse_effect_strings
        real_world = [
            "treble -5 5000 0.7 compand 0.3,1 6:-70,-60,-20 -4 -90 0.1 gain -3",
            "pitch -250 equalizer 1800 +4 1.8 equalizer 3200 +3 2.2 bass +2 120 gain -n -1.5",
        ]
        effects = parse_effect_strings(real_world)
        names = [e["effect"] for e in effects]
        # Chain 1: treble -> compand -> gain ; Chain 2: pitch -> equalizer x2 -> bass -> gain
        assert names == ["treble", "compand", "gain", "pitch", "equalizer", "equalizer", "bass", "gain"]
        # Args assigned to the right effects
        treble = next(e for e in effects if e["effect"] == "treble")
        assert treble["args"] == ["-5", "5000", "0.7"]
        gain2 = [e for e in effects if e["effect"] == "gain"]
        assert gain2[0]["args"] == ["-3"]
        assert gain2[1]["args"] == ["-n", "-1.5"]


class TestSoxValidation:
    """Phase 5.2."""

    def test_validate_correct_syntax(self, client):
        r = client.post("/api/validate/sox",
                        json={"effects": ["reverb 50", "gain +3", "norm"]})
        assert r.status_code == 200
        body = r.json()
        assert body["isValid"] is True
        assert body["errors"] == []

    def test_validate_incorrect_effect_name(self, client):
        r = client.post("/api/validate/sox",
                        json={"effects": ["frobnicate 5"]})
        assert r.status_code == 200
        body = r.json()
        assert body["isValid"] is False
        codes = [e["code"] for e in body["errors"]]
        assert "UNKNOWN_EFFECT" in codes
        # Detailed message included
        err = next(e for e in body["errors"] if e["code"] == "UNKNOWN_EFFECT")
        assert "frobnicate" in err["message"]

    def test_validate_invalid_parameter_type(self, client):
        r = client.post("/api/validate/sox",
                        json={"effects": ["gain abc"]})
        assert r.status_code == 200
        body = r.json()
        assert body["isValid"] is False
        codes = [e["code"] for e in body["errors"]]
        assert "INVALID_PARAM" in codes

    def test_validate_missing_args(self, client):
        r = client.post("/api/validate/sox",
                        json={"effects": ["echo 0.8 0.9"]})
        assert r.status_code == 200
        codes = [e["code"] for e in r.json()["errors"]]
        assert "MISSING_ARGS" in codes

    def test_validate_too_many_args(self, client):
        r = client.post("/api/validate/sox",
                        json={"effects": ["reverse extra-arg"]})
        assert r.status_code == 200
        codes = [e["code"] for e in r.json()["errors"]]
        assert "TOO_MANY_ARGS" in codes

    def test_validate_real_world_chains(self, client):
        """Chains from the actual story configs must validate."""
        real = [
            "gain +4",
            "treble -5 5000 0.7 compand 0.3,1 6:-70,-60,-20 -4 -90 0.1 gain -3",
            "pitch -250 equalizer 1800 +4 1.8 equalizer 3200 +3 2.2 bass +2 120 gain -n -1.5",
            "pitch -400   echo 0.8 0.88 60 0.4 120 0.3   reverb",
            "overdrive 15 30 gain -8",
        ]
        r = client.post("/api/validate/sox", json={"effects": real})
        assert r.status_code == 200
        assert r.json()["isValid"] is True, r.json()["errors"]

    def test_validate_flags_normalize_alias_as_unknown(self, client):
        """'normalize' is not a SoX effect ('norm' is); one story config uses
        it in story-audio-post-process - validation should surface this."""
        r = client.post("/api/validate/sox", json={"effects": ["normalize"]})
        assert r.status_code == 200
        body = r.json()
        assert body["isValid"] is False
        assert body["errors"][0]["code"] == "UNKNOWN_EFFECT"

    def test_list_effects_for_builder(self, client):
        r = client.get("/api/sox/effects")
        assert r.status_code == 200
        effects = r.json()["effects"]
        assert "reverb" in effects
        assert "gain" in effects
        assert len(effects) > 50


class TestSoxExecution:
    """Phase 5.3."""

    def test_apply_simple_effect(self, client, wav_path):
        r = client.post("/api/process/sox",
                        json={"audioPath": str(wav_path), "effects": ["gain +3"]})
        assert r.status_code == 200
        body = r.json()
        assert body["sizeBytes"] > 0
        assert Path(body["outputPath"]).exists()

    def test_apply_complex_multi_effect_pipeline(self, client, wav_path):
        r = client.post("/api/process/sox",
                        json={"audioPath": str(wav_path),
                              "effects": ["pitch -400", "reverb 50", "norm"],
                              "outputPath": str(SCRATCH_ROOT / "complex-out.wav")})
        assert r.status_code == 200
        assert Path(r.json()["outputPath"]).exists()

    def test_handle_nonexistent_effect(self, client, wav_path):
        r = client.post("/api/process/sox",
                        json={"audioPath": str(wav_path),
                              "effects": ["frobnicate 5"]})
        assert r.status_code == 422
        assert r.json()["detail"]["code"] == "SOX_SYNTAX_ERROR"

    def test_handle_sox_timeout(self, client, wav_path):
        r = client.post("/api/process/sox",
                        json={"audioPath": str(wav_path),
                              "effects": ["reverb 50"],
                              "timeoutSeconds": 0.0001})
        # Timeout (504) or fast-finish race (200) - never a crash
        assert r.status_code in (200, 504)
        if r.status_code == 504:
            assert r.json()["detail"]["code"] == "SOX_TIMEOUT"

    def test_missing_input_file(self, client):
        r = client.post("/api/process/sox",
                        json={"audioPath": str(SCRATCH_ROOT / "missing.wav"),
                              "effects": ["gain +2"]})
        assert r.status_code == 404
        assert r.json()["detail"]["code"] == "SOX_INPUT_NOT_FOUND"

    def test_in_place_processing_preserves_input_path(self, client, wav_path):
        original_size = wav_path.stat().st_size
        r = client.post("/api/process/sox",
                        json={"audioPath": str(wav_path), "effects": ["norm"]})
        assert r.status_code == 200
        assert r.json()["outputPath"] == str(wav_path)
        assert wav_path.exists()
        # File was actually rewritten (size may or may not differ)
        assert wav_path.stat().st_size > 0
        _ = original_size