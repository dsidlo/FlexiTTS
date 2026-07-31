# Character Voice Configuration - Requirements Document

**Date:** 2026-03-20  
**Status:** DRAFT  
**Priority:** HIGH  
**Related:** [Commercial TTS Implementation Plan](./2026-03-20-commercial-tts-implementation-plan.md)

---

## Executive Summary

This document defines requirements for extending the character voice configuration schema in `story-config.yml` to support:

1. **Multi-provider voice configurations** (local Qwen3-TTS, Fish.audio, Grok-TTS, ElevenLabs, Cartesia)
2. **Provider-specific emotion mappings** for expressive narration
3. **Voice augmentation prompts** for dynamic context-aware speech
4. **Sound effects integration** for non-verbal cues
5. **Fallback mechanisms** when primary providers fail

---

## Background

### Current State

The current `story-config.yml` supports:

```yaml
characters:
  - name: Hendrix
    custom-voice:
      language: English
      speaker: ryan
      instruct: "Deep manly voice..."
    sox-effects:
      - overdrive 15 30
```

**Limitations:**
- Only supports Qwen3-TTS local provider
- No per-emotion voice variation
- No sound effects vocabulary
- No fallback if provider unavailable
- Cannot leverage commercial TTS features (emotion tags, cloned voices)

### Proposed State

Extended schema supporting multi-provider TTS with rich emotion control.

---

## Requirements

### REQ-001: Provider Declaration in custom-voice

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `custom-voice.provider` | enum | **Yes** | One of: `local`, `fish`, `grok`, `elevenlabs`, `cartesia`, `deepgram`, `playht` |

**Acceptance Criteria:**
- [ ] `provider` field must be validated against supported list
- [ ] Missing `provider` defaults to `local` for backward compatibility
- [ ] Invalid provider value triggers validation error with suggestions

**Example:**
```yaml
custom-voice:
  provider: fish
  voice_id: "f2e6ad6f82a14878a7cf6e8fb50a47c7"
```

---

### REQ-002: Fallback Voice Configuration

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `fallback-voice` | object | No | Alternative voice config if primary fails |

**Acceptance Criteria:**
- [ ] Fallback triggered when primary provider throws `TTSConnectionError`
- [ ] Fallback can be different provider type (e.g., commercial → local)
- [ ] Log warning when fallback activated
- [ ] Support nested fallback (fallback of fallback)

**Example:**
```yaml
custom-voice:
  provider: fish
  voice_id: "abc123"
fallback-voice:
  provider: local
  language: English
  speaker: ryan
  instruct: "Narrator voice, clear and professional"
```

---

### REQ-003: Provider-Specific Emotion Mappings

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `emotion-voices.{provider}` | map | No | Emotion → provider-specific expression |

**Standard Emotions:**
- `neutral`, `happy`, `excited`, `whispering`, `sad`, `angry`, `surprised`, `scared`, `mysterious`, `laughing`, `crying`, `sighing`

**Provider Mapping Syntax:**

| Provider | Mapping Format | Example |
|----------|----------------|---------|
| **Fish.audio** | Inline tags | `(happy)`, `(whisper)`, `[laughter]` |
| **Grok-TTS** | Natural language | `"Speak with enthusiasm"` |
| **ElevenLabs** | Tags + intensity | `[happy:0.8]`, `[whispering]` |
| **Cartesia** | Emotion IDs | `satisfaction:amusement` |
| **Local** | Instruct suffix | `"[excited tone]"` |

**Acceptance Criteria:**
- [ ] Emotion tags prepended/appended to text at render time
- [ ] Unknown emotions fall back to `neutral`
- [ ] Multiple emotions can be combined (e.g., `scared_whispering`)
- [ ] Validation warns if emotion not mapped for active provider

**Example:**
```yaml
emotion-voices:
  fish:
    neutral: "(calm)"
    happy: "(happy)"
    excited: "(excited) (fast)"
    whispering: "(whisper)"
    sad: "(sad) (slow)"
    surprised: "(OMG)"
    laughing: "[laughter]"
```

---

### REQ-004: Dynamic Voice Augmentation

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `voice-augmentation.scene-context` | map | No | Emotion modifier by scene type |
| `voice-augmentation.time-context` | map | No | Modifier by time of day |
| `voice-augmentation.location-context` | map | No | Modifier by location |

**Scene Context Keys:**
- `battle`, `stealth`, `dialogue`, `introspection`, `flashback`, `dream`

**Time Context Keys:**
- `morning`, `day`, `evening`, `night`, `dawn`, `dusk`

**Location Context Keys:**
- Open-ended (cave, forest, city, space, underwater, etc.)

**Acceptance Criteria:**
- [ ] Augmentation combines with base emotion (emotion + scene modifier)
- [ ] Multiple contexts can apply (scene + location)
- [ ] Context detected from story metadata or manual tagging
- [ ] Augmentation syntax matches provider format

