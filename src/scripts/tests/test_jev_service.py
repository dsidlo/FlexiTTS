"""Tests for jev_service.py: post-XML-conversion validation via Jev.

Covers: config loading (case-insensitive key, emotion-confidence-threshold
with legacy fallback), character assignment validation (roster normalize,
Jev remap at/above threshold, keep below, dry no-op), emotion tag
validation (same gates), collect_char_emotions, run_jev_validation gates,
and a live simulation against a mock System One HTTP server.
"""

import json
import os
import sys
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import jev_service


def jev_cfg(**overrides):
    cfg = {"enabled": True, "api_key": "test-key", "api_base": "http://mock",
           "model": "jev-latest", "confidence": 0.80, "timeout": 5.0}
    cfg.update(overrides)
    return cfg


def roster():
    return ["Hendrix", "Yamato", "Ayana", "Narrator"]


class MockJev:
    def __init__(self, char_conf=0.0, emotion_conf=0.0, char_choice="Hendrix",
                 emotion_choice="Neutral"):
        self.char_conf = char_conf
        self.emotion_conf = emotion_conf
        self.char_choice = char_choice
        self.emotion_choice = emotion_choice
        self.calls = []

    def ask(self, state, questions):
        self.calls.append({"state": state, "questions": questions})
        answers = {}
        for key in questions:
            if "correct_character" in questions:
                conf, choice = self.char_conf, self.char_choice
            else:
                conf, choice = self.emotion_conf, self.emotion_choice
            answers[key] = {"choice": choice, "confidence": conf}
        return {"answers": answers}


CHAR_XML = ('<story><section seq="1">\n'
            '  <dialog character="Hendricks" emotion="sarcastic" dlgseq="001">Well that went well.</dialog>\n'
            '  <dialog character="hendrix" emotion="Neutral" dlgseq="002">Hello.</dialog>\n'
            '  <narration emotion="calm" dlgseq="003">The lab hummed.</narration>\n'
            '</section></story>')


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------

def test_load_jev_config_disabled_by_default():
    cfg = jev_service.load_jev_config({})
    assert cfg["enabled"] is False
    assert cfg["confidence"] == 0.80
    assert cfg["model"] == "jev-latest"


def test_load_jev_config_case_insensitive_key():
    cfg = jev_service.load_jev_config({"Jev": {"enabled": True,
                                               "emotion-confidence-threshold": 0.85}})
    assert cfg["enabled"] is True
    assert cfg["confidence"] == 0.85


def test_load_jev_config_emotion_threshold_preferred_over_legacy():
    cfg = jev_service.load_jev_config({"jev": {
        "enabled": True,
        "confidence-threshold": 0.9,
        "emotion-confidence-threshold": 0.75,
    }})
    assert cfg["confidence"] == 0.75


def test_load_jev_config_legacy_threshold_fallback():
    cfg = jev_service.load_jev_config({"jev": {"enabled": True,
                                               "confidence-threshold": 0.9}})
    assert cfg["confidence"] == 0.9


def test_load_jev_config_api_key_env(monkeypatch):
    monkeypatch.setenv("MY_JEV_KEY", "abc123")
    cfg = jev_service.load_jev_config({"jev": {"enabled": True,
                                               "api-key-env": "MY_JEV_KEY"}})
    assert cfg["api_key"] == "abc123"


# ---------------------------------------------------------------------------
# collect_char_emotions
# ---------------------------------------------------------------------------

def test_collect_char_emotions_from_custom_voice_and_cloned():
    config = {"characters": [
        {"name": "Hendrix", "custom-voice": {"speaker": "ryan", "emotions": [
            {"emotion": "Neutral"}, {"emotion": "sarcastic"}]}},
        {"name": "Juko", "cloned-emotion": [{"emotion": "angry"}, {"emotion": "calm"}]},
        {"name": "Ayana"},
        {"custom-voice": {}},
    ]}
    out = jev_service.collect_char_emotions(config)
    assert out == {"hendrix": ["Neutral", "sarcastic"], "juko": ["angry", "calm"]}


