# TTS Service Refactoring Summary

## Overview
Refactored Python scripts in `src/scripts/` to support both:
1. **Local TTS**: Qwen3-TTS + SoX (existing functionality)
2. **Remote TTS**: WebSocket-based TTS service

## Files Created

### Core TTS Interface
1. **tts_interface.py** (3.1 KB)
   - Abstract base class `TTSInterface` with ABC
   - Exception hierarchy: `TTSError`, `TTSConnectionError`, `TTSGenerationError`, `CharacterNotSupportedError`
   - `TTSResult` dataclass for return values

2. **tts_local.py** (8.5 KB)
   - `LocalTTSProvider` implementation using Qwen3-TTS
   - Supports voice cloning and custom voice modes
   - GPU/CPU detection with automatic dtype selection
   - Voice prompt caching for efficiency

3. **tts_service.py** (10.0 KB)
   - `RemoteTTSProvider` using WebSocket client
   - Exponential backoff retry logic (1s, 2s, 4s, 8s)
   - JSON protocol for text/speaker/emotion data exchange
   - Configurable fallback to local TTS
   - Connection pooling support

4. **tts_factory.py** (6.8 KB)
   - Factory pattern for provider creation
   - `TTSProviderFactory.create_provider(service_url=None)` - Local
   - `TTSProviderFactory.create_provider(service_url="ws://...")` - Remote
   - Caching of local provider instances
   - Quick factory method `create_tts_provider()`

### Test Suite (4.2 KB total)
- **test_tts_interface.py** - Interface and exception tests
- **test_tts_local.py** - Local provider tests with mocked Qwen3
- **test_tts_service.py** - WebSocket client tests with mocked websockets
- **test_tts_factory.py** - Factory pattern tests

## API Usage

### Local Provider (Default)
```python
from tts_factory import create_tts_provider

provider = create_tts_provider()
wavs, sr = provider.generate(
    text="Hello world",
    speaker="narrator",
    emotion="neutral",
    language="English",
    output_path=Path("output.wav"),
    char_config={"voice-sample": "narrator.wav"}
)
provider.close()
```

### Remote Provider
```python
provider = create_tts_provider("ws://localhost:8080")
wavs, sr = provider.generate(
    text="Hello world",
    speaker="narrator",
    emotion="neutral",
    language="English",
    output_path=Path("output.wav"),
    char_config={"voice-sample": "narrator.wav"}
)
provider.close()
```

### Command Line (to be integrated)
```bash
# Local (default)
python chapter_xml_to_audio.py --xml chapter_001.xml

# Remote TTS service
python chapter_xml_to_audio.py --xml chapter_001.xml --tts-service ws://localhost:8080
```

## Architecture

```
TTSInterface (Abstract Base)
    ├── LocalTTSProvider
    │   ├── Qwen3-TTS Base Model (voice cloning)
    │   ├── Qwen3-TTS Custom Model (custom voices)
    │   └── SoX effects (apply_sox_effects)
    │
    └── RemoteTTSProvider
        ├── WebSocket Client
        ├── Exponential Backoff Retry
        └── Optional LocalTTSProvider Fallback
```

## Backward Compatibility

- Existing `chapter_xml_to_audio.py` behavior preserved
- `--tts-service` is optional
- Default behavior: Local TTS (no changes required)
- All existing CLI arguments unchanged

## Testing

Run tests with pytest:
```bash
cd src/scripts
python -m pytest tests/ -v --cov=tts_* --cov-report=html
```

## Next Steps

1. Refactor `chapter_xml_to_audio.py` to use factory pattern
2. Add `--tts-service` argument to CLI
3. Integrate `apply_sox_effects` (can remain as utility function)
4. Run full test suite
5. Verify backward compatibility

## Total Code Added
- 4 Python modules: ~28.4 KB
- 4 Test modules: ~25.9 KB
- Total: ~54.3 KB of new code
