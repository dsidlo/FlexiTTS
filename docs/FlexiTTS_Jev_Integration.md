# Jev (TypeSafe AI) Research Report — Fit Assessment for FlexiTTS

**Date:** 2026-09-21
**Sources:** docs.typesafe.ai (introduction, primitives, patterns, use-case map, SDK), independent analysis at DataCamp, and a code-level inventory of FlexiTTS decision points (`chapter_xml_to_audio.py`, `chapter_to_xml.py`, `validate_config.py`, `sox_service.py`, `flexitts_api.py`).

---

## 1. What Jev is

Jev is TypeSafe's first "System One" model (launched September 15, 2026, early access). Unlike LLMs that generate text, Jev takes program **state** plus typed **questions** and returns **structured, typed decisions with calibrated probabilities** — no text generation, nothing to parse.

Three primitives, all evaluated in parallel against the same state in one call (70-500ms latency):

| Primitive | Question type | Returns |
|---|---|---|
| **Choice** | Pick one option from a defined list | `choice`, `probabilities`, `confidence` |
| **Score** | Rate against an ordered rubric | `score`, `probabilities`, `confidence` |
| **Noul** | Yes/no judgment | probability 0-1 |

Key properties and economics:

- ~$0.042 per million input tokens; output tokens free
- ~$0.0004 per decision case (~76x cheaper than GPT-5.6 Terra at comparable accuracy, per vendor benchmarks)
- Zero structured-output errors by construction (outputs are schema-constrained)
- Calibrated confidence on every output — usable as an architectural gate, not decoration
- Access: early access behind a waitlist; `POST https://api.typesafe.ai/v1/systemone`, model route `jev-latest`; Python SDK via `uv add typesafe-sdk`

### Honest caveats

- Benchmarks are vendor-reported (their own eval harness, reference answers from OpenAI/Anthropic models); no independent reproduction has surfaced yet
- Peaks ~5-6 accuracy points below the best frontier LLMs on their benchmark (67.8% vs 73-74%)
- Returns numbers only — no rationale/explanation, which matters for debugging and audit
- Wrong tool for open-ended generation (writes no text at all)
- Cloud dependency: FlexiTTS currently runs fully offline with local TTS; a Jev call adds a network dependency

---

## 2. Fit assessment against FlexiTTS decision points

The codebase's judgment points were inventoried and mapped to Jev primitives.

### Good fits

**1. Emotion fallback inference — best fit.**
Today `chapter_xml_to_audio.py` uses a string heuristic when a character's utterance emotion does not exactly match a configured emotion:

```python
if emotion_instruct:
    instruct = emotion_instruct
elif base_instruct:
    instruct = f"{base_instruct}. Speak in a {utt.emotion} tone."
else:
    instruct = f"Speak in a {utt.emotion} tone."
```

A Choice question per utterance — *"Given this character's base instruct and the line's text, which configured emotion best fits?"* over the character's emotion list — would map dialogue to the **closest defined** emotion instead of inventing tone text that Qwen may not honor. High volume (one per utterance), bounded options (the character's configured emotions), and confidence lets the code fall back to the current heuristic when uncertain. This composes directly with the existing Qwen3-TTS instruct pipeline.

**2. Pre-render sanity gate (pre-flight verification).**
A Noul question per chapter — *"Is this XML dialog breakdown plausible for the source chapter text?"* — catches bad LLM breakdowns before GPU generation time is spent. Cheap verification; the render pipeline already has a preflight hook (`validate_character_voice_setup`).

**3. Unresolved-reference suggestion.**
When `ReferenceField` commits a typo'd reference, a Choice over existing dialog-effects/voice-samples ("did they mean X?") could auto-resolve instead of leaving the field red. Low volume, but a clear UX improvement inside the existing stub-generation flow.

**4. Chapter-to-XML guardrails (universal verification pattern).**
Noul checks on the Grok breakdown output — "does every dialog line's speaker exist in the config?", "is this emotion label one of the character's defined emotions?" — form a cheap second-opinion layer on LLM structured output before audio generation. This matches TypeSafe's "Universal Verification" pattern.

### Poor fits (explicit no's)

| Area | Why not |
|---|---|
| Chapter-to-XML breakdown itself | Open-ended text generation; that is Grok's job. Jev generates no text. |
| `validate_config.py` | Deterministic JSON Schema checks; a model adds cost and nondeterminism where code guarantees correctness. |
| SoX effect validation | Already a whitelist lookup against documented effects; a model adds nothing. |
| Help system / user-facing diagnostics | Jev returns a number with no rationale; explanations need an LLM. |

---

## 3. Recommended integration: emotion fallback (prototype sketch)

Keep it optional and heuristic-fallback-safe:

```python
# Optional dependency; feature-flagged in FlexiTTS.yml
# jev:
#   enabled: true
#   api-key-env: TYPESAFE_API_KEY
#   confidence-threshold: 0.75

def resolve_emotion_via_jev(char_cfg: dict, utt, emotions: list[str]) -> str | None:
    """Return the best-matching configured emotion name, or None to use
    the existing heuristic. Confidence-gated."""
    resp = _jev_call(
        state={
            "character_base_instruct": char_cfg.get("custom-voice", {}).get("instruct", ""),
            "line_text": utt.text,
            "requested_emotion": utt.emotion,
        },
        questions={
            "emotion": {"type": "choice", "options": emotions},
        },
    )
    if resp["confidence"] >= config_threshold:
        return resp["choice"]
    return None  # caller falls back to the current string heuristic
```

Design notes:

- Cost: ~$0.0004 per utterance; a 1000-utterance chapter is ~$0.40 worst case (only unmatched emotions need the call — exact matches stay free)
- Latency: 70-500ms per unmatched utterance; batch all unresolved utterances of a chapter into one call (TypeSafe evaluates questions in parallel, so batching barely changes latency)
- Graceful degradation: network failure or waitlist absence falls back to today's behavior — the feature flag means nothing breaks
- Confidence gate: below threshold, use the current heuristic (the system never acts on a low-confidence guess)

---

## 4. Verdict

**Yes, Jev is useful within FlexiTTS — as a targeted enhancement, not a foundation.** The first integration to build is the emotion-fallback Choice: it replaces a string heuristic with a calibrated, typed answer at exactly the volume point where FlexiTTS currently guesses. Everything else (config validation, SoX validation, text generation) either already guarantees correctness deterministically or requires open-ended generation Jev cannot do. Because Jev is cloud-only and early-access, keep the integration behind a config flag with heuristic fallback so offline/local operation is unaffected.
