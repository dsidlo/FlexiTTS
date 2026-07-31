# Implementation Plan: TTS Commercial Server

**Date:** 2026-03-20  
**Target Module:** `src/scripts/tts_commercial_server.py`  
**Integrates With:** `src/scripts/tts_service.py`  
**Based On:** Unified TTS API (`docs/api/unified-tts-api.md`)

---

## Executive Summary

Create a `CommercialTTSProvider` class that implements `TTSInterface` and provides unified access to commercial TTS APIs (ElevenLabs, Cartesia, Deepgram, Fish.audio, Hume.ai, Play.ht, Lovo, Grok-TTS). This provider will be a first-class citizen in the FlexiTTS provider hierarchy, usable via:

1. **Direct import** for local usage
2. **WebSocket service** via `tts_service.py` for distributed generation
3. **Factory pattern** via `tts_factory.py` for runtime selection

---

## Architecture Integration

### Provider Inheritance Chain

```
TTSInterface (abstract base)
    ├── LocalTTSProvider (Qwen3-TTS + local models)
    ├── RemoteTTSProvider (WebSocket client to remote service)
    └── CommercialTTSProvider (NEW - commercial cloud APIs)
```

### Factory Registration

Add to `tts_factory.py`:

```python
from tts_commercial_server import CommercialTTSProvider

# Factory method
@staticmethod
def create_commercial_provider(
    provider: str = "elevenlabs",  # Provider name
    api_key: Optional[str] = None,
    voice_id: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None,
    **kwargs
) -> CommercialTTSProvider:
    """Create a commercial TTS provider.
    
    Args:
        provider: One of ['elevenlabs', 'cartesia', 'deepgram', 
                         'fish-audio', 'hume-ai', 'playht', 'lovo', 'grok']
        api_key: API key for the provider (falls back to env vars)
        voice_id: Default voice ID
        config: Provider-specific configuration
    """
    return CommercialTTSProvider(
        provider=provider,
        api_key=api_key,
        voice_id=voice_id,
        config=config,
        **kwargs
    )
```

---

## Module Structure

### File: `src/scripts/tts_commercial_server.py`

```
├── Imports
│   ├── Standard library (asyncio, dataclasses, etc.)
│   ├── Third-party (requests, pydantic, numpy, soundfile)
│   └── FlexiTTS (tts_interface)
│
├── Configuration Classes
│   ├── CommercialVoiceConfig
│   ├── CommercialProsodyConfig
│   ├── CommercialEmotionConfig
│   └── CommercialAudioConfig
│
├── Provider Client Classes
│   ├── BaseCommercialClient (abstract)
│   ├── ElevenLabsClient
│   ├── CartesiaClient
│   ├── DeepgramClient
│   ├── FishAudioClient
│   ├── HumeAIClient
│   ├── PlayHtClient
│   ├── LovoClient
│   └── GrokTTSClient
│
├── Main Provider Class
│   └── CommercialTTSProvider(TTSInterface)
│       ├── generate()          # Main generation method
│       ├── supports_character() # Character support check
│       ├── close()             # Resource cleanup
│       └── _map_to_unified()   # Provider-specific mapping
│
└── Utilities
    ├── get_commercial_client()  # Factory for clients
    └── validate_environment()   # Check API keys
```

---

## Python Package Requirements

### Required Packages

| Package | Version | Purpose | Install |
|---------|---------|---------|---------|
| `elevenlabs` | `^1.50.0` | ElevenLabs API | `pip install elevenlabs` |
| `cartesia` | `^1.4.0` | Cartesia Sonic API | `pip install cartesia` |
| `requests` | `^2.32.0` | HTTP clients for all providers | `pip install requests` |
| `pydantic` | `^2.0.0` | Data validation | `pip install pydantic` |
| `numpy` | `^1.26.0` | Audio processing | Already required |
| `soundfile` | `^0.12.0` | Audio I/O | Already required |
| `websockets` | `^12.0.0` | Streaming support | Already required |

### Optional Dependencies

