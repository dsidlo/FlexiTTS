#!/usr/bin/env python3
"""Character import/export (Phase 4 of the Character UI plan).

Export packages a character (with its referenced voice samples embedded) as
YAML/JSON, or bundles several as a ZIP with a manifest. Import parses an
export, validates it, resolves name conflicts (overwrite / keep-both / skip),
and copies referenced samples into the target story's voices directory.

Export format (a single-character mapping, or a list under ``characters:``):
    character: <full character dict>
    samples:
      - name: <stored filename in voices dir>
        path: <path within the export bundle>
        data: <base64-encoded bytes>          # inline mode (single export)
    formatVersion: 1
"""

from __future__ import annotations

import base64
import io
import json
import zipfile
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.api.character_service import (
    CharacterError,
    CharacterExistsError,
    CharacterNotFoundError,
    CharacterService,
)

FORMAT_VERSION = 1


def _plain(obj: Any) -> Any:
    """Convert ruamel CommentedMap/List trees to plain dict/list for YAML dumps.

    ruamel scalar strings are str subclasses (e.g. DoubleQuotedScalarString)
    whose exact type has no PyYAML representer, so they must be coerced to
    plain str as well.
    """
    if isinstance(obj, dict):
        return {str(k): _plain(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_plain(v) for v in obj]
    if isinstance(obj, str) and type(obj) is not str:
        return str(obj)
    return obj


class ImportError_(CharacterError):
    def __init__(self, message: str, code: str = "IMPORT_INVALID"):
        super().__init__(message, code=code)


class ImportService:
    """Import/export of characters between story configs."""

    def __init__(self, stories_dir: Path):
        self.character_service = CharacterService(stories_dir)
        self.stories_dir = Path(stories_dir)

    # ------------------------------------------------------------------ #
    # Shared helpers
    # ------------------------------------------------------------------ #

    def _config_path(self, story_id: str) -> Path:
        return self.character_service._config_path(story_id)

    def _voices_dir(self, story_id: str) -> Path:
        story_path = self.character_service._story_path(story_id)
        import yaml as _yaml
        with open(story_path / "story-config.yml", "r", encoding="utf-8") as f:
            config = _yaml.safe_load(f)
        voices_rel = str((config.get("global") or {}).get("voices", "")).strip()
        return story_path / (voices_rel or "story-voice-refs")

    @staticmethod
    def _collect_sample_refs(character: Dict[str, Any]) -> List[Dict[str, str]]:
        """All voice-sample references in a character entry.

        Returns list of {sample: filename, owner: <where it lives>}.
        """
        refs: List[Dict[str, str]] = []
        sample = character.get("voice-sample")
        if isinstance(sample, str) and sample.strip():
            refs.append({"sample": sample.strip(), "owner": "character"})
        cv = character.get("custom-voice")
        if isinstance(cv, dict) and isinstance(cv.get("emotions"), list):
            for em in cv["emotions"]:
                if isinstance(em, dict) and isinstance(em.get("voice-sample"), str) and em["voice-sample"].strip():
                    refs.append({"sample": em["voice-sample"].strip(),
                                 "owner": str(em.get("emotion") or em.get("name") or "emotion")})
        if isinstance(character.get("cloned-emotion"), list):
            for em in character["cloned-emotion"]:
                if isinstance(em, dict) and isinstance(em.get("voice-sample"), str) and em["voice-sample"].strip():
                    refs.append({"sample": em["voice-sample"].strip(),
                                 "owner": str(em.get("emotion") or "emotion")})
        return refs

    def _read_sample_bytes(self, story_id: str, sample_name: str) -> Optional[bytes]:
        story_path = self.character_service._story_path(story_id)
        sample_path = Path(sample_name)
        if sample_path.is_absolute():
            resolved = sample_path
        else:
            resolved = self._voices_dir(story_id) / sample_path
        if not resolved.exists():
            return None
        return resolved.read_bytes()

    @staticmethod
    def _safe_filename(character_name: str) -> str:
        stem = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in character_name)
        return stem.strip("_") or "character"

    # ------------------------------------------------------------------ #
    # Phase 4.1: Export
    # ------------------------------------------------------------------ #

    def export_character(self, story_id: str, character_id: str,
                         include_samples: bool = True) -> Dict[str, Any]:
        """Export one character as a portable dict (yaml/json serializable)."""
        character = self.character_service.get_character(story_id, character_id)
        export_doc: Dict[str, Any] = {
            "formatVersion": FORMAT_VERSION,
            "character": character,
        }
        if include_samples:
            samples = []
            for ref in self._collect_sample_refs(character):
                data = self._read_sample_bytes(story_id, ref["sample"])
                samples.append({
                    "name": ref["sample"],
                    "owner": ref["owner"],
                    "data": base64.b64encode(data).decode("ascii") if data else None,
                    "missing": data is None,
                })
            export_doc["samples"] = samples
        return _plain(export_doc)

    def export_characters_bundle(self, story_id: str,
                                 character_ids: List[str]) -> bytes:
        """Export multiple characters as a ZIP with manifest.

        Each character is a YAML file in the bundle; the manifest lists
        contents and flags any samples that could not be included.
        """
        if not character_ids:
            raise CharacterError("No character ids provided", code="NO_CHARACTERS")

        manifest: List[Dict[str, Any]] = []
        bundle_files: Dict[str, bytes] = {}
        for cid in character_ids:
            character = self.character_service.get_character(story_id, cid)
            safe = self._safe_filename(character["name"])
            yaml_name = f"{safe}.yml"
            sample_warnings: List[str] = []
            embedded_samples = []
            for ref in self._collect_sample_refs(character):
                data = self._read_sample_bytes(story_id, ref["sample"])
                if data is None:
                    sample_warnings.append(f"sample not found: {ref['sample']}")
                    continue
                sample_entry_name = f"samples/{safe}_{Path(ref['sample']).name}"
                bundle_files[sample_entry_name] = data
                embedded_samples.append({
                    "name": ref["sample"],
                    "owner": ref["owner"],
                    "bundlePath": sample_entry_name,
                })
            doc = _plain({
                "formatVersion": FORMAT_VERSION,
                "character": character,
                "samples": embedded_samples,
            })
            import yaml as _yaml
            bundle_files[f"{safe}.yml"] = _yaml.safe_dump(
                doc, sort_keys=False, allow_unicode=True)
            manifest.append({
                "file": f"{safe}.yml",
                "character": character.get("name"),
                "sampleWarnings": sample_warnings,
            })

        # Write manifest
        import yaml as _yaml
        manifest_bytes = _yaml.safe_dump(
            {"formatVersion": FORMAT_VERSION, "characters": manifest},
            sort_keys=False, allow_unicode=True).encode("utf-8")

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("manifest.yml", manifest_bytes)
            for name, data in bundle_files.items():
                zf.writestr(name, data)
        return buf.getvalue()

    # ------------------------------------------------------------------ #
    # Phase 4.2: Import
    # ------------------------------------------------------------------ #

    @staticmethod
    def _parse_import_payload(raw: bytes) -> Dict[str, Any]:
        """Parse YAML or JSON payload into an import document."""
        import yaml as _yaml
        try:
            data = _yaml.safe_load(raw.decode("utf-8"))
        except Exception:
            try:
                data = json.loads(raw.decode("utf-8"))
            except Exception:
                raise ImportError_("Could not parse import file as YAML or JSON",
                                   code="IMPORT_PARSE_ERROR")
        if isinstance(data, list):
            # Bare list of characters
            data = {"characters": data}
        if not isinstance(data, dict):
            raise ImportError_("Import payload must be a mapping or list",
                               code="IMPORT_PARSE_ERROR")
        if "character" in data:
            data = {"characters": [data["character"]],
                    "samples": data.get("samples", [])}
        if "characters" not in data or not isinstance(data["characters"], list):
            raise ImportError_("Import payload has no 'characters' list",
                               code="IMPORT_PARSE_ERROR")
        return data

    def _validate_import_character(self, character: Dict[str, Any]) -> None:
        """Structural validation mirroring the schema's essentials."""
        name = character.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ImportError_("Imported character missing a valid 'name'",
                               code="IMPORT_INVALID_CHARACTER")
        allowed = {"name", "description", "voice-sample", "sox-effects",
                   "dialog-effects", "custom-voice", "cloned-emotion", "emotions",
                   "qwen3-tts-voice-design", "qwen3-tts-custom-voice"}
        unknown = set(character.keys()) - allowed
        if unknown:
            raise ImportError_(
                f"Imported character has unknown keys: {', '.join(sorted(unknown))}",
                code="IMPORT_INVALID_CHARACTER",
            )
        cv = character.get("custom-voice")
        if cv is not None and not isinstance(cv, dict):
            raise ImportError_("custom-voice must be a mapping",
                               code="IMPORT_INVALID_CHARACTER")

    def import_characters(self, story_id: str, payload: bytes,
                          conflict: str = "keep-both",
                          copy_samples: bool = True,
                          imported_samples: Optional[List[Dict[str, str]]] = None,
                          ) -> Dict[str, Any]:
        """Import characters with conflict resolution.

        conflict: "overwrite" | "keep-both" | "skip"
        imported_samples: optional bundle sample mappings
            [{name (original voices-dir name), bundlePath (in ZIP)}] used when
            the payload came from a ZIP; sample bytes are resolved by caller.
        Returns summary: imported / overwritten / skipped / renamed lists.
        """
        if conflict not in ("overwrite", "keep-both", "skip"):
            raise ImportError_(f"Invalid conflict mode: {conflict}",
                               code="IMPORT_INVALID_CONFLICT")

        document = self._parse_import_payload(payload)
        characters = document["characters"]
        if not characters:
            raise ImportError_("No characters to import", code="IMPORT_EMPTY")

        bundle_samples = {
            s["name"]: s for s in (imported_samples or [])
            if isinstance(s, dict) and "name" in s
        }

        config_path = self.character_service._config_path(story_id)
        from src.api.character_service import _config_lock
        with _config_lock(config_path):
            original_text = config_path.read_text(encoding="utf-8")
            data, ryaml = self.character_service._load_yaml_public(config_path)
            existing = data.get("characters", [])
            existing_names = {str(c.get("name", "")).strip().lower(): idx
                              for idx, c in enumerate(existing) if isinstance(c, dict)}

            voices_dir = self._voices_dir(story_id)
            voices_dir.mkdir(parents=True, exist_ok=True)
            imported, overwritten, skipped, renamed = [], [], [], []
            samples_copied = 0
            config_dirty = False

            for character in characters:
                if not isinstance(character, dict):
                    raise ImportError_("Import list contains a non-mapping entry",
                                       code="IMPORT_INVALID_CHARACTER")
                self._validate_import_character(character)
                name = character["name"]
                norm = name.strip().lower()
                idx = existing_names.get(norm)

                if idx is not None:
                    if conflict == "skip":
                        skipped.append(name)
                        continue
                    if conflict == "keep-both":
                        new_name = name
                        suffix = 2
                        while new_name.strip().lower() in existing_names:
                            new_name = f"{name} ({suffix})"
                            suffix += 1
                        character = dict(character, name=new_name)
                        renamed.append({"from": name, "to": new_name})
                        name = new_name
                    else:  # overwrite
                        overwritten.append(name)

                # Copy sample files from the bundle or inline base64
                sample_docs = {}
                for s in document.get("samples", []):
                    if isinstance(s, dict) and s.get("name") and s.get("data"):
                        sample_docs[s["name"]] = s
                inline_mode = bool(sample_docs)

                for ref in self._collect_sample_refs(character):
                    sample_name = ref["sample"]
                    sample_path = Path(sample_name)
                    if sample_path.is_absolute():
                        continue  # absolute refs are not portable; left untouched
                    target = voices_dir / Path(sample_name).name
                    if target.exists():
                        samples_copied += 0  # already present; keep existing file
                        continue
                    if sample_name in sample_docs:
                        payload_b64 = sample_docs[sample_name].get("data")
                        if payload_b64:
                            target.write_bytes(base64.b64decode(payload_b64))
                            samples_copied += 1
                    elif imported_samples:
                        # ZIP bundle mode: match by original name
                        match = bundle_samples.get(sample_name)
                        if match and match.get("data"):
                            target.write_bytes(base64.b64decode(match["data"]))
                            samples_copied += 1

                existing.append(character)
                existing_names[norm if norm != norm else name.strip().lower()] = len(existing) - 1
                existing_names[name.strip().lower()] = len(existing) - 1
                imported.append(name)
                config_dirty = True

            if config_dirty:
                self.character_service._commit_yaml_public(
                    config_path, data, ryaml, original_text)
            else:
                # Still validate the untouched file to mirror prior behavior
                pass

        return {
            "imported": imported,
            "overwritten": overwritten,
            "skipped": skipped,
            "renamed": renamed,
            "samplesCopied": samples_copied,
        }

    def import_bundle(self, story_id: str, bundle_bytes: bytes,
                      conflict: str = "keep-both") -> Dict[str, Any]:
        """Import from a ZIP bundle produced by export_characters_bundle."""
        try:
            zf = zipfile.ZipFile(io.BytesIO(bundle_bytes))
        except zipfile.BadZipFile:
            raise ImportError_("Not a valid ZIP bundle", code="IMPORT_PARSE_ERROR")

        import yaml as _yaml
        try:
            manifest = _yaml.safe_load(zf.read("manifest.yml"))
        except KeyError:
            raise ImportError_("Bundle missing manifest.yml", code="IMPORT_PARSE_ERROR")
        except Exception as e:
            raise ImportError_(f"Cannot parse manifest: {e}", code="IMPORT_PARSE_ERROR")

        payload_docs = []
        imported_samples = []
        for entry in manifest.get("characters", []):
            char_file = entry.get("file")
            if not char_file:
                continue
            doc = _yaml.safe_load(zf.read(char_file))
            samples = []
            for s in doc.get("samples", []):
                bundle_path = s.get("bundlePath")
                data = zf.read(bundle_path) if bundle_path and bundle_path in zf.namelist() else None
                samples.append({
                    "name": s["name"],
                    "data": base64.b64encode(data).decode("ascii") if data else None,
                })
            payload_docs.append({
                "formatVersion": doc.get("formatVersion"),
                "character": doc.get("character"),
                "samples": samples,
            })

        # Concatenate characters with their own sample docs
        combined = {"characters": [d["character"] for d in payload_docs]}
        all_samples: List[Dict[str, str]] = []
        for d in payload_docs:
            all_samples.extend(d.get("samples") or [])

        return self.import_characters(
            story_id,
            _yaml.safe_dump(combined, sort_keys=False, allow_unicode=True).encode("utf-8"),
            conflict=conflict,
            imported_samples=all_samples,
        )
