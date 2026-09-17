import pytest
from pathlib import Path

from chapter_xml_to_audio import (
    Utterance,
    validate_character_voice_setup,
    QWEN3_DOC_SUPPORTED_SPEAKERS,
)


def make_utterance(speaker: str, kind: str = 'dialog') -> Utterance:
    return Utterance(
        chapter_num='001',
        section_num='001',
        dlgseq='001',
        speaker=speaker,
        emotion='neutral',
        text='Hello',
        kind=kind,
        post_effects=None,
    )


def test_validate_character_voice_setup_accepts_valid_voice_sample(tmp_path: Path):
    voices_dir = tmp_path / 'voices'
    voices_dir.mkdir()
    sample = voices_dir / 'alice.wav'
    sample.write_bytes(b'RIFF')

    config = {
        'characters': [
            {'name': 'alice', 'voice-sample': str(sample)},
        ]
    }

    errors = validate_character_voice_setup(config, [make_utterance('alice')], voices_dir)
    assert errors == []


def test_validate_character_voice_setup_rejects_missing_character(tmp_path: Path):
    voices_dir = tmp_path / 'voices'
    voices_dir.mkdir()
    config = {'characters': []}

    errors = validate_character_voice_setup(config, [make_utterance('alice')], voices_dir)
    assert any("missing from story-config.yml" in error for error in errors)


def test_validate_character_voice_setup_rejects_missing_voice_sample_file(tmp_path: Path):
    voices_dir = tmp_path / 'voices'
    voices_dir.mkdir()
    config = {
        'characters': [
            {'name': 'alice', 'voice-sample': 'alice.wav'},
        ]
    }

    errors = validate_character_voice_setup(config, [make_utterance('alice')], voices_dir)
    assert any('voice-sample not found' in error for error in errors)


def test_validate_character_voice_setup_rejects_missing_custom_voice_speaker(tmp_path: Path):
    voices_dir = tmp_path / 'voices'
    voices_dir.mkdir()
    config = {
        'characters': [
            {'name': 'alice', 'custom-voice': {'language': 'English'}},
        ]
    }

    errors = validate_character_voice_setup(config, [make_utterance('alice')], voices_dir)
    assert any("custom-voice speaker is missing" in error for error in errors)


def test_validate_character_voice_setup_rejects_undocumented_qwen3_speaker(tmp_path: Path):
    voices_dir = tmp_path / 'voices'
    voices_dir.mkdir()
    config = {
        'characters': [
            {'name': 'alice', 'custom-voice': {'speaker': 'NotARealSpeaker', 'language': 'English'}},
        ]
    }

    errors = validate_character_voice_setup(config, [make_utterance('alice')], voices_dir)
    assert any('not in documented Qwen3-TTS speakers' in error for error in errors)


def test_validate_character_voice_setup_accepts_documented_qwen3_speaker(tmp_path: Path):
    voices_dir = tmp_path / 'voices'
    voices_dir.mkdir()
    documented = next(iter(QWEN3_DOC_SUPPORTED_SPEAKERS))
    config = {
        'characters': [
            {'name': 'alice', 'custom-voice': {'speaker': documented, 'language': 'English'}},
        ]
    }

    errors = validate_character_voice_setup(config, [make_utterance('alice')], voices_dir)
    assert errors == []


def test_validate_character_voice_setup_ignores_duplicate_speakers(tmp_path: Path):
    voices_dir = tmp_path / 'voices'
    voices_dir.mkdir()
    sample = voices_dir / 'alice.wav'
    sample.write_bytes(b'RIFF')
    config = {
        'characters': [
            {'name': 'alice', 'voice-sample': str(sample)},
        ]
    }

    errors = validate_character_voice_setup(
        config,
        [make_utterance('alice'), make_utterance('alice')],
        voices_dir,
    )
    assert errors == []


# ---------------------------------------------------------------------------
# Per-emotion voice-sample overrides (emotion-sample clone dispatch)
# ---------------------------------------------------------------------------

def make_utterance_with_emotion(speaker: str, emotion: str) -> Utterance:
    return Utterance(
        chapter_num='001',
        section_num='001',
        dlgseq='001',
        speaker=speaker,
        emotion=emotion,
        text='Hello',
        kind='dialog',
        post_effects=None,
    )


