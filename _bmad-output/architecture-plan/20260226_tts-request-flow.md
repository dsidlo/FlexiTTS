# TTS Service UI Integration - TTS Request Flow

**Date**: 2026-02-26  
**Status**: Exploratory Architecture Study

## TTS Request Sequence

```mermaid
sequenceDiagram
    autonumber
    participant User as User
    participant UI as React UI
    participant Bridge as PythonBridge
    participant IPC as Electron IPC
    participant MP as Main Process
    participant CH as chapter_xml_to_audio.py
    participant Factory as TTSFactory
    participant Remote as RemoteTTSProvider
    participant WS as WebSocket
    participant TS as TTS Service
    participant GPU as GPU Memory
    participant Audio as Audio Player

    %% Phase 1: User Initiates Request
    rect rgb(230, 245, 255)
    Note over User,Audio: Phase 1: User Action
    User->>UI: Click "Generate Audio"
    UI->>UI: Validate chapter.xml exists
    Note over UI: Chapter: 01-Hendrix.xml
    Note over UI: Section: 1, DialogSeq: 3
    end

    %% Phase 2: UI Bridge Request
    rect rgb(255, 245, 230)
    Note over User,Audio: Phase 2: UI Bridge
    UI->>+Bridge: playAudio("01-Hendrix", "1", "3")
    Bridge->>Bridge: Log: "[playAudio] Starting generation..."
    Bridge->>IPC: window.api.runPythonScript()
    
    %% Arguments for chapter_xml_to_audio.py
    Note right of Bridge: Args: [<br/>
      "Story-Entanglement/story-xml/01-Hendrix.xml",<br/>
      "--section", "1",<br/>
      "--dlgseq", "3",<br/>
      "--tts-service", "ws://localhost:8080"
    ]
    end

    %% Phase 3: Main Process Spawn
    rect rgb(230, 255, 230)
    Note over User,Audio: Phase 3: Spawn Chapter Script
    IPC->>+MP: ipcMain.handle('run-python-script')
    MP->>MP: Determine projectRoot
    MP->>MP: Generate procId: "python-chapter_xml_to_audio-..."
    MP->>MP: Store in activeProcesses Map
    
    MP->>+CH: spawn('uv run python chapter_xml_to_audio.py', args)
    CH->>CH: Parse CLI arguments
    CH->>CH: Load story-config.yml
    CH->>CH: Parse XML: 01-Hendrix.xml
    CH->>CH: Extract section 1, dlgseq 3
    Note over CH: Found: "Alice: Hello there!"<br/>Emotion: happy<br/>Character: Alice
    end

    %% Phase 4: Factory Creates Provider
    rect rgb(243, 229, 245)
    Note over User,Audio: Phase 4: TTS Provider Creation
    CH->>+Factory: TTSProviderFactory.create_provider(
      service_url="ws://localhost:8080"
    )
    
    Factory->>Factory: Check service_url is not None
    Factory->>Factory: _create_remote_provider()
    Factory->>Factory: Create fallback LocalTTSProvider
    Factory->>+Remote: RemoteTTSProvider(
      service_url="ws://localhost:8080",
      fallback_provider=local,
      max_retries=4,
      timeout=30.0
    )
    Remote->>Remote: Validate URL format (ws://)
    Remote-->>-Factory: provider instance
    Factory-->>-CH: RemoteTTSProvider
    end

    %% Phase 5: WebSocket Connection
    rect rgb(255, 235, 238)
    Note over User,Audio: Phase 5: WebSocket Connection
    CH->>+Remote: generate(
      text="Hello there!",
      speaker="Alice",
      emotion="happy",
      language="English",
      output_path=Path("/tmp/chapter_001_001_003_alice.wav")
    )
    
    Remote->>+Remote: _connect_with_retry()
    loop Retry with Exponential Backoff (max 4)
        Remote->>WS: websockets.connect("ws://localhost:8080")
        WS->>+TS: TCP Connection
        TS->>TS: Accept connection
        TS-->>WS: WebSocket handshake
        WS-->>-Remote: Connection established
    end
    Remote-->>-Remote: Return websocket
    end

    %% Phase 6: TTS Generation
    rect rgb(232, 245, 233)
    Note over User,Audio: Phase 6: TTS Generation
    Remote->>WS: Send JSON request
    Note right of Remote: {<br/>
      "text": "Hello there!",<br/>
      "speaker": "Alice",<br/>
      "emotion": "happy",<br/>
      "language": "English",<br/>
      "instruct": "",<br/>
      "output_format": "wav",<br/>
      "character_config": {...}<br/>
    }
    
    WS->>+TS: Receive request
    TS->>TS: Parse JSON
    TS->>TS: Validate request fields
    TS->>+GPU: Generate audio with Qwen3-TTS
    GPU->>GPU: Run inference
    GPU-->>-GPU: Audio tensor output
    Note over GPU: Model warmed up, fast inference
    
    TS->>TS: Encode to WAV format
    TS->>WS: Send metadata JSON: {"done": true}
    TS->>WS: Send binary audio data
    WS-->>-GPU: 
    
    WS-->>-Remote: Receive response
    end

    %% Phase 7: Save Audio
    rect rgb(255, 243, 224)
    Note over User,Audio: Phase 7: Save & Process
    Remote->>Remote: Write binary to output_path
    Remote->>Remote: Read with soundfile
    Remote-->>-CH: return ([audio_array], sr)
    
    CH->>CH: Apply SoX effects (if configured)
    Note over CH: Effects: reverb, normalize
    CH->>CH: Save final to clips directory
    Note over CH: Story-Entanglement/story-audio/clips/01-Hendrix/chapter_001_001_003_alice.wav
    CH->>CH: stdout: "Generated chapter_001_001_003_alice.wav"
    CH-->>-MP: Process exit code 0
    end

    %% Phase 8: Result Parsing
    rect rgb(227, 242, 253)
    Note over User,Audio: Phase 8: Result Processing
    MP->>MP: Remove from activeProcesses
    MP->>MP: Parse stdout for filename
    Note over MP: Regex match: "Generated (.*\.wav)"
    MP-->>-IPC: Return stdout
    IPC-->>-Bridge: Response: "Generated chapter_001_001_003_alice.wav"
    
    Bridge->>Bridge: Parse filename from output
    Bridge->>Bridge: Construct full path
    Bridge-->>-UI: Audio generation complete
    end

    %% Phase 9: Audio Playback
    rect rgb(243, 229, 245)
    Note over User,Audio: Phase 9: Audio Playback
    UI->>+Audio: playAudio(generatedPath)
    Audio->>IPC: window.api.playSoundFile(path)
    IPC->>+MP: ipcMain.handle('play-sound-file')
    MP->>MP: Platform-specific player
    alt macOS
        MP->>MP: spawn('afplay', [path])
    else Windows
        MP->>MP: spawn('powershell', [...])
    else Linux
        MP->>MP: spawn('aplay', [path])
    end
    MP-->>-IPC: Playback started
    IPC-->>-Audio: Playing...
    Audio-->>-UI: Playback complete
    UI->>User: Visual feedback: Audio played
    end

    %% Error Path
    rect rgb(255, 235, 238)
    Note over User,Audio: Error Path: Service Unavailable → Fallback
    alt WebSocket Connection Failed
        Remote-xRemote: Connection refused
        Remote->>Remote: retry attempts exhausted
        alt Fallback Enabled
            Remote->>Factory: fallback_provider.enable()
            Remote->>+Factory: fallback_provider.generate(...)
            Factory->>LocalTTS: LocalTTSProvider.generate()
            LocalTTS->>GPU: Load model (if not cached)
            GPU-->>LocalTTS: Audio generated
            LocalTTS-->>-Remote: ([audio], sr)
            Remote-->>CH: Continue normally
        else Fallback Disabled
            Remote-->>-CH: Throw TTSConnectionError
        end
    end
    end
```

