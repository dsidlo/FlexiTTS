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
