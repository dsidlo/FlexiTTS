# TTS Service UI Integration - Implementation Tasks

**Date**: 2026-02-26  
**Status**: Exploratory Architecture Study  
**Estimated Total Effort**: 3-5 days

## Task List

### Phase 1: Main Process IPC Additions
**Complexity**: Medium | **Estimated Time**: 1 day

#### Task 1.1: Add TTS Service IPC Handlers
**File**: `src/ui/electron/main.ts`  
**Complexity**: Medium  
**Description**: Implement IPC handlers for TTS service lifecycle management

```typescript
// New IPC handlers to add
ipcMain.handle('start-tts-service', async () => { ... });
ipcMain.handle('stop-tts-service', async () => { ... });
ipcMain.handle('get-tts-service-status', async () => { ... });
ipcMain.handle('check-tts-service-health', async (port) => { ... });
```

**Acceptance Criteria**:
- [ ] Handler spawns tts_service.py subprocess
- [ ] Handler manages process in activeProcesses Map
- [ ] Handler returns service status and port
- [ ] Error handling for spawn failures

---

#### Task 1.2: Implement Port Allocation
**File**: `src/ui/electron/main.ts`  
**Complexity**: Low  
**Description**: Find available TCP port for TTS service

```typescript
function findAvailablePort(startPort: number): Promise<number>;
```

**Acceptance Criteria**:
- [ ] Scan ports starting from 8080
- [ ] Return first available port
- [ ] Handle port conflicts gracefully

---

#### Task 1.3: Service Health Check Integration
**File**: `src/ui/electron/main.ts`  
**Complexity**: Low  
**Description**: TCP/WebSocket connectivity check to service

```typescript
async function checkServiceHealth(port: number): Promise<boolean>;
```

**Acceptance Criteria**:
- [ ] Attempt WebSocket connection
- [ ] Return true if connection succeeds
- [ ] Return false on timeout (2s)

---

#### Task 1.4: Update Process Cleanup
**File**: `src/ui/electron/main.ts`  
**Complexity**: Medium  
**Description**: Graceful shutdown of TTS service on app quit

```typescript
app.on('before-quit', async () => {
    // Send SIGTERM to tts-service process
    // Wait 5 seconds for graceful exit
    // Send SIGKILL if still running
});
```

**Acceptance Criteria**:
- [ ] Hook into before-quit event
- [ ] Send SIGTERM signal
- [ ] Implement 5-second timeout
- [ ] Force kill (SIGKILL) on timeout

---

### Phase 2: Preload Script Updates
**Complexity**: Low | **Estimated Time**: 0.5 day

#### Task 2.1: Expose New IPC Channels
**File**: `src/ui/electron/preload.ts`  
**Complexity**: Low  
**Description**: Add service control methods to preload script

```typescript
contextBridge.exposeInMainWorld('api', {
    // Existing methods...
    startTTSService: () => ipcRenderer.invoke('start-tts-service'),
    stopTTSService: () => ipcRenderer.invoke('stop-tts-service'),
    getTTSServiceStatus: () => ipcRenderer.invoke('get-tts-service-status'),
});
```

**Acceptance Criteria**:
- [ ] All service IPC methods exposed
- [ ] TypeScript types updated
- [ ] Backward compatible

---

### Phase 3: Python Bridge Updates
**Complexity**: Medium | **Estimated Time**: 1 day

#### Task 3.1: Add Service Control Methods
**File**: `src/ui/src/services/pythonBridge.ts`  
**Complexity**: Medium  
**Description**: UI-facing methods for TTS service management

```typescript
export const PythonBridgeService = {
    // Existing methods...
    
    startTTSService: async (): Promise<{ success: boolean; port?: number }> => {
        // Call IPC handler
    },
    
    stopTTSService: async (): Promise<void> => {
        // Call IPC handler
    },
    
    waitForService: async (timeout?: number): Promise<void> => {
        // Poll health endpoint until ready
        // Exponential backoff
    },
};
```

**Acceptance Criteria**:
- [ ] startTTSService method works
- [ ] waitForService with exponential backoff
- [ ] Proper error handling

---

#### Task 3.2: Modify playAudio for Service Integration
**File**: `src/ui/src/services/pythonBridge.ts`  
**Complexity**: Medium  
**Description**: Ensure service running before TTS requests

