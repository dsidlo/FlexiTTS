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
        k.lower() in ("jev", "laya") and isinstance(v, dict)
        for k, v in config.items())


def _find_blocks(config: dict) -> Tuple[dict, dict]:
    """Extract (jev_block, laya_block) from a config dict, case-insensitively."""
    jev_block: dict = {}
    laya_block: dict = {}
    if isinstance(config, dict):
        for k, v in config.items():
            lk = k.lower()
            if lk == "jev" and isinstance(v, dict):
                jev_block = dict(v)
            elif k.lower() == "laya" and isinstance(v, dict):
                laya_block = dict(v)
    return jev_block, laya_block


def _find_global_config_file() -> Optional[Path]:
    """Global config: XDG ~/.config/FlexiTTS/FlexiTTS.yml (preferred),
    .yaml legacy fallback, then the repo's config/FlexiTTS.yml."""
    candidates = []
    xdg = os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))
    candidates.append(Path(xdg) / "FlexiTTS" / "FlexiTTS.yml")
    candidates.append(Path(xdg) / "FlexiTTS" / "FlexiTTS.yaml")
    repo_cfg = Path(__file__).resolve().parent.parent.parent / "config" / "FlexiTTS.yml"
    candidates.append(repo_cfg)
    for c in candidates:
        if c.exists():
            return c
    return None


def _load_global_blocks() -> Tuple[dict, dict]:
    """Load (jev_block, laya_block) from the global config file, if any."""
    path = _find_global_config_file()
    if not path:
        return {}, {}
    try:
        import yaml
        data = yaml.safe_load(path.read_text()) or {}
        return _find_blocks(data)
    except Exception:
        return {}, {}


def _ensure_env_loaded() -> None:
    """Load ~/.env once so api-key-env resolution works without dotenv callers."""
    if os.getenv("JEV_ENV_LOADED"):
        return
    env_path = Path.home() / ".env"
    if env_path.exists():
        try:
            from dotenv import load_dotenv
            load_dotenv(dotenv_path=env_path)
        except ImportError:
            # minimal parser fallback: KEY=VALUE lines
            for line in env_path.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    os.environ.setdefault(k.strip(), v.strip())
    os.environ["JEV_ENV_LOADED"] = "1"


def _normalize_block(block: dict) -> dict:
    """Case-insensitive sub-key view of a config block."""
    return {k.lower(): v for k, v in (block or {}).items()}


def load_validation_config(config: dict) -> dict:
    """Load merged validation settings.

    Precedence: story-config.yml blocks > FlexiTTS.yml global blocks.
    Jev is the preferred engine; Laya is the local fallback.
    """
    _ensure_env_loaded()

    story_jev, story_laya = _find_blocks(config or {})
    if not story_jev and not story_laya:
        global_jev, global_laya = _load_global_blocks()
        jev_block, laya_block = global_jev, global_laya
    else:
        jev_block, laya_block = story_jev, story_laya

    j = _normalize_block(jev_block)
    l = _normalize_block(laya_block)

    def _first(*keys, default=None):
        for k in keys:
            if k in j:
                return j[k]
        for k in keys:
            if k in l:
                return l[k]
        return default

    key_env = str(_first("api-key-env", default="TYPESAFE_API_KEY"))
    emotion_key = _first("emotion-confidence-threshold", default=None)
    if emotion_key is None:
        emotion_key = _first("confidence-threshold", default=DEFAULT_CONFIDENCE)
    confidence = float(emotion_key)

    jev_enabled = bool(j.get("enabled", False))
    laya_enabled = bool(l.get("enabled", False))

    return {
        "jev": {
            "enabled": jev_enabled,
            "api_key": os.getenv(key_env, ""),
            "api_base": str(j.get("api-base", DEFAULT_API_BASE)),
            "model": str(j.get("model", DEFAULT_MODEL)),
            "timeout": float(j.get("timeout", DEFAULT_TIMEOUT)),
        },
        "laya": {
            "enabled": laya_enabled,
            "model": str(l.get("model", j.get("laya-model", "english"))),
            "min-vram-mb": int(l.get("min-vram-mb", 1500)),
            "device": str(l.get("device", "auto")),
            "confidence": float(l.get("emotion-confidence-threshold",
                                      l.get("confidence-threshold",
                                            confidence))),
        },
        # validation-wide values (engine-independent)
        "confidence": confidence,
        "key_env": key_env,
        # legacy keys kept for existing tests/callers
        "enabled": jev_enabled or laya_enabled,
        "api_key": os.getenv(key_env, ""),
        "api_base": str(j.get("api-base", DEFAULT_API_BASE)),
        "model": str(j.get("model", DEFAULT_MODEL)),
        "timeout": float(j.get("timeout", DEFAULT_TIMEOUT)),
        "min-vram-mb": int(l.get("min-vram-mb", 1500)),
    }


