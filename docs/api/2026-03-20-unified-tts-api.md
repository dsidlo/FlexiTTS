# Unified TTS API Interface Definition

Based on deep research into commercial TTS providers (ElevenLabs, Cartesia, Deepgram, Fish.audio, Hume.ai, Play.ht, Lovo.ai, Grok-TTS), this document defines a cross-provider API interface that abstracts the common parameters across all providers.

## API Version

`v1.0.0`

---

## Core Design Principles

1. **Abstraction over Implementation**: Hide provider-specific quirks behind a unified interface
2. **Progressive Enhancement**: Common parameters work everywhere; provider-specific features are optional extensions
3. **Emotion-First Design**: All providers support emotion/acting instructions to varying degrees
4. **Voice Cloning Support**: Unified interface for both pre-built and custom/cloned voices

---

## Request Schema

### `POST /v1/tts/synthesize`

#### Headers

```http
Authorization: Bearer {api_key}
Content-Type: application/json
X-TTS-Provider: elevenlabs | cartesia | deepgram | fish-audio | hume-ai | playht | lovo | grok
```

#### Request Body

```typescript
interface TtsRequest {
  // Required fields
  text: string;                    // Text to synthesize
  voice: VoiceConfig;              // Voice configuration

  // Optional synthesis controls
  model?: ModelConfig;             // Model selection
  audio?: AudioConfig;             // Audio output configuration
  prosody?: ProsodyConfig;         // Prosody/voice characteristics
  emotion?: EmotionConfig;        // Emotional expression
  context?: ContextConfig;         // Context for continuity
  streaming?: StreamingConfig;     // Streaming options
  
  // Provider-specific overrides
  provider?: ProviderConfig;       // Provider-specific parameters
}
```

---

## Field Definitions

### `VoiceConfig`

Unified voice specification supporting pre-built voices, cloned voices, and voice design.

```typescript
interface VoiceConfig {
  // Identification (one of id, name, or design required)
  id?: string;                     // Provider-specific voice ID
  name?: string;                   // Voice name (e.g., "Bella", "Adam")
  
  // Voice design/cloning (optional)
  design?: {
    description: string;           // Natural language description
    sample_url?: string;           // Reference audio for cloning
    sample_base64?: string;        // Base64 encoded reference audio
    instructions?: string;         // Specific instructions (Qwen3-style)
  };
  
  // Language specification
  language?: string;               // ISO 639-1 code (e.g., "en", "es")
  
  // Voice characteristics (optional, overrides preset)
  characteristics?: {
    gender?: 'male' | 'female' | 'neutral';
    age?: 'young' | 'adult' | 'mature';
    accent?: string;               // e.g., "american", "british"
    style?: string;                  // e.g., "conversational", "narrative"
  };
}
```

**Provider Mapping:**

| Field | ElevenLabs | Cartesia | Deepgram | Fish.audio | Hume.ai | Play.ht | Lovo | Grok |
|-------|-----------|----------|----------|------------|---------|---------|------|------|
| `id` | ✓ `voice_id` | ✓ `voice_id` | ✓ model param | ✓ `reference_id` | ✓ `voice.id` | ✓ `voice` | ✓ `speaker` | ✗ |
| `name` | ✓ via GET | ✓ via GET | ✗ | ✓ via GET | ✓ `voice.name` | ✓ via GET | ✓ via GET | ✓ `voice` |
| `design.description` | ✓ | ✗ | ✗ | ✗ | ✓ voice design | ✗ | ✗ | ✗ |
| `design.sample_*` | ✓ | ✗ | ✗ | ✓ cloning | ✓ cloning | ✓ Voice Clone | ✗ | ✗ |
| `language` | ✓ `language_code` | ✓ `language` | ✓ via model | ✗ | ✓ | ✓ | ✓ | ✗ |

---

### `ModelConfig`

TTS model and version selection.

```typescript
interface ModelConfig {
  id?: string;                     // Model identifier
  version?: string;                // Specific version/snapshot
  
  // Quality vs Latency trade-off
  tier?: 'ultra' | 'premium' | 'standard' | 'draft';
  latency_optimization?: number;     // 0-4 (ElevenLabs style)
}
```

**Provider Mapping:**

| Parameter | ElevenLabs | Cartesia | Deepgram | Fish.audio | Hume.ai | Play.ht | Lovo | Grok |
|-----------|-----------|----------|----------|------------|---------|---------|------|------|
| `id` | ✓ `model_id` | ✓ `model_id` | ✓ model | ✓ Model ID | ✓ `version` | ✓ Model | ✗ | ✗ |
| `version` | ✗ | ✓ Snapshot | ✗ | ✗ | ✓ | ✗ | ✗ | ✗ |
| `tier` | ✓ Flash/Turbo | ✓ Sonic-3/Sonic-Turbo | ✗ | ✓ S2/S2-Pro | ✓ Octave 1/2 | ✓ draft/standard/premium | ✗ | ✗ |