```typescript
playAudio: async (chapterName, sectionNum, dlgseqNum, ...) => {
    // Check if service is running
    // Start service if not running
    // Wait for service ready
    // Pass --tts-service flag to chapter_xml_to_audio.py
}
```

**Acceptance Criteria**:
- [ ] Check service status before request
- [ ] Start service on-demand
- [ ] Pass --tts-service URL to script

---

### Phase 4: TTS Service Python Updates
**Complexity**: Medium | **Estimated Time**: 1 day

#### Task 4.1: Add Health Check Endpoint
**File**: `src/scripts/tts_service.py`  
**Complexity**: Low  
**Description**: HTTP/WS health endpoint for readiness probe

```python
@app.get("/health")
async def health_check():
    return {
        "status": "ready" if model_loaded else "loading",
        "model": "qwen3-tts",
        "queue_size": request_queue.qsize()
    }
```

**Acceptance Criteria**:
- [ ] HTTP GET /health returns JSON
- [ ] Status reflects model load state
- [ ] Returns 200 OK when ready

---

#### Task 4.2: Implement Graceful Shutdown
**File**: `src/scripts/tts_service.py`  
**Complexity**: Medium  
**Description**: SIGTERM handler for graceful shutdown

```python
import signal
import sys

shutdown_requested = False

def handle_sigterm(signum, frame):
    global shutdown_requested
    shutdown_requested = True
    # Complete current request, then exit

signal.signal(signal.SIGTERM, handle_sigterm)

# In main loop
if shutdown_requested and not processing_request:
    cleanup_and_exit()
```

**Acceptance Criteria**:
- [ ] SIGTERM handler registered
- [ ] Finish current request
- [ ] Close WebSocket connections
- [ ] Release GPU memory
- [ ] Exit with code 0

---

#### Task 4.3: Add Port Configuration
**File**: `src/scripts/tts_service.py`  
**Complexity**: Low  
**Description**: Accept --port CLI argument

```python
parser.add_argument("--port", type=int, default=8080)
```

**Acceptance Criteria**:
- [ ] Parse --port argument
- [ ] Bind server to specified port
- [ ] Validate port range

---

### Phase 5: Chapter Script Integration
**Complexity**: Medium | **Estimated Time**: 0.5 day

#### Task 5.1: Add --tts-service Flag
**File**: `src/scripts/chapter_xml_to_audio.py`  
**Complexity**: Low  
**Description**: CLI argument to specify TTS service URL

```python
parser.add_argument(
    "--tts-service", 
    type=str,
    help="WebSocket URL for remote TTS service (e.g., ws://localhost:8080)"
)
```

**Acceptance Criteria**:
- [ ] Parse --tts-service argument
- [ ] Pass URL to TTS provider factory

---

#### Task 5.2: Integrate TTS Factory
**File**: `src/scripts/chapter_xml_to_audio.py`  
**Complexity**: Medium  
**Description**: Use factory to create appropriate provider

```python
from tts_factory import TTSProviderFactory

if args.tts_service:
    provider = TTSProviderFactory.from_command_line(
        service_url=args.tts_service
    )
else:
    provider = TTSProviderFactory.from_command_line()  # Local fallback
```

**Acceptance Criteria**:
- [ ] Create RemoteTTSProvider when service URL provided
- [ ] Fallback to LocalTTSProvider if URL not provided
- [ ] Error handling for connection failures

---

### Phase 6: UI Integration
**Complexity**: Low | **Estimated Time**: 0.5 day

#### Task 6.1: Add Service Status Indicator
**File**: `src/ui/src/App.tsx` (or appropriate component)  
**Complexity**: Low  
**Description**: Visual indicator for TTS service status

```typescript
// Component state
const [ttsServiceStatus, setTtsServiceStatus] = useState<
  'stopped' | 'starting' | 'ready' | 'error'
>('stopped');

// Display
<StatusIndicator status={ttsServiceStatus} />
```

**Acceptance Criteria**:
- [ ] Status indicator shows service state
- [ ] Updates on service start/stop
- [ ] Error state displayed

---

#### Task 6.2: Add Service Control UI
**File**: `src/ui/src/components/` (new or existing)  
**Complexity**: Low  
**Description**: Buttons/dropdown for service control

```typescript
// Start/Stop/Restart buttons
<button onClick={startService}>Start TTS Service</button>
<button onClick={stopService}>Stop TTS Service</button>
```

