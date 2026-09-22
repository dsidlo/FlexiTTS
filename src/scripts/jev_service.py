#!/usr/bin/env python3
"""jev_service: post-conversion XML validation via TypeSafe's Jev (System One).

Runs AFTER chapter_to_xml.py has produced a chapter XML (character
assignments and emotions are chosen by the LLM during that step; this module
never invents new ones at render time). Jev then:

1. Character-assignment check: for every <dialog> element, asks Jev whether
   the assigned speaker is the correct configured character, catching LLM
   spelling mistakes ("Hendricks" vs "Hendrix"). Low-confidence verdicts
   leave the XML untouched.
2. Emotion matching: for characters with configured emotions (custom-voice
   emotions or cloned-emotion lists), asks Jev which configured emotion best
   matches each utterance. Applied only at confidence >= 0.8; otherwise the
   LLM's original emotion is left as-is.

Modes (auto): live when TYPESAFE_API_KEY is set; otherwise dry-run mode
logs what would be checked and returns the XML unchanged, so the offline
pipeline is unaffected.

API: POST https://api.typesafe.ai/v1/systemone, route jev-latest.
Config (story-config.yml or FlexiTTS.yml):
    jev:
      enabled: true
      api-key-env: TYPESAFE_API_KEY
      emotion-confidence-threshold: 0.80
      model: jev-latest
"""

from __future__ import annotations

import json
import os
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from xml.etree import ElementTree as ET

DEFAULT_API_BASE = "https://api.typesafe.ai/v1/systemone"
DEFAULT_MODEL = "jev-latest"
DEFAULT_CONFIDENCE = 0.80
DEFAULT_TIMEOUT = 15.0


def _log(msg: str) -> None:
    print(f"[jev_service] {msg}")


def load_jev_config(config: dict) -> dict:
    """Read the jev: block from a story/global config, with defaults.
    Key lookup is case-insensitive (jev / Jev / JEV all match)."""
    cfg = {}
    if isinstance(config, dict):
        for k, v in config.items():
            if k.lower() == "jev" and isinstance(v, dict):
                cfg = v
                break
    key_env = cfg.get("api-key-env", "TYPESAFE_API_KEY")
    confidence = cfg.get("emotion-confidence-threshold",
                         cfg.get("confidence-threshold", DEFAULT_CONFIDENCE))
    return {
        "enabled": bool(cfg.get("enabled", False)),
        "api_key": os.getenv(key_env, ""),
        "api_base": cfg.get("api-base", DEFAULT_API_BASE),
        "model": cfg.get("model", DEFAULT_MODEL),
        "confidence": float(confidence),
        "timeout": float(cfg.get("timeout", DEFAULT_TIMEOUT)),
    }


class JevClient:
    """Thin client for the TypeSafe System One API."""

    def __init__(self, api_base: str, api_key: str, model: str, timeout: float):
        self.api_base = api_base.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def ask(self, state: Dict[str, Any], questions: Dict[str, Dict[str, Any]]) -> Optional[dict]:
        payload = {"model": self.model, "state": state, "questions": questions}
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            self.api_base, data=data,
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {self.api_key}"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = json.loads(resp.read().decode())
                return body
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            _log(f"api call failed: {type(e).__name__}: {e}")
            return None
        except json.JSONDecodeError as e:
            _log(f"api returned non-JSON: {e}")
            return None


def _is_dry_mode(jev_cfg: dict) -> bool:
    return not (jev_cfg.get("enabled") and jev_cfg.get("api_key"))


def _ask_choice(client: Optional[JevClient], state: dict, key: str,
                options: List[str], instruction: str) -> Tuple[Optional[str], float]:
    """Send one Choice question. Returns (choice, confidence); None client
    (dry mode) returns (None, 0.0)."""
    if client is None:
        return None, 0.0
    resp = client.ask(state, {key: {"type": "choice", "options": options,
                                    "instruction": instruction}})
    if not resp:
        return None, 0.0
    try:
        answer = resp["answers"][key]
        return answer.get("choice"), float(answer.get("confidence", 0.0))
    except (KeyError, TypeError, ValueError):
        _log(f"unexpected api response shape: {json.dumps(resp)[:200]}")
        return None, 0.0