```python
# Provider-specific optional deps
EXTRAS = {
    'elevenlabs': ['elevenlabs>=1.50.0'],
    'cartesia': ['cartesia>=1.4.0'],
    'all': ['elevenlabs', 'cartesia', 'httpx', 'aiohttp'],
}
```

---

## Implementation Details

### 1. Configuration Classes

```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class CommercialVoiceConfig:
    """Voice configuration for commercial TTS providers."""
    id: Optional[str] = None
    name: Optional[str] = None
    language: Optional[str] = "en"
    
    # Character characteristics
    gender: Optional[str] = None  # 'male', 'female', 'neutral'
    age: Optional[str] = None      # 'young', 'adult', 'mature'
    accent: Optional[str] = None   # 'american', 'british', etc.
    style: Optional[str] = None    # 'conversational', 'narrative'

@dataclass  
class CommercialProsodyConfig:
    """Prosody controls."""
    speed: float = 1.0        # 0.5 to 2.0
    volume: float = 1.0       # 0.5 to 2.0 (Cartesia)
    pitch: float = 0.0        # -1.0 to 1.0
    trailing_silence: float = 0.0  # Seconds

@dataclass
class CommercialEmotionConfig:
    """Emotion configuration."""
    primary: str = "neutral"
    intensity: float = 1.0      # 0.0 to 2.0
    description: Optional[str] = None  # Natural language instructions
```

### 2. Provider Client Implementations

Each client implements a common interface:

```python
class BaseCommercialClient(ABC):
    """Abstract base for commercial TTS clients."""
    
    @abstractmethod
    def generate(
        self,
        text: str,
        voice_config: CommercialVoiceConfig,
        prosody: Optional[CommercialProsodyConfig] = None,
        emotion: Optional[CommercialEmotionConfig] = None,
        output_path: Optional[Path] = None,
    ) -> Tuple[np.ndarray, int]:
        """Generate audio. Returns (audio_array, sample_rate)."""
        pass
    
    @abstractmethod
    def list_voices(self) -> List[Dict[str, Any]]:
        """List available voices."""
        pass
```

### 3. ElevenLabs Client Example

```python
class ElevenLabsClient(BaseCommercialClient):
    """ElevenLabs API client."""
    
    def __init__(self, api_key: Optional[str] = None):
        from elevenlabs import ElevenLabs
        self.client = ElevenLabs(api_key=api_key or os.getenv("ELEVENLABS_API_KEY"))
        
    def generate(
        self,
        text: str,
        voice_config: CommercialVoiceConfig,
        prosody: Optional[CommercialProsodyConfig] = None,
        emotion: Optional[CommercialEmotionConfig] = None,
        output_path: Optional[Path] = None,
    ) -> Tuple[np.ndarray, int]:
        # Map unified config to ElevenLabs-specific
        voice_id = voice_config.id or "21m00Tcm4TlvDq8ikWAM"  # Default Bella
        
        # Prepare voice settings
        voice_settings = None
        if emotion and emotion.intensity != 1.0:
            # ElevenLabs uses stability/similarity_boost
            voice_settings = {
                "stability": 0.5,
                "similarity_boost": min(emotion.intensity, 1.0),
            }
        
        # Generate
        audio = self.client.text_to_speech.convert(
            text=text,
            voice_id=voice_id,
            model_id="eleven_multilingual_v2",
            output_format="mp3_44100_128",
            voice_settings=voice_settings,
        )
        
        # Save and load as numpy array
        if output_path:
            with open(output_path, "wb") as f:
                f.write(audio)
            data, sr = sf.read(output_path)
            return data, sr
        
        # Return raw bytes processed
        import io
        data, sr = sf.read(io.BytesIO(audio))
        return data, sr
```

### 4. Cartesia Client Example

