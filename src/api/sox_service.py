#!/usr/bin/env python3
"""SoX effects engine (Phase 5 of the Character UI plan).

5.1 Command builder: parses SoX effect strings (e.g. "reverb 50",
"pitch -400") into structured effects, validates effect names and parameter
types/ranges, and builds full sox command argument lists with chaining.

5.2 Validation: syntax-checks effect chains against SoX's known effect set
and per-effect parameter specifications, returning detailed errors.

5.3 Execution: runs a sox pipeline over an audio file with a timeout.
"""

from __future__ import annotations

import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class SoxError(Exception):
    def __init__(self, message: str, code: str = "SOX_ERROR"):
        super().__init__(message)
        self.code = code


class SoxSyntaxError(SoxError):
    def __init__(self, message: str):
        super().__init__(message, code="SOX_SYNTAX_ERROR")


class SoxExecutionError(SoxError):
    def __init__(self, message: str):
        super().__init__(message, code="SOX_EXECUTION_ERROR")


class SoxTimeoutError(SoxError):
    def __init__(self, message: str):
        super().__init__(message, code="SOX_TIMEOUT")


# Well-known SoX effects parameter signatures used for validation.
# Types: i=int, f=float, n=number(int|float), s=string/word, + = one or more.
# SoX accepts both signed and unsigned numerics for most numeric params.
EFFECT_SIGNATURES: Dict[str, Dict[str, Any]] = {
    "gain": {"min_args": 1, "max_args": 2, "numeric": True},
    "pitch": {"min_args": 1, "max_args": 2, "numeric": True},
    "norm": {"min_args": 0, "max_args": 1, "numeric": True},
    "vol": {"min_args": 1, "max_args": 3, "numeric": True},
    "reverb": {"min_args": 0, "max_args": 3, "numeric_first": True, "strings": True},
    "echo": {"min_args": 4, "max_args": None, "numeric": True, "even_args": True},
    "echos": {"min_args": 4, "max_args": None, "numeric": True, "even_args": True},
    "bass": {"min_args": 1, "max_args": 3, "numeric": True},
    "treble": {"min_args": 1, "max_args": 3, "numeric": True},
    "equalizer": {"min_args": 3, "max_args": 4, "numeric": True},
    "highpass": {"min_args": 1, "max_args": 2, "numeric": True},
    "lowpass": {"min_args": 1, "max_args": 2, "numeric": True},
    "overdrive": {"min_args": 1, "max_args": 2, "numeric": True},
    "speed": {"min_args": 1, "max_args": 1, "numeric": True},
    "rate": {"min_args": 1, "max_args": 1, "numeric": True},
    "fade": {"min_args": 1, "max_args": 6},
    "compand": {"min_args": 1, "max_args": None},
    "trim": {"min_args": 1, "max_args": 2, "numeric": True},
    "delay": {"min_args": 1, "max_args": None, "numeric": True},
    "pad": {"min_args": 1, "max_args": 2, "numeric": True},
    "silence": {"min_args": 2, "max_args": None},
    "reverse": {"min_args": 0, "max_args": 0},
    "chorus": {"min_args": 4, "max_args": None},
    "flanger": {"min_args": 4, "max_args": None},
    "phaser": {"min_args": 4, "max_args": None},
    "tremolo": {"min_args": 2, "max_args": 2, "numeric": True},
    "tempo": {"min_args": 1, "max_args": 4, "numeric": True},
    "dcshift": {"min_args": 1, "max_args": 2, "numeric": True},
    "high": {"min_args": 0, "max_args": 0},
}

# Effects that take no parameters
NO_ARG_EFFECTS = {"reverse", "loudness0"}  # loudness takes args; kept explicit only

# Effects accepted without strict signature checking (flexible/complex syntax)
FLEXIBLE_EFFECTS = {"compand", "silence", "synth", "bend", "chorus", "flanger",
                    "phaser", "fade", "biquad", "fir", "firfit", "ladspa",
                    "spectrogram", "splice", "stretch", "vad", "deemph", "riaa",
                    "earwax", "hilbert", "dither", "contrast", "oops", "swap"}