# Backwards-compat alias
def load_jev_config(config: dict) -> dict:
    return load_validation_config(config)


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

    TOURNAMENT_THRESHOLD = int(os.environ.get("JLISTEN_LAYA_MAX_OPTIONS", "8"))
    GROUP_SIZE = 4
    ADVANCE_PER_GROUP = 2

    def ask(self, state, questions):
        try:
            router = self._get_router()
            laya_questions = {}
            for key, q in questions.items():
                opts = q.get("options") or []
                if q.get("type") == "choice" and len(opts) > self.TOURNAMENT_THRESHOLD:
                    # Two-stage tournament keeps option counts within Laya's
                    # architectural budget while covering every candidate.
                    winner, confidence = self._tournament_choice(
                        router, state, key, q, opts)
                    return {"answers": {key: {"choice": winner,
                                              "confidence": confidence}}}
                laya_questions[key] = {
                    "type": q.get("type"),
                    "instructions": q.get("instruction", ""),
                    "criteria": {o: o for o in opts},
                }
            t0 = time.time()
            res = router.predict(state, laya_questions, model=self.laya_model)
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

    def _run_choice(self, router, state, instruction: str, options: list,
                    group_label: str = ""):
        """Single small choice question; returns (choice, confidence)."""
        q = {"type": "choice", "instructions": instruction,
             "criteria": {o: o for o in options}}
        res = router.predict(state, {"q": q}, model=self.laya_model)
        a = (res.get("answers") or {}).get("q", {})
        choice, conf = a.get("choice"), float(a.get("confidence", 0.0))
        _log(f"laya tournament round: opts={len(options)} -> "
             f"{choice!r} ({conf:.2f})")
        return choice, conf

    def _tournament_choice(self, router, state, key, q, options: list):
        """Grouped rounds + final: every candidate covered exactly once;
        per-group winners (plus runners-up) advance to a small final round.
        Returns (best_choice, final_confidence)."""
        instruction = q.get("instruction", "Which option best matches?")
        groups = [options[i:i + self.GROUP_SIZE]
                  for i in range(0, len(options), self.GROUP_SIZE)]
        _log(f"laya tournament: {len(options)} options -> {len(groups)} groups "
             f"of <= {self.GROUP_SIZE}")
        ranked: list = []  # (choice, confidence) from each group
        assigned = str(state.get("assigned_speaker", ""))
        for gi, group in enumerate(groups):
            choice, conf = self._run_choice(router, state, instruction, group)
            if not choice:
                continue
            # Name-similarity tiebreak: Laya's base weights are uncalibrated
            # (often 0.00 confidence), so boost candidates whose name is close
            # to the assigned speaker. Ratio 0..1, weighted lightly.
            boost = 0.0
            if assigned:
                import difflib
                boost = difflib.SequenceMatcher(None, assigned.lower(),
                                                choice.lower()).ratio() * 0.1
            ranked.append((choice, conf + boost))
        if not ranked:
            return None, 0.0
        # Reassess: rank round-1 winners by confidence; winners advance, then
        # fill remaining finalist slots with runners-up until GROUP_SIZE.
        ranked.sort(key=lambda x: -x[1])
        finalists = []
        for choice, _conf in ranked:
            if choice not in finalists:
                finalists.append(choice)
        for gi, group in enumerate(groups):
            if len(finalists) >= self.GROUP_SIZE:
                break
            for o in group:
                if len(finalists) >= self.GROUP_SIZE:
                    break
                if o not in finalists:
                    finalists.append(o)
        if len(finalists) == 1:
            return finalists[0], ranked[0][1]
        winner, confidence = self._run_choice(router, state, instruction,
                                              finalists)
        return winner, confidence


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
    """Resolve the engine per the user's conditions:

    1. Jev, if jev.enabled and an api key exists.
    2. Laya, if laya.enabled and GPU + free VRAM meet min-vram-mb.
    3. Laya on CPU if laya.enabled and device is explicitly "cpu".
    4. Otherwise: no engine (caller skips).
    """
    jev = jev_cfg["jev"]
    laya = jev_cfg["laya"]

    if jev["enabled"]:
        if jev["api_key"]:
            return (JevClient(jev["api_base"], jev["api_key"],
                              jev["model"], jev["timeout"]), "jev")
        _log("jev enabled but no api key; trying laya fallback")

    if laya["enabled"]:
        if _laya_available(laya):
            device = laya["device"] if laya["device"] != "auto" else None
            return LayaClient(laya["model"], device or "auto"), "laya"
        if str(laya["device"]).lower() == "cpu":
            return LayaClient(laya["model"], "cpu"), "laya"
        _log("laya enabled but GPU/VRAM/package unavailable")

    return None, None