---

### `AudioConfig`

Audio output format configuration.

```typescript
interface AudioConfig {
  format?: AudioFormat;            // Container format
  encoding?: AudioEncoding;        // Audio encoding
  sample_rate?: SampleRate;        // Sample rate in Hz
  bitrate?: number;                // Bitrate in kbps
  
  // Volume normalization
  normalization?: boolean | {
    target_dBFS?: number;          // Target loudness
    true_peak?: number;             // True peak limit
  };
}

type AudioFormat = 'mp3' | 'wav' | 'pcm' | 'ogg' | 'flac' | 'mulaw';
type AudioEncoding = 'pcm_s16le' | 'pcm_s24le' | 'pcm_f32le' | 'mp3' | 'opus';
type SampleRate = 8000 | 16000 | 22050 | 24000 | 44100 | 48000;
```

**Provider Mapping:**

| Parameter | ElevenLabs | Cartesia | Deepgram | Fish.audio | Hume.ai | Play.ht | Lovo | Grok |
|-----------|-----------|----------|----------|------------|---------|---------|------|------|
| `format` | ✓ `output_format` | ✓ `container` | ✓ | ✓ | ✓ | ✓ | ✓ MP3 | ✓ |
| `encoding` | ✓ via format | ✓ `encoding` | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| `sample_rate` | ✓ via format | ✓ | ✓ `sample_rate` | ✗ | ✗ | ✗ | ✗ | ✗ |
| `bitrate` | ✓ via format | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |

---

### `ProsodyConfig`

Voice characteristics and speech prosody.

```typescript
interface ProsodyConfig {
  // Speed/Pace
  speed?: number;                  // 0.5 to 2.0 (multiplier)
  
  // Volume/Loudness
  volume?: number;                 // 0.5 to 2.0 (multiplier)
  
  // Pitch
  pitch?: number;                  // -1.0 to 1.0 (relative shift)
  pitch_shift?: number;            // Semitones (e.g., -4 for deeper)
  
  // Energy/Intensity
  energy?: number;                 // 0.0 to 2.0
  
  // Pauses
  trailing_silence?: number;        // Seconds of silence at end
  pause_duration?: number;         // Seconds for [pause] tags
}
```

**Provider Mapping:**

| Parameter | ElevenLabs | Cartesia | Deepgram | Fish.audio | Hume.ai | Play.ht | Lovo | Grok |
|-----------|-----------|----------|----------|------------|---------|---------|------|------|
| `speed` | ✗ | ✓ `speed` (0.6-1.5) | ✗ | ✗ | ✓ (0.5-2.0) | ✓ (0.5-2.0) | ✗ | ✗ |
| `volume` | ✗ | ✓ `volume` (0.5-2.0) | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| `pitch` | ✗ | ✗ | ✗ | ✗ | ✗ | ✓ via SSML | ✗ | ✗ |
| `pitch_shift` | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| `energy` | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| `trailing_silence` | ✗ | ✗ | ✗ | ✗ | ✓ | ✗ | ✗ | ✗ |

---

### `EmotionConfig`

Emotional expression and acting instructions.

```typescript
interface EmotionConfig {
  // Primary emotion
  primary?: EmotionValue;          // Primary emotional state
  intensity?: number;                // 0.0 to 2.0 (1.0 = normal)
  
  // Secondary emotions
  secondary?: EmotionValue[];        // Additional emotional layers
  
  // Natural language acting instructions
  description?: string;              // e.g., "calm, pedagogical"
  instructions?: string[];           // Specific acting directions
  
  // Context
  context?: 'narrative' | 'dialogue' | 'conversation' | 'performance';
  
  // Non-verbal sounds
  allow_nonverbals?: boolean;        // [laughter], [sigh], etc.
}
type EmotionValue = 
   
  // Core emotions (Cartesia/Hume style)
  | 'neutral' | 'happy' | 'sad' | 'angry' | 'excited' | 'calm' 
  | 'scared' | 'surprised' | 'disgusted' | 'content' | 'anxious'
  // Extended emotions
  | 'enthusiastic' | 'melancholic' | 'sarcastic' | 'whispered' | 'shouting'
  // Other valid emotions...
  ;
```

**Provider Mapping:**