def _speaker_attr(dlg):
    """Speaker attribute: character= is the FlexiTTS convention; accept
    name= and speaker= for robustness."""
    for attr in ("character", "name", "speaker"):
        v = (dlg.get(attr) or "").strip()
        if v:
            return attr, v
    return None, None


def _correct_case(name: str, roster: List[str]) -> Optional[str]:
    """Case-insensitive + punctuation-insensitive roster lookup."""
    norm = lambda s: "".join(c for c in s.lower() if c.isalnum())
    target = norm(name)
    for cand in roster:
        if norm(cand) == target:
            return cand
    return None


def validate_character_assignments(
    xml_path: Path,
    characters: List[str],
    jev_cfg: dict,
    client: Optional[JevClient] = None,
) -> Dict[str, Any]:
    """Check every dialog speaker against the character roster.

    - Exact roster match (case/punctuation-insensitive): fix spelling only.
    - No match: ask Jev whether the speaker's dialog text fits one of the
      roster characters; apply at confidence >= threshold.
    Returns a summary dict; writes the (possibly corrected) XML in place.
    """
    tree = ET.parse(xml_path)
    root = tree.getroot()
    roster_lower = {c.lower(): c for c in characters}
    changed: List[Dict[str, str]] = []

    for dlg in root.iter("dialog"):
        attr, speaker = _speaker_attr(dlg)
        if not speaker:
            continue
        if speaker.lower() in roster_lower:
            if speaker == roster_lower[speaker.lower()]:
                continue  # exact canonical match: fine
            # right name, wrong case: normalize without Jev
            canonical = roster_lower[speaker.lower()]
            dlg.set(attr, canonical)
            changed.append({"from": speaker, "to": canonical, "how": "roster-normalize"})
            _log(f"character normalized: '{speaker}' -> '{canonical}'")
            continue

        canonical = _correct_case(speaker, characters)
        if canonical:
            dlg.set(attr, canonical)
            changed.append({"from": speaker, "to": canonical, "how": "roster-normalize"})
            _log(f"character normalized: '{speaker}' -> '{canonical}'")
            continue

        # Unknown name: ask Jev which roster character fits this dialog text.
        text = (dlg.text or "").strip()[:500]
        choice, confidence = _ask_choice(
            client,
            {"dialog_text": text, "assigned_speaker": speaker},
            "correct_character",
            characters,
            "Given the dialog text and the (possibly misspelled) assigned "
            "speaker name, which roster character most likely speaks this line?",
        )
        if choice and float(confidence) >= float(jev_cfg["confidence"]):
            dlg.set(attr, choice)
            changed.append({"from": speaker, "to": choice, "how": "jev"})
            _log(f"jev reassigned speaker: '{speaker}' -> '{choice}'")
        else:
            _log(f"unresolved speaker '{speaker}': left as-is "
                 f"(jev={'dry' if client is None else 'low-confidence'})")

    if changed:
        tree.write(xml_path, encoding="unicode", xml_declaration=False)
    return {"characters": changed}


def confidence_ok(jev_cfg: dict, confidence: float) -> bool:
    return confidence >= float(jev_cfg["confidence"])