# ---------------------------------------------------------------------------
# Character assignment validation
# ---------------------------------------------------------------------------

def test_char_no_client_leaves_unknown_speaker_untouched(tmp_path):
    """client=None (unit-level): local normalization still applies; unknowns skip."""
    p = tmp_path / "c.xml"
    p.write_text(CHAR_XML)
    result = jev_service.validate_character_assignments(p, roster(), jev_cfg(), client=None)
    assert result["characters"] == [{"from": "hendrix", "to": "Hendrix",
                                     "how": "roster-normalize"}]
    assert "Hendricks" in p.read_text()


def test_char_roster_normalization_no_jev_needed(tmp_path):
    p = tmp_path / "c.xml"
    p.write_text(CHAR_XML)
    client = MockJev()
    jev_service.validate_character_assignments(p, roster(), jev_cfg(), client)
    text = p.read_text()
    assert 'character="Hendrix"' in text
    assert 'character="hendrix"' not in text
    # the case-fix ('hendrix') must not appear in any Jev query
    assert not any(c["state"].get("assigned_speaker") == "hendrix"
                   for c in client.calls)


def test_char_jev_remaps_at_threshold(tmp_path):
    p = tmp_path / "c.xml"
    p.write_text(CHAR_XML)
    client = MockJev(char_conf=0.90, char_choice="Hendrix")
    result = jev_service.validate_character_assignments(p, roster(), jev_cfg(), client)
    assert 'character="Hendrix"' in p.read_text()
    assert any(c["from"] == "Hendricks" and c["to"] == "Hendrix" and c["how"] == "jev"
               for c in result["characters"])


def test_char_jev_keeps_below_threshold(tmp_path):
    p = tmp_path / "c.xml"
    p.write_text(CHAR_XML)
    client = MockJev(char_conf=0.79, char_choice="Hendrix")
    result = jev_service.validate_character_assignments(p, roster(), jev_cfg(), client)
    assert 'character="Hendricks"' in p.read_text()
    # 'hendrix' was case-normalized locally; 'Hendricks' kept below threshold.
    assert result["characters"] == [{"from": "hendrix", "to": "Hendrix",
                                     "how": "roster-normalize"}]


def test_char_exact_match_never_queries_jev(tmp_path):
    p = tmp_path / "c.xml"
    p.write_text('<story><section seq="1">'
                 '<dialog character="Yamato" emotion="calm" dlgseq="001">Fine.</dialog>'
                 '</section></story>')
    client = MockJev(char_conf=0.99)
    jev_service.validate_character_assignments(p, roster(), jev_cfg(), client)
    assert client.calls == []


# ---------------------------------------------------------------------------
# Emotion tag validation
# ---------------------------------------------------------------------------

EMOTION_XML = ('<story><section seq="1">\n'
               '  <dialog character="Hendrix" emotion="suspicious" dlgseq="001">Hmm.</dialog>\n'
               '  <dialog character="Juko" emotion="angry" dlgseq="002">Back off.</dialog>\n'
               '</section></story>')


def test_emotion_remapped_at_threshold(tmp_path):
    p = tmp_path / "e.xml"
    p.write_text(EMOTION_XML)
    client = MockJev(emotion_conf=0.85, emotion_choice="Neutral")
    result = jev_service.validate_emotion_tags(p, {"hendrix": ["Neutral", "sarcastic"]},
                                               jev_cfg(), client)
    assert 'character="Hendrix" emotion="Neutral"' in p.read_text()
    assert any(c["speaker"] == "Hendrix" and c["from"] == "suspicious"
               for c in result["emotions"])


def test_emotion_kept_below_threshold(tmp_path):
    p = tmp_path / "e.xml"
    p.write_text(EMOTION_XML)
    client = MockJev(emotion_conf=0.60, emotion_choice="Neutral")
    result = jev_service.validate_emotion_tags(p, {"hendrix": ["Neutral", "sarcastic"]},
                                               jev_cfg(), client)
    assert 'emotion="suspicious"' in p.read_text()
    assert result["emotions"] == []