| Parameter | ElevenLabs | Cartesia | Deepgram | Fish.audio | Hume.ai | Play.ht | Lovo | Grok |
|-----------|-----------|----------|----------|------------|---------|---------|------|------|
| `primary` | ✓ via tags | ✓ 50+ emotions | ✗ | ✓ via text tags | ✓ via `description` | ✓ via tags | ✗ | ✓ via style |
| `intensity` | ✓ (0-1.5) via Chatterbox | ✓ implicit | ✗ | ✓ via tags | ✓ implicit | ✓ via `temperature` | ✗ | ✗ |
| `description` | ✓ via tags/prompt | ✓ `emotion` string | ✗ | ✓ inline tags | ✓ `description` | ✓ via prompt | ✗ | ✗ |
| `allow_nonverbals` | ✓ `[laughs]` | ✓ `[laughter]` | ✗ | ✓ tags | ✗ | ✗ | ✗ | ✗ |

---

### `ContextConfig`

Continuity and context for natural speech flow.

```typescript
interface ContextConfig {
  // Previous/next text for continuity
  previous_text?: string;
  next_text?: string;
  
  // Request chaining for multi-chunk generation
  previous_request_id?: string;
  next_request_id?: string;
  
  // Seed for deterministic generation
  seed?: number;                   // Use same seed for reproducibility
}
```

**Provider Mapping:**

| Parameter | ElevenLabs | Cartesia | Deepgram | Fish.audio | Hume.ai | Play.ht | Lovo | Grok |
|-----------|-----------|----------|----------|------------|---------|---------|------|------|
| `previous_text` | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| `next_text` | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| `previous_request_id` | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| `seed` | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |

---

### `StreamingConfig`

Real-time streaming options.

```typescript
interface StreamingConfig {
  enabled?: boolean;
  format?: 'chunked' | 'websocket';
  chunk_overlap?: number;          // For smooth chunk stitching
}
```

---

## Response Schema

### Success Response

```typescript
interface TtsResponse {
  // Response metadata
  id: string;                      // Generation ID
  request_id: string;              // Request tracking ID
  
  // Audio output
  audio: {
    url?: string;                   // URL to audio file
    base64?: string;                // Base64 encoded audio
    stream?: ReadableStream;        // Streaming response
  };
  
  // Metadata
  metadata: {
    model: string;
    voice_id: string;
    duration_seconds?: number;
    characters_used: number;
    latency_ms: number;
  };
  
  // Optional extras
  extras?: {
    word_timings?: WordTiming[];
    phoneme_timings?: PhonemeTiming[];
  };
}

interface WordTiming {
  word: string;
  start_ms: number;
  end_ms: number;
  confidence?: number;
}

interface PhonemeTiming {
  phoneme: string;
  start_ms: number;
  end_ms: number;
}
```

---

## Text Enhancement Features

### SSML Support

Most providers support a subset of SSML:

```xml
<speak>
  <prosody rate="fast" pitch="+10%">
    Fast, higher pitched speech
  </prosody>
  <break time="500ms"/>
  <emphasis level="strong">Important!</emphasis>
</speak>
```

### Inline Tags

Special inline syntax for emotions and effects:

| Tag Format | Supported By | Example |
|------------|------------|---------|
| `[emotion]` | ElevenLabs, Fish.audio | `[laughs] That's funny!` |
| `(emotion)` | Fish.audio | `(excited) I won!` |
| `<emotion>` | Cartesia | `<emotion value="angry"/>How dare you!` |
| `[action]` | Cartesia | `[laughter]` |

---

## Provider Configuration

### `ProviderConfig`

Provider-specific parameters that override unified defaults.

```typescript
interface ProviderConfig {
  elevenlabs?: {
    optimize_streaming_latency?: number;  // 0-4
    apply_text_normalization?: 'auto' | 'on' | 'off';
    pronunciation_dictionary_ids?: string[];
    enable_logging?: boolean;
  };
  
  cartesia?: {
    transcript?: string[];  // For speech-to-speech
    voice_changer?: boolean;
  };
  
  deepgram?: {
    utterance_limit?: number;
    interim_results?: boolean;
  };
  
  fish_audio?: {
    reference_id?: string;
    normalize?: boolean;
  };
  
  hume_ai?: {
    num_generations?: number;
    instant_mode?: boolean;  // Skip cache for dynamic voice design
    continuation?: boolean;
  };
  
  playht?: {
    quality?: 'draft' | 'standard' | 'premium';
    temperature?: number;  // 0.0 to 1.0
    voice_engine?: 'PlayDialog' | 'Play3.0' | 'PlayDialog-turbo';
    sample_rate?: number;
  };
  
  lovo?: {
    // Async TTS job tracking
    job_id?: string;
  };
  
  grok?: {
    // Voice agent specific
    instructions?: string;
    turn_detection?: object;
    tools?: object[];
  };
}
```

---

## Error Handling

### Error Response

