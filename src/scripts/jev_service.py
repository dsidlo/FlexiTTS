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
import time
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


def _has_jev_block(config: dict) -> bool:
    return isinstance(config, dict) and any(
        k.lower() == "jev" and isinstance(v, dict) for k, v in config.items())


def _find_global_jev_config() -> dict:
    """Optional global Jev block from config/FlexiTTS.yml (repo) or the XDG
    ~/.config/FlexiTTS/FlexiTTS.yml. story-config.yml wins when it has its
    own jev block."""
    candidates = []
    xdg = os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))
    # Same preference order as base_config_manager: .yaml first, then .yml
    candidates.append(Path(xdg) / "FlexiTTS" / "FlexiTTS.yaml")
    candidates.append(Path(xdg) / "FlexiTTS" / "FlexiTTS.yml")
    repo_cfg = Path(__file__).resolve().parent.parent.parent / "config" / "FlexiTTS.yml"
    candidates.append(repo_cfg)
    for c in candidates:
        try:
            if c.exists():
                import yaml
                data = yaml.safe_load(c.read_text()) or {}
                for k, v in data.items():
                    if k.lower() == "jev" and isinstance(v, dict):
                        return v
        except Exception:
            continue
    return {}


def load_jev_config(config: dict) -> dict:
    """Read the jev: block from a story/global config, with defaults.
    Key lookup is case-insensitive (jev / Jev / JEV all match).
    Precedence: story-config.yml jev block > FlexiTTS.yml jev block.

    backend: jev | laya | auto (default auto).
      - jev: cloud API; requires api key (skips without one).
      - laya: local Laya model; requires GPU + free VRAM (min-vram-mb).
      - auto: laya when the laya package is installed AND a GPU with enough
        free VRAM is present; otherwise jev when an api key exists; else skip.
    """
    cfg = {}
    if _has_jev_block(config):
        for k, v in config.items():
            if k.lower() == "jev" and isinstance(v, dict):
                cfg = dict(v)
                break
    else:
        cfg = _find_global_jev_config()

    # Sub-keys are also read case-insensitively (Backend / BACKEND etc.)
    lc = {k.lower(): v for k, v in cfg.items()}
    key_env = str(lc.get("api-key-env", "TYPESAFE_API_KEY"))
    confidence = lc.get("emotion-confidence-threshold",
                        lc.get("confidence-threshold", DEFAULT_CONFIDENCE))
    return {
        "enabled": bool(lc.get("enabled", False)),
        "backend": str(lc.get("backend", "auto")).strip().lower(),
        "api_key": os.getenv(key_env, ""),
        "api_base": str(lc.get("api-base", DEFAULT_API_BASE)),
        "model": str(lc.get("model", DEFAULT_MODEL)),
        "confidence": float(confidence),
        "timeout": float(lc.get("timeout", DEFAULT_TIMEOUT)),
        "min-vram-mb": int(lc.get("min-vram-mb", 1500)),
        "laya-model": str(lc.get("laya-model", "english")),
        "device": str(lc.get("device", "auto")),
    }