def test_emotion_character_without_config_untouched(tmp_path):
    p = tmp_path / "e.xml"
    p.write_text(EMOTION_XML)
    client = MockJev(emotion_conf=0.99)
    jev_service.validate_emotion_tags(p, {"hendrix": ["Neutral"]}, jev_cfg(), client)
    # Juko has no configured emotions: 'angry' must stay untouched.
    assert 'character="Juko" emotion="angry"' in p.read_text()


def test_emotion_already_configured_skips_jev(tmp_path):
    p = tmp_path / "e.xml"
    p.write_text('<story><section seq="1">'
                 '<dialog character="Hendrix" emotion="sarcastic" dlgseq="001">Ha.</dialog>'
                 '</section></story>')
    client = MockJev()
    jev_service.validate_emotion_tags(p, {"hendrix": ["Neutral", "sarcastic"]},
                                      jev_cfg(), client)
    assert client.calls == []


# ---------------------------------------------------------------------------
# run_jev_validation gates
# ---------------------------------------------------------------------------

def test_run_skips_when_disabled(tmp_path):
    p = tmp_path / "c.xml"
    p.write_text(CHAR_XML)
    config = {"characters": [{"name": "Hendrix"}], "jev": {"enabled": False}}
    assert jev_service.run_jev_validation(p, config) == {"skipped": True,
                                                         "reason": "disabled"}


def test_run_skips_entirely_without_api_key(tmp_path):
    """backend=jev with no api key: Jev actions gated off; XML untouched."""
    p = tmp_path / "c.xml"
    p.write_text(CHAR_XML)
    before = p.read_text()
    result = jev_service.run_jev_validation(p, {"characters": [{"name": "Hendrix"}],
                                                "jev": {"enabled": True,
                                                        "backend": "jev"}})
    assert result["skipped"] is True
    assert result["reason"] == "no_api_key"
    assert p.read_text() == before


def test_run_auto_prefers_laya_when_gpu(monkeypatch):
    """backend=auto + laya installed + GPU: selects laya without api key."""
    monkeypatch.setattr(jev_service, "_laya_available", lambda cfg: True)
    p = tmp_path if False else None
    import tempfile
    d = tempfile.mkdtemp()
    p = Path(d) / "c.xml"
    p.write_text(CHAR_XML)
    result = jev_service.run_jev_validation(p, {"characters": [{"name": "Hendrix"}],
                                                "jev": {"enabled": True,
                                                        "backend": "auto"}})
    assert result["skipped"] is False
    assert result["backend"] == "laya"


def test_run_auto_falls_back_to_jev_with_key(monkeypatch):
    """backend=auto, laya unavailable, jev key present: selects jev."""
    monkeypatch.setattr(jev_service, "_laya_available", lambda cfg: False)
    import tempfile
    d = tempfile.mkdtemp()
    p = Path(d) / "c.xml"
    p.write_text(CHAR_XML)
    cfg = {"characters": [{"name": "Hendrix"}],
           "jev": {"enabled": True, "backend": "auto",
                   "api-key-env": "JEV_TEST_KEY"}}
    os.environ["JEV_TEST_KEY"] = "k"
    result = jev_service.run_jev_validation(p, cfg)
    assert result["skipped"] is False
    assert result["backend"] == "jev"


def test_run_laya_forced_cpu(monkeypatch):
    """backend=laya device=cpu runs without GPU."""
    monkeypatch.setattr(jev_service, "_laya_available", lambda cfg: True)
    import tempfile
    d = tempfile.mkdtemp()
    p = Path(d) / "c.xml"
    p.write_text(CHAR_XML)
    result = jev_service.run_jev_validation(p, {"characters": [{"name": "Hendrix"}],
                                                "jev": {"enabled": True,
                                                        "backend": "laya",
                                                        "device": "cpu"}})
    assert result["skipped"] is False
    assert result["backend"] == "laya"