```typescript
interface TtsError {
  code: string;
  message: string;
  details?: {
    provider_error?: object;
    validation_errors?: string[];
  };
  retryable: boolean;
}
```

Common Error Codes:
- `voice_not_found`: Requested voice doesn't exist
- `language_not_supported`: Language not supported by voice/model
- `rate_limit_exceeded`: API rate limit hit
- `content_policy_violation`: Text violates content policy
- `insufficient_credits`: Account out of credits
- `provider_error`: Provider-specific error

---

## Usage Examples

### Basic Request

```json
POST /v1/tts/synthesize
{
  "text": "Hello, world!",
  "voice": {
    "name": "Bella"
  }
}
```

### Advanced Request with Emotion

```json
POST /v1/tts/synthesize
{
  "text": "I can't believe you actually did that!",
  "voice": {
    "id": "c961b81c-a935-4c17-bfb3-ba2239de8c2f",
    "characteristics": {
      "gender": "male",
      "age": "adult"
    }
  },
  "model": {
    "tier": "premium"
  },
  "prosody": {
    "speed": 1.1,
    "volume": 1.2
  },
  "emotion": {
    "primary": "surprised",
    "intensity": 1.3,
    "description": "shocked disbelief"
  },
  "audio": {
    "format": "mp3",
    "sample_rate": 44100
  }
}
```

### Voice Cloning Request

```json
POST /v1/tts/synthesize
{
  "text": "This is my custom cloned voice speaking.",
  "voice": {
    "design": {
      "sample_url": "https://example.com/voice-sample.mp3",
      "instructions": "Deep, resonant voice with slight rasp"
    }
  },
  "provider": {
    "hume_ai": {
      "instant_mode": false
    }
  }
}
```

### Streaming Request

```json
POST /v1/tts/synthesize/stream
{
  "text": "This will stream audio chunks as they're generated...",
  "voice": {
    "id": "sonic-3-premium"
  },
  "streaming": {
    "enabled": true,
    "format": "websocket"
  }
}
```

---

## Provider Feature Matrix

| Feature | ElevenLabs | Cartesia Sonic-3 | Deepgram Aura-2 | Fish.audio | Hume.ai Octave | Play.ht | Lovo | Grok |
|---------|-----------|------------------|-----------------|------------|----------------|---------|------|------|
| **Voice Library** | 10,000+ | 100+ | 40+ | 100,000+ | 50+ | 900+ | 500+ | Limited |
| **Voice Cloning** | ✓ 30s sample | ✗ | ✗ | ✓ 10s sample | ✓ 15s sample | ✓ | ✗ | ✗ |
| **Voice Design** | ✓ (prompt) | ✗ | ✗ | ✗ | ✓ (prompt) | ✗ | ✗ | ✗ |
| **Speed Control** | ✗ | ✓ (0.6-1.5) | ✗ | ✗ | ✓ (0.5-2.0) | ✓ (0.5-2.0) | ✗ | ✗ |
| **Volume Control** | ✗ | ✓ (0.5-2.0) | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| **Emotion Control** | ✓ Tags | ✓ 50+ emotions | ✗ | ✓ Inline tags | ✓ Natural lang | ✓ Tags | ✗ | ✓ Context |
| **SSML Support** | Partial | ✓ | Partial | ✗ | Partial | Partial | ✗ | ✗ |
| **Non-verbals** | ✓ | ✓ [laughter] | ✗ | ✓ | ✗ | ✗ | ✗ | ✗ |
| **Streaming Latency** | ~75ms | ~40-90ms | ~200ms | ~100ms | ~100-200ms | ~200ms | Async | ~300ms |
| **Multi-language** | 32 | 42 | 20+ | 80+ | 11 | 140+ | 100+ | 1 |
| **Word Timings** | ✓ | ✗ | ✗ | ✗ | Coming | ✗ | ✗ | ✗ |
| **Continuation** | ✓ | ✗ | ✗ | ✗ | ✓ | ✗ | ✗ | ✗ |

---

## Implementation Recommendations

1. **Provider Selection Logic**: Choose provider based on feature requirements
   - Voice Cloning → Hume.ai, ElevenLabs, Fish.audio
   - Ultra-low Latency → Cartesia Sonic-3
   - Max Emotions → Cartesia (50+ emotions)
   - Natural Acting → Hume.ai (LLM-native)
   - Budget Streaming → Cartesia, Fish.audio

2. **Graceful Degradation**: If a parameter isn't supported by the selected provider:
   - Log warning
   - Skip parameter
   - Don't fail the request

3. **Voice Caching**: Cache voice IDs to avoid repeated lookups

4. **Fallback Chain**: Configure fallback providers for high-availability

---

## Version History

- **v1.0.0** (2026-03-20): Initial unified API definition covering 8 major TTS providers

