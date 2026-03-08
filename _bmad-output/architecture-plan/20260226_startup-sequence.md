# TTS Service UI Integration - Startup Sequence

**Date**: 2026-02-26  
**Status**: Exploratory Architecture Study

## Startup Sequence Diagram

```mermaid
sequenceDiagram
    autonumber
    participant UI as React UI
    participant IPC as Electron IPC
    participant MP as Main Process
    participant TS as TTS Service
    participant GPU as GPU Memory
    participant Bridge as pythonBridge.ts

    %% Phase 1: App Launch
    rect rgb(230, 245, 255)
    Note over UI,GPU: Phase 1: Application Launch
    MP->>MP: app.whenReady()
    MP->>MP: createWindow()
    MP->>UI: Load Renderer Process
    end

    %% Phase 2: Service Detection
    rect rgb(255, 245, 230)
    Note over UI,GPU: Phase 2: TTS Service Detection
    UI->>+Bridge: initialize()
    Bridge->>IPC: window.api.getServiceStatus()
    IPC->>+MP: IPC: get-tts-service-status
    MP->>MP: Check activeProcesses Map
    alt Service Not Running
        MP-->>-IPC: { running: false, port: null }
        IPC-->>-Bridge: { running: false, port: null }
        Bridge-->>UI: Service not running
    else Service Already Running
        MP-->>-IPC: { running: true, port: 8080 }
        IPC-->>-Bridge: { running: true, port: 8080 }
        Bridge-->>UI: Service ready
        Note over UI: Skip to Phase 5
    end
    end

    %% Phase 3: Service Startup
    rect rgb(230, 255, 230)
    Note over UI,GPU: Phase 3: TTS Service Startup
    UI->>+Bridge: startTTSService()
    Bridge->>IPC: window.api.startTTSService()
    IPC->>+MP: IPC: start-tts-service
    
    MP->>MP: Allocate available port
    MP->>+TS: spawn('uv run python tts_service.py --port 8080')
    TS->>TS: Parse CLI args
    TS->>TS: Load story-config.yml
    TS->>TS: Initialize TTS model
    TS->>+GPU: Load model weights
    GPU-->>-TS: Model loaded (~2-5s)
    TS->>TS: Start WebSocket server
    TS-->>-MP: Service ready (stdout: "Listening on ws://localhost:8080")
    MP->>MP: Store in activeProcesses['tts-service']
    MP-->>-IPC: { success: true, port: 8080 }
    IPC-->>-Bridge: { success: true, port: 8080 }
    Bridge-->>-UI: Service started on port 8080
    end

    %% Phase 4: Health Check
    rect rgb(255, 235, 238)
    Note over UI,GPU: Phase 4: Health Check / Readiness Probe
    Bridge->>+Bridge: pollServiceHealth(port)
    loop Until ready or timeout (30s)
        Bridge->>IPC: window.api.checkServiceHealth(port)
        IPC->>+MP: HTTP/TCP check ws://localhost:8080/health
        MP->>TS: Connect attempt
        TS-->>MP: HTTP 200 OK { status: "ready", model: "loaded" }
        MP-->>-IPC: { healthy: true }
        IPC-->>Bridge: { healthy: true }
    end
    Bridge-->>-UI: Service healthy, ready for TTS
    end

    %% Phase 5: UI Initialization Complete
    rect rgb(243, 229, 245)
    Note over UI,GPU: Phase 5: UI Ready
    UI->>UI: Enable audio controls
    UI->>UI: Display "TTS Service Ready" status
    Note over UI,GPU: Application fully initialized
    end

    %% Error Path
    rect rgb(255, 235, 238)
    Note over UI,GPU: Error Path: Service Startup Failure
    alt Startup Timeout or Error
        TS-->>MP: Error or timeout
        MP->>MP: Cleanup process
        MP-->>IPC: { success: false, error: "..." }
        IPC-->>Bridge: { success: false, error: "..." }
        Bridge-->>UI: Service startup failed
        UI->>UI: Show error dialog
        Note over UI: Fallback to local TTS or disable
    end
    end
```

## Sequence Explanation

### Phase 1: Application Launch (0-1s)
- Electron main process starts
- Renderer window created
- React app begins initialization

### Phase 2: Service Detection (1-2s)
- UI checks if TTS service is already running
- Uses `pythonBridge.ts` to query service status
- Main process checks `activeProcesses` Map

### Phase 3: TTS Service Startup (2-10s)
- If not running, spawn `tts_service.py` subprocess
- Service loads Python environment, config, and TTS model
- **Critical**: GPU model loading takes 2-5 seconds
- WebSocket server starts listening
- Process tracked in `activeProcesses`

### Phase 4: Health Check (10-12s)
- Poll service health endpoint until ready
- Timeout after 30 seconds
- Retry with exponential backoff

### Phase 5: UI Ready (12s+)
- UI enables audio controls
- Status indicator shows "TTS Service Ready"
- Application fully functional

## Startup Failure Scenarios

### Scenario 1: Port Already in Use
```
1. Main process allocates port (e.g., 8080)
2. Spawn service → Error: Address in use
3. Try next available port (8081, 8082...)
4. Store actual port in activeProcesses
```

### Scenario 2: GPU Memory Exhausted
```
1. Service starts loading model
2. CUDA out of memory error
3. Service exits with error code
4. Main process detects failure
5. UI shows error: "GPU memory insufficient"
6. Fallback to CPU mode or disable TTS
```

### Scenario 3: Model Load Timeout
```
1. Service starts but model loading slow
2. Health check times out (30s)
3. Main process kills service
4. Retry up to 3 times
5. After 3 failures → disable TTS
```

## Implementation Tasks (for startup-sequence.md)

### Task 1: Port Allocation
**Description**: Main process finds available port before spawning service  
**Complexity**: Medium  
**Location**: `src/ui/electron/main.ts`

```typescript
// Pseudo-code
function findAvailablePort(startPort: number = 8080): Promise<number> {
    // Try ports until one is available
    // Return port number
}
```

### Task 2: Service Spawn
**Description**: Spawn tts_service.py with allocated port  
**Complexity**: Medium  
**Location**: `src/ui/electron/main.ts`

```typescript
// Spawn with port argument
spawn('uv', ['run', 'python', 'tts_service.py', '--port', port])
```

### Task 3: Health Check Endpoint
**Description**: Add HTTP health endpoint to tts_service.py  
**Complexity**: Low  
**Location**: `src/scripts/tts_service.py`

```python
# Add route
@app.get("/health")
async def health():
    return {"status": "ready" if model_loaded else "loading"}
```

### Task 4: Readiness Probe
**Description**: UI polls health until service ready  
**Complexity**: Medium  
**Location**: `src/ui/src/services/pythonBridge.ts`

```typescript
async function waitForService(port: number, timeout: number = 30000) {
    // Poll /health endpoint with exponential backoff
    // Throw if timeout exceeded
}
```

## Timing Considerations

| Phase | Expected Time | Worst Case |
|-------|---------------|------------|
| App Launch | < 1s | 2s |
| Service Spawn | 1-2s | 5s |
| Model Load | 2-5s | 15s (cold start) |
| Health Check | 0.5s | 30s timeout |
| **Total** | **3.5-8s** | **52s** |

## References

- `src/ui/electron/main.ts` - IPC handlers, process spawn
- `src/scripts/tts_service.py` - WebSocket service
- `src/ui/src/services/pythonBridge.ts` - UI bridge