class JevClient:
    """Thin client for the TypeSafe System One API."""

    def __init__(self, api_base: str, api_key: str, model: str, timeout: float):
        self.api_base = api_base.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    @staticmethod
    def _to_wire_questions(questions: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """Convert our internal question form to the System One wire format:
        choice questions use criteria {key: description} (not options lists)
        and the field is 'instructions' (plural)."""
        wire = {}
        for key, q in questions.items():
            wq = dict(q)
            qtype = q.get("type")
            if qtype == "choice":
                opts = q.get("options") or []
                wq["criteria"] = {o: o for o in opts}
                wq["instructions"] = q.get("instruction", "")
                wq.pop("options", None)
                wq.pop("instruction", None)
            elif qtype == "score":
                crit = q.get("criteria")
                if isinstance(crit, list):
                    wq["criteria"] = crit
                wq["instructions"] = q.get("instruction", "")
                wq.pop("instruction", None)
            elif qtype == "noul":
                wq["instructions"] = q.get("instruction", "")
                wq.pop("instruction", None)
            wire[key] = wq
        return wire

    def ask(self, state: Dict[str, Any], questions: Dict[str, Dict[str, Any]]) -> Optional[dict]:
        payload = {"model": self.model, "state": state,
                   "questions": self._to_wire_questions(questions)}
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
        except urllib.error.HTTPError as e:
            try:
                detail = e.read().decode()[:300]
            except Exception:
                detail = ""
            _log(f"api call failed: HTTP {e.code}: {detail}")
            return None
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


def _ask_choice_tournament(client, state: dict, options: List[str],
                           instruction: str,
                           group_size: int = 5,
                           advance: int = 2) -> Tuple[Optional[str], float]:
    """Grouped choice rounds + reassessed final for large option sets.

    Large rosters dilute per-option confidence (real API: 0.56 on a
    14-name roster vs 0.93 on 4 names). Splitting into small groups keeps
    each round's confidence meaningful while covering every candidate.
    """
    if client is None:
        return None, 0.0
    groups = [options[i:i + group_size]
              for i in range(0, len(options), group_size)]
    winners: List[Tuple[str, float]] = []
    for group in groups:
        choice, conf = _ask_choice(client, state, "correct_character",
                                   group, instruction)
        if choice:
            winners.append((choice, conf))
    if not winners:
        return None, 0.0
    winners.sort(key=lambda x: -x[1])
    finalists: List[str] = []
    for choice, _conf in winners:
        if choice not in finalists:
            finalists.append(choice)
    for group in groups:
        if len(finalists) >= group_size:
            break
        for o in group:
            if len(finalists) >= group_size:
                break
            if o not in finalists:
                finalists.append(o)
    if len(finalists) == 1:
        return finalists[0], winners[0][1]
    return _ask_choice(client, state, "correct_character", finalists,
                       instruction)


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
        # Large rosters dilute per-option confidence; use a grouped tournament
        # (small choice sets per round) so confidence stays meaningful.
        text = (dlg.text or "").strip()[:500]
        state = {"dialog_text": text, "assigned_speaker": speaker}
        instruction = ("Given the dialog text and the (possibly misspelled) "
                       "assigned speaker name, which roster character most "
                       "likely speaks this line?")
        if len(characters) > 8:
            choice, confidence = _ask_choice_tournament(
                client, state, characters, instruction)
        else:
            choice, confidence = _ask_choice(
                client, state, "correct_character", characters, instruction)
        if choice and float(confidence) >= float(jev_cfg["confidence"]):
            dlg.set(attr, choice)
            changed.append({"from": speaker, "to": choice, "how": "jev"})
            _log(f"jev reassigned speaker: '{speaker}' -> '{choice}' "
                 f"(confidence {confidence:.2f})")
        else:
            _log(f"unresolved speaker '{speaker}': left as-is "
                 f"(confidence {confidence:.2f} < gate)")

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
    jev_cfg = load_validation_config(config)
    if not jev_cfg["enabled"]:
        _log("neither Jev nor Laya enabled: skipping validation")
        return {"skipped": True, "reason": "disabled"}

    client, backend = select_backend(jev_cfg)
    if client is None:
        _log("no engine available: jev missing key, laya unavailable")
        return {"skipped": True, "reason": "no_engine"}

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