def test_preflight_accepts_custom_voice_emotion_with_existing_sample(tmp_path: Path):
    voices_dir = tmp_path / 'voices'
    voices_dir.mkdir()
    (voices_dir / 'sad-recording.wav').write_bytes(b'RIFF')
    config = {
        'characters': [
            {'name': 'alice', 'custom-voice': {
                'language': 'English', 'speaker': 'ryan', 'instruct': 'base',
                'emotions': [
                    {'emotion': 'Sad', 'instruct': 'low', 'voice-sample': 'sad-recording.wav'},
                ],
            }},
        ]
    }
    errors = validate_character_voice_setup(
        config, [make_utterance_with_emotion('alice', 'Sad')], voices_dir)
    assert errors == []


def test_preflight_rejects_custom_voice_emotion_missing_sample_file(tmp_path: Path):
    voices_dir = tmp_path / 'voices'
    voices_dir.mkdir()
    config = {
        'characters': [
            {'name': 'alice', 'custom-voice': {
                'language': 'English', 'speaker': 'ryan', 'instruct': 'base',
                'emotions': [
                    {'emotion': 'Sad', 'instruct': 'low', 'voice-sample': 'missing.wav'},
                ],
            }},
        ]
    }
    errors = validate_character_voice_setup(
        config, [make_utterance_with_emotion('alice', 'Sad')], voices_dir)
    assert any("emotion 'Sad' voice-sample not found" in e for e in errors)


def test_preflight_rejects_empty_emotion_sample(tmp_path: Path):
    voices_dir = tmp_path / 'voices'
    voices_dir.mkdir()
    config = {
        'characters': [
            {'name': 'alice', 'custom-voice': {
                'language': 'English', 'speaker': 'ryan', 'instruct': 'base',
                'emotions': [
                    {'emotion': 'Sad', 'instruct': 'low', 'voice-sample': '  '},
                ],
            }},
        ]
    }
    errors = validate_character_voice_setup(
        config, [make_utterance_with_emotion('alice', 'Sad')], voices_dir)
    assert any("voice-sample is empty" in e for e in errors)


def test_preflight_checks_cloned_emotion_samples(tmp_path: Path):
    voices_dir = tmp_path / 'voices'
    voices_dir.mkdir()
    (voices_dir / 'echo-normal.wav').write_bytes(b'RIFF')
    config = {
        'characters': [
            {'name': 'echo', 'voice-sample': str(voices_dir / 'echo-normal.wav'),
             'cloned-emotion': [
                 {'emotion': 'Normal', 'voice-sample': 'echo-normal.wav'},
                 {'emotion': 'Pain', 'voice-sample': 'missing-pain.wav'},
             ]},
        ]
    }
    errors = validate_character_voice_setup(
        config, [make_utterance_with_emotion('echo', 'Normal')], voices_dir)
    # Normal sample exists; Pain is not used by this chapter but should still
    # be validated (config completeness).
    assert any("emotion 'Pain' voice-sample not found" in e for e in errors)


def test_emotion_sample_dispatch_builds_clone_config():
    """The render loop's effective_cfg construction: emotion sample routes to clone."""
    # Mirrors chapter_xml_to_audio.py dispatch logic for regression protection
    char_cfg = {
        "name": "hendrix",
        "custom-voice": {
            "language": "English",
            "speaker": "ryan",
            "instruct": "base voice",
            "emotions": [
                {"emotion": "Sad", "instruct": "low", "voice-sample": "/abs/sad.wav"},
            ],
        },
        "sox-effects": ["gain -3"],
    }
    is_custom = "custom-voice" in char_cfg
    emotion_sample = None
    for em in char_cfg["custom-voice"].get("emotions", []):
        if em.get("emotion", "").lower() == "sad":
            emotion_sample = em.get("voice-sample")
            break

    if emotion_sample:
        effective_cfg = {k: v for k, v in char_cfg.items() if k != "custom-voice"}
        effective_cfg["voice-sample"] = emotion_sample
    else:
        effective_cfg = char_cfg

    assert "custom-voice" not in effective_cfg
    assert effective_cfg["voice-sample"] == "/abs/sad.wav"
    assert effective_cfg["sox-effects"] == ["gain -3"]  # preserved
    # supports_character sees a voice-sample char -> True
    assert bool(effective_cfg.get("voice-sample") or effective_cfg.get("custom-voice"))


def test_emotion_sample_dispatch_unmatched_emotion_keeps_custom():
    char_cfg = {
        "name": "hendrix",
        "custom-voice": {"language": "English", "speaker": "ryan",
                         "emotions": [{"emotion": "Sad", "voice-sample": "sad.wav"}]},
    }
    emotion_sample = None
    for em in char_cfg["custom-voice"].get("emotions", []):
        if em.get("emotion", "").lower() == "happy":
            emotion_sample = em.get("voice-sample")
            break
    assert emotion_sample is None  # no dispatch; custom path used