**Example:**
```yaml
voice-augmentation:
  scene-context:
    battle: "(intense) (loud)"
    stealth: "(whisper) (cautious)"
    magic: "(mysterious) (resonant)"
  time-context:
    morning: "(energetic)"
    night: "(tired) (low_energy)"
  location-context:
    cave: "Add cavernous reverb suggestion"
    forest: "Natural ambient tone"
```

---

### REQ-005: Sound Effects Integration

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `sound-effects.text-tags` | map | No | Text pattern → sound tag |
| `sound-effects.utterance-effects` | object | No | Pre/post utterance sounds |
| `sound-effects.emotion-tags` | map | No | Emotion → sound tag |

**Supported Sound Tags (Fish.audio):**
- `[laughter]`, `[sigh]`, `[gasp]`, `[cough]`, `[throat_clear]`, `[breathing]`, `[crying]`, `[sneezing]`

**Utterance Effects:**
- `prefix`: Sound before speech
- `suffix`: Sound after speech  
- `breathing`: Add breathing between lines (boolean)

**Acceptance Criteria:**
- [ ] Text patterns replaced with sound tags before TTS generation
- [ ] Regex support for text pattern matching
- [ ] Sound tags validated against provider capabilities
- [ ] Prefix/suffix sounds added to text for supported providers

**Example:**
```yaml
sound-effects:
  text-tags:
    "*chuckles*": "[laughter]"
    "*sighs*": "[sigh]"
    "*gasp*": "[gasp]"
    "*clears throat*": "[throat_clear]"
  utterance-effects:
    prefix: "[beep]"
    suffix: ""
    breathing: true
  emotion-tags:
    laughing: "[laughter]"
    crying: "[crying]"
```

---

### REQ-006: Voice Sample Cloning (Commercial Providers)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `custom-voice.voice-sample` | path | No | Path to audio sample for cloning |
| `custom-voice.clone-options` | object | No | Cloning parameters |

**Clone Options:**
- `name`: Voice name for marketplace
- `description`: Voice description
- `visibility`: `public` or `private` (Fish.audio)

**Acceptance Criteria:**
- [ ] Sample cloned automatically on first use
- [ ] Clone ID cached in `~/.flexitts/voice-cache.yml`
- [ ] Clone validated (10s minimum, supported format)
- [ ] Re-clone on sample file hash change
- [ ] Error on cloning failure with provider message

**Example:**
```yaml
custom-voice:
  provider: fish
  voice-sample: "voices/character-sample.wav"
  clone-options:
    name: "MyCharacterVoice"
    description: "Deep, resonant fantasy character voice"
    visibility: private
```

---

### REQ-007: Post-Generation Audio Effects

**Note:** Existing `sox-effects` and `dialog-effects` remain unchanged.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `sox-effects` | list | No | Post-processing via SoX |
| `dialog-effects` | list | No | Named effect presets |

**Acceptance Criteria:**
- [ ] Effects applied after TTS generation
- [ ] Effects order preserved (chaining)
- [ ] Effects validated before rendering
- [ ] Dry-run mode previews effect chain

---

## Configuration Schema (YAML)

```yaml
characters:
  - name: string (required, unique)
    description: string (optional)
    
    # Primary voice configuration
    custom-voice:
      provider: enum [local, fish, grok, elevenlabs, cartesia, deepgram, playht]
      # Provider-specific fields:
      # For 'local':
      language: string
      speaker: string
      instruct: string
      # For 'fish', 'elevenlabs', etc.:
      voice_id: string
      # For cloning:
      voice-sample: path
      clone-options:
        name: string
        description: string
        visibility: enum [public, private]
    
    # Fallback configuration
    fallback-voice:
      # Same structure as custom-voice
    
    # Emotion mappings by provider
    emotion-voices:
      {provider}:
        {emotion}: {expression}
      # Example:
      fish:
        neutral: "(calm)"
        happy: "(happy)"
      grok:
        neutral: "Speak normally."
        happy: "Speak cheerfully."
    
    # Dynamic voice augmentation
    voice-augmentation:
      scene-context:
        {scene_type}: {expression_modifier}
      time-context:
        {time_of_day}: {expression_modifier}
      location-context:
        {location}: {expression_modifier}
    
    # Sound effects mapping
    sound-effects:
      text-tags:
        {text_pattern}: {sound_tag}
      utterance-effects:
        prefix: {sound_tag}
        suffix: {sound_tag}
        breathing: boolean
      emotion-tags:
        {emotion}: {sound_tag}
    
    # Audio post-processing (existing)
    sox-effects:
      - {sox_command}
    dialog-effects:
      - {preset_name}
```

---

## Validation Requirements

### VAL-001: Schema Validation

Validate at `story-config.yml` load time:

```python
def validate_character_config(config: dict) -> List[ValidationError]:
    errors = []
    
    # REQ-001: Provider must be valid
    if provider not in SUPPORTED_PROVIDERS:
        errors.append(InvalidProviderError(provider))
    
    # REQ-003: Emotions must be valid keys
    for emotion in emotion_voices.get(provider, {}):
        if emotion not in STANDARD_EMOTIONS:
            errors.append(UnknownEmotionError(emotion))
    
    # REQ-006: Voice sample must exist and be valid format
    if voice_sample and not Path(voice_sample).exists():
        errors.append(MissingSampleError(voice_sample))
    
    return errors
```

### VAL-002: Provider Capability Validation

Check at render time:

```python
EMOTION_CAPABILITIES = {
    "local": ["neutral", "instruct_modifiers"],
    "fish": ["neutral", "happy", "sad", "excited", "whispering", 
             "surprised", "laughing", "sighing", "speed"],
    "grok": ["neutral", "instruct_modifiers"],
    "elevenlabs": ["neutral", "happy", "sad", "whispering"],
}

def validate_emotion_for_provider(emotion: str, provider: str) -> bool:
    if emotion not in EMOTION_CAPABILITIES[provider]:
        logger.warning(f"Emotion '{emotion}' not supported by {provider}, using 'neutral'")
        return False
    return True
```

---

## Implementation Phases

### Phase 1: Core Schema Changes (Week 1)

| Task | Status | Notes |
|------|--------|-------|
| Update config parser for `provider` field | TODO | Backward compatible |
| Add `fallback-voice` support | TODO | Error handling |
| Update `chapter_xml_to_audio.py` | TODO | Read new fields |

### Phase 2: Emotion Mapping (Week 1-2)

| Task | Status | Notes |
|------|--------|-------|
| Define `emotion-voices` schema | TODO | Provider-agnostic emotions |
| Implement emotion-to-expression mapping | TODO | Provider-specific logic |
| Add emotion validation | TODO | Warning on unsupported |

### Phase 3: Augmentation & Effects (Week 2)

| Task | Status | Notes |
|------|--------|-------|
| Implement `voice-augmentation` | TODO | Context detection |
| Add `sound-effects` processing | TODO | Text pattern replacement |
| Support utterance prefix/suffix | TODO | Provider-specific |

### Phase 4: Voice Cloning (Week 2-3)

| Task | Status | Notes |
|------|--------|-------|
| Implement voice cloning callback | TODO | First-use cloning |
| Add clone caching | TODO | `~/.flexitts/voice-cache.yml` |
| Validate sample format | TODO | 10s minimum, WAV/MP3 |

### Phase 5: Testing & Documentation (Week 3)

| Task | Status | Notes |
|------|--------|-------|
| Unit tests for validation | TODO | All REQ items |
| Integration tests for providers | TODO | Mock API responses |
| Update documentation | TODO | This doc + user guide |

---

## Migration Guide

### Existing Config (No Changes Required)

```yaml
# Current format - continues to work
custom-voice:
  language: English
  speaker: ryan
  instruct: "..."
```

### Recommended Migration

Add `provider: local` explicitly:

```yaml
# Recommended - explicit provider
custom-voice:
  provider: local    # NEW: explicit declaration
  language: English
  speaker: ryan
  instruct: "..."
emotion-voices:      # NEW: emotion control
  local:
    neutral: ""
    excited: "[enthusiastic tone]"
```

### Full Migration Example

```yaml
# Before
custom-voice:
  language: English
  speaker: ryan
  instruct: "Deep voice"
sox-effects:
  - pitch -200

# After  
custom-voice:
  provider: local
  language: English
  speaker: ryan
  instruct: "Deep voice"

emotion-voices:
  local:
    neutral: ""
    excited: "[excited tone]"
    whispering: "[whispered]"

fallback-voice:
  provider: fish
  voice_id: "f2e6ad6f82a14878a7cf6e8fb50a47c7"

sox-effects:
  - pitch -200
```

---

## Testing Requirements

### Test Cases

| Test ID | Description | Expected |
|---------|-------------|----------|
| TC-001 | Missing provider field | Defaults to `local` |
| TC-002 | Invalid provider value | Validation error |
| TC-003 | Provider emotion mapping | Correct tags applied |
| TC-004 | Unknown emotion | Falls back to `neutral` |
| TC-005 | Fallback activation | Secondary voice used |
| TC-006 | Voice cloning first use | Clone created and cached |
| TC-007 | Sound effects replacement | Text → tags replaced |
| TC-008 | Augmentation context | Modifier applied |
| TC-009 | Full character pipeline | All features work together |
| TC-010 | Commercial API failure | Fallback triggers |

---

## References

- [Unified TTS API](./unified-tts-api.md)
- [Commercial TTS Implementation Plan](./2026-03-20-commercial-tts-implementation-plan.md)
- [Fish.audio Documentation](https://fish.audio/docs)
- [Grok-TTS Documentation](https://docs.x.ai/docs/guides/voice)

---

## Change Log

| Date | Version | Changes |
|------|---------|---------|
| 2026-03-20 | 1.0.0 | Initial requirements |