## Flow Explanation

### Happy Path Summary
1. **User clicks** "Generate Audio" on a dialog line
2. **UI calls** `PythonBridge.playAudio()` with chapter/section/dlgseq
3. **Main Process spawns** `chapter_xml_to_audio.py` with `--tts-service` flag
4. **Script parses** XML, extracts text and emotion
5. **Factory creates** `RemoteTTSProvider` pointing to WebSocket service
6. **Remote Provider connects** to WebSocket with retry logic
7. **TTS Service generates** audio using cached GPU model
8. **Audio saved** to clips directory
9. **Result parsed** and returned to UI
10. **Audio played** via platform-specific player

### Key Integration Points

#### Point A: --tts-service Flag
```python
# In chapter_xml_to_audio.py
parser.add_argument("--tts-service", type=str, 
                    help="WebSocket URL for TTS service")
# ...
if args.tts_service:
    provider = TTSProviderFactory.create_provider(
        service_url=args.tts_service
    )
```

#### Point B: Provider Selection
```python
# In tts_factory.py
def create_provider(self, service_url=None, ...):
    if service_url is None:
        return self._create_local_provider(...)
    return self._create_remote_provider(
        service_url, ...
    )
```

#### Point C: WebSocket Communication
```python
# In RemoteTTSProvider._generate_remote()
await websocket.send(json.dumps(request))
message = await websocket.recv()
if isinstance(message, str):  # JSON
    msg_data = json.loads(message)
elif isinstance(message, bytes):  # Binary audio
    audio_data.extend(message)
```

