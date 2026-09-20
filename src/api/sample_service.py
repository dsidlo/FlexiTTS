#!/usr/bin/env python3
"""Voice sample upload, validation, and retrieval (Phase 3 of the Character UI plan).

- Uploads land in the story's ``global.voices`` directory, where voice-sample
  references already resolve.
- Integrity/duration probing uses soundfile (libsndfile) first and falls back
  to ffprobe for container formats libsndfile rejects (mp3/ogg).
- All writes go through a size limit and extension whitelist; decoded duration
  is returned for every accepted sample.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from src.api.character_service import (
    CharacterError,
    CharacterNotFoundError,
    CharacterService,
)

SUPPORTED_FORMATS = (".wav", ".mp3", ".ogg")
DEFAULT_MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MiB

_CONTENT_TYPES = {
    ".wav": "audio/wav",
    ".mp3": "audio/mpeg",
    ".ogg": "audio/ogg",
}


class SampleError(CharacterError):
    def __init__(self, message: str, code: str):
        super().__init__(message, code=code)


class UnsupportedFormatError(SampleError):
    def __init__(self, message: str):
        super().__init__(message, code="UNSUPPORTED_FORMAT")


class CorruptAudioError(SampleError):
    def __init__(self, message: str):
        super().__init__(message, code="CORRUPT_AUDIO")


class FileTooLargeError(SampleError):
    def __init__(self, message: str):
        super().__init__(message, code="FILE_TOO_LARGE")


def probe_audio(path: Path) -> Dict[str, Any]:
    """Extract duration/size/format via soundfile, falling back to ffprobe.

    Returns metadata dict: duration, sampleRate, channels, format, sizeBytes.
    Raises CorruptAudioError when the file cannot be decoded by either prober.
    """
    size = path.stat().st_size
    try:
        import soundfile as sf

        info = sf.info(str(path))
        return {
            "duration": round(info.duration, 3),
            "sampleRate": info.samplerate,
            "channels": info.channels,
            "format": str(info.format),
            "sizeBytes": size,
        }
    except Exception:
        pass

    # ffprobe fallback (mp3/ogg or unusual containers)
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        raise CorruptAudioError(f"Cannot decode audio file: {path.name}")

    result = subprocess.run(
        [ffprobe, "-v", "quiet", "-print_format", "json",
         "-show_format", "-show_streams", str(path)],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0:
        raise CorruptAudioError(f"Cannot decode audio file: {path.name}")

    try:
        meta = json.loads(result.stdout)
        fmt = meta.get("format", {})
        streams = meta.get("streams", [])
        audio = next((s for s in streams if s.get("codec_type") == "audio"), {})
        duration = float(fmt.get("duration") or audio.get("duration") or 0)
        rate = int(audio.get("sample_rate") or 0)
        channels = int(audio.get("channels") or 0)
        ext = path.suffix.lstrip(".").upper() or "AUDIO"
        return {
            "duration": round(duration, 3),
            "sampleRate": rate,
            "channels": channels,
            "format": ext,
            "sizeBytes": size,
        }
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
        raise CorruptAudioError(f"Cannot decode audio file: {path.name} ({e})")


class SampleService:
    """Voice sample storage over a story's voices directory."""

    def __init__(self, stories_dir: Path, max_upload_bytes: int = DEFAULT_MAX_UPLOAD_BYTES):
        import sys as _sys
        script_dir = Path(__file__).resolve().parent.parent / "scripts"
        if str(script_dir) not in _sys.path:
            _sys.path.insert(0, str(script_dir))
        from src.api.character_service import CharacterService

        self.character_service = CharacterService(stories_dir)
        self.max_upload_bytes = max_upload_bytes

    # ------------------------------------------------------------------ #
    # Path helpers
    # ------------------------------------------------------------------ #

    def _story_path(self, story_id: str) -> Path:
        return self.character_service._story_path(story_id)

    def _voices_dir(self, story_id: str) -> Path:
        story_path = self._story_path(story_id)
        config_path = story_path / "story-config.yml"
        if not config_path.exists():
            raise CharacterNotFoundError(f"Story config not found for: {story_id}")
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        voices_rel = str((config.get("global") or {}).get("voices", "")).strip()
        voices_dir = story_path / (voices_rel or "story-voice-refs")
        return voices_dir

    def _resolve_character_and_emotion(self, story_id: str, character_id: str,
                                       emotion_id: Optional[str],
                                       data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Return the config entry owning the sample (character or emotion).

        When ``data`` is provided, resolution happens inside that (possibly
        ruamel) tree so mutations persist when it is committed.
        """
        if data is None:
            data = self.character_service._load(story_id)
        character = self.character_service._find_character(data, character_id)

        if emotion_id:
            key = "custom-voice" if character.get("custom-voice") else "cloned-emotion"
            if key == "custom-voice":
                emotions = (character.get("custom-voice") or {}).get("emotions") or []
            else:
                emotions = character.get("cloned-emotion") or []
            for em in emotions:
                if str(em.get("emotion") or em.get("name") or "").strip().lower() == emotion_id.strip().lower():
                    return em
            raise CharacterNotFoundError(
                f"Emotion not found: {emotion_id} for character {character_id}"
            )
        return character

    def _current_sample_name(self, owner: Dict[str, Any]) -> Optional[str]:
        sample = owner.get("voice-sample")
        if isinstance(sample, str) and sample.strip():
            return sample.strip()
        return None

    # ------------------------------------------------------------------ #
    # Phase 3.1: upload
    # ------------------------------------------------------------------ #

    def upload_sample(self, story_id: str, character_id: str,
                      emotion_id: Optional[str], filename: str,
                      content: bytes,
                      max_bytes: Optional[int] = None) -> Dict[str, Any]:
        """Store an uploaded sample and wire it into the config entry."""
        limit = max_bytes if max_bytes is not None else self.max_upload_bytes
        name = (filename or "").strip()
        ext = Path(name).suffix.lower()
        if ext not in SUPPORTED_FORMATS:
            raise UnsupportedFormatError(
                f"Unsupported format '{ext or '(none)'}'. Supported: "
                f"{', '.join(SUPPORTED_FORMATS)}"
            )
        if not name or "/" in name or "\\" in name or ".." in name:
            raise SampleError(f"Invalid filename: {filename}", code="INVALID_FILENAME")

        if len(content) > limit:
            raise FileTooLargeError(
                f"File exceeds size limit: {len(content)} bytes > {limit} bytes"
            )

        voices_dir = self._voices_dir(story_id)
        voices_dir.mkdir(parents=True, exist_ok=True)

        # Store under <character>[_<emotion>]_<filename> to avoid collisions
        # between characters sharing a sample name.
        stem = Path(name).stem
        owner = self._resolve_character_and_emotion(story_id, character_id, emotion_id)
        owner_label = "".join(
            ch for ch in (character_id + ("_" + emotion_id if emotion_id else "")).replace(" ", "_")
            if ch.isalnum() or ch in "_-"
        ).strip("_") or "sample"
        target_name = f"{owner_label}_{stem}{ext}"
        target_path = voices_dir / target_name

        # Validate integrity BEFORE storing: decode from a temp file
        tmp_path = voices_dir / f".tmp-{target_name}"
        try:
            tmp_path.write_bytes(content)
            metadata = probe_audio(tmp_path)
        finally:
            if tmp_path.exists():
                tmp_path.unlink()

        # Integrity OK: store the file (overwrite allowed - same logical sample)
        with open(target_path, "wb") as f:
            f.write(content)

        original_text = (self._story_path(story_id) / "story-config.yml").read_text(encoding="utf-8")
        config_path = self._story_path(story_id) / "story-config.yml"
        from src.api.character_service import _config_lock
        with _config_lock(config_path):
            data, ryaml = self.character_service._load_yaml_public(config_path)
            try:
                owner_fresh = self._resolve_character_and_emotion(
                    story_id, character_id, emotion_id, data=data)
                owner_fresh["voice-sample"] = target_name
                self.character_service._commit_yaml_public(config_path, data, ryaml, original_text)
            except Exception:
                # Roll the stored file back out if config update fails
                if target_path.exists():
                    target_path.unlink()
                raise

        return {
            "filename": target_name,
            "path": str(target_path),
            "sizeBytes": metadata["sizeBytes"],
            "duration": metadata["duration"],
            "sampleRate": metadata.get("sampleRate"),
            "channels": metadata.get("channels"),
            "format": metadata.get("format"),
        }

    # ------------------------------------------------------------------ #
    # Phase 3.2/3.3: metadata and streaming
    # ------------------------------------------------------------------ #

    def get_sample_metadata(self, story_id: str, character_id: str,
                            emotion_id: Optional[str]) -> Dict[str, Any]:
        owner = self._resolve_character_and_emotion(story_id, character_id, emotion_id)
        sample = self._current_sample_name(owner)
        if not sample:
            raise CharacterNotFoundError(
                f"Character '{character_id}' has no voice-sample configured"
            )
        voices_dir = self._voices_dir(story_id)
        sample_path = Path(sample)
        if sample_path.is_absolute():
            resolved = sample_path
        else:
            resolved = voices_dir / sample_path
        if not resolved.exists():
            raise CharacterNotFoundError(f"Sample file not found: {sample}")
        metadata = probe_audio(resolved)
        metadata["filename"] = sample
        metadata["path"] = str(resolved)
        return metadata

    def get_sample_file(self, story_id: str, character_id: str,
                        emotion_id: Optional[str]) -> Path:
        metadata = self.get_sample_metadata(story_id, character_id, emotion_id)
        path = Path(metadata["path"])
        ext = path.suffix.lower()
        # Validate again for streaming: refuse undecodable files
        probe_audio(path)
        return path

    @staticmethod
    def content_type_for(path: Path) -> str:
        return _CONTENT_TYPES.get(path.suffix.lower(), "application/octet-stream")