def _get_known_effects() -> List[str]:
    """Effect names from the local SoX binary, with a bundled fallback."""
    sox = shutil.which("sox")
    if sox:
        try:
            result = subprocess.run([sox, "--help"], capture_output=True,
                                    text=True, timeout=10)
            output = result.stdout + result.stderr
            for line in output.splitlines():
                if line.startswith("EFFECTS:"):
                    names = line.split(":", 1)[1].split()
                    # Strip deprecation/experimental/libsox markers
                    return [n.rstrip("*+#") for n in names]
        except Exception:
            pass
    return list(EFFECT_SIGNATURES.keys())


def parse_effect_strings(effects_list: List[str]) -> List[Dict[str, Any]]:
    """Parse raw effect strings into structured effect objects.

    Each string may contain ONE effect ("reverb 50") or a CHAIN of effects
    separated by spaces where each known effect name starts a new effect
    ("pitch -250 equalizer 1800 +4 gain -n" -> pitch, equalizer, gain).
    Chained forms are what story-config.yml sox-effects entries use; SoX
    applies chained effects sequentially within a single invocation.
    Quoted parameters are preserved via shlex for special characters.
    """
    effects: List[Dict[str, Any]] = []
    known = set(_get_known_effects())
    for raw in effects_list:
        if raw is None:
            continue
        text = str(raw).strip()
        if not text:
            continue
        try:
            parts = shlex.split(text)
        except ValueError:
            # Malformed quoting: degrade to whitespace split so validation
            # can still report the chain structurally.
            parts = text.split()
        if not parts:
            continue

        # Chain segmentation: a token that is a known effect name starts a new
        # effect (except the first token, which always starts one).
        current: Dict[str, Any] = {"effect": parts[0].lower(), "args": [], "raw": text}
        for token in parts[1:]:
            if token.lower() in known and current["effect"] in known:
                # Ambiguity guard: a numeric-looking token equal to an effect
                # name cannot happen (effect names are alphabetic).
                effects.append(current)
                current = {"effect": token.lower(), "args": [], "raw": text}
            else:
                current["args"].append(token)
        effects.append(current)
    return effects


def validate_effects(effects_list: List[str]) -> Tuple[bool, List[Dict[str, Any]]]:
    """Validate an effect chain. Returns (is_valid, errors).

    Errors are dicts: {index, effect, message, type} where type is one of
    UNKNOWN_EFFECT, MISSING_ARGS, TOO_MANY_ARGS, INVALID_PARAM, PARSE_ERROR.
    """
    effects = parse_effects_safe(effects_list)
    known = set(_get_known_effects())
    errors: List[Dict[str, Any]] = []

    for eff in effects:
        idx = effects.index(eff)
        name = eff["effect"].lower()
        args = eff["args"]

        if name not in known:
            errors.append({
                "index": idx, "effect": eff["raw"], "position": name,
                "code": "UNKNOWN_EFFECT",
                "message": f"Unknown SoX effect '{name}'",
            })
            continue

        sig = EFFECT_SIGNATURES.get(name)
        if sig is None or name in FLEXIBLE_EFFECTS:
            # No strict signature: only structural checks
            if sig and sig.get("min_args") is not None and len(args) < sig["min_args"]:
                errors.append({
                    "index": idx, "effect": eff["raw"], "position": name,
                    "code": "MISSING_ARGS",
                    "message": f"Effect '{name}' requires at least {sig['min_args']} argument(s), got {len(args)}",
                })
            continue

        min_args = sig.get("min_args", 0)
        max_args = sig.get("max_args")
        if len(args) < min_args:
            errors.append({
                "index": idx, "effect": eff["raw"], "position": name,
                "code": "MISSING_ARGS",
                "message": f"Effect '{name}' requires at least {min_args} argument(s), got {len(args)}",
            })
            continue
        if max_args is not None and len(args) > max_args:
            errors.append({
                "index": idx, "effect": eff["raw"], "position": name,
                "code": "TOO_MANY_ARGS",
                "message": f"Effect '{name}' accepts at most {max_args} argument(s), got {len(args)}",
            })
            continue

        # Numeric parameter validation
        if sig.get("numeric"):
            even = sig.get("even_args")
            allowed_flags = {"-n"}  # e.g. gain -n (normalize)
            for j, arg in enumerate(args):
                if even and j % 2 == 0:
                    continue  # e.g. echo pairs start with gain-like numbers anyway
                if arg in allowed_flags:
                    continue
                try:
                    float(arg)
                except ValueError:
                    errors.append({
                        "index": idx, "effect": eff["raw"], "position": f"{name}[{j}]",
                        "code": "INVALID_PARAM",
                        "message": f"Effect '{name}' parameter {j + 1} ('{arg}') must be numeric",
                    })

    return (len(errors) == 0, errors)


