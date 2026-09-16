#!/usr/bin/env python3
"""Migrate existing character entries to the new emotion-aware structure.

Implements Phase 1.2 of docs/FlexiTTS Create Character UI-Plan.md:

- Converts existing ``custom-voice`` entries to the new format (schema now
  supports ``emotions`` with per-emotion ``sox-effects`` and instruct text).
- Generates a default "Neutral" emotion for migrated custom-voice characters
  that have no emotion list, carrying the character's top-level ``instruct``
  text into it.
- Normalizes ``cloned-emotion`` entries to carry ``voice-sample`` (required)
  plus optional ``sox-effects`` / ``dialog-effects`` overrides.
- Accepts the ``qwen3-tts-custom-voice`` / ``qwen3-tts-voice-design`` key
  aliases from the Create Character UI spec, folding them back to the
  canonical ``custom-voice`` / ``cloned-emotion`` keys.
- Backs up the original config before writing (``story-config.yml.bak``).

The script is idempotent: characters already carrying an emotion list are
left untouched (except alias normalization), and running it twice produces
no further changes.

Usage:
    python migrate_characters_to_emotions.py [path/to/story-config.yml ...]
        [--dry-run] [--no-backup]

With no paths, every Stories/*/story-config.yml is processed.
"""

import argparse
import os
import shutil
import sys
from pathlib import Path

import yaml

NEUTRAL_EMOTION = "Neutral"

# Key aliases from docs/FlexiTTS Create Character UI.md -> canonical keys
ALIASES = {
    "qwen3-tts-custom-voice": "custom-voice",
    "qwen3-tts-voice-design": "cloned-emotion",
}


def migrate_character(char: dict) -> tuple[dict, list[str]]:
    """Migrate one character entry. Returns (new_char, notes)."""
    char_notes: list[str] = []
    name = char.get("name", "?")

    # Ensure custom-voice is a dict if present
    custom = char.get("custom-voice")
    if custom is not None and not isinstance(custom, dict):
        raise ValueError(f"Character '{name}' has non-mapping 'custom-voice'; cannot migrate.")

    # 1. custom-voice without emotions -> add default Neutral emotion
    if isinstance(custom, dict) and not custom.get("emotions"):
        instruct = custom.get("instruct", "")
        neutral = {"emotion": NEUTRAL_EMOTION}
        if instruct:
            neutral["instruct"] = instruct
        custom["emotions"] = [neutral]
        char_notes.append(f"{name}: added default {NEUTRAL_EMOTION} emotion from top-level instruct")

    # 2. Ensure emotion entries use canonical keys and valid shapes
    if isinstance(custom, dict):
        emotions = custom.get("emotions")
        if isinstance(emotions, list):
            for idx, em in enumerate(emotions):
                if not isinstance(em, dict):
                    raise ValueError(
                        f"Character '{name}' emotions[{idx}] is not a mapping."
                    )
                # Prefer canonical 'emotion' key; fold 'name' alias
                if "emotion" not in em and "name" in em:
                    em["emotion"] = em.pop("name")
                    char_notes.append(f"{name}: emotions[{idx}] renamed 'name' -> 'emotion'")
                if not str(em.get("emotion", "")).strip():
                    raise ValueError(
                        f"Character '{name}' emotions[{idx}] has no emotion name."
                    )
                # sox-effects must be a list of strings when present
                if "sox-effects" in em and not isinstance(em["sox-effects"], list):
                    raise ValueError(
                        f"Character '{name}' emotions[{idx}] 'sox-effects' must be a list."
                    )

    # 3. cloned-emotion entries require voice-sample; ensure it is present
    cloned = char.get("cloned-emotion")
    if cloned is not None:
        if not isinstance(cloned, list):
            raise ValueError(f"Character '{name}' has non-list 'cloned-emotion'.")
        for idx, em in enumerate(cloned):
            if not isinstance(em, dict):
                raise ValueError(f"Character '{name}' cloned-emotion[{idx}] is not a mapping.")
            if not str(em.get("voice-sample", "")).strip():
                top_sample = str(char.get("voice-sample", "")).strip()
                if top_sample:
                    em["voice-sample"] = top_sample
                    char_notes.append(
                        f"{name}: cloned-emotion[{idx}] inherited character voice-sample"
                    )
                else:
                    raise ValueError(
                        f"Character '{name}' cloned-emotion[{idx}] has no 'voice-sample' "
                        "and the character has none to inherit."
                    )
            if "emotion" not in em or not str(em.get("emotion", "")).strip():
                raise ValueError(
                    f"Character '{name}' cloned-emotion[{idx}] has no 'emotion' name."
                )

    return char, char_notes


def migrate_config(config: dict) -> tuple[dict, list[str]]:
    """Migrate a full parsed story-config. Returns (new_config, notes)."""
    notes: list[str] = []
    characters = config.get("characters")
    if not isinstance(characters, list):
        return config, notes

    for i, char in enumerate(characters):
        if not isinstance(char, dict):
            continue
        characters[i] = normalize_character_copy(char, notes, i)

    return config, notes