## Error Handling Flows

### Error 1: Service Not Running
```
User → UI → Bridge → Main Process (spawn) → Script
                                         ↓
                              RemoteTTSProvider
                                         ↓
                              Connection refused (ECONNREFUSED)
                                         ↓
                              Fallback to LocalTTSProvider
                                         ↓
                              Continue with local generation
```

### Error 2: WebSocket Timeout
```
RemoteTTSProvider → WebSocket.connect()
         ↓
    Timeout after 30s
         ↓
    Retry with backoff (2^attempt seconds)
         ↓
    After 4 retries → TTSConnectionError
         ↓
    If fallback → LocalTTSProvider
    Else → Error dialog
```

### Error 3: GPU Out of Memory
```
TTS Service → GPU inference
         ↓
    CUDA out of memory
         ↓
    Exception caught
         ↓
    JSON error response → WebSocket
         ↓
    RemoteTTSProvider receives error
         ↓
    TTSGenerationError thrown
```

## Performance Considerations

### Cold Path (First Request)
- Service startup: +2-5s
- WebSocket connection: +50ms
- Model already loaded in service
- **Total overhead**: ~2.5s

### Warm Path (Subsequent Requests)
- WebSocket reuse: Connection pooled
- Model cached: No reload needed
- **Total overhead**: ~50ms

### Fallback Path (Service Unavailable)
- Connection failure: +2s (4 retries)
- Local model load: +5s (first time)
- **Total overhead**: ~7s

## Data Flow Sizes

| Step | Data Type | Size | Direction |
|------|-----------|------|-------------|
| IPC Request | JSON | ~200 bytes | UI → Main |
| Script Args | Strings | ~100 bytes | Main → Script |
| WebSocket Request | JSON | ~500 bytes | Script → Service |
| WebSocket Response | Binary | ~100KB | Service → Script |
| IPC Result | String | ~100 bytes | Main → UI |

## References

- `src/ui/src/services/pythonBridge.ts` - Bridge.playAudio()
- `src/ui/electron/main.ts` - IPC handlers
- `src/scripts/chapter_xml_to_audio.py` - Main TTS script
- `src/scripts/tts_factory.py` - Provider factory
- `src/scripts/tts_service.py` - RemoteTTSProvider