def validate_emotion_tags(
    xml_path: Path,
    char_emotions: Dict[str, List[str]],
    jev_cfg: dict,
    client: Optional[JevClient] = None,
) -> Dict[str, Any]:
    """For characters with configured emotions, remap utterance emotion tags
    to the configured set when Jev matches at confidence >= the
    emotion-confidence-threshold. Emotions on characters with no configured
    emotions are left untouched.
    """
    tree = ET.parse(xml_path)
    root = tree.getroot()
    changed: List[Dict[str, str]] = []

    for dlg in root.iter("dialog"):
        _attr, speaker = _speaker_attr(dlg)
        emotions = char_emotions.get(speaker.lower(), []) if speaker else []
        if not emotions:
            continue
        current = (dlg.get("emotion") or "").strip()
        if not current or current.lower() in (e.lower() for e in emotions):
            continue
        text = (dlg.text or "").strip()[:600]
        base_instruct = ""
        choice, confidence = _ask_choice(
            client,
            {"dialog_text": text, "current_emotion": current,
             "character_base_instruct": base_instruct},
            "best_emotion",
            emotions,
            "Given the dialog text and its current emotion tag, which of the "
            "character's configured emotions best matches this line?",
        )
        if choice and confidence >= float(jev_cfg["confidence"]):
            dlg.set("emotion", choice)
            changed.append({"speaker": speaker, "from": current, "to": choice,
                            "confidence": f"{confidence:.2f}"})
            _log(f"jev emotion remap: {speaker} '{current}' -> '{choice}' "
                 f"(confidence {confidence:.2f})")
        else:
            _log(f"emotion '{current}' for {speaker}: kept as-is "
                 f"(confidence {confidence:.2f} < {jev_cfg['confidence']})")

    if changed:
        tree.write(xml_path, encoding="unicode", xml_declaration=False)
    return {"emotions": changed}


def collect_char_emotions(config: dict) -> Dict[str, List[str]]:
    """Build {character_lower: [emotion names]} from a story config."""
    out: Dict[str, List[str]] = {}
    for char in config.get("characters", []):
        name = str(char.get("name", "")).strip().lower()
        if not name:
            continue
        emotions: List[str] = []
        cv = char.get("custom-voice")
        if isinstance(cv, dict) and isinstance(cv.get("emotions"), list):
            emotions.extend(
                e.get("emotion") or e.get("name")
                for e in cv["emotions"] if isinstance(e, dict)
            )
        for e in char.get("cloned-emotion", []) or []:
            if isinstance(e, dict) and e.get("emotion"):
                emotions.append(e["emotion"])
        if emotions:
            out[name] = [str(e) for e in emotions if e]
    return out


def run_jev_validation(xml_path: Path, config: dict) -> Dict[str, Any]:
    """Pipeline entry point: call after chapter_to_xml writes the XML.

    Config gate: jev.enabled must be true; otherwise this is a no-op.
    Live mode requires TYPESAFE_API_KEY (or jev.api-key-env); without it the
    run is a dry pass that logs roster-mismatches but changes nothing.
    """
    jev_cfg = load_jev_config(config)
    if not jev_cfg["enabled"]:
        _log("jev.enabled is false: skipping validation")
        return {"skipped": True}

    if not jev_cfg["api_key"]:
        # No API key configured: Jev actions require it. Log and skip entirely
        # (the XML is left untouched; no dry-run side effects).
        _log("no api key configured: jev validation skipped entirely "
             f"(set {os.getenv('JEV_KEY_HINT', 'TYPESAFE_API_KEY')} to enable)")
        return {"skipped": True, "reason": "no_api_key"}

    client = JevClient(jev_cfg["api_base"], jev_cfg["api_key"],
                       jev_cfg["model"], jev_cfg["timeout"])

    roster = [str(c.get("name")) for c in config.get("characters", []) if c.get("name")]
    result = {"skipped": False, "dry": False,
              **validate_character_assignments(xml_path, roster, jev_cfg, client),
              **validate_emotion_tags(xml_path, collect_char_emotions(config), jev_cfg, client)}
    return result


if __name__ == "__main__":
    import argparse
    import yaml
    ap = argparse.ArgumentParser(description="Jev post-conversion XML validation")
    ap.add_argument("xml_file", type=Path)
    ap.add_argument("--config", type=Path, default=Path("story-config.yml"))
    args = ap.parse_args()
    with open(args.config) as f:
        cfg = yaml.safe_load(f)
    result = run_jev_validation(args.xml_path.resolve(), cfg or {})
    print(json.dumps(result, indent=2))