def normalize_character_copy(char: dict, notes: list[str], index: int) -> dict:
    """Normalize aliases, run migration, and record notes."""
    name = char.get("name", f"characters[{index}]")
    try:
        char = normalize_aliases_inplace(char, notes)
        migrated, char_notes = migrate_character(char)
        notes.extend(char_notes)
        return migrated
    except ValueError as e:
        # Re-raise with character context for the caller to report
        raise ValueError(f"characters[{index}]: {e}") from e


def normalize_aliases_inplace(char: dict, notes: list[str]) -> dict:
    """Fold alias keys onto canonical keys, noting the rename."""
    for alias, canonical in ALIASES.items():
        if alias in char:
            if canonical in char:
                raise ValueError(
                    f"defines both '{alias}' and '{canonical}'; resolve manually"
                )
            char[canonical] = char.pop(alias)
            notes.append(f"{char.get('name', '?')}: '{alias}' folded to '{canonical}'")
    return char


def process_file(config_path: Path | str, dry_run: bool = False, backup: bool = True) -> bool:
    """Migrate a single story-config.yml. Returns True when the file changed."""
    config_path = Path(config_path)
    if not config_path.exists():
        print(f"Not found: {config_path}")
        return False

    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    if not isinstance(config, dict):
        print(f"Skipping (not a mapping): {config_path}")
        return False

    notes: list[str] = []
    try:
        new_config, notes = migrate_config(config)
    except ValueError as e:
        print(f"ERROR in {config_path}: {e}")
        return False

    if not notes:
        print(f"No changes needed: {config_path}")
        return True

    if dry_run:
        print(f"[dry-run] Would migrate {config_path}:")
        for note in notes:
            print(f"  - {note}")
        return True

    if backup:
        backup_path = config_path.with_suffix(config_path.suffix + ".bak")
        shutil.copy2(config_path, backup_path)
        print(f"Backup written: {backup_path}")

    # Comment-preserving rewrite: ruamel round-trips comments and formatting
    # (including the user's inline documentation) which plain safe_dump drops.
    try:
        from ruamel.yaml import YAML

        ryaml = YAML()
        ryaml.preserve_quotes = True
        ryaml.indent(mapping=2, sequence=4, offset=2)
        ryaml.width = 4096

        with open(config_path, "r") as f:
            rt_data = ryaml.load(f)

        # Apply the same in-place migrations to the round-trip tree. The
        # migration mutates nested dicts/lists, which ruamel shares by
        # reference, so the edits land in rt_data as well.
        ryaml_notes: list[str] = []
        characters = rt_data.get("characters")
        if isinstance(characters, list):
            for i, char in enumerate(characters):
                if not isinstance(char, dict):
                    continue
                try:
                    characters[i] = normalize_character_copy(char, ryaml_notes, i)
                except ValueError as e:
                    print(f"ERROR in {config_path}: {e}")
                    return False
        elif "characters" not in rt_data:
            print(f"Skipping (no characters section): {config_path}")
            return False

        with open(config_path, "w") as f:
            ryaml.dump(rt_data, f)
    except ImportError:
        # ruamel unavailable: fall back to comment-dropping PyYAML rewrite
        with open(config_path, "w") as f:
            yaml.safe_dump(new_config, f, sort_keys=False, allow_unicode=True)
        print("WARNING: ruamel.yaml not available; comments in the config were not preserved.")

    print(f"Migrated {config_path}:")
    for note in notes + ryaml_notes:
        print(f"  - {note}")

    # Best-effort validation of the migrated config
    script_dir = Path(__file__).resolve().parent
    if str(script_dir) not in sys.path:
        sys.path.insert(0, str(script_dir))
    try:
        import validate_config as vc  # noqa: E402

        if vc.validate_config(str(config_path)):
            return True
        print(f"WARNING: migrated config failed validation: {config_path}")
        return False
    except Exception as e:  # pragma: no cover - defensive
        print(f"WARNING: could not run post-migration validation: {e}")
        return True


def default_config_paths() -> list[Path]:
    """All Stories/*/story-config.yml paths."""
    root = Path(__file__).resolve().parent
    # Script lives in src/scripts; Stories may live at repo root or alongside.
    candidates = [root.parent.parent / "Stories", root / "Stories", Path.cwd() / "Stories"]
    for stories in candidates:
        if stories.is_dir():
            return sorted(stories.glob("Story-*/story-config.yml"))
    return []


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate characters to the emotions structure")
    parser.add_argument("paths", nargs="*", help="story-config.yml paths (default: all stories)")
    parser.add_argument("--dry-run", action="store_true", help="Show changes without writing")
    parser.add_argument("--no-backup", action="store_true", help="Skip .bak backup before writing")
    args = parser.parse_args()

    paths = [Path(p) for p in args.paths] if args.paths else default_config_paths()
    if not paths:
        print("No story-config.yml files found.")
        return 1

    ok = True
    for path in paths:
        if not process_file(path, dry_run=args.dry_run, backup=not args.no_backup):
            ok = False
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())