```python
class CartesiaClient(BaseCommercialClient):
    """Cartesia Sonic-3 API client."""
    
    def __init__(self, api_key: Optional[str] = None):
        from cartesia import Cartesia
        self.client = Cartesia(api_key=api_key or os.getenv("CARTESIA_API_KEY"))
        
    def generate(
        self,
        text: str,
        voice_config: CommercialVoiceConfig,
        prosody: Optional[CommercialProsodyConfig] = None,
        emotion: Optional[CommercialEmotionConfig] = None,
        output_path: Optional[Path] = None,
    ) -> Tuple[np.ndarray, int]:
        # Build generation config
        generation_config = {}
        
        if prosody:
            if prosody.speed != 1.0:
                generation_config["speed"] = max(0.6, min(1.5, prosody.speed))
            if prosody.volume != 1.0:
                generation_config["volume"] = max(0.5, min(2.0, prosody.volume))
                
        if emotion:
            if emotion.primary != "neutral":
                generation_config["emotion"] = emotion.primary.lower()
                
        # Generate via WebSocket for best latency
        voice_id = voice_config.id or "c961b81c-a935-4c17-bfb3-ba2239de8c2f"  # Kyle
        
        audio_buffer = b""
        for chunk in self.client.tts.send(
            model_id="sonic-3",
            transcript=text,
            voice_id=voice_id,
            output_format={
                "container": "raw",
                "encoding": "pcm_s16le",
                "sample_rate": 24000,
            },
            generation_config=generation_config if generation_config else None,
        ):
            audio_buffer += chunk
            
        # Convert to numpy
        audio_array = np.frombuffer(audio_buffer, dtype=np.int16)
        
        if output_path:
            sf.write(output_path, audio_array, 24000)
            
        return audio_array, 24000
```

### 5. Main CommercialTTSProvider Class

```python
class CommercialTTSProvider(TTSInterface):
    """Commercial TTS provider supporting multiple cloud APIs."""
    
    PROVIDER_MAP = {
        "elevenlabs": ElevenLabsClient,
        "cartesia": CartesiaClient,
        "deepgram": DeepgramClient,
        "fish-audio": FishAudioClient,
        "hume-ai": HumeAIClient,
        "playht": PlayHtClient,
        "lovo": LovoClient,
        "grok": GrokTTSClient,
    }
    
    def __init__(
        self,
        provider: str,
        api_key: Optional[str] = None,
        voice_id: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        **kwargs
    ):
        """Initialize commercial TTS provider.
        
        Args:
            provider: One of the supported provider names
            api_key: API key (or auto-detect from env)
            voice_id: Default voice ID
            config: Additional provider configuration
        """
        if provider not in self.PROVIDER_MAP:
            raise ValueError(f"Unknown provider: {provider}")
            
        self.provider_name = provider
        self.voice_id = voice_id
        self.config = config or {}
        
        # Initialize client
        client_class = self.PROVIDER_MAP[provider]
        self.client = client_class(api_key=api_key, **kwargs)
        
        # Supported emotions per provider
        self.supported_emotions = self._get_supported_emotions()
        
    def generate(
        self,
        text: str,
        speaker: str,
        emotion: str,
        language: str,
        output_path: Path,
        instruct: str = "",
        char_config: Optional[Dict[str, Any]] = None,
        story: Optional[str] = None,
        chapter: Optional[str] = None,
        section: Optional[str] = None,
        dialog: Optional[str] = None
    ) -> tuple[List[Any], int]:
        """Generate audio via commercial API."""
        # Map FlexiTTS parameters to unified config
        voice_config = self._map_speaker_to_voice(speaker, char_config)
        prosody_config = self._map_to_prosody(emotion, instruct)
        emotion_config = self._map_to_emotion(emotion, instruct)
        
        # Generate
        audio_array, sample_rate = self.client.generate(
            text=text,
            voice_config=voice_config,
            prosody=prosody_config,
            emotion=emotion_config,
            output_path=output_path,
        )
        
        # Return as list of segments (single segment for commercial APIs)
        return [audio_array], sample_rate
        
    def supports_character(self, char_config: Dict[str, Any]) -> bool:
        """Check if character is supported."""
        # Commercial APIs support:
        # - Custom voice (voice_id)
        # - Voice design (description/instruction)
        # - Standard emotions
        if "custom-voice" in char_config:
            return True
        if "voice-sample" in char_config:
            # Check if provider supports voice cloning
            return self.provider_name in ["elevenlabs", "hume-ai", "fish-audio", "playht"]
        return True  # Default voices always work
        
    def close(self) -> None:
        """Cleanup resources."""
        if hasattr(self.client, 'close'):
            self.client.close()
```