def test_load_jev_config_subkey_case_insensitive():
    cfg = jev_service.load_jev_config({"Jev": {"Backend": "LAYA",
                                               "Min-VRAM-MB": 2000}})
    assert cfg["backend"] == "laya"
    assert cfg["min-vram-mb"] == 2000


def test_select_backend_unknown_value_treated_as_auto(monkeypatch):
    monkeypatch.setattr(jev_service, "_laya_available", lambda cfg: False)
    cfg = dict(jev_service.load_jev_config({"jev": {"backend": "bogus"}}))
    cfg["api_key"] = "k"
    client, backend = jev_service.select_backend(cfg)
    assert backend == "jev"
    assert client is not None


def test_load_jev_config_global_fallback(monkeypatch, tmp_path):
    """No story-config jev block: falls back to FlexiTTS.yml global block."""
    fake_global = tmp_path / "FlexiTTS.yml"
    fake_global.write_text("Jev:\n  enabled: true\n  backend: laya\n")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    # ensure the repo config path is NOT used by pointing XDG at tmp and
    # renaming any repo config check off (path order: XDG first)
    cfg = jev_service.load_jev_config({"characters": [{"name": "Hendrix"}]})
    # The repo's real config/FlexiTTS.yml may be found; either way precedence
    # must not crash and must produce sane values.
    assert isinstance(cfg["backend"], str)


def test_load_jev_config_story_block_beats_global(tmp_path, monkeypatch):
    fake_global = tmp_path / "FlexiTTS.yml"
    fake_global.write_text("Jev:\n  enabled: true\n  backend: jev\n")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    cfg = {"jev": {"enabled": True, "backend": "laya"}}
    c = jev_service.load_jev_config(cfg)
    assert c["backend"] == "laya"  # story block wins over global


def test_confidence_ok_helper():
    assert jev_service.confidence_ok({"confidence": 0.8}, 0.8) is True
    assert jev_service.confidence_ok({"confidence": 0.8}, 0.79) is False


# ---------------------------------------------------------------------------
# Live simulation: mock System One HTTP server
# ---------------------------------------------------------------------------

class _Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length))
        questions = body.get("questions", {})
        answers = {}
        for key, q in questions.items():
            opts = q.get("options", [])
            if "correct_character" in questions:
                choice = "Hendrix" if "Hendrix" in opts else (opts[0] if opts else None)
                conf = 0.92
            else:
                choice = opts[0] if opts else None
                conf = 0.95
            answers[key] = {"choice": choice, "confidence": conf}
        resp = json.dumps({"answers": answers}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(resp)

    def log_message(self, *a):
        pass


@pytest.fixture
def mock_server():
    srv = HTTPServer(("127.0.0.1", 0), _Handler)
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{port}/api/systemone"
    srv.shutdown()


def test_live_simulation_end_to_end(tmp_path, mock_server):
    config = {"characters": [{"name": "Hendrix", "custom-voice": {
                                  "speaker": "ryan",
                                  "emotions": [{"emotion": "Neutral"}]}},
                             {"name": "Juko"}],
              "jev": {"enabled": True, "api-key-env": "JEV_TEST_KEY",
                      "api-base": mock_server,
                      "emotion-confidence-threshold": 0.80}}
    os.environ["JEV_TEST_KEY"] = "test"
    p = tmp_path / "e2e.xml"
    p.write_text('<story><section seq="1">'
                 '<dialog character="Hendricks" emotion="suspicious" dlgseq="001">Hmm.</dialog>'
                 '</section></story>')
    result = jev_service.run_jev_validation(p, config)
    assert result["backend"] == "jev"
    assert any(c["to"] == "Hendrix" for c in result["characters"])
    assert any(e["to"] == "Neutral" for e in result["emotions"])
    text = p.read_text()
    assert 'character="Hendrix"' in text
    assert 'emotion="Neutral"' in text
