#!/usr/bin/env python3
"""Character and emotion CRUD operations over story-config.yml files.

Implements Phase 2.1 (Character CRUD) and Phase 2.2 (Emotion Management) of
docs/FlexiTTS Create Character UI-Plan.md. All operations:

- Resolve the story by its directory id through ConfigManager (security:
  path-traversal guarded).
- Load and rewrite ``story-config.yml`` with a ruamel round-trip so comments
  and formatting survive edits.
- Validate the resulting config after every mutation; a failed validation
  rolls the file back to its pre-operation state.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List

import yaml

try:
    from ruamel.yaml import YAML

    _HAS_RUAMEL = True
except ImportError:  # pragma: no cover - ruamel is in requirements
    _HAS_RUAMEL = False


class CharacterError(Exception):
    """Base error for character operations."""

    def __init__(self, message: str, code: str = "CHARACTER_ERROR"):
        super().__init__(message)
        self.code = code


class CharacterNotFoundError(CharacterError):
    def __init__(self, message: str):
        super().__init__(message, code="CHARACTER_NOT_FOUND")


class CharacterExistsError(CharacterError):
    def __init__(self, message: str):
        super().__init__(message, code="CHARACTER_EXISTS")


class EmotionNotFoundError(CharacterError):
    def __init__(self, message: str):
        super().__init__(message, code="EMOTION_NOT_FOUND")


class EmotionExistsError(CharacterError):
    def __init__(self, message: str):
        super().__init__(message, code="EMOTION_EXISTS")


class ValidationError(CharacterError):
    def __init__(self, message: str):
        super().__init__(message, code="CHARACTER_VALIDATION_FAILED")


def _load_yaml(path: Path):
    """Load YAML preserving comments. Returns (data, ruamel_yaml or None)."""
    if _HAS_RUAMEL:
        ryaml = YAML()
        ryaml.preserve_quotes = True
        ryaml.indent(mapping=2, sequence=4, offset=2)
        ryaml.width = 4096
        with open(path, "r", encoding="utf-8") as f:
            return ryaml.load(f), ryaml
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f), None


def _save_yaml(path: Path, data: Any, ryaml) -> None:
    """Write YAML preserving comments when ruamel is available."""
    with open(path, "w", encoding="utf-8") as f:
        if ryaml is not None:
            ryaml.dump(data, f)
        else:
            yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True)


def _emotion_name(em: Dict[str, Any]) -> str:
    """Canonical emotion name of an entry ('emotion' key, 'name' fallback)."""
    return str(em.get("emotion") or em.get("name") or "").strip()


def _emotion_list(char: Dict[str, Any], key: str) -> List[Dict[str, Any]]:
    """Return (creating if absent) the emotion list for the character."""
    if key == "custom-voice":
        cv = char.get("custom-voice")
        if cv is None or not isinstance(cv, dict):
            raise CharacterError(
                f"Character '{char.get('name', '?')}' has no custom-voice; "
                "emotions require a custom-voice (built-in speaker) character.",
                code="VOICE_TYPE_MISMATCH",
            )
        if not isinstance(cv.get("emotions"), list):
            cv["emotions"] = []
        return cv["emotions"]
    if key == "cloned-emotion":
        if not isinstance(char.get("cloned-emotion"), list):
            char["cloned-emotion"] = []
        return char["cloned-emotion"]
    if not isinstance(char.get("emotions"), list):
        char["emotions"] = []
    return char["emotions"]


class CharacterService:
    """CRUD operations for characters and emotions in story-config.yml."""

    def __init__(self, stories_dir: Path):
        self.stories_dir = Path(stories_dir)

    # ------------------------------------------------------------------ #
    # Path helpers
    # ------------------------------------------------------------------ #

    def _story_path(self, story_id: str) -> Path:
        """Resolve a story id to its directory with containment checks.

        Accepts either a bare directory name ("Story-Entanglement") or an
        absolute path inside the stories directory. The absolute form arrives
        because Electron's executePythonScript prepends stories-dir to args
        that start with the story prefix.
        """
        stories_root = self.stories_dir.resolve()
        if not story_id or ".." in story_id:
            raise CharacterError(f"Invalid story id: {story_id}", code="INVALID_STORY_ID")
        story_path = (self.stories_dir / story_id).resolve()
        # Containment: resolved path must be a direct child of stories_dir
        if story_path.parent != stories_root:
            raise CharacterError(f"Invalid story id: {story_id}", code="INVALID_STORY_ID")
        if not story_path.is_dir():
            raise CharacterNotFoundError(f"Story not found: {story_id}")
        return story_path

    def _config_path(self, story_id: str) -> Path:
        path = self._story_path(story_id) / "story-config.yml"
        if not path.exists():
            raise CharacterNotFoundError(f"Story config not found for: {story_id}")
        return path

    # ------------------------------------------------------------------ #
    # Core load/save with rollback
    # ------------------------------------------------------------------ #

    def _load(self, story_id: str) -> Any:
        data, _ = _load_yaml(self._config_path(story_id))
        return data

    # Public wrappers used by sibling services (e.g. SampleService) that
    # operate on the same config file with their own ownership resolution.
    def _load_yaml_public(self, path: Path):
        return _load_yaml(path)

    def _commit_yaml_public(self, path: Path, data: Any, ryaml, original_text: str) -> None:
        self._commit(path, data, ryaml, original_text)

    def _commit(self, path: Path, data: Any, ryaml, original_text: str) -> None:
        """Save, validate, and roll back to original text on failure."""
        _save_yaml(path, data, ryaml)
        script_dir = Path(__file__).resolve().parent.parent / "scripts"
        import sys as _sys
        import io as _io
        import contextlib as _contextlib
        if str(script_dir) not in _sys.path:
            _sys.path.insert(0, str(script_dir))
        import validate_config as vc  # noqa: E402

        # Suppress validate_config's stdout so JSON bridge output stays clean
        buf = _io.StringIO()
        with _contextlib.redirect_stdout(buf):
            valid = vc.validate_config(str(path))

        if not valid:
            with open(path, "w", encoding="utf-8") as f:
                f.write(original_text)
            raise ValidationError(
                "Change rejected: resulting story-config.yml fails validation "
                "(rolled back)"
            )

    # ------------------------------------------------------------------ #
    # Character lookup
    # ------------------------------------------------------------------ #

    @staticmethod
    def _find_character(data: Dict[str, Any], character_id: str) -> Dict[str, Any]:
        characters = data.get("characters", [])
        for char in characters:
            if str(char.get("name", "")).strip().lower() == character_id.strip().lower():
                return char
        raise CharacterNotFoundError(f"Character not found: {character_id}")

    @staticmethod
    def _validate_unique_name(data: Dict[str, Any], name: str, exclude: str = None):
        norm = name.strip().lower()
        for char in data.get("characters", []):
            existing = str(char.get("name", "")).strip().lower()
            if existing == norm and (exclude is None or existing != exclude.strip().lower()):
                raise CharacterExistsError(f"Character name already in use: {name}")

    @staticmethod
    def _validate_language(language: str):
        # Supported language list per Qwen3-TTS docs surfaced in the UI
        supported = {lang.lower() for lang in supported_languages()}
        if not language or language.strip().lower() not in supported:
            raise CharacterError(
                f"Unsupported language: {language}. Supported: {', '.join(sorted(supported_languages()))}",
                code="INVALID_LANGUAGE",
            )

    # ------------------------------------------------------------------ #
    # Phase 2.1: Character CRUD
    # ------------------------------------------------------------------ #

    def create_character(self, story_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """POST /api/characters - create with unique-name and language checks."""
        name = str(payload.get("name", "")).strip()
        if not name:
            raise CharacterError("Character name is required", code="NAME_REQUIRED")
        language = str(payload.get("language", "") or "").strip()
        self._validate_language(language)

        path = self._config_path(story_id)
        original_text = path.read_text(encoding="utf-8")
        data, ryaml = _load_yaml(path)

        self._validate_unique_name(data, name)
        if not isinstance(data.get("characters"), list):
            data["characters"] = []

        character: Dict[str, Any] = {"name": name}
        voice = payload.get("voice") or {}
        voice_type = str(payload.get("voiceType") or "").strip().lower()

        if voice_type in ("custom", "custom-voice", "qwen3-tts-custom-voice"):
            speaker = str(voice.get("speaker", "")).strip()
            if not speaker:
                raise CharacterError("custom-voice requires a speaker", code="SPEAKER_REQUIRED")
            character["custom-voice"] = {
                "language": language,
                "speaker": speaker,
                "instruct": str(voice.get("instruct", "") or ""),
            }
            emotions = voice.get("emotions")
            if isinstance(emotions, list) and emotions:
                character["custom-voice"]["emotions"] = emotions
            else:
                # Default Neutral emotion so the character has a usable baseline
                instruct = character["custom-voice"]["instruct"]
                neutral = {"emotion": "Neutral"}
                if instruct:
                    neutral["instruct"] = instruct
                character["custom-voice"]["emotions"] = [neutral]
        elif voice_type in ("sample", "voice-sample", "qwen3-tts-voice-design"):
            sample = str(voice.get("voiceSample", voice.get("voice-sample", "")) or "").strip()
            if not sample:
                raise CharacterError("sample voice requires a voice-sample", code="SAMPLE_REQUIRED")
            character["voice-sample"] = sample
        # voiceType absent: minimal character (name + language via voice later)

        data["characters"].append(character)
        self._commit(path, data, ryaml, original_text)
        return deepcopy(character)

    def get_character(self, story_id: str, character_id: str) -> Dict[str, Any]:
        """GET /api/characters/{id}"""
        data = self._load(story_id)
        return deepcopy(self._find_character(data, character_id))

    def list_characters(self, story_id: str) -> List[Dict[str, Any]]:
        """GET /api/characters"""
        data = self._load(story_id)
        characters = data.get("characters", [])
        return deepcopy(characters) if isinstance(characters, list) else []

    def update_character(self, story_id: str, character_id: str,
                         payload: Dict[str, Any]) -> Dict[str, Any]:
        """PUT /api/characters/{id} - basic info and sox-effects updates."""
        path = self._config_path(story_id)
        original_text = path.read_text(encoding="utf-8")
        data, ryaml = _load_yaml(path)
        character = self._find_character(data, character_id)

        if "name" in payload:
            new_name = str(payload["name"]).strip()
            if not new_name:
                raise CharacterError("Character name cannot be empty", code="NAME_REQUIRED")
            self._validate_unique_name(data, new_name, exclude=character.get("name", ""))
            character["name"] = new_name

        if "description" in payload:
            character["description"] = str(payload["description"] or "")

        if "soxEffects" in payload:
            effects = payload["soxEffects"]
            if effects is None:
                character.pop("sox-effects", None)
            elif isinstance(effects, list):
                character["sox-effects"] = [str(e) for e in effects]
            else:
                raise CharacterError("soxEffects must be a list of strings", code="INVALID_SOX_EFFECTS")

        if "sox-effects" in payload:
            effects = payload["sox-effects"]
            if effects is None:
                character.pop("sox-effects", None)
            elif isinstance(effects, list):
                character["sox-effects"] = [str(e) for e in effects]
            else:
                raise CharacterError("sox-effects must be a list of strings", code="INVALID_SOX_EFFECTS")

        if "customVoice" in payload and payload["customVoice"] is not None:
            cv = character.get("custom-voice")
            if not isinstance(cv, dict):
                language = str(payload.get("language", "English") or "English")
                self._validate_language(language)
                cv = {"language": language, "speaker": "", "instruct": ""}
                character["custom-voice"] = cv
            cv_payload = payload["customVoice"]
            if "language" in cv_payload:
                self._validate_language(str(cv_payload["language"]))
                cv["language"] = str(cv_payload["language"])
            if "speaker" in cv_payload:
                cv["speaker"] = str(cv_payload["speaker"] or "").strip()
            if "instruct" in cv_payload:
                cv["instruct"] = str(cv_payload["instruct"] or "")

        if "dialogEffects" in payload:
            effects = payload["dialogEffects"]
            if effects is None:
                character.pop("dialog-effects", None)
            elif isinstance(effects, list):
                character["dialog-effects"] = [str(e) for e in effects]
            else:
                raise CharacterError("dialogEffects must be a list of names", code="INVALID_DIALOG_EFFECTS")

        self._commit(path, data, ryaml, original_text)
        return deepcopy(character)

    def delete_character(self, story_id: str, character_id: str,
                         payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """DELETE /api/characters/{id} - warn on dependent dialogs."""
        payload = payload or {}
        dependent_dialogs = int(payload.get("dependentDialogs", 0) or 0)
        path = self._config_path(story_id)
        original_text = path.read_text(encoding="utf-8")
        data, ryaml = _load_yaml(path)
        characters = data.get("characters", [])

        target = None
        for char in characters:
            if str(char.get("name", "")).strip().lower() == character_id.strip().lower():
                target = char
                break
        if target is None:
            raise CharacterNotFoundError(f"Character not found: {character_id}")

        affected = dependent_dialogs
        characters.remove(target)
        self._commit(path, data, ryaml, original_text)
        return {"deleted": deepcopy(target), "affectedDialogs": affected}

    # ------------------------------------------------------------------ #
    # Phase 2.2: Emotion management
    # ------------------------------------------------------------------ #

    @staticmethod
    def _norm(name: str) -> str:
        return name.strip().lower()

    def _find_emotion(self, emotions: List[Dict[str, Any]], emotion_id: str):
        for idx, em in enumerate(emotions):
            name = str(em.get("emotion") or em.get("name") or "").strip()
            if name.lower() == emotion_id.strip().lower():
                return idx, em
        raise EmotionNotFoundError(f"Emotion not found: {emotion_id}")

    def _check_emotion_unique(self, emotions: List[Dict[str, Any]], name: str,
                              exclude_idx: int = None):
        norm = name.strip().lower()
        for idx, em in enumerate(emotions):
            if idx == exclude_idx:
                continue
            existing = str(em.get("emotion") or em.get("name") or "").strip().lower()
            if existing == norm:
                raise EmotionExistsError(f"Emotion name already in use: {name}")

    def add_emotion(self, story_id: str, character_id: str,
                    payload: Dict[str, Any]) -> Dict[str, Any]:
        """POST /api/characters/{id}/emotions"""
        name = str(payload.get("emotion") or payload.get("name") or "").strip()
        if not name:
            raise CharacterError("Emotion name is required", code="EMOTION_NAME_REQUIRED")

        path = self._config_path(story_id)
        original_text = path.read_text(encoding="utf-8")
        data, ryaml = _load_yaml(path)
        character = self._find_character(data, character_id)

        # Emotions live under custom-voice for custom voices; for sample-based
        # characters they live in cloned-emotion (one sample per emotion).
        list_key = "custom-voice" if character.get("custom-voice") else "cloned-emotion"
        emotions = _emotion_list(character, list_key)
        self._check_emotion_unique(emotions, name)

        entry: Dict[str, Any] = {"emotion": name}
        if "instruct" in payload:
            entry["instruct"] = str(payload["instruct"] or "")
        if "soxEffects" in payload and payload["soxEffects"] is not None:
            if not isinstance(payload["soxEffects"], list):
                raise CharacterError("soxEffects must be a list", code="INVALID_SOX_EFFECTS")
            entry["sox-effects"] = [str(e) for e in payload["soxEffects"]]

        emotions.append(entry)
        self._commit(path, data, ryaml, original_text)
        return deepcopy(entry)

    def update_emotion(self, story_id: str, character_id: str, emotion_id: str,
                       payload: Dict[str, Any]) -> Dict[str, Any]:
        """PUT /api/characters/{id}/emotions/{emotion_id}"""
        path = self._config_path(story_id)
        original_text = path.read_text(encoding="utf-8")
        data, ryaml = _load_yaml(path)
        character = self._find_character(data, character_id)
        key = "custom-voice" if character.get("custom-voice") else "cloned-emotion"
        key = "custom-voice" if character.get("custom-voice") else "cloned-emotion"
        emotions = _emotion_list(character, key)
        idx, entry = self._find_emotion(emotions, emotion_id)

        if "instruct" in payload:
            entry["instruct"] = str(payload["instruct"] or "")
        if "soxEffects" in payload:
            if payload["soxEffects"] is None:
                entry.pop("sox-effects", None)
            elif isinstance(payload["soxEffects"], list):
                entry["sox-effects"] = [str(e) for e in payload["soxEffects"]]
            else:
                raise CharacterError("soxEffects must be a list", code="INVALID_SOX_EFFECTS")

        if "emotion" in payload or "name" in payload:
            new_name = str(payload.get("emotion") or payload.get("name") or "").strip()
            if not new_name:
                raise CharacterError("Emotion name cannot be empty", code="EMOTION_NAME_REQUIRED")
            self._check_emotion_unique(emotions, new_name, exclude_idx=idx)
            if "emotion" in entry:
                entry["emotion"] = new_name
            else:
                entry["name"] = new_name

        self._commit(path, data, ryaml, original_text)
        return deepcopy(entry)

    def delete_emotion(self, story_id: str, character_id: str, emotion_id: str,
                       allow_delete_last: bool = False) -> Dict[str, Any]:
        """DELETE /api/characters/{id}/emotions/{emotion_id}"""
        path = self._config_path(story_id)
        original_text = path.read_text(encoding="utf-8")
        data, ryaml = _load_yaml(path)
        character = self._find_character(data, character_id)
        key = "custom-voice" if character.get("custom-voice") else "cloned-emotion"
        emotions = _emotion_list(character, key)
        idx, entry = self._find_emotion(emotions, emotion_id)

        if len(emotions) == 1 and not allow_delete_last:
            raise CharacterError(
                "Cannot delete the last emotion (set allowDeleteLast to override)",
                code="LAST_EMOTION_PROTECTED",
            )

        emotions.pop(idx)
        self._commit(path, data, ryaml, original_text)
        return {"deleted": deepcopy(entry), "remainingCount": len(emotions)}

    def reorder_emotions(self, story_id: str, character_id: str,
                         ordered_names: List[str]) -> List[Dict[str, Any]]:
        """PUT /api/characters/{id}/emotions/reorder - accepts ordered emotion ids."""
        if not isinstance(ordered_names, list) or not ordered_names:
            raise CharacterError("orderedEmotions must be a non-empty list of names",
                                 code="INVALID_ORDER")

        path = self._config_path(story_id)
        original_text = path.read_text(encoding="utf-8")
        data, ryaml = _load_yaml(path)
        character = self._find_character(data, character_id)
        key = "custom-voice" if character.get("custom-voice") else "cloned-emotion"
        emotions = _emotion_list(character, key)
        norm = self._norm
        requested = [norm(n) for n in ordered_names]
        existing = [norm(str(em.get("emotion") or em.get("name") or "")) for em in emotions]

        if sorted(requested) != sorted(existing):
            raise CharacterError(
                "orderedEmotions must be a permutation of the character's emotions",
                code="INVALID_ORDER",
            )

        by_name = {norm(str(em.get("emotion") or em.get("name") or "")): em for em in emotions}
        reordered = [by_name[n] for n in requested]
        emotions[:] = reordered
        self._commit(path, data, ryaml, original_text)
        return deepcopy(reordered)

    def set_default_emotion(self, story_id: str, character_id: str,
                            emotion_id: str) -> Dict[str, Any]:
        """PUT /api/characters/{id}/emotions/{emotion_id}/default.

        Default = first emotion in the list (render uses index 0); this moves
        the requested emotion to the front. No extra flag is written because
        the schema forbids unknown keys.
        """
        path = self._config_path(story_id)
        original_text = path.read_text(encoding="utf-8")
        data, ryaml = _load_yaml(path)
        character = self._find_character(data, character_id)
        key = "custom-voice" if character.get("custom-voice") else "cloned-emotion"
        emotions = _emotion_list(character, key)
        idx, entry = self._find_emotion(emotions, emotion_id)

        emotions.pop(idx)
        emotions.insert(0, entry)
        self._commit(path, data, ryaml, original_text)
        return deepcopy(entry)


def supported_languages() -> List[str]:
    """Languages supported by Qwen3-TTS voices (documented in config comments)."""
    return ["English", "Chinese", "Japanese", "Korean"]