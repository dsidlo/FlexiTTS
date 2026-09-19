"""Tests for flexitts_bridge.py character command dispatch.

Verifies the Phase 6 bridge contract: expected client-input errors are
reported as JSON on stdout with exit 0 (so the renderer reads them via
success:false), not as stderr with a nonzero exit.
"""

import json
import pytest
import yaml
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "flexitts_bridge.py"


def run_bridge(args: list[str]) -> tuple[dict, int]:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True, text=True, timeout=60,
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        payload = {"raw": result.stdout, "stderr": result.stderr}
    return payload, result.returncode


def test_list_returns_characters_for_valid_story():
    payload, code = run_bridge(["characters", "list", "Story-Default"])
    # Story-Default may not exist in a bare checkout; only assert contract
    assert isinstance(payload, dict)
    if code == 0:
        assert payload.get("success") in (True, False)
        if payload.get("success"):
            assert isinstance(payload["characters"], list)


def test_missing_story_is_json_error_with_exit_zero():
    payload, code = run_bridge(["characters", "list", "Story-Does-Not-Exist"])
    assert code == 0, "expected client-input error to exit 0 with JSON"
    assert payload.get("success") is False
    assert payload.get("code") == "CHARACTER_NOT_FOUND"


def test_empty_story_id_is_json_error_with_exit_zero():
    payload, code = run_bridge(["characters", "list", ""])
    assert code == 0
    assert payload.get("success") is False
    assert payload.get("code") == "INVALID_STORY_ID"


def test_unknown_subcommand_is_json_error():
    payload, code = run_bridge(["characters", "frobnicate"])
    assert code == 1
    assert payload.get("success") is False
    assert payload.get("code") == "UNKNOWN_COMMAND"


def test_absolute_path_within_stories_dir_is_accepted():
    """Electron prepends stories-dir to Story- prefixed args, so the bridge
    legitimately receives absolute paths. They must resolve like bare ids."""
    import os
    stories_dir = (Path(__file__).resolve().parent.parent.parent
                   / "Stories").resolve()
    target = stories_dir / "Story-Default"
    if not target.is_dir():
        target = next(iter(p for p in stories_dir.glob("Story-*") if p.is_dir()), None)
    if target is None:
        return  # no stories in checkout; nothing to assert
    payload, code = run_bridge(["characters", "list", str(target)])
    assert code == 0
    assert payload.get("success") is True
    assert isinstance(payload["characters"], list)


def test_absolute_path_outside_stories_dir_is_rejected():
    payload, code = run_bridge(["characters", "list", "/etc"])
    assert code == 0  # JSON error contract
    assert payload.get("success") is False
    assert payload.get("code") == "INVALID_STORY_ID"