---

## Integration with `tts_service.py`

### WebSocket Service Enhancement

Add a new provider type to the WebSocket service:

```python
# In tts_service.py or a new config section
COMMERCIAL_PROVIDERS = {
    "elevenlabs": {"requires_api_key": True, "streaming": False},
    "cartesia": {"requires_api_key": True, "streaming": True},
    "deepgram": {"requires_api_key": True, "streaming": True},
    "fish-audio": {"requires_api_key": True, "streaming": True},
    "hume-ai": {"requires_api_key": True, "streaming": True},
    "playht": {"requires_api_key": True, "streaming": True},
    "lovo": {"requires_api_key": True, "streaming": False},
    "grok": {"requires_api_key": True, "streaming": True},
}

class RemoteTTSProvider:
    """Updated to support commercial provider requests."""
    
    async def _handle_generation_request(
        self,
        websocket,
        request: Dict[str, Any]
    ) -> None:
        """Handle generation request with commercial provider support."""
        
        provider_type = request.get("provider", "local")
        
        if provider_type in COMMERCIAL_PROVIDERS:
            # Route to commercial provider
            result = await self._generate_commercial(request)
        else:
            # Route to local Qwen3-TTS
            result = await self._generate_local(request)
            
        # ... rest of handling
```

### Environment Configuration

Create `~/.flexitts/commercial-providers.yml`:

```yaml
# ~/.flexitts/commercial-providers.yml
providers:
  elevenlabs:
    api_key: ${ELEVENLABS_API_KEY}
    default_voice: "21m00Tcm4TlvDq8ikWAM"  # Bella
    default_model: "eleven_multilingual_v2"
    
  cartesia:
    api_key: ${CARTESIA_API_KEY}
    default_voice: "c961b81c-a935-4c17-bfb3-ba2239de8c2f"  # Kyle
    default_model: "sonic-3"
    
  deepgram:
    api_key: ${DEEPGRAM_API_KEY}
    default_model: "aura-2-athena-en"
    
  fish-audio:
    api_key: ${FISH_AUDIO_API_KEY}
    
  hume-ai:
    api_key: ${HUME_API_KEY}
    default_version: "octave-2"
    
  playht:
    api_key: ${PLAYHT_API_KEY}
    user_id: ${PLAYHT_USER_ID}
    default_voice: "s3://voice-cloning..."
    
  # ... etc
```

---

## Phased Implementation Plan

### Phase 1: Foundation (Week 1)

- [ ] Create `tts_commercial_server.py` with base classes
- [ ] Implement `BaseCommercialClient` abstract class
- [ ] Implement `CommercialTTSProvider` with `TTSInterface` compliance
- [ ] Add HTTP request utilities for non-SDK providers
- [ ] Create configuration validation

**Deliverable:** Module structure with working `CommercialTTSProvider`

### Phase 2: Core Providers (Week 2)

- [ ] Implement `ElevenLabsClient` (has official SDK)
- [ ] Implement `CartesiaClient` (has official SDK)
- [ ] Implement `DeepgramClient` (REST API)
- [ ] Add `ElevenLabsClient.list_voices()`
- [ ] Add `CartesiaClient.list_voices()`
- [ ] Create voice ID mapper utility

**Deliverable:** 3 working provider clients

### Phase 3: Extended Providers (Week 3)

- [ ] Implement `FishAudioClient` (REST API)
- [ ] Implement `HumeAIClient` (has SDK or REST)
- [ ] Implement `PlayHtClient` (has SDK)
- [ ] Implement `LovoClient` (REST API)
- [ ] Implement `GrokTTSClient` (if API available)

**Deliverable:** All 8 providers working

### Phase 4: Integration (Week 4)