**Acceptance Criteria**:
- [ ] Start/stop buttons work
- [ ] Confirmation dialogs
- [ ] Progress indicators

---

### Phase 7: Testing & Validation
**Complexity**: Medium | **Estimated Time**: 1 day

#### Task 7.1: Integration Testing
**File**: `src/scripts/tests/`  
**Complexity**: Medium  
**Description**: Test full integration flow

```python
def test_tts_service_starts():
    # Start service
    # Check health endpoint
    # Verify WebSocket connectivity

def test_chapter_script_uses_service():
    # Start service
    # Run chapter_xml_to_audio.py with --tts-service
    # Verify audio generated correctly
```

**Acceptance Criteria**:
- [ ] Service starts successfully
- [ ] Health check passes
- [ ] Chapter script generates audio via service
- [ ] Service shuts down gracefully

---

#### Task 7.2: Error Scenario Testing
**File**: `src/scripts/tests/`  
**Complexity**: Medium  
**Description**: Test error handling and recovery

```python
def test_service_not_available_fallback():
    # Don't start service
    # Run chapter script with --tts-service
    # Verify fallback to local TTS

def test_service_restart():
    # Kill service mid-request
    # Verify UI handles gracefully
    # Restart service
```

**Acceptance Criteria**:
- [ ] Fallback to local TTS works
- [ ] Graceful handling of service crash
- [ ] Service restart works

---

#### Task 7.3: Manual Testing
**Complexity**: Low  
**Description**: Manual validation of UI flows

**Acceptance Criteria**:
- [ ] App launches and starts service
- [ ] Audio generation uses service
- [ ] Multiple consecutive requests work
- [ ] App quit stops service
- [ ] Works across restarts

---

## Task Summary Table

| ID | Task | Phase | Complexity | Est. Time | Dependencies |
|----|------|-------|------------|-----------|--------------|
| 1.1 | TTS Service IPC Handlers | 1 | Medium | 4h | None |
| 1.2 | Port Allocation | 1 | Low | 2h | None |
| 1.3 | Health Check Integration | 1 | Low | 2h | 1.1 |
| 1.4 | Process Cleanup | 1 | Medium | 3h | 1.1 |
| 2.1 | Preload Script | 2 | Low | 2h | 1.1 |
| 3.1 | Service Control Methods | 3 | Medium | 4h | 2.1 |
| 3.2 | playAudio Update | 3 | Medium | 4h | 3.1 |
| 4.1 | Health Endpoint | 4 | Low | 2h | None |
| 4.2 | Graceful Shutdown | 4 | Medium | 4h | 4.1 |
| 4.3 | Port Configuration | 4 | Low | 1h | 4.1 |
| 5.1 | --tts-service Flag | 5 | Low | 2h | None |
| 5.2 | TTS Factory Integration | 5 | Medium | 3h | 5.1 |
| 6.1 | Status Indicator | 6 | Low | 2h | 3.1 |
| 6.2 | Service Control UI | 6 | Low | 2h | 3.1 |
| 7.1 | Integration Testing | 7 | Medium | 4h | All above |
| 7.2 | Error Testing | 7 | Medium | 3h | 7.1 |
| 7.3 | Manual Testing | 7 | Low | 2h | 7.1 |

**Total Estimated Effort**: 3-5 days

## Risk-Adjusted Timeline

| Scenario | Probability | Impact | Mitigation Calendar |
|----------|-------------|--------|---------------------|
| Smooth | 40% | None | 3 days |
| GPU Driver Issues | 30% | High (+1d) | 4 days |
| WebSocket Complexity | 20% | Medium (+0.5d) | 3.5 days |
| Integration Bugs | 10% | High (+2d) | 5 days |

## Development Order Recommendation

1. **Start with Python backend** (Tasks 4.1-5.2)
   - Lower risk, can test independently
   - Establish service interface

2. **Add Main Process support** (Tasks 1.1-1.4)
   - Core IPC infrastructure
   - Process management

3. **Connect UI Bridge** (Tasks 2.1-3.2)
   - Expose to frontend
   - Service lifecycle

4. **UI Polish** (Tasks 6.1-6.2)
   - Visual indicators
   - User controls

5. **Test Everything** (Tasks 7.1-7.3)
   - Validation
   - Error scenarios
