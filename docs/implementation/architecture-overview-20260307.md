# FlexiTTS UI Architecture Overview

**Document Date:** March 7, 2026
**Total Lines of Code:** ~4,200
**Architecture Pattern:** React + Custom Hooks + Service Layer + Provider Pattern
**State Management:** React Hooks (useState, useRef, useCallback)
**Backend Integration:** Electron IPC Bridge + Python Scripts + WebSocket TTS Service

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [System Architecture](#system-architecture)
3. [Component Hierarchy](#component-hierarchy)
4. [Data Flow Architecture](#data-flow-architecture)
5. [Service Layer Architecture](#service-layer-architecture)
6. [TTS Service Architecture](#tts-service-architecture)
7. [Alert System Architecture Details](#alert-system-architecture-details)
8. [Voice Cache Architecture](#voice-cache-architecture)
9. [State Management Flow](#state-management-flow)
10. [File Structure](#file-structure)
11. [Key Design Decisions](#key-design-decisions)
12. [Testing Architecture](#testing-architecture)

---

## Executive Summary

FlexiTTS is an **Electron-based desktop application** for converting story
chapters into spoken audio using Text-to-Speech (TTS) technology. The UI
architecture follows modern React patterns with a clear separation of concerns
and a sophisticated TTS provider system supporting both local and remote
GPU-cached TTS processing.

| Layer             | Purpose                           | LOC    |
|:----------------- |:--------------------------------- |:------ |
| **Components**    | UI rendering                      | ~1,100 |
| **Hooks**         | State management & business logic | ~900   |
| **Services**      | External communication            | ~600   |
| **TTS Providers** | Local/Remote TTS abstraction      | ~800   |
| **Models**        | Type definitions                  | ~100   |
| **Utils**         | Helper functions                  | ~50    |
| **Tests**         | Test coverage                     | ~1,200 |

### Recent Refactoring Achievement (March 2026)

- **TTS Service Architecture**: New WebSocket-based remote TTS with GPU model caching
- **Provider Pattern**: Abstract `TTSInterface` with `LocalTTSProvider` and `RemoteTTSProvider`
- **Voice Cache System**: Thread-safe LRU cache for voice cloning prompts
- **Alert System**: WebSocket-based real-time alerts from TTS service to UI
- **299 Python tests passing (100%)**
- **Zero TypeScript errors**

---

## System Architecture

### High-Level System Diagram

```mermaid
%%{init: {
  "theme": "base",
  "themeVariables": {
    "primaryColor": "#ffffff",
    "primaryTextColor": "#000000",
    "primaryBorderColor": "#000000",
    "lineColor": "#000000",
    "background": "#ffffff"
  }
}}%%
flowchart TB
    subgraph "Electron Main Process"
        MAIN[main.ts<br/>IPC Handlers & TTS Spawner]
        TTS_SPAWN[TTS Service Spawner<br/>start_tts_service.py]
        PYTHON[Python Scripts<br/>chapter_to_xml.py<br/>chapter_xml_to_audio.py<br/>validate_config.py]
    end

    subgraph "TTS Service Process"
        WS_SERVER[TTS WebSocket Server<br/>tts_ws_server.py:8765]
        GPU_CACHE[GPU Model Cache<br/>Qwen3-TTS Cached]
        VOICE_CACHE[LRU Voice Cache<br/>Thread-Safe]
        HANDLER[Request Handler<br/>Audio Generation]
    end

    subgraph "Electron Renderer Process"
        subgraph "React Application"
            APP[App.tsx<br/>Orchestrator]

            subgraph "Custom Hooks"
                UC[useChapter.ts<br/>Chapter State]
                UA[useAudio.ts<br/>Audio State]
                UM[useMarkdown.ts<br/>Editor State]
                UALERT[useAlerts.ts<br/>Alert State]
                UTTS[useTtsAlerts.ts<br/>TTS WebSocket Client]
            end

            subgraph "UI Components"
                TB[TopBar.tsx<br/>Navigation & Controls]
                DB[DialogBar.tsx<br/>Dialog Editor]
                ALERT[AlertContainer.tsx<br/>Toast Notifications]
            end

            subgraph "Services"
                PBS[PythonBridgeService.ts<br/>IPC Communication]
                CS[chapterService.ts<br/>XML Generation]
            end
        end

        subgraph "Models"
            TYPES[types.ts<br/>TypeScript Interfaces]
        end
    end

    subgraph "File System"
        MD[*.md<br/>Markdown Chapters]
        XML[*.xml<br/>Chapter Structure]
        WAV[*.wav<br/>Audio Clips]
        YAML[story-config.yml<br/>Configuration]
    end

    %% Data Flow
    APP --> UC
    APP --> UA
    APP --> UM
    APP --> UALERT
    APP --> UTTS
    APP --> TB
    APP --> DB
    APP --> ALERT

    UC --> PBS
    UA --> PBS
    UM --> PBS
    UTTS -->|WebSocket| WS_SERVER

    PBS --> MAIN
    MAIN --> PYTHON
    MAIN --> TTS_SPAWN
    TTS_SPAWN -->|spawn| WS_SERVER

    WS_SERVER --> GPU_CACHE
    WS_SERVER --> VOICE_CACHE
    WS_SERVER --> HANDLER

    UC --> CS

    PYTHON --> MD
    PYTHON --> XML
    PYTHON --> WAV
    PBS --> YAML
    HANDLER --> WAV

    %% Styling
    classDef hook fill:#e1f5fe,stroke:#01579b
    classDef service fill:#f3e5f5,stroke:#4a148c
    classDef component fill:#e8f5e9,stroke:#1b5e20
    classDef main fill:#fff3e0,stroke:#e65100
    classDef data fill:#fce4ec,stroke:#880e4f
    classDef tts fill:#c8e6c9,stroke:#2e7d32
    classDef cache fill:#fff9c4,stroke:#f57f17

    class UC,UA,UM,UALERT,UTTS hook
    class PBS,CS service
    class TB,DB,ALERT component
    class MAIN,PYTHON,TTS_SPAWN main
    class MD,XML,WAV,YAML data
    class WS_SERVER,GPU_CACHE,VOICE_CACHE,HANDLER tts
```

## Service Layer Architecture

### Architecture Layers

```mermaid
flowchart LR
    subgraph "Presentation Layer"
        C1[App.tsx]
        C2[TopBar.tsx]
        C3[DialogBar.tsx]
        C4[AlertContainer.tsx]
    end

    subgraph "Business Logic Layer"
        H1[useChapter.ts]
        H2[useAudio.ts]
        H3[useMarkdown.ts]
        H4[useAlerts.ts]
        H5[useTtsAlerts.ts]
    end

    subgraph "Service Layer"
        S1[PythonBridgeService.ts]
        S2[chapterService.ts]
        S3[TTSProviderFactory]
    end

    subgraph "Infrastructure Layer"
        I1[Electron IPC]
        I2[Python Scripts]
        I3[WebSocket TTS]
        I4[File System]
    end

    C1 --> H1
    C1 --> H2
    C1 --> H3
    C1 --> H4
    C2 --> C1
    C3 --> C1
    C4 --> H4

    H1 --> S1
    H1 --> S2
    H2 --> S1
    H3 --> S1
    H5 --> S3

    S1 --> I1
    S1 --> I2
    S1 --> I4
    S3 --> I3
```

---

## TTS Service Architecture

### TTS Service Overview

The TTS (Text-to-Speech) Service Architecture introduces a **Provider Pattern**
with both local and remote TTS implementations. The remote TTS service uses
WebSocket communication with GPU model caching for enhanced performance.

**Key Architectural Patterns:**

- **Abstract Interface**: `TTSInterface` defines the contract for all TTS providers
- **Factory Pattern**: `TTSProviderFactory` creates appropriate provider instances
- **Strategy Pattern**: Switch between local and remote providers transparently
- **Fallback Pattern**: Automatic fallback from remote to local on failure
- **LRU Cache**: Thread-safe voice prompt caching for voice cloning

**Key Benefits:**

- **GPU Model Caching**: Remote service maintains loaded TTS models in GPU memory
- **Reduced Memory Fragmentation**: Long-running service prevents repeated model
  loading/unloading
- **Flexible Deployment**: Run TTS locally or remotely based on configuration
- **Graceful Degradation**: Automatic fallback to local TTS if remote fails
- **Thread-Safe Caching**: LRU voice cache with proper synchronization

### TTS Provider Class Hierarchy

```mermaid
classDiagram
    class TTSInterface {
        <<abstract>>
        +generate(text, speaker, ...)
        +supports_character(char_config)
        +close()
    }

    class LocalTTSProvider {
        +base_model: Qwen3TTSModel
        +custom_model: Qwen3TTSModel
        +voices_dir: Path
        +_voice_prompts: Dict
        +generate(...)
        +supports_character(char_config)
        +close()
    }

    class RemoteTTSProvider {
        +service_url: str
        +fallback_provider: TTSInterface
        +max_retries: int
        +timeout: float
        +_websocket: WebSocket
        +generate(...)
        +health_check()
        +supports_character(char_config)
        +close()
    }

    class TTSProviderFactory {
        +_cache: Dict
        +_local_provider: LocalTTSProvider
        +create_provider(...)
        +close_all()
        +from_command_line(...)
    }

    class TTSError {
        <<exception>>
    }

    class TTSConnectionError {
        <<exception>>
    }

    class TTSGenerationError {
        <<exception>>
    }

    class CharacterNotSupportedError {
        <<exception>>
    }

    class TTSResult {
        +audio_segments: List
        +sample_rate: int
        +duration: float
    }

    TTSInterface <|-- LocalTTSProvider
    TTSInterface <|-- RemoteTTSProvider
    TTSProviderFactory ..> LocalTTSProvider : creates
    TTSProviderFactory ..> RemoteTTSProvider : creates
    RemoteTTSProvider o-- LocalTTSProvider : fallback
    TTSError <|-- TTSConnectionError
    TTSError <|-- TTSGenerationError
    TTSError <|-- CharacterNotSupportedError
```

### TTS Service System Diagram

```mermaid
%%{init: {
  "theme": "base",
  "themeVariables": {
    "primaryColor": "#ffffff",
    "primaryTextColor": "#000000",
    "primaryBorderColor": "#000000",
    "lineColor": "#000000",
    "background": "#ffffff"
  }
}}%%
flowchart TB
    subgraph "Client Side"
        FACTORY[TTSProviderFactory]
        REMOTE[RemoteTTSProvider<br/>WebSocket Client]
        FALLBACK[LocalTTSProvider<br/>Fallback]
        CHAPTER[chapter_xml_to_audio.py]
    end

    subgraph "TTS Service Process"
        WS_SERVER[TTS WebSocket Server<br/>Port 8765]
        GPU_CACHE[GPU Model Cache<br/>Qwen3-TTS Model]
        VOICE_CACHE[LRU Voice Cache<br/>Thread-Safe]
        HANDLER[Request Handler]
    end

    subgraph "Output"
        WAV["*.wav<br/>Audio Clips"]
    end

    %% Creation Flow
    CHAPTER -->|uses --tts-service| FACTORY
    FACTORY -->|creates| REMOTE
    REMOTE -->|fallback on failure| FALLBACK

    %% Runtime Flow
    REMOTE -->|WebSocket| WS_SERVER
    WS_SERVER -->|uses| GPU_CACHE
    WS_SERVER -->|uses| VOICE_CACHE
    WS_SERVER -->|generates| HANDLER
    HANDLER -->|writes| WAV

    %% Fallback Flow
    FALLBACK -->|generates| WAV

    %% Styling
    classDef factory fill:#e3f2fd,stroke:#1565c0
    classDef client fill:#e8f5e9,stroke:#2e7d32
    classDef fallback fill:#ffebee,stroke:#c62828
    classDef service fill:#c8e6c9,stroke:#2e7d32
    classDef cache fill:#fff9c4,stroke:#f57f17
    classDef output fill:#f3e5f5,stroke:#6a1b9a

    class FACTORY factory
    class CHAPTER,REMOTE client
    class FALLBACK fallback
    class WS_SERVER,GPU_CACHE,HANDLER service
    class VOICE_CACHE cache
    class WAV output
```

### TTS Service Startup Sequence

```mermaid
sequenceDiagram
    participant Main as Electron Main
    participant Spawner as start_tts_service.py
    participant Server as tts_ws_server.py
    participant GPU as GPU Memory
    participant Cache as LRU Voice Cache
    participant Health as Health Check

    Note over Main,Health: TTS Service Startup Phase

    Main->>Spawner: spawn start_tts_service.py
    activate Spawner
    Spawner->>Server: Start WebSocket server
    activate Server
    Server->>GPU: Load Qwen3-TTS model to GPU
    GPU-->>Server: Model cached (10-30s)
    Server->>Cache: Initialize LRU cache (default: 10)
    Server->>Server: Start WebSocket listener (port 8765)
    Server-->>Spawner: Service ready
    deactivate Spawner
    Server-->>Main: Process started

    Main->>Health: Begin health polling via check_tts_service.py
    loop Health Check (via WebSocket)
        Health->>Server: Connect ws://localhost:8765
        Health->>Server: Send {"action": "health"}
        Server-->>Health: {"status": "healthy", "ready": true}
    end
    Health-->>Main: Service ready confirmed

    Note over Main,Health: TTS Service Ready for Requests
```

### WebSocket Communication Protocol

The TTS Service uses a JSON-based WebSocket protocol for request/response
communication with support for binary audio streaming:

**Request Format:**

```json
{
  "text": "Hello, this is a test.",
  "speaker": "narrator",
  "emotion": "neutral",
  "language": "English",
  "instruct": "Speak clearly and naturally",
  "character_config": {
    "voice-sample": "refs/voice.wav",
    "custom-voice": { "key": "..." }
  },
  "story": "Story-Entanglement",
  "chapter": "01",
  "section": "002",
  "dialog": "001"
}
```

**Response Flow:**

1. **Handshake**: Connection established with retry logic
2. **Metadata Message** (JSON): Contains sample rate, duration, format info
3. **Binary Audio Chunks**: Streamed WAV audio data
4. **Completion Message** (JSON): `{"done": true}` or `{"error": "message"}`

**Error Handling:**

- Connection failures trigger exponential backoff retry (1s, 2s, 4s, 8s)
- After max retries (default: 4), falls back to LocalTTSProvider
- Timeout for generation requests: configurable (default: 60s)

### Remote TTS Provider with Retry Logic

```mermaid
flowchart TB
    subgraph "RemoteTTSProvider.generate()"
        START[Start Generation]
        CONNECT{_connect_with_retry}
        SEND[Send Request]
        RECEIVE{Receive Response}
        SUCCESS[Success]
        RETRY{Retry Count < Max?}
        BACKOFF[Exponential Backoff]
        FALLBACK[_try_fallback]
        ERROR[Raise TTSError]
    end

    START --> CONNECT
    CONNECT -->|Connection Failed| RETRY
    RETRY -->|Yes| BACKOFF
    BACKOFF --> CONNECT
    RETRY -->|No| FALLBACK

    CONNECT -->|Connected| SEND
    SEND --> RECEIVE
    RECEIVE -->|Success| SUCCESS
    RECEIVE -->|Error| FALLBACK

    FALLBACK -->|Fallback Available| LOCAL[LocalTTSProvider.generate]
    FALLBACK -->|No Fallback| ERROR
    LOCAL --> SUCCESS

    style SUCCESS fill:#c8e6c9
    style ERROR fill:#ffcdd2
    style FALLBACK fill:#fff9c4
```

### Configuration Options

| Option                 | Default    | Description                                        |
|:---------------------- |:---------- |:-------------------------------------------------- |
| `service_url`          | `None`     | WebSocket URL (ws:// or wss://) for remote service |
| `max_retries`          | 4          | Max retry attempts with exponential backoff        |
| `timeout`              | 30s        | Connection timeout in seconds                      |
| `enable_fallback`      | `True`     | Enable fallback to local TTS on failure            |
| `voices_dir`           | `./voices` | Directory for voice reference samples              |
| `max_voice_cache_size` | 10         | Maximum voice prompts to cache (config.yml)        |
| `tts-device`           | `auto`     | Device selection: auto/cpu/cuda/cuda:N             |

---

## Alert System Architecture Details

### Alert System Overview

The Alert System provides real-time notifications from the TTS service to the UI
via WebSocket, enabling users to see TTS generation progress and errors without
polling.

**Key Components:**

- **useAlerts**: Generic alert state management hook
- **useTtsAlerts**: WebSocket client for TTS service alerts
- **AlertContainer**: Fixed-position toast notification container
- **AlertToast**: Individual toast component with animations

### Alert System Architecture

```mermaid
%%{init: {
  "theme": "base",
  "themeVariables": {
    "primaryColor": "#ffffff",
    "primaryTextColor": "#000000",
    "primaryBorderColor": "#000000",
    "lineColor": "#000000",
    "background": "#ffffff"
  }
}}%%
flowchart TB
    subgraph "TTS Service"
        TTS_GEN[TTS Generation]
        WS_SEND[WebSocket Send]
    end

    subgraph "UI - React Hooks"
        UTTS[useTtsAlerts.ts<br/>WebSocket Client]
        UALERT[useAlerts.ts<br/>Alert State]
    end

    subgraph "UI - Components"
        CONTAINER[AlertContainer.tsx]
        TOAST[AlertToast.tsx]
    end

    subgraph "Message Flow"
        MSG1["TTS Alert Message<br/>{type: 'alert', alertType: 'info', message: '...', metadata: {...}}"]
        MSG2["Status Message<br/>{type: 'status', status: 'ready', ready: true}"]
    end

    TTS_GEN -->|sends| WS_SEND
    WS_SEND -->|ws://localhost:8765| UTTS
    UTTS -->|onAlert callback| UALERT
    UTTS -->|onStatus callback| MSG2
    UALERT -->|alerts array| CONTAINER
    CONTAINER -->|maps| TOAST

    style TTS_GEN fill:#c8e6c9
    style UTTS fill:#e3f2fd
    style UALERT fill:#e3f2fd
    style CONTAINER fill:#fff3e0
    style TOAST fill:#fff3e0
```

```typescript
// Alert types for visual styling
type AlertType = 'info' | 'success' | 'warning' | 'error';
type AlertSource = 'internal' | 'tts-service';

interface Alert {
  id: string;
  message: string;
  type: AlertType;
  source: AlertSource;
  timestamp: Date;
  duration?: number; // ms, default 3000
}
```

### Alert Type Visuals

| Type      | Icon | Background | Usage               |
|:--------- |:---- |:---------- |:------------------- |
| `info`    | ℹ️   | Blue       | General information |
| `success` | ✓    | Green      | Operation completed |
| `warning` | ⚠️   | Yellow     | Non-critical issues |
| `error`   | ✕    | Red        | Critical errors     |

### WebSocket Alert Protocol

**From TTS Service to UI:**

```json
{
  "type": "alert",
  "alertType": "info|success|warning|error",
  "message": "Generating audio for chapter_001_002_001...",
  "source": "tts-service",
  "metadata": {
    "chapter": "01",
    "section": "002",
    "dialog": "001",
    "character": "narrator"
  }
}
```

**Status Updates:**

```json
{
  "type": "status",
  "status": "ready",
  "ready": true,
  "cached": true
}
```

### Alert Lifecycle

```mermaid
sequenceDiagram
    participant TTS as TTS Service
    participant WS as WebSocket
    participant Hook as useTtsAlerts
    participant State as useAlerts
    participant UI as AlertToast

    TTS->>TTS: Generate audio for dialog
    TTS->>WS: Send alert message
    WS->>Hook: onmessage event
    Hook->>Hook: Parse JSON
    Hook->>State: onAlert callback
    State->>State: addAlert()
    State->>State: setAlerts([...alerts, newAlert])
    State-->>UI: alerts prop updated
    UI->>UI: Mount with enter animation

    Note over UI: Auto-dismiss after duration

    UI->>UI: Exit animation trigger
    UI->>State: removeAlert(id)
    State->>State: Filter out alert
    State-->>UI: alerts prop updated
    UI->>UI: Unmount component
```

---

## Voice Cache Architecture

### Voice Cache Overview

The Voice Cache provides thread-safe LRU (Least Recently Used) caching for
voice cloning prompts, significantly improving performance when generating
audio for the same character multiple times.

**Key Features:**

- **Thread-Safe**: All operations protected by `threading.Lock`
- **Configurable Size**: Set via `max_voice_cache_size` in story-config.yml
  (default: 10)
- **LRU Eviction**: Oldest entries removed when capacity reached
- **Statistics**: Hit/miss rate tracking for performance monitoring
- **Threading-Safe**: Proper synchronization for multi-threaded TTS generation

### Voice Cache Class Diagram

```mermaid
classDiagram
    class LRUVoiceCache {
        -_cache: OrderedDict
        -_lock: Lock
        -_hits: int
        -_misses: int
        +maxsize: int
        +get(key): Optional(Any)
        +put(key, value): void
        +clear(): void
        +stats: dict
    }

    class LocalTTSProvider {
        +_voice_prompts: LRUVoiceCache
        +_load_voice_prompt(voice_sample): Any
    }

    class Qwen3TTSAdapter {
        +voice_cache: LRUVoiceCache
    }

    LocalTTSProvider --> LRUVoiceCache : uses
    Qwen3TTSAdapter --> LRUVoiceCache : uses
```

### Voice Cache Sequence

```mermaid
sequenceDiagram
    participant Gen as Audio Generation
    participant Provider as LocalTTSProvider
    participant Cache as LRUVoiceCache
    participant Model as Qwen3TTSModel
    participant File as Voice Sample File

    Gen->>Provider: generate(text, speaker, char_config)
    Provider->>Provider: _load_voice_prompt(sample)

    Provider->>Cache: get(sample)
    alt Cache Hit
        Cache-->>Provider: cached_prompt
        Provider->>Cache: move_to_end(sample)
        Cache->>Cache: _hits++
    else Cache Miss
        Cache-->>Provider: None
        Cache->>Cache: _misses++
        Provider->>File: Read voice sample (.wav)
        File-->>Provider: audio data
        Provider->>Model: create_voice_clone_prompt(audio)
        Model-->>Provider: prompt
        Provider->>Cache: put(sample, prompt)
        alt Cache Full
            Cache->>Cache: Evict oldest entry
        end
        Cache->>Cache: Insert new entry
    end

    Provider-->>Gen: voice prompt ready
```

### Thread Safety

The voice cache implements proper thread safety for concurrent TTS generation:

```python
import threading
from collections import OrderedDict
from typing import Any, Optional


class LRUVoiceCache:
    def __init__(self, maxsize: int = 10):
        self.maxsize = maxsize
        self._cache: OrderedDict[str, Any] = OrderedDict()
        self._lock = threading.Lock()  # Thread-safe lock

    def get(self, key: str) -> Optional[Any]:
        with self._lock:  # Protected access
            if key in self._cache:
                self._cache.move_to_end(key)
                return self._cache[key]
            return None

    def put(self, key: str, value: Any) -> None:
        with self._lock:  # Protected access
            # Eviction and insertion logic
            pass
```

### Statistics and Monitoring

```python
{
    'size': 5,           # Current cached items
    'maxsize': 10,       # Maximum capacity
    'hits': 45,          # Cache hits
    'misses': 12,        # Cache misses
    'hit_rate': 0.789    # Hit rate (0-1)
}
```

---

## Component Hierarchy

### Component Tree

```mermaid
%%{init: {
  "theme": "base",
  "themeVariables": {
    "primaryColor": "#ffffff",
    "primaryTextColor": "#000000",
    "primaryBorderColor": "#000000",
    "lineColor": "#000000",
    "background": "#ffffff"
  }
}}%%
flowchart TD
    subgraph "Entry Point"
        ROOT[main.tsx]
    end

    subgraph "Root Component"
        APP[App.tsx]

        subgraph "Custom Hooks"
            USE_CHAPTER[useChapter.ts]
            USE_AUDIO[useAudio.ts]
            USE_MARKDOWN[useMarkdown.ts]
            USE_ALERTS[useAlerts.ts]
            USE_TTS[useTtsAlerts.ts]
        end
    end

    subgraph "Child Components"
        TOPBAR[TopBar.tsx]
        DIALOG_BAR[DialogBar.tsx]
        ALERT[AlertContainer.tsx]
        CHAPTER_MENU[Context Menu]
        EDITOR[Markdown Editor]
    end

    subgraph "TTS Providers"
        FACTORY[TTSProviderFactory]
        LOCAL[LocalTTSProvider]
        REMOTE[RemoteTTSProvider]
        CACHE[LRUVoiceCache]
    end

    ROOT --> APP

    APP --> USE_CHAPTER
    APP --> USE_AUDIO
    APP --> USE_MARKDOWN
    APP --> USE_ALERTS
    APP --> USE_TTS

    APP --> TOPBAR
    APP --> DIALOG_BAR
    APP --> ALERT
    APP --> CHAPTER_MENU
    APP --> EDITOR

    USE_TTS -->|creates| FACTORY
    FACTORY -->|creates| LOCAL
    FACTORY -->|creates| REMOTE
    LOCAL -->|uses| CACHE
    REMOTE -->|fallback| LOCAL
```

---

## Data Flow Architecture

### State Management Flow

```mermaid
%%{init: {
  "theme": "base",
  "themeVariables": {
    "primaryColor": "#ffffff",
    "primaryTextColor": "#000000",
    "primaryBorderColor": "#000000",
    "lineColor": "#000000",
    "background": "#ffffff"
  }
}}%%
flowchart LR
    subgraph "External State Sources"
        FILE[File System]
        WS[WebSocket TTS]
        ELECTRON[Electron IPC]
    end

    subgraph "Service Layer"
        PBS[PythonBridgeService]
        TTS[TTSProviderFactory]
    end

    subgraph "Hook State"
        UC[useChapter]
        UA[useAudio]
        UM[useMarkdown]
        UAL[useAlerts]
        UTTS[useTtsAlerts]
    end

    subgraph "Components"
        APP[App.tsx]
        ALERT[AlertContainer]
    end

    FILE -->|read| PBS
    WS -->|messages| UTTS
    ELECTRON -->|IPC| PBS

    PBS -->|updates| UC
    PBS -->|updates| UA
    TTS -->|updates| UTTS

    UC --> APP
    UA --> APP
    UM --> APP
    UAL --> ALERT
    UTTS --> UAL
```

---

## File Structure

```text
src/
├── scripts/
│   ├── tts_interface.py          # Abstract TTS interface
│   ├── tts_local.py              # Local TTS provider
│   ├── tts_service.py            # Remote TTS provider
│   ├── tts_factory.py            # TTS provider factory
│   ├── tts_ws_server.py          # WebSocket TTS server
│   ├── start_tts_service.py      # TTS service startup script
│   ├── stop_tts_service.py       # TTS service shutdown script
│   ├── check_tts_service.py      # TTS health check
│   ├── chapter_xml_to_audio.py   # Chapter rendering
│   └── tts_models/
│       └── adapters/
│           └── qwen3/
│               └── voice_cache.py  # LRU voice cache
│
└── ui/
    └── src/
        ├── App.tsx
        ├── components/
        │   ├── AlertContainer.tsx    # Toast container
        │   └── AlertToast.tsx        # Individual toast
        ├── hooks/
        │   ├── useAlerts.ts          # Alert state management
        │   ├── useTtsAlerts.ts       # TTS WebSocket client
        │   └── index.ts
        └── services/
            └── pythonBridge.ts
```

---

## Key Design Decisions

### 1. TTS Provider Pattern

**Decision:** Abstract `TTSInterface` with `LocalTTSProvider` and
`RemoteTTSProvider`.

**Rationale:**

- Clean separation between local and remote TTS
- Easy to add new provider types (e.g., cloud services)
- Factory pattern for configurable instantiation
- Fallback mechanism for reliability

**Trade-off:** More abstraction layers, but enables flexible deployment.

### 2. Voice Cache with Thread Safety

**Decision:** Thread-safe LRU cache using `threading.Lock` for voice prompts.

**Rationale:**

- Significant performance improvement for repeated characters
- Thread-safe for concurrent TTS generation
- Configurable size via story-config.yml
- Hit rate monitoring for optimization

**Trade-off:** Memory usage for cached prompts, but configurable limits.

### 3. WebSocket Alert System

**Decision:** Real-time WebSocket alerts from TTS service to UI.

**Rationale:**

- No polling required for status updates
- Real-time feedback during chapter generation
- Decoupled from main TTS generation flow
- Automatic reconnection with exponential backoff

**Trade-off:** Additional WebSocket connection, but minimal overhead.

### 4. Tracking Parameters in generate()

**Decision:** Added `story`, `chapter`, `section`, `dialog` parameters to
`generate()`.

**Rationale:**

- Enables context-aware error messages
- Supports detailed progress tracking
- Facilitates alert metadata for UI
- Non-breaking (all optional parameters)

**Trade-off:** Slightly more complex method signature.

### 5. Remote TTS with Exponential Backoff

**Decision:** Retry logic with exponential backoff for remote TTS connections.

**Rationale:**

- Handles transient network issues
- Graceful degradation to local TTS
- Configurable retry counts and timeouts
- Better user experience during service startup

**Trade-off:** Slightly longer recovery time in some failure scenarios.

---

## Testing Architecture

### Test Coverage (299 Python Tests)

```mermaid
%%{init: {
  "theme": "base",
  "themeVariables": {
    "primaryColor": "#ffffff",
    "primaryTextColor": "#000000",
    "primaryBorderColor": "#000000",
    "lineColor": "#000000",
    "background": "#ffffff"
  }
}}%%
flowchart TB
    subgraph "Test Categories"
        TTS["TTS Provider Tests<br/>test_tts_local.py<br/>test_tts_service.py<br/>test_tts_factory.py<br/>test_tts_interface.py<br/>test_tts_service_startup.py<br/>test_tts_service_retry.py<br/>test_tts_service_health.py"]

        CACHE["Voice Cache Tests<br/>test_voice_cache_threading.py<br/>test_voice_cache.py"]

        WS["WebSocket Tests<br/>test_websocket_stress.py"]

        CHAPTER["Chapter Tests<br/>test_chapter_*.py<br/>test_integration_chapter_*.py"]

        CONFIG["Config Tests<br/>test_validate_config.py<br/>test_integration_validate_config.py"]
    end

    subgraph "Test Tools"
        VITEST[vitest]
        PYTEST[pytest]
        RTL[@testing-library/react]
    end

    TTS -->|python| PYTEST
    CACHE -->|python| PYTEST
    WS -->|python| PYTEST
    CHAPTER -->|python| PYTEST
    CONFIG -->|python| PYTEST
```

---

## Summary

### Architecture Strengths (March 2026)

1. **Flexible TTS Providers**: Switch between local and remote TTS transparently
2. **GPU Model Caching**: 10-30x faster repeated TTS generation
3. **Thread-Safe Voice Cache**: Optimized voice cloning performance
4. **Real-Time Alerts**: WebSocket-based user feedback without polling
5. **Graceful Fallback**: Automatic recovery from remote service failures
6. **Robust Testing**: 299 Python tests with 100% pass rate
7. **Type-Safe**: Full TypeScript coverage for UI

### Areas for Future Improvement

1. **Cloud Provider Support**: Add AWS/GCP/Azure TTS providers
2. **Voice Cache Persistence**: Save/load cache across app restarts
3. **Batch Generation**: Optimize for multiple chapters
4. **Progress Streaming**: Real-time audio streaming during generation
5. **Voice Training**: Support for custom voice training workflows

---

## Conclusion

*Generated: March 7, 2026*
*Tool: Mermaid.js v10+ compatible diagrams*
