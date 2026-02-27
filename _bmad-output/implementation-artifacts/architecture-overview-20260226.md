# FlexiTTS UI Architecture Overview

**Document Date:** February 26, 2026  
**Total Lines of Code:** 3,386  
**Architecture Pattern:** React + Custom Hooks + Service Layer  
**State Management:** React Hooks (useState, useRef, useCallback)  
**Backend Integration:** Electron IPC Bridge + Python Scripts

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [System Architecture](#system-architecture)
3. [Component Hierarchy](#component-hierarchy)
4. [Data Flow Architecture](#data-flow-architecture)
5. [Service Layer](#service-layer)
6. [TTS Service Architecture](#tts-service-architecture)
7. [State Management](#state-management)
8. [File Structure](#file-structure)
9. [Key Design Decisions](#key-design-decisions)
10. [Testing Architecture](#testing-architecture)

---

## Executive Summary

FlexiTTS is an **Electron-based desktop application** for converting story chapters into spoken audio using Text-to-Speech (TTS) technology. The UI architecture follows modern React patterns with a clear separation of concerns:

| Layer | Purpose | LOC |
|-------|---------|-----|
| **Components** | UI rendering | ~900 |
| **Hooks** | State management & business logic | ~800 |
| **Services** | External communication | ~500 |
| **Models** | Type definitions | ~50 |
| **Utils** | Helper functions | ~30 |
| **Tests** | Test coverage | ~1,100 |

### Recent Refactoring Achievement

- **App.tsx reduced from 723 → 322 lines (-55.5%)**
- **72 tests passing (100%)**
- **Zero TypeScript errors**

---

## System Architecture

### High-Level System Diagram

```mermaid
%%{init: {
  'theme': 'base',
  'themeVariables': {
    'primaryColor': '#ffffff',
    'primaryTextColor': '#000000',
    'primaryBorderColor': '#000000',
    'lineColor': '#000000',
    'background': '#ffffff'
  }
}}%%
flowchart TB
    subgraph "Electron Main Process"
        MAIN[main.ts<br/>IPC Handlers]
        PYTHON[Python Scripts<br/>chapter_to_xml.py<br/>chapter_xml_to_audio.py<br/>validate_config.py]
    end

    subgraph "Electron Renderer Process"
        subgraph "React Application"
            APP[App.tsx<br/>Orchestrator]
            
            subgraph "Custom Hooks"
                UC[useChapter.ts<br/>Chapter State]
                UA[useAudio.ts<br/>Audio State]
                UM[useMarkdown.ts<br/>Editor State]
            end
            
            subgraph "UI Components"
                TB[TopBar.tsx<br/>Navigation & Controls]
                DB[DialogBar.tsx<br/>Dialog Editor]
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
    APP --> TB
    APP --> DB
    
    UC --> PBS
    UA --> PBS
    UM --> PBS
    
    PBS --> MAIN
    MAIN --> PYTHON
    
    UC --> CS
    
    PYTHON --> MD
    PYTHON --> XML
    PYTHON --> WAV
    PBS --> YAML
    
    %% Styling
    classDef hook fill:#e1f5fe,stroke:#01579b
    classDef service fill:#f3e5f5,stroke:#4a148c
    classDef component fill:#e8f5e9,stroke:#1b5e20
    classDef main fill:#fff3e0,stroke:#e65100
    classDef data fill:#fce4ec,stroke:#880e4f
    
    class UC,UA,UM hook
    class PBS,CS service
    class TB,DB component
    class MAIN,PYTHON main
    class MD,XML,WAV,YAML data
```

### Architecture Layers

```mermaid
flowchart LR
    subgraph "Presentation Layer"
        C1[App.tsx]
        C2[TopBar.tsx]
        C3[DialogBar.tsx]
    end

    subgraph "Business Logic Layer"
        H1[useChapter.ts]
        H2[useAudio.ts]
        H3[useMarkdown.ts]
    end

    subgraph "Service Layer"
        S1[PythonBridgeService.ts]
        S2[chapterService.ts]
    end

    subgraph "Infrastructure Layer"
        I1[Electron IPC]
        I2[Python Scripts]
        I3[File System]
    end

    C1 --> H1
    C1 --> H2
    C1 --> H3
    C2 --> C1
    C3 --> C1
    
    H1 --> S1
    H1 --> S2
    H2 --> S1
    H3 --> S1
    
    S1 --> I1
    S1 --> I2
    S2 --> I3
```

---

## Component Hierarchy

### Component Tree

```mermaid
%%{init: {
  'theme': 'base',
  'themeVariables': {
    'primaryColor': '#ffffff',
    'primaryTextColor': '#000000',
    'primaryBorderColor': '#000000',
    'lineColor': '#000000',
    'background': '#ffffff'
  }
}}%%
flowchart TD
    subgraph "Entry Point"
        ROOT[main.tsx]
    end

    subgraph "Root Component"
        APP[App.tsx]
        
        subgraph "Custom Hooks (useState/useRef)"
            USE_CHAPTER[useChapter.ts<br/>17 state items]
            USE_AUDIO[useAudio.ts<br/>2 state items]
            USE_MARKDOWN[useMarkdown.ts<br/>5 state items]
        end
    end

    subgraph "Child Components"
        TOPBAR[TopBar.tsx<br/>Props: Chapter, Config, Handlers]
        DIALOG_BAR[DialogBar.tsx<br/>Props: DialogElement, Handlers]
        CHAPTER_MENU[Context Menu<br/>Chapter Selection]
        EDITOR[Markdown Editor<br/>Side Panel]
    end

    subgraph "State Flow"
        SF1[Refs for Sync Access]
        SF2[useCallback for Handlers]
        SF3[Props Drilling to Children]
    end

    ROOT --> APP
    
    APP --> USE_CHAPTER
    APP --> USE_AUDIO
    APP --> USE_MARKDOWN
    
    APP --> TOPBAR
    APP --> DIALOG_BAR
    APP --> CHAPTER_MENU
    APP --> EDITOR
    
    USE_CHAPTER -.->|provides handlers| SF1
    USE_CHAPTER -.->|memoized| SF2
    SF2 -->|via props| TOPBAR
    SF2 -->|via props| DIALOG_BAR

    %% Styling
    classDef root fill:#e3f2fd,stroke:#1565c0
    classDef app fill:#e8f5e9,stroke:#2e7d32
    classDef hook fill:#fff3e0,stroke:#ef6c00
    classDef child fill:#f3e5f5,stroke:#6a1b9a
    classDef flow fill:#fce4ec,stroke:#c2185b
    
    class ROOT root
    class APP app
    class USE_CHAPTER,USE_AUDIO,USE_MARKDOWN hook
    class TOPBAR,DIALOG BAR,CHAPTER_MENU,EDITOR child
    class SF1,SF2,SF3 flow
```

### Component Communication Pattern

```mermaid
sequenceDiagram
    participant User
    participant App as App.tsx
    participant Hook as useChapter.ts
    participant Service as PythonBridge
    participant Python as Python Scripts
    participant FS as File System

    User->>App: Select Chapter
    App->>Hook: handleChapterSelect(file)
    
    alt XML Exists
        Hook->>Service: checkXmlExists(stem)
        Service->>Python: check_xml_exists()
        Python->>FS: Check file
        FS-->>Python: exists
        Python-->>Service: true
        Service-->>Hook: true
        
        Hook->>Service: loadChapter(xmlPath)
        Service->>Python: readChapterFile()
        Python->>FS: Read XML
        FS-->>Python: content
        Python-->>Service: XML string
        Service-->>Hook: parse XML
        Hook->>Hook: parseChapterXML()
        Hook->>Hook: setChapter(parsed)
    else XML Missing
        Hook->>Hook: runXmlGenerationPipeline()
        Note over Hook,Python: 3-step pipeline with retries
        
        Hook->>Service: runPythonScript(chapter_to_xml.py)
        Service->>Python: Generate XML from MD
        Python->>FS: Read .md, Write .xml
        
        Hook->>Service: runPythonScript(chapter_seq_xml.py)
        Service->>Python: Sequence XML
        Python->>FS: Update XML
        
        Hook->>Service: runPythonScript(chapter_validate_xml.py)
        Service->>Python: Validate XML
        Python->>FS: Validate against XSD
        
        Hook->>Service: loadChapter()
    end
    
    Hook-->>App: chapter updated
    App->>App: render with new chapter
```

---

## Data Flow Architecture

### State Management Flow

```mermaid
%%{init: {
  'theme': 'base',
  'themeVariables': {
    'primaryColor': '#ffffff',
    'primaryTextColor': '#000000',
    'primaryBorderColor': '#000000',
    'lineColor': '#000000',
    'background': '#ffffff'
  }
}}%%
flowchart LR
    subgraph "External State Sources"
        FILE[File System<br/>XML, MD, Config]
        ELECTRON[Electron IPC<br/>window.api]
    end

    subgraph "Service Layer"
        PBS[PythonBridgeService<br/>Async I/O]
        CS[chapterService<br/>Pure Functions]
    end

    subgraph "Hook State Containers"
        UC["useChapter.ts
            chapter: Chapter | null
            config: StoryConfig | null
            chapterList: string-array
            availableClips: string-array
            isGenerating: boolean
        "]
        
        UA[useAudio.ts
            availableClips: string-array
            hasChapterAudio: boolean
        ]
        
        UM[useMarkdown.ts
            markdownContent: string
            editorMode: boolean
            hasUnsavedChanges: boolean
        ]
    end

    subgraph "Component State Users"
        APP[App.tsx]
        TB[TopBar.tsx]
        DB[DialogBar.tsx]
    end

    FILE -->|read| PBS
    ELECTRON -->|IPC| PBS
    
    PBS -->|updates| UC
    PBS -->|updates| UA
    PBS -->|updates| UM
    
    CS -->|generates| UC
    
    UC -->|provides| APP
    UA -->|provides| APP
    UM -->|provides| APP
    
    APP -->|props| TB
    APP -->|props| DB

    %% Styling
    classDef external fill:#e3f2fd,stroke:#1565c0
    classDef service fill:#f3e5f5,stroke:#6a1b9a
    classDef hook fill:#fff3e0,stroke:#ef6c00
    classDef comp fill:#e8f5e9,stroke:#2e7d32
    
    class FILE,ELECTRON external
    class PBS,CS service
    class UC,UA,UM hook
    class APP,TB,DB comp
```

### Chapter Data Flow

```mermaid
%%{init: {
  'theme': 'base',
  'themeVariables': {
    'primaryColor': '#ffffff',
    'primaryTextColor': '#000000',
    'primaryBorderColor': '#000000',
    'lineColor': '#000000',
    'background': '#ffffff'
  }
}}%%
flowchart TB
    subgraph "Source of Truth"
        XML[chapter.xml<br/>File System]
    end

    subgraph "Data Transformation"
        LOAD[PythonBridgeService.readChapterFile]
        PARSE[DOMParser.parseFromString]
        EXTRACT[extract DialogElements]
        GEN[generateXMLFromChapter]
    end

    subgraph "React State"
        CHAPTER_STATE[chapter: Chapter<br/>in useChapter hook]
        DIALOGS[chapter-dialogs-array
        DialogElement-array]
    end

    subgraph "UI Representation"
        DIALOG_BAR[DialogBar.tsx
        One per dialog]
        TOP_BAR[TopBar.tsx
        Chapter controls]
    end

    XML -->|load| LOAD
    LOAD -->|xml string| PARSE
    PARSE -->|xmlDoc| EXTRACT
    EXTRACT -->|Chapter object| CHAPTER_STATE
    
    CHAPTER_STATE --> DIALOGS
    DIALOGS -->|map| DIALOG_BAR
    CHAPTER_STATE --> TOP_BAR
    
    %% Edit flow
    DIALOG_BAR -->|onUpdateDialog| CHAPTER_STATE
    CHAPTER_STATE -->|regenerate| GEN
    GEN -->|saves unsaved| CHAPTER_STATE

    %% Styling
    classDef source fill:#e3f2fd,stroke:#1565c0
    classDef transform fill:#fff3e0,stroke:#ef6c00
    classDef state fill:#e8f5e9,stroke:#2e7d32
    classDef ui fill:#f3e5f5,stroke:#6a1b9a
    
    class XML source
    class LOAD,PARSE,EXTRACT,GEN transform
    class CHAPTER_STATE,DIALOGS state
    class DIALOG_BAR,TOP_BAR ui
```

---

## Service Layer

### PythonBridgeService Architecture

```mermaid
classDiagram
    class PythonBridgeService {
        +showErrorDialog(title, message) Promise~void~
        +showConfirmDialog(title, message, detail) Promise~number~
        +validateConfig() Promise~void~
        +validateChapterXML(path) Promise~void~
        +loadStoryConfig() Promise~StoryConfig~
        +readChapterFile(path) Promise~string~
        +listChapterFiles() Promise~string-array~
        +checkXmlExists(stem) Promise~boolean~
        +readFile(path) Promise~string~
        +writeChapterFile(path, content) Promise~boolean~
        +playAudio(chapter, section, dialog-sequence, callback, skip) Promise~void~
        +listChapterClips(name) Promise~string-array~
        +checkChapterAudio(name) Promise~boolean~
        +cancelAudio(match) Promise~void~
        -runPythonScript(path, args) Promise~string~
    }

    class WindowApi["window.api"] {
        +runPythonScript(script, args)
        +readFile(path)
        +writeFile(path, content)
        +showErrorDialog(title, content)
        +showConfirmDialog(title, message, detail)
        +listChapterClips(chapter)
        +checkChapterAudio(chapter)
        +checkXmlExists(stem)
        +listChapterFiles()
        +playSoundFile(path)
        +killProcess(match)
    }

    class electronMain {
        +ipcMain.handle(channel, handler)
    }

    class PythonScripts {
        +validate_config.py
        +chapter_to_xml.py
        +chapter_seq_xml.py
        +chapter_validate_xml.py
        +chapter_xml_to_audio.py
    }

    PythonBridgeService --> WindowApi : calls
    WindowApi --> electronMain : IPC
    electronMain --> PythonScripts : spawns
```

### Service Communication Flow

```mermaid
flowchart TB
    subgraph "Renderer Process"
        HOOK[Custom Hook
        useAudio / useChapter]
        
        PBS[PythonBridgeService
        Service Layer]
        
        note1[Checks window.api existence
        Falls back to mocks in browser]
    end

    subgraph "Main Process"
        IPC[Electron IPC
        ipcMain.handle]
        
        note2[Type-safe IPC handlers
        Error handling]
    end

    subgraph "Python Layer"
        PS1[validate_config.py]
        PS2[chapter_to_xml.py]
        PS3[chapter_xml_to_audio.py]
        PS4[chapter_validate_xml.py]
        PS5[chapter_seq_xml.py]
    end

    subgraph "File System"
        FS1[story-config.yml]
        FS2[*.md chapters]
        FS3[*.xml structure]
        FS4[*.wav audio]
    end

    HOOK -->|calls| PBS
    PBS -->|checks| note1
    
    PBS -->|IPC call| IPC
    IPC -->|spawn| PS1
    IPC -->|spawn| PS2
    IPC -->|spawn| PS3
    IPC -->|spawn| PS4
    IPC -->|spawn| PS5
    
    PS1 -->|reads| FS1
    PS2 -->|reads/writes| FS2
    PS2 -->|writes| FS3
    PS3 -->|reads| FS3
    PS3 -->|writes| FS4
    PS4 -->|validates| FS3
    PS5 -->|modifies| FS3
```

---

## TTS Service Architecture

### Overview

The TTS (Text-to-Speech) Service Architecture introduces a WebSocket-based remote TTS provider that enables distributed audio generation with GPU model caching for enhanced performance. This architecture extends the existing Factory pattern to support both local and remote TTS processing.

**Key Benefits:**
- **GPU Model Caching**: The remote service maintains loaded TTS models in GPU memory, eliminating reload overhead between requests
- **Reduced Memory Fragmentation**: Long-running service prevents repeated model loading/unloading cycles
- **Faster Repeated Operations**: Subsequent TTS requests benefit from cached model state
- **Graceful Fallback**: Automatic fallback to local TTS provider if remote service is unavailable

### TTS Service System Diagram

```mermaid
%%{init: {
  'theme': 'base',
  'themeVariables': {
    'primaryColor': '#ffffff',
    'primaryTextColor': '#000000',
    'primaryBorderColor': '#000000',
    'lineColor': '#000000',
    'background': '#ffffff'
  }
}}%%
flowchart TB
    subgraph "Electron Main Process"
        MAIN[main.ts<br/>IPC Handlers]
        SPAWNER[Process Spawner<br/>tts_service.py]
    end

    subgraph "TTS Service Process"
        SERVER[TTS Service Server<br/>WebSocket Listener]
        CACHE[GPU Model Cache<br/>Cached TTS Model]
        HANDLER[Request Handler<br/>Audio Generation]
    end

    subgraph "Python Scripts"
        CHAPTER[chapter_xml_to_audio.py]
        FACTORY[TTSProviderFactory]
    end

    subgraph "Client Side"
        REMOTE[RemoteTTSProvider<br/>WebSocket Client]
        FALLBACK[LocalTTSProvider<br/>Fallback]
    end

    subgraph "Output"
        WAV["*.wav<br/>Audio Clips"]
    end

    %% Startup Flow
    MAIN -->|spawns| SPAWNER
    SPAWNER -->|starts| SERVER
    SERVER -->|loads| CACHE

    %% Runtime Flow
    CHAPTER -->|uses --tts-service flag| FACTORY
    FACTORY -->|creates| REMOTE
    REMOTE -->|connects via WebSocket| SERVER
    SERVER -->|uses| CACHE
    SERVER -->|generates| HANDLER
    HANDLER -->|writes| WAV

    %% Fallback Flow
    REMOTE -.->|fallback on failure| FALLBACK
    FALLBACK -->|generates| WAV

    %% Styling
    classDef main fill:#fff3e0,stroke:#e65100
    classDef service fill:#e1f5fe,stroke:#01579b
    classDef client fill:#e8f5e9,stroke:#1b5e20
    classDef fallback fill:#ffebee,stroke:#c62828
    classDef output fill:#f3e5f5,stroke:#6a1b9a

    class MAIN,SPAWNER main
    class SERVER,CACHE,HANDLER service
    class CHAPTER,FACTORY,REMOTE client
    class FALLBACK fallback
    class WAV output
```

### TTS Service Startup Sequence

```mermaid
sequenceDiagram
    participant Main as Electron Main
    participant Spawner as Process Spawner
    participant Service as TTS Service
    participant GPU as GPU Memory
    participant Health as Health Check

    Note over Main,Health: TTS Service Startup Phase

    Main->>Spawner: spawn tts_service.py --port 8080
    activate Spawner
    Spawner->>Service: Start Python process
    activate Service
    Service->>GPU: Load TTS model to GPU
    GPU-->>Service: Model cached
    Service->>Service: Start WebSocket server
    Service-->>Spawner: Service ready (port 8080)
    deactivate Spawner
    Service-->>Main: Process started
    deactivate Service

    Main->>Health: Begin health polling
    loop Health Check (every 1s)
        Health->>Service: WebSocket connection test
        Service-->>Health: Connection OK
    end
    Health-->>Main: Service ready state confirmed

    Note over Main,Health: TTS Service Ready for Requests
```

### WebSocket Communication Protocol

The TTS Service uses a JSON-based WebSocket protocol for request/response communication:

**Request Format:**
```json
{
  "text": "Hello, this is a test.",
  "speaker": "narrator",
  "emotion": "neutral",
  "language": "English",
  "instruct": "Speak clearly and naturally",
  "output_format": "wav",
  "character_config": {
    "voice": "custom-voice-id",
    "pitch": 1.0
  }
}
```

**Response Flow:**
1. **Metadata Message** (JSON): Contains sample rate, duration, format info
2. **Binary Audio Chunks**: Streamed WAV audio data
3. **Completion Message** (JSON): `{"done": true}` or `{"error": "message"}`

**Error Handling:**
- Connection failures trigger exponential backoff retry (1s, 2s, 4s, 8s delays)
- After max retries (default: 4), falls back to LocalTTSProvider if configured
- Timeout for individual generation requests: 60 seconds

### TTS Service Shutdown Sequence

```mermaid
sequenceDiagram
    participant Main as Electron Main
    participant Client as RemoteTTSProvider
    participant Service as TTS Service
    participant GPU as GPU Memory

    Note over Main,GPU: Graceful Shutdown Phase

    Main->>Client: Request shutdown
    Client->>Client: Stop accepting new requests

    Client->>Service: Send shutdown signal
    Service->>Service: Complete pending generations
    Service->>GPU: Release GPU memory
    GPU-->>Service: Memory freed
    Service->>Service: Close WebSocket connections
    Service-->>Client: Shutdown confirmed

    Client->>Client: close() cleanup
    Main->>Service: Terminate process
    deactivate Service

    Note over Main,GPU: Fallback to LocalTTSProvider
    Main->>Client: Switch to fallback mode
    Client->>Client: Use LocalTTSProvider
```

### Integration Points

**1. Command-Line Interface (`chapter_xml_to_audio.py`):**
```python
# Using --tts-service flag for remote TTS
python chapter_xml_to_audio.py chapter_001.xml --tts-service ws://localhost:8080

# Without flag (local TTS)
python chapter_xml_to_audio.py chapter_001.xml
```

**2. TTSProviderFactory Integration:**
```python
from tts_factory import create_tts_provider

# Create remote provider with fallback
provider = create_tts_provider(
    service_url="ws://localhost:8080",  # Remote service
    voices_dir=Path("voices")           # For fallback
)

# Generate audio (uses remote, falls back on failure)
audio_segments, sample_rate = provider.generate(
    text="Hello world",
    speaker="narrator",
    emotion="neutral",
    language="English",
    output_path=Path("output.wav")
)
```

**3. Factory Pattern Implementation:**
```mermaid
classDiagram
    class TTSInterface {
        <<interface>>
        +generate(text, speaker, emotion, language, output_path)
        +supports_character(char_config)
        +close()
    }

    class LocalTTSProvider {
        +generate(...)
        -_load_model()
    }

    class RemoteTTSProvider {
        +generate(...)
        -_connect_with_retry()
        -_try_fallback()
        -_websocket
        -fallback_provider
    }

    class TTSProviderFactory {
        +create_provider(service_url, voices_dir)
        +_create_local_provider(voices_dir)
        +_create_remote_provider(url, voices_dir, enable_fallback)
    }

    TTSInterface <|-- LocalTTSProvider
    TTSInterface <|-- RemoteTTSProvider
    TTSProviderFactory ..> LocalTTSProvider : creates
    TTSProviderFactory ..> RemoteTTSProvider : creates
    RemoteTTSProvider o-- LocalTTSProvider : fallback
```

### GPU Model Caching Benefits

**Problem Without Caching:**
- Each TTS generation loads the model from disk to GPU
- Model loading: 10-30 seconds per request
- GPU memory fragmentation from repeated allocate/free cycles
- Poor user experience for chapter generation

**Solution With TTS Service:**
- Model loaded once at service startup
- Subsequent requests use cached model (sub-second response)
- GPU memory remains stable during service lifetime
- Supports batch processing of entire chapters efficiently

```mermaid
flowchart LR
    subgraph "Without Caching (Local TTS)"
        A1[Request 1] --> L1[Load Model<br/>~15s] --> G1[Generate<br/>~2s] --> U1[Unload<br/>~1s]
        A2[Request 2] --> L2[Load Model<br/>~15s] --> G2[Generate<br/>~2s] --> U2[Unload<br/>~1s]
        A3[Request 3] --> L3[Load Model<br/>~15s] --> G3[Generate<br/>~2s] --> U3[Unload<br/>~1s]
    end

    subgraph "With Caching (TTS Service)"
        S[Service startup<br/>Load Model ~15s]
        S --> C[Cached Model<br/>in GPU memory]
        B1[Request 1] --> C --> H1[Generate<br/>~2s]
        B2[Request 2] --> C --> H2[Generate<br/>~2s]
        B3[Request 3] --> C --> H3[Generate<br/>~2s]
    end

    style S fill:#c8e6c9
    style C fill:#c8e6c9
```

### Configuration Options

| Option | Default | Description |
|--------|---------|-------------|
| `service_url` | `None` | WebSocket URL (ws:// or wss://) for remote service |
| `max_retries` | 4 | Maximum connection retry attempts with exponential backoff |
| `timeout` | 30s | Connection timeout in seconds |
| `enable_fallback` | `True` | Enable automatic fallback to local TTS on failure |
| `voices_dir` | `./voices` | Directory for voice reference samples (used by fallback) |

### Security Considerations

- **WebSocket Protocol**: Supports both `ws://` (unencrypted) and `wss://` (TLS encrypted)
- **Local-Only by Default**: TTS service binds to localhost by default for security
- **No Authentication**: Current implementation assumes trusted local network
- **Resource Limits**: Service should implement request rate limiting for production use

---

## State Management

### useChapter Hook Structure

```mermaid
%%{init: {
  'theme': 'base',
  'themeVariables': {
    'primaryColor': '#ffffff',
    'primaryTextColor': '#000000',
    'primaryBorderColor': '#000000',
    'lineColor': '#000000',
    'background': '#ffffff'
  }
}}%%
flowchart TB
    subgraph "useChapter State"
        direction TB
        
        STATE1["config: StoryConfig | null"]
        STATE2["chapter: Chapter | null"]
        STATE3[chapterList: string-array]
        STATE4[currentChapterFile: string]
        STATE5[selectedCharacterFilter: string]
        STATE6[availableClips: string-array]
        STATE7[hasChapterAudio: boolean]
        STATE8[isGeneratingStructure: boolean]
        STATE9[generateAttempt: number]
        
        REF1[xmlContentRef: MutableRefObject]
        REF2[lastSavedXmlRef: MutableRefObject]
        REF3[hasUnsavedChangesRef: MutableRefObject]
    end

    subgraph "useChapter Actions"
        ACT1["loadChapter(filePath)"]
        ACT2["handleChapterSelect(file)"]
        ACT3["handleUpdateDialog(id, dialog)"]
        ACT4["runXmlGenerationPipeline(stem, attempt)"]
        ACT5["setLastSavedXmlValue(value)"]
        ACT6["setHasUnsavedChangesValue(value)"]
    end

    subgraph "Usage"
        APP[App.tsx]
    end

    STATE1 --> APP
    STATE2 --> APP
    STATE3 --> APP
    REF1 -.->|sync access| APP
    REF2 -.->|sync access| APP
    REF3 -.->|sync access| APP
    
    APP -->|calls| ACT1
    APP -->|calls| ACT2
    APP -->|calls| ACT3
    APP -->|calls| ACT4
    
    ACT4 -->|updates| STATE8
    ACT3 -->|updates| STATE2
    ACT1 -->|updates| STATE2
    ACT1 -.->|updates| REF1
    ACT1 -.->|updates| REF2  
    ACT1 -.->|updates| REF3

    %% Styling
    classDef state fill:#e3f2fd,stroke:#1565c0
    classDef action fill:#e8f5e9,stroke:#2e7d32
    classDef ref fill:#fff3e0,stroke:#ef6c00
    classDef usage fill:#f3e5f5,stroke:#6a1b9a
    
    class STATE1,STATE2,STATE3,STATE4,STATE5,STATE6,STATE7,STATE8,STATE9 state
    class REF1,REF2,REF3 ref
    class ACT1,ACT2,ACT3,ACT4,ACT5,ACT6 action
    class APP usage
```

### Ref Pattern for Synchronous Access

```mermaid
sequenceDiagram
    participant User
    participant Component as React Component
    participant Handler as Event Handler
    participant Ref as useRef
    participant State as useState

    Note over Component,State: Problem: stale closures in async handlers

    User->>Component: Type/Click
    Component->>State: setState(newValue)
    State-->>Component: state updated
    
    Note right of Ref: Solution: useRef for sync access

    Ref->>Ref: ref.current = newValue
    
    User->>Component: Click Save (async)
    Component->>Handler: handleSave()
    
    Note over Handler: Inside async handler
    Handler->>Ref: check ref.current
    Ref-->>Handler: latest value (not stale)
    
    alt Has Changes
        Handler->>State: Perform save
        State-->>Handler: success
        Handler->>Ref: Update ref.current
        Handler->>State: Reset state
    else No Changes
        Handler->>Handler: Skip save
    end
```

---

## File Structure

```
src/ui/src/
├── App.tsx                    # Root orchestrator component
├── App.css                    # Component styles
├── main.tsx                   # React entry point
├── index.css                  # Global styles
├──
├── components/                # UI components
│   ├── TopBar.tsx            # Navigation bar
│   └── DialogBar.tsx         # Dialog editor
│
├── hooks/                    # Custom React hooks
│   ├── index.ts              # Barrel exports
│   ├── useChapter.ts         # Chapter state (17 states)
│   ├── useAudio.ts           # Audio state (2 states)
│   └── useMarkdown.ts        # Editor state (5 states)
│
├── services/                 # External communication
│   ├── pythonBridge.ts       # Electron IPC bridge
│   └── chapterService.ts     # XML generation (pure)
│
├── models/                   # Type definitions
│   └── types.ts              # StoryConfig, Chapter, DialogElement
│
├── utils/                    # Helper utilities
│   └── colors.ts             # Character color mapping
│
└── __tests__/                # Test suite
    ├── setup.ts              # Test configuration
    ├── App.test.tsx          # Component tests
    ├── useChapter.test.ts    # Hook tests
    ├── useAudio.test.ts      # Hook tests
    ├── chapterService.test.ts # Service tests
    └── __snapshots__/        # Jest snapshots
```

### File Size Breakdown

```mermaid
pie
    title Code Distribution by File Type
    "Components (.tsx)" : 900
    "Hooks (.ts)" : 800
    "Services (.ts)" : 500
    "Models (.ts)" : 50
    "Utils (.ts)" : 30
    "Tests (.test.ts)" : 1100
```

---

## Key Design Decisions

### 1. Custom Hooks Over State Management Library

**Decision:** Use React's built-in hooks (useState, useRef, useCallback) instead of Redux/Zustand.

**Rationale:**
- Application state is complex but localized
- useChapter hook encapsulates 17 related state items
- useRef pattern solves stale closure issues
- No need for global state management

**Trade-off:** Less boilerplate, but requires careful ref management.

### 2. Service Layer with Mock Fallbacks

**Decision:** PythonBridgeService checks `window.api` and provides browser-compatible mocks.

**Rationale:**
- UI can be developed/tested without Electron running
- Easier debugging in browser DevTools
- Graceful degradation for development

**Trade-off:** Some mocks are simplified (e.g., confirm dialog).

### 3. Ref Pattern for Unsaved Changes

**Decision:** Use useRef for synchronous access to change tracking state.

**Rationale:**
- Event handlers need current state synchronously
- Async handlers would capture stale closures
- Refs bypass React's render cycle

**Code Example:**
```typescript
const hasUnsavedChangesRef = useRef(false);
hasUnsavedChangesRef.current = xmlContent !== lastSavedXml;
// Handler can read latest value without re-render
```

### 4. Pipeline Pattern for XML Generation

**Decision:** Chain 3 Python scripts with retry logic.

**Pipeline:**
1. `chapter_to_xml.py` - Markdown → XML
2. `chapter_seq_xml.py` - Sequence XML IDs
3. `chapter_validate_xml.py` - XSD validation

**Rationale:**
- Each script does one thing well
- Retry logic handles transient failures
- Clear separation of concerns

### 5. Pure Function for XML Serialization

**Decision:** `generateXMLFromChapter` is a pure utility function.

**Rationale:**
- Deterministic output for input
- Easy to test with snapshot matching
- Reusable across components

---

## Testing Architecture

### Test Pyramid

```mermaid
%%{init: {
  'theme': 'base',
  'themeVariables': {
    'primaryColor': '#ffffff',
    'primaryTextColor': '#000000',
    'primaryBorderColor': '#000000',
    'lineColor': '#000000',
    'background': '#ffffff'
  }
}}%%
flowchart TB
    subgraph "Test Coverage (72 Tests Total)"
        E2E["E2E Tests
        0 tests
        (Not implemented)"]
        
        INT["Integration Tests
        App.test.tsx
        11 tests"]
        
        UNIT["Unit Tests
        useChapter: 18
        useAudio: 21
        chapterService: 22
        61 tests"]
    end

    subgraph "Test Tools"
        VITEST[vitest]
        RTL[@testing-library/react]
        MOCK[vi.mock]
    end

    E2E -->|calls| INT
    INT -->|uses| UNIT
    
    VITEST -->|runs| E2E
    VITEST -->|runs| INT
    VITEST -->|runs| UNIT
    
    RTL -->|renders| INT
    MOCK -->|stubs| UNIT

    %% Styling
    classDef e2e fill:#ffcdd2,stroke:#c62828
    classDef int fill:#fff9c4,stroke:#f9a825
    classDef unit fill:#c8e6c9,stroke:#2e7d32
    classDef tools fill:#e1f5fe,stroke:#0277bd
    
    class E2E e2e
    class INT int
    class UNIT unit
    class VITEST,RTL,MOCK tools
```

### Mock Strategy

```mermaid
flowchart TB
    subgraph "Mock Layers"
        A[window.api Mock
        IPC Methods]
        
        B[PythonBridgeService Mock
        Service Methods]
        
        C[Component Mock
        TopBar / DialogBar]
        
        D[Hook Mock
        useChapter / useAudio]
    end

    subgraph "Test Types"
        T1[chapterService.test.ts
        No mocks - pure functions]
        
        T2[useChapter.test.ts
        Mocks window.api
        Mocks PythonBridgeService]
        
        T3[useAudio.test.ts
        Mocks window.api
        Tests async flows]
        
        T4[App.test.tsx
        Mocks components
        Mocks hooks]
    end

    T1 -.->|no mocks needed| T1
    
    T2 -->|mocks| A
    T2 -->|mocks| B
    
    T3 -->|mocks| A
    
    T4 -->|mocks| C
    T4 -->|mocks| D
```

---

## Summary

### Architecture Strengths

1. **Clear Separation:** Hooks, services, and components have distinct responsibilities
2. **Testable:** 72 tests with 100% pass rate
3. **Type-Safe:** Full TypeScript coverage
4. **Maintainable:** 55% reduction in App.tsx complexity
5. **Flexible:** Mock fallbacks enable browser-based development

### Areas for Future Improvement

1. **State Persistence:** Auto-save to localStorage
2. **Error Boundaries:** Add React error boundaries
3. **Loading States:** More granular loading indicators
4. **Optimistic Updates:** Faster UI response
5. **E2E Tests:** Add Playwright/Cypress tests

---

**End of Architecture Overview**

*Generated: February 26, 2026*  
*Tool: Mermaid.js v10+ compatible diagrams*