- [ ] Update `tts_factory.py` with `.create_commercial_provider()`
- [ ] Add `CommercialTTSProvider` to `tts_service.py` routing
- [ ] Create commercial provider config loader
- [ ] Write tests for each provider client
- [ ] Add error handling and retry logic

**Deliverable:** Full integration with existing FlexiTTS infrastructure

### Phase 5: Optimization (Week 5)

- [ ] Implement streaming for supported providers (Cartesia, Deepgram)
- [ ] Add batching support for multiple utterances
- [ ] Create voice caching layer
- [ ] Implement fallback chain (Primary -> Backup -> Local)
- [ ] Add usage tracking and quota management

**Deliverable:** Production-ready commercial TTS service

---

## Testing Strategy

### Unit Tests

```python
# tests/test_tts_commercial_server.py

import pytest
from tts_commercial_server import CommercialTTSProvider

class TestElevenLabsClient:
    """Test ElevenLabs-specific functionality."""
    
    @pytest.mark.skipif(not os.getenv("ELEVENLABS_API_KEY"))
    def test_list_voices(self):
        provider = CommercialTTSProvider("elevenlabs")
        voices = provider.client.list_voices()
        assert len(voices) > 0
        
    @pytest.mark.skipif(not os.getenv("ELEVENLABS_API_KEY"))
    def test_generate_basic(self, tmp_path):
        provider = CommercialTTSProvider("elevenlabs")
        output_path = tmp_path / "test.wav"
        
        audio_segments, sr = provider.generate(
            text="Hello, world!",
            speaker="test",
            emotion="neutral",
            language="en",
            output_path=output_path,
        )
        
        assert len(audio_segments) == 1
        assert sr == 44100
        assert output_path.exists()
```

### Integration Tests

```python
# tests/test_tts_service_commercial.py

@pytest.mark.asyncio
class TestTTSServiceWithCommercial:
    """Test WebSocket service routing to commercial providers."""
    
    async def test_service_routes_to_elevenlabs(self):
        """Test that service correctly routes ElevenLabs requests."""
        pass
```

---

## Configuration Files

### New Files to Create

| File | Purpose |
|------|---------|
| `src/scripts/tts_commercial_server.py` | Main module implementation |
| `src/scripts/tts_commercial_clients.py` | Individual provider clients (or separate files) |
| `src/scripts/tts_commercial_config.py` | Configuration loading/validation |
| `~/.flexitts/commercial-providers.yml` | User API keys and defaults |
| `tests/test_tts_commercial_server.py` | Test suite |
| `docs/api/2026-03-20-tts-commercial-usage.md` | Usage documentation |

### Files to Modify

| File | Changes |
|------|---------|
| `src/scripts/tts_factory.py` | Add `create_commercial_provider()` method |
| `src/scripts/tts_service.py` | Add commercial provider routing |
| `requirements.txt` | Add elevenlabs, cartesia dependencies |

---

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| API key exposure | High | Use env vars only, never commit keys |
| Rate limiting | Medium | Implement exponential backoff |
| Provider API changes | Medium | Abstract behind unified interface |
| High latency vs local | Low | Allow provider selection per character |
| Cost overruns | Medium | Add usage tracking and budgets |

---

## Success Criteria

1. ✅ All 8 commercial providers accessible via unified interface
2. ✅ `CommercialTTSProvider` passes `TTSInterface` compliance tests
3. ✅ Works via `tts_service.py` WebSocket service
4. ✅ Voice cloning supported where available
5. ✅ Emotion/prosody controls mapped to each provider
6. ✅ Streaming supported for capable providers
7. ✅ Graceful fallback when provider unavailable
8. ✅ Comprehensive error messages for debugging

---

## Next Steps

1. **Review this plan** and approve/modify approach
2. **Set up environment variables** for development API keys
3. **Begin Phase 1** - Foundation implementation
4. **Create tracking ticket** for phased implementation

**Estimated Total Effort:** 5 weeks (25 development days)

**Priority:** High - Enables high-quality voices without local GPU