def gpu_free_vram_mb() -> int:
    """Free VRAM in MB via nvidia-smi; 0 when no NVIDIA GPU is present."""
    try:
        import subprocess
        out = subprocess.run(["nvidia-smi", "--query-gpu=memory.free",
                              "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=5)
        if out.returncode == 0 and out.stdout.strip():
            # first GPU's free memory
            return int(out.stdout.strip().splitlines()[0])
    except Exception:
        pass
    return 0


class LayaClient:
    """Local Laya (System 1) adapter. Same ask() contract as JevClient.

    Maps Jev-style choice questions (options: [...]) to Laya criteria
    ({opt: opt}) and normalizes the response into
    {"answers": {key: {"choice": ..., "confidence": ...}}}.
    """

    _router = None  # class-level singleton: keep model resident

    def __init__(self, laya_model: str = "english", device: str = "auto"):
        self.laya_model = laya_model
        self.device = device

    def _get_router(self):
        if LayaClient._router is None:
            import warnings
            warnings.filterwarnings("ignore")
            from laya import Router
            kwargs = {}
            if self.device == "cpu":
                kwargs["device"] = "cpu"
            LayaClient._router = Router(preload=True, **kwargs)
        return LayaClient._router

    def ask(self, state, questions):
        try:
            router = self._get_router()
            laya_questions = {}
            for key, q in questions.items():
                if q.get("type") == "choice":
                    opts = q.get("options") or []
                    laya_questions[key] = {
                        "type": "choice",
                        "instructions": q.get("instruction", ""),
                        "criteria": {o: o for o in opts},
                    }
                else:
                    laya_questions[key] = dict(q)
            t0 = time.time()
            res = router.predict(state, laya_questions,
                                 model=self.laya_model)
            _log(f"laya predict {time.time()-t0:.3f}s")
            answers = {}
            for key, a in (res.get("answers") or {}).items():
                conf = a.get("confidence", 0.0)
                if "choice" in a:
                    answers[key] = {"choice": a["choice"], "confidence": conf}
                elif "noul" in a:
                    answers[key] = {"choice": bool(a["noul"] >= 0.5),
                                    "confidence": a["noul"]}
                elif "score" in a:
                    answers[key] = {"score": a.get("score"), "confidence": conf}
            return {"answers": answers}
        except Exception as e:
            _log(f"laya ask failed: {type(e).__name__}: {e}")
            return None


def _gpu_ok(min_vram_mb: int) -> bool:
    free = gpu_free_vram_mb()
    ok = free >= min_vram_mb
    _log(f"gpu check: free={free}MB required={min_vram_mb}MB -> {ok}")
    return ok


def _laya_available(jev_cfg: dict) -> bool:
    try:
        import laya  # noqa: F401
    except ImportError:
        _log("laya package not installed")
        return False
    return _gpu_ok(int(jev_cfg["min-vram-mb"]))


def select_backend(jev_cfg: dict) -> Tuple[Optional[Any], Optional[str]]:
    """Resolve the backend per config + machine state.

    Returns (client, backend_name) or (None, None) when nothing qualifies.
      - backend jev: JevClient (api key required by caller gate)
      - backend laya: LayaClient (GPU/VRAM checked)
      - backend auto: laya if available; else jev (caller checks key)
    """
    backend = jev_cfg["backend"]
    if backend not in ("jev", "laya", "auto"):
        _log(f"unknown backend '{backend}': treating as auto")
        backend = "auto"
    if backend == "laya":
        if _laya_available(jev_cfg):
            return LayaClient(jev_cfg["laya-model"], jev_cfg["device"]), "laya"
        _log("laya unavailable (package/GPU/VRAM); will fall back")
        return None, None
    if backend == "jev":
        return JevClient(jev_cfg["api_base"], jev_cfg["api_key"],
                         jev_cfg["model"], jev_cfg["timeout"]), "jev"
    # auto
    if _laya_available(jev_cfg):
        return LayaClient(jev_cfg["laya-model"], jev_cfg["device"] if
                          isinstance(jev_cfg["device"], str) else "auto"), "laya"
    if jev_cfg["api_key"]:
        return (JevClient(jev_cfg["api_base"], jev_cfg["api_key"],
                          jev_cfg["model"], jev_cfg["timeout"]), "jev")
    return None, None


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
        return {"skipped": True, "reason": "disabled"}

    client, backend = select_backend(jev_cfg)

    if backend == "jev" and not jev_cfg["api_key"]:
        # Jev cloud requires the api key; skip entirely (XML untouched).
        _log("backend jev but no api key configured: validation skipped "
             "(set TYPESAFE_API_KEY to enable, or use the laya backend)")
        return {"skipped": True, "reason": "no_api_key"}
    if client is None:
        # auto/laya resolved to nothing: laya unavailable (package/GPU/VRAM)
        # and no jev api key. Local-first design falls back to laya on CPU
        # only when explicitly requested (backend: laya, device: cpu).
        if jev_cfg["backend"] == "laya" and str(jev_cfg["device"]).lower() == "cpu":
            client, backend = LayaClient(jev_cfg["laya-model"], "cpu"), "laya"
        else:
            _log("no usable backend (no laya package/GPU, no jev api key): "
                 "validation skipped")
            return {"skipped": True, "reason": "no_backend"}

    _log(f"backend selected: {backend}")
    roster = [str(c.get("name")) for c in config.get("characters", []) if c.get("name")]
    result = {"skipped": False, "backend": backend,
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
    result = run_jev_validation(args.xml_file.resolve(), cfg or {})
    print(json.dumps(result, indent=2))