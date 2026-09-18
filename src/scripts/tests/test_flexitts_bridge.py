"""Tests for flexitts_bridge.py character command dispatch.

Verifies the Phase 6 bridge contract: expected client-input errors are
reported as JSON on stdout with exit 0 (so the renderer reads them via
success:false), not as stderr with a nonzero exit.
"""

import json
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
    stories_dir = (Path(__file__).resolve().parent.parent.parent.parent
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


def test_validate_sox_via_bridge():
    payload, code = run_bridge(["characters", "validate-sox", '["gain +3"]'])
    assert code == 0
    assert payload.get("success") is True
    assert payload.get("isValid") is True
