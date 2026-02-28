# TTS Service Communication Contract

**Document Date:** February 27, 2026  
**Version:** 1.0  
**Protocol:** WebSocket (ws://)  
**Default Port:** 8765

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Communication Flow](#communication-flow)
4. [Request Format](#request-format)
5. [Response Format](#response-format)
6. [Error Handling](#error-handling)
7. [Implementation Status](#implementation-status)

---

## Overview

The TTS service provides distributed text-to-speech generation via WebSocket protocol. It consists of:

| Component | File | Role |
|-----------|------|------|
| **Client** | `chapter_xml_to_audio.py` | Orchestrates TTS generation from XML |
| **Factory** | `tts_factory.py` | Creates local or remote TTS providers |
| **Remote Provider** | `tts_service.py` | WebSocket client implementation |
| **Server** | `tts_ws_server.py` | WebSocket TTS service endpoint |
| **Local Provider** | `tts_local.py` | Direct Qwen3-TTS model execution |
| **Interface** | `tts_interface.py` | Abstract base class definition |

### Use Cases

- **Local Mode:** Direct model execution (no server required)
- **Remote Mode:** Distributed TTS processing via WebSocket
- **Fallback Mode:** Remote with automatic local fallback on failure

---

## Architecture

```
┌─────────────────────────┐     WebSocket (ws://localhost:8765)    ┌─────────────────────────┐
│  chapter_xml_to_audio   │ ──────────────────────────────────────>│     tts_ws_server       │
│      (Client)           │                                          │      (Server)           │
│                         │<─ JSON request/response + binary audio──│                         │
└─────────────────────────┘                                          └─────────────────────────┘
           │                                                                   │
           │ Uses tts_factory.create_tts_provider()                          │
           │ Creates RemoteTTSProvider (tts_service.py)                      │
           └─────────────────────────────────────────────────────────────────┘
```

### Provider Pattern

```
chapter_xml_to_audio.py
    └── create_tts_provider(service_url=...)
            └── TTSProviderFactory.create_provider()
                    ├── RemoteTTSProvider (if service_url provided)
                    │       └── WebSocket connection to tts_ws_server
                    └── LocalTTSProvider (fallback or default)
                            └── Direct Qwen3-TTS model
```

---

## Communication Flow

### Step 1: Provider Initialization

**From:** `chapter_xml_to_audio.py` (line 187-195)

```python
provider = create_tts_provider(
    service_url=args.tts_service,  # e.g., "ws://localhost:8765"
    voices_dir=voices_dir
)
```

**Factory:** Creates `RemoteTTSProvider` when `service_url` is provided.

---

### Step 2: Connection Establishment

**From:** `tts_service.py` → `_connect_with_retry()`

```python
for attempt in range(self.max_retries):
    try:
        self._websocket = await asyncio.wait_for(
            websockets.connect(self.service_url),
            timeout=self.timeout
        )
        return self._websocket
    except Exception as e:
        wait_time = 2 ** attempt  # 1, 2, 4, 8 seconds
        await asyncio.sleep(wait_time)
```

**Configuration:**

| Parameter | Default | Description |
|-----------|---------|-------------|
| `max_retries` | 4 | Connection retry attempts |
| `timeout` | 30.0s | Connection timeout |

---

### Step 3: Request Transmission

**From:** `tts_service.py` → `_generate_remote()`

**JSON Request Structure:**

```json
{
  "text": "Hello, this is a test utterance",
  "speaker": "hendrix",
  "emotion": "neutral",
  "language": "English",
  "instruct": "Speak in a neutral tone",
  "output_format": "wav",
  "character_config": {
    "voice-sample": "refs/hendrix.wav",
    "emotion": "neutral",
    "custom-voice": {...}
  }
}
```

**Field Descriptions:**

| Field | Type | Required | Description | Source |
|-------|------|----------|-------------|--------|
| `text` | string | Yes | Text to synthesize | XML content |
| `speaker` | string | Yes | Character identifier | XML `character` attribute |
| `emotion` | string | Yes | Emotional tone | XML `emotion` attribute or config |
| `language` | string | Yes | Language code | Config (default: "English") |
| `instruct` | string | No | TTS instructions | Built from emotion + config |
| `output_format` | string | Yes | Audio format | "wav" (fixed) |
| `character_config` | object | No | Full character config | `story-config.yml` |

---

### Step 4: Server Processing

**From:** `tts_ws_server.py` → `handle_request()`

**Server Actions:**
1. Accept WebSocket connection on `ws://localhost:8765`
2. Parse JSON request
3. Log request: `INFO: Received request: {speaker} - {emotion}`
4. Return acknowledgment
5. Send completion signal

**Current Implementation (Mock):**

```python
response = {
    "status": "success",
    "message": "Audio generation request received",
    "text_length": len(request.get('text', '')),
    "speaker": request.get('speaker'),
    "emotion": request.get('emotion')
}

# Send done signal
await websocket.send(json.dumps({"done": True}))
```

---

### Step 5: Response Reception

**From:** `tts_service.py` → message handling loop

```python
while True:
    message = await websocket.recv()
    
    if isinstance(message, str):
        # JSON - metadata or done signal
        msg_data = json.loads(message)
        if "error" in msg_data:
            raise TTSGenerationError(msg_data["error"])
        elif "done" in msg_data:
            break
        else:
            metadata = msg_data
    else:
        # Binary - audio data
        audio_data.extend(message)
```

**Post-Processing:**
1. Write audio bytes to `output_path`
2. Read back with `soundfile` to get numpy array
3. Return: `([audio_segment], sample_rate)`

---

## Request Format

### WebSocket Message Types (Client → Server)

| Type | Format | Purpose |
|------|--------|---------|
| **Request** | JSON string | TTS parameters |
| **Close** | WebSocket close | End connection |

### Request JSON Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["text", "speaker", "emotion", "language", "output_format"],
  "properties": {
    "text": {
      "type": "string",
      "description": "Text to convert to speech"
    },
    "speaker": {
      "type": "string",
      "description": "Character/speaker identifier"
    },
    "emotion": {
      "type": "string",
      "description": "Emotional tone (neutral, happy, sad, etc.)"
    },
    "language": {
      "type": "string",
      "description": "Language code (e.g., 'English')"
    },
    "instruct": {
      "type": "string",
      "description": "Additional TTS instructions"
    },
    "output_format": {
      "type": "string",
      "enum": ["wav"],
      "description": "Audio output format"
    },
    "character_config": {
      "type": "object",
      "description": "Character-specific configuration from story-config.yml"
    }
  }
}
```

---

## Response Format

### WebSocket Message Types (Server → Client)

| Type | Format | Purpose |
|------|--------|---------|
| **Acknowledgment** | JSON string | Request received status |
| **Error** | JSON string | Error information |
| **Audio Data** | Binary | Raw audio bytes (WAV) |
| **Completion** | JSON | `{ "done": true }` |

### Response JSON Schema

**Success Acknowledgment:**
```json
{
  "status": "success",
  "message": "Audio generation request received",
  "text_length": 42,
  "speaker": "hendrix",
  "emotion": "neutral"
}
```

**Error Response:**
```json
{
  "error": "Invalid JSON: ..."
}
```

**Completion Signal:**
```json
{
  "done": true
}
```

### Audio Data Format

| Attribute | Value |
|-----------|-------|
| **Format** | WAV (RIFF) |
| **Sample Rate** | 24,000 Hz (default) |
| **Channels** | Mono (1) or Stereo (2) |
| **Encoding** | PCM 16-bit or 32-bit float |
| **Transmission** | Binary WebSocket frames |

---

## Error Handling

### Retry Logic

**From:** `tts_service.py` → `_connect_with_retry()`

```python
for attempt in range(self.max_retries):
    try:
        # Connect...
    except Exception as e:
        if attempt < self.max_retries - 1:
            wait_time = 2 ** attempt  # Exponential backoff
            await asyncio.sleep(wait_time)
        else:
            raise TTSConnectionError(f"Failed after {self.max_retries} attempts")
```

### Error Types

| Error Type | Trigger | Response | Client Action |
|------------|---------|----------|---------------|
| `TTSConnectionError` | WebSocket connection failure | Exception raised | Retry with backoff |
| `TTSGenerationError` | Server returns error JSON | `{"error": "..."}` | Raise exception |
| `JSONDecodeError` | Invalid JSON from server | Parse error | Log and continue |
| `TimeoutError` | Operation timeout | `asyncio.TimeoutError` | Close and retry |

### Fallback Behavior

**Configuration:** `enable_fallback=True` in factory

**Flow:**
```
RemoteTTSProvider.generate() fails
    └── Try fallback to LocalTTSProvider
            └── LocalTTSProvider.generate()
                    └── Direct model execution
```

**Fallback Trigger Conditions:**
- Connection fails after max retries
- WebSocket connection closed unexpectedly
- Generation timeout exceeded

---

## Implementation Status

| Component | Status | Notes |
|-----------|--------|-------|
| `tts_ws_server.py` | ⚠️ **Mock** | Returns acknowledgment only, no audio generation |
| `tts_service.py` | ✅ **Complete** | Full client implementation with retry logic |
| `tts_factory.py` | ✅ **Complete** | Factory pattern for provider creation |
| `tts_local.py` | ✅ **Complete** | Real Qwen3-TTS model execution |
| `tts_interface.py` | ✅ **Complete** | Abstract base class with exceptions |
| `chapter_xml_to_audio.py` | ✅ **Complete** | XML to audio orchestration |

### Known Limitations

1. **Server is Mock:** `tts_ws_server.py` doesn't generate audio - needs integration with actual TTS model
2. **No Binary Audio:** Server doesn't currently send audio data (expected by client)
3. **Missing Error Details:** Error responses lack detailed debugging info

### Future Enhancements

| Enhancement | Description |
|-------------|-------------|
| Real TTS Integration | Connect server to Qwen3-TTS or similar model |
| Streaming Audio | Support chunked audio transmission |
| Authentication | Add API key or token-based auth |
| Load Balancing | Support multiple TTS worker nodes |
| Progress Updates | Send generation progress percentage |
| Voice Cache | Cache generated audio on server |

---

## Usage Examples

### Start TTS Server

```bash
# Start WebSocket server
python src/scripts/tts_ws_server.py --port 8765

# Or with custom host/port
python src/scripts/tts_ws_server.py --host 0.0.0.0 --port 8080
```

### Client Connection

```bash
# Generate audio via WebSocket
python src/scripts/chapter_xml_to_audio.py \
    story-xml/01-chapter.xml \
    --tts-service ws://localhost:8765
```

### Python API

```python
from tts_factory import create_tts_provider

# Create remote provider
provider = create_tts_provider(
    service_url="ws://localhost:8765",
    voices_dir=Path("refs")
)

# Generate audio
wavs, sr = provider.generate(
    text="Hello world",
    speaker="narrator",
    emotion="neutral",
    language="English",
    output_path=Path("output.wav"),
    instruct="Speak clearly"
)

# Cleanup
provider.close()
```

---

## File References

| File | Path | Purpose |
|------|------|---------|
| Client | `src/scripts/chapter_xml_to_audio.py` | XML to audio orchestration |
| Factory | `src/scripts/tts_factory.py` | Provider factory |
| Remote Provider | `src/scripts/tts_service.py` | WebSocket client |
| Server | `src/scripts/tts_ws_server.py` | WebSocket endpoint |
| Local Provider | `src/scripts/tts_local.py` | Qwen3-TTS wrapper |
| Interface | `src/scripts/tts_interface.py` | Abstract definitions |
| Check Script | `src/scripts/check_tts_service.py` | Health check utility |
| Start Script | `src/scripts/start_tts_service.py` | Service launcher |

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-02-27 | Initial documentation of WebSocket TTS service contract |

---

*Document generated from codebase analysis. See individual source files for implementation details.*