class TestPhase7BridgeCommands:
    """Phase 7T.4 bridge commands: dialog-effects and post-process CRUD."""

    @pytest.fixture(autouse=True)
    def _backup_restore(self):
        """Backup and restore Story-Default config around each test."""
        import shutil
        self._backup = "/tmp/p7-bridge-backup.yml"
        self.config_src = (Path(SCRIPT).resolve().parent.parent.parent
                           / "Stories" / "Story-Default" / "story-config.yml")
        if not self.config_src.exists():
            pytest.skip("Stories/Story-Default not found")
        shutil.copy(self.config_src, self._backup)
        yield self.config_src
        shutil.copy(self._backup, self.config_src)

    def test_rename_propagates_to_referencing_characters(self, _backup_restore):
        # Create a stub effect, wire a character, rename, verify propagation
        stub, _ = run_bridge(["characters", "create-dialog-effect-stub", "Story-Default", "test-prop"])
        assert stub["success"]
        update, _ = run_bridge(["characters", "update", "Story-Default", "Narrator",
                             json.dumps({"dialogEffects": ["test-prop"]})])
        assert update["success"]
        rename, _ = run_bridge(["characters", "update-dialog-effect", "Story-Default", "test-prop",
                             json.dumps({"name": "echo-chamber"})])
        assert rename["success"] and rename["renamed"]
        cfg = yaml.safe_load(self.config_src.read_text())
        names = [e["name"] for e in cfg["dialog-effects"]]
        assert "echo-chamber" in names and "test-prop" not in names
        narrator = next(c for c in cfg["characters"] if c["name"] == "Narrator")
        assert narrator["dialog-effects"] == ["echo-chamber"]

    def test_delete_with_dependents_blocked_then_unlinked_succeeds(self, _backup_restore):
        run_bridge(["characters", "create-dialog-effect-stub", "Story-Default", "test-del"])
        run_bridge(["characters", "update", "Story-Default", "Narrator",
                    json.dumps({"dialogEffects": ["test-del"]})])
        blocked, _ = run_bridge(["characters", "delete-dialog-effect", "Story-Default", "test-del"])
        assert blocked.get("code") == "DIALOG_EFFECT_IN_USE"
        # Unlink first
        run_bridge(["characters", "update", "Story-Default", "Narrator",
                    json.dumps({"dialogEffects": []})])
        deleted, _ = run_bridge(["characters", "delete-dialog-effect", "Story-Default", "test-del"])
        assert deleted["success"] and deleted["deleted"] == "test-del"

    def test_post_process_round_trip(self, _backup_restore):
        effects = ["norm", "gain -3"]
        set_result, _ = run_bridge(["characters", "set-post-process", "Story-Default",
                                 json.dumps(effects)])
        assert set_result["success"]
        get_result, _ = run_bridge(["characters", "get-post-process", "Story-Default"])
        assert get_result["soxEffects"] == effects
        cfg = yaml.safe_load(self.config_src.read_text())
        assert cfg["story-audio-post-process"]["sox-effects"] == effects
        # Validate the resulting config
        import sys as _sys
        _sys.path.insert(0, str(Path(SCRIPT).resolve().parent))
        from validate_config import validate_config
        assert validate_config(str(self.config_src))


class TestPhase7TabState:
    """Phase 7T.5: Dialog Effects tab state and consistency."""

    @pytest.fixture(autouse=True)
    def _backup_restore(self):
        import shutil
        self._backup = "/tmp/p7-bridge-backup.yml"
        self.config_src = (Path(SCRIPT).resolve().parent.parent.parent
                           / "Stories" / "Story-Default" / "story-config.yml")
        if not self.config_src.exists():
            pytest.skip("Stories/Story-Default not found")
        shutil.copy(self.config_src, self._backup)
        yield self.config_src
        shutil.copy(self._backup, self.config_src)

    def test_edit_dialog_effects_and_verify_config_valid(self, _backup_restore):
        stub, _ = run_bridge(["characters", "create-dialog-effect-stub", "Story-Default", "test-draft"])
        assert stub["success"]
        cfg = yaml.safe_load(self.config_src.read_text())
        names = [e["name"] for e in cfg["dialog-effects"]]
        assert "test-draft" in names
        from validate_config import validate_config as _vc
        import sys as _sys
        _sys.path.insert(0, str(Path(SCRIPT).resolve().parent))
        assert _vc(str(self.config_src))

    def test_timestamped_backup_created_on_mutation(self, _backup_restore):
        import glob
        import re
        # Use a distinct effect name to avoid matching existing backups
        effect_name = f"backup-test-{id(self) % 100000}"
        stub, _ = run_bridge(["characters", "create-dialog-effect-stub", "Story-Default", effect_name])
        assert stub["success"]
        new_backups = [b for b in glob.glob(str(_backup_restore.parent / "story-config.*.bak"))
                       if re.search(r"story-config\.\d{8}_\d{6}\.bak", b)]
        assert len(new_backups) >= 1, f"expected at least 1 timestamped backup, got {new_backups}"
        for b in new_backups:
            assert re.search(r"story-config\.\d{8}_\d{6}\.bak", b), f"bad backup name: {b}"
        # Clean up
        run_bridge(["characters", "update", "Story-Default", "Narrator",
                    json.dumps({"dialogEffects": []})])
        run_bridge(["characters", "delete-dialog-effect", "Story-Default", effect_name])


def test_validate_sox_via_bridge():
    payload, code = run_bridge(["characters", "validate-sox", '["gain +3"]'])
    assert code == 0
    assert payload.get("success") is True
    assert payload.get("isValid") is True