def parse_effects_safe(effects_list: List[str]) -> List[Dict[str, Any]]:
    """Chain-aware parse that never raises: malformed quoting falls back to
    whitespace splitting so validation can report all issues at once."""
    try:
        return parse_effect_strings(effects_list)
    except SoxSyntaxError:
        # shlex failed somewhere; degrade to whitespace splitting per string
        effects: List[Dict[str, Any]] = []
        known = set(_get_known_effects())
        for raw in effects_list or []:
            if raw is None:
                continue
            text = str(raw).strip()
            if not text:
                continue
            parts = text.split()
            if not parts:
                continue
            current: Dict[str, Any] = {"effect": parts[0].lower(), "args": [], "raw": text}
            for token in parts[1:]:
                if token.lower() in known and current["effect"] in known:
                    effects.append(current)
                    current = {"effect": token.lower(), "args": [], "raw": text}
                else:
                    current["args"].append(token)
            effects.append(current)
        return effects


def build_command(input_path: Path, output_path: Path,
                  effects_list: List[str]) -> Tuple[List[str], List[Dict[str, Any]]]:
    """Build the full sox command for an effect chain.

    Returns (argv, structured_effects). Chaining: SoX natively applies
    multiple effects in sequence within a single invocation, so all effects
    are appended after the file arguments.
    """
    effects = parse_effects_safe(effects_list)
    argv = ["sox", str(input_path), str(output_path)]
    for eff in effects:
        argv.append(eff["effect"])
        argv.extend(eff["args"])
    return argv, effects


def quote_effect_string(effect: str, args: List[str]) -> str:
    """Rebuild an effect string with proper quoting for special characters."""
    parts = [effect] + [shlex.quote(a) for a in args]
    return " ".join(parts)


class SoxEngine:
    """Validation and execution of SoX effect pipelines."""

    def __init__(self, timeout_seconds: float = 60.0):
        self.timeout_seconds = timeout_seconds

    # ------------------------------------------------------------------ #
    # Phase 5.2: validation
    # ------------------------------------------------------------------ #

    def validate(self, effects_list: List[str]) -> Dict[str, Any]:
        is_valid, errors = validate_effects(effects_list)
        return {
            "isValid": is_valid,
            "errors": errors,
            "effects": parse_effects_safe(effects_list),
        }

    # ------------------------------------------------------------------ #
    # Phase 5.3: execution
    # ------------------------------------------------------------------ #

    def process(self, input_path: Path, effects_list: List[str],
                output_path: Optional[Path] = None) -> Dict[str, Any]:
        """Execute a sox pipeline over an audio file.

        Without output_path, processing is in-place via a temp file (matching
        chapter_xml_to_audio.apply_sox_effects semantics).
        """
        input_path = Path(input_path)
        if not input_path.exists():
            raise SoxError(f"Input file not found: {input_path}", code="SOX_INPUT_NOT_FOUND")
        if not shutil.which("sox"):
            raise SoxError("sox binary not found on PATH", code="SOX_NOT_INSTALLED")

        is_valid, errors = validate_effects(effects_list)
        if not is_valid:
            raise SoxSyntaxError(
                "Invalid effect chain: " + "; ".join(e["message"] for e in errors))

        in_place = output_path is None
        if in_place:
            output_path = input_path.parent / (input_path.stem + ".soxproc.wav")

        argv = build_command(input_path, output_path, effects_list)[0]
        try:
            result = subprocess.run(
                argv, capture_output=True, text=True,
                timeout=self.timeout_seconds,
            )
        except subprocess.TimeoutExpired:
            if output_path.exists():
                output_path.unlink()
            raise SoxTimeoutError(
                f"SoX execution timed out after {self.timeout_seconds}s")
        except Exception as e:
            raise SoxExecutionError(f"SoX execution failed: {e}")

        if result.returncode != 0:
            stderr = (result.stderr or "").strip()
            if output_path.exists():
                output_path.unlink()
            raise SoxExecutionError(f"SoX failed: {stderr or result.returncode}")

        if in_place:
            input_path.unlink()
            output_path.rename(input_path)
            output_path = input_path

        return {
            "outputPath": str(output_path),
            "appliedEffects": effects_list,
            "sizeBytes": output_path.stat().st_size if output_path.exists() else 0,
        }