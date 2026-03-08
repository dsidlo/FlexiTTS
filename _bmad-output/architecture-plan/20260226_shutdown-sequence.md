# TTS Service UI Integration - Shutdown Sequence

**Date**: 2026-02-26  
**Status**: Exploratory Architecture Study

## Shutdown Scenarios

### Scenario A: Graceful Application Quit
### Scenario B: Service Health Check Failure
### Scenario C: User-Initiated Restart

## Shutdown Sequence Diagram

```mermaid
sequenceDiagram
    autonumber
    participant User as User/User Action
    participant UI as React UI
    participant Bridge as PythonBridge
    participant IPC as Electron IPC
    participant MP as Main Process
    participant CH as Chapter Script
    participant TS as TTS Service
    participant GPU as GPU Memory

    %% Phase 1: Shutdown Trigger
    rect rgb(255, 235, 238)
    Note over User,GPU: Phase 1: Shutdown Trigger
    
    alt Scenario A: User Closes App
        User->>UI: Click X (close window)
        UI->>UI: window.beforeunload
        UI->>Bridge: prepareForShutdown()
        Note over UI: Cleanup ongoing operations
    else Scenario B: Service Unhealthy
        MP->>MP: Health check timeout
        MP->>MP: Mark service unhealthy
        Note over MP: Automatic restart or disable
    else Scenario C: Fatal Error
        CH-->>MP: Exit code 1 (crash)
        MP->>MP: Detect process crash
        Note over MP: Log error, trigger replacement
    end
    end

    %% Phase 2: Cleanup Initiation
    rect rgb(255, 245, 230)
    Note over User,GPU: Phase 2: Cleanup Initiation
    
    %% UI Cleanup
    UI->>+Bridge: stopAllAudio()
    Bridge->>IPC: window.api.killProcess('audio-')
    IPC->>+MP: ipcMain.handle('kill-process')
    MP->>MP: Find processes matching 'audio-'
    loop For each audio process
        MP->>MP: proc.kill('SIGKILL')
        MP->>MP: activeProcesses.delete(key)
    end
    MP-->>-IPC: { killed: true }
    IPC-->>-Bridge: Audio stopped
    Bridge-->>-UI: Audio cleanup complete
    
    %% Cancel ongoing Python scripts
    UI->>+Bridge: cancelPythonScripts()
    Bridge->>IPC: window.api.killProcess('python-chapter')
    IPC->>+MP: ipcMain.handle('kill-process')
    MP->>MP: Find processes matching 'python-chapter'
    loop For each Python script
        MP->>+CH: proc.kill('SIGTERM')
        CH->>CH: Catch SIGTERM signal
        CH->>CH: Cleanup partial files
        CH-->>-MP: Exit code (SIGTERM)
        MP->>MP: activeProcesses.delete(key)
    end
    MP-->>-IPC: { killed: true }
    IPC-->>-Bridge: Scripts cancelled
    Bridge-->>-UI: Script cleanup complete
    end

    %% Phase 3: TTS Service Shutdown
    rect rgb(230, 255, 230)
    Note over User,GPU: Phase 3: TTS Service Graceful Shutdown
    
    UI->>+Bridge: stopTTSService()
    Bridge->>IPC: window.api.stopTTSService()
    IPC->>+MP: ipcMain.handle('stop-tts-service')
    
    MP->>MP: Lookup activeProcesses['tts-service']
    alt Service is running
        MP->>+TS: Send SIGTERM signal
        TS->>TS: Signal handler catches SIGTERM
        TS->>TS: Set shutdown_flag = True
        
        alt Processing Active Request
            TS->>TS: Finish current request
            TS->>TS: Send completion to client
        else Idle
            TS->>TS: No active request
        end
        
        TS->>TS: Close WebSocket connections
        TS->>TS: Cancel pending queue
        TS->>+GPU: Release GPU memory
        GPU->>GPU: Free CUDA tensors
        GPU-->>-TS: Memory freed
        TS->>TS: Garbage collect model
        TS-->>-MP: Exit code 0 (graceful)
        MP->>MP: activeProcesses.delete('tts-service')
        Note over MP: Wait with timeout
        MP->>TS: Wait for exit (5s timeout)
    else Already Stopped
        MP->>MP: Service not in activeProcesses
        Note over MP: Nothing to stop
    end
    
    alt Force Kill (if graceful fails)
        TS-xTS: Still running after timeout
        MP->>TS: Send SIGKILL signal
        TS-xTS: Terminate immediately
        MP->>MP: Force cleanup
    end
    
    MP-->>-IPC: { stopped: true }
    IPC-->>-Bridge: Service stopped
    Bridge-->>-UI: TTS service shutdown complete
    end

    %% Phase 4: Final Cleanup
    rect rgb(243, 229, 245)
    Note over User,GPU: Phase 4: Final Process Cleanup
    
    MP->>MP: Iterate remaining activeProcesses
    
    %% Force kill any stragglers
    loop For each remaining process
        MP->>MP: Get proc from Map
        MP->>MP: proc.kill('SIGKILL')
        MP->>MP: activeProcesses.delete(key)
        Note over MP: Ensure all processes terminated
    end
    
    MP->>MP: Clear activeProcesses Map
    Note over MP: All process tracking cleaned
    end

    %% Phase 5: App Quit
    rect rgb(230, 245, 255)
    Note over User,GPU: Phase 5: Application Exit
    
    MP->>MP: app.quit() initiated
    MP->>MP: window.destroy()
    UI-->>MP: Renderer process exits
    MP->>MP: Cleanup Electron resources
    MP->>MP: Application exit
    Note over MP: Process complete
    end

    %% Error Recovery Path
    rect rgb(255, 235, 238)
    Note over User,GPU: Error Recovery: Shutdown Failure
    alt Service Won't Die
        MP->>TS: SIGTERM (ignored by service)
        MP->>MP: Wait 5 seconds...
        MP-xTS: Still running
        MP->>MP: Log warning
        MP->>TS: SIGKILL
        MP->>MP: Update activeProcesses
    else GPU Memory Leak
        TS->>GPU: Release memory (fails silently)
        TS-->>MP: Exit success
        MP->>MP: Log warning: "GPU memory may be leaked"
    end
    end
```

## Shutdown Explanation

### Graceful Shutdown Steps

1. **Trigger Detection**
   - User closes window (beforeunload event)
   - System shutdown signal
   - Health check failure

2. **Cancel Active Operations**
   - Stop all audio playback (SIGKILL)
   - Cancel running Python scripts (SIGTERM first, then SIGKILL)
   - Update UI to show "Shutting down..."

3. **Service Graceful Shutdown**
   - Send SIGTERM to tts_service.py
   - Service completes current request (if any)
   - Close WebSocket connections
   - Release GPU memory
   - Exit cleanly

4. **Force Cleanup (Fallback)**
   - If graceful shutdown times out (5s)
   - Send SIGKILL for immediate termination
   - Force resource release

5. **Process Verification**
   - Clear all process tracking
   - Log any leaked processes
   - Final cleanup

## Implementation Tasks

### Task 1: SIGTERM Handler in tts_service.py
**Description**: Add graceful shutdown handler to TTS service  
**Complexity**: Low  

```python
# In tts_service.py
import signal
import sys

# Global flag
shutdown_requested = False

def signal_handler(signum, frame):
    global shutdown_requested
    print("SIGTERM received, shutting down gracefully...")
    shutdown_requested = True
    
signal.signal(signal.SIGTERM, signal_handler)

# In request handler
global shutdown_requested
if shutdown_requested:
    # Complete current request, then exit
    pass
```

### Task 2: Cleanup Code in Main Process
**Description**: Shutdown all tracked processes on app quit  
**Complexity**: Medium  
**Location**: `src/ui/electron/main.ts`

```typescript
app.on('before-quit', async (event) => {
    event.preventDefault(); // Delay quit until cleanup
    
    // Stop all processes in activeProcesses Map
    for (const [key, proc] of activeProcesses.entries()) {
        if (key === 'tts-service') {
            // Graceful shutdown with timeout
            await gracefulShutdown(proc, 5000);
        } else {
            // Force kill others
            proc.kill('SIGKILL');
        }
    }
    
    app.exit(0);
});
```

### Task 3: GPU Memory Release
**Description**: Ensure GPU memory is freed on exit  
**Complexity**: Low  
**Location**: `src/scripts/tts_service.py`

```python
def cleanup():
    global model
    if model is not None:
        del model
        torch.cuda.empty_cache()
        print("GPU memory released")

atexit.register(cleanup)
```

### Task 4: UI Shutdown Notification
**Description**: Notify UI of shutdown progress  
**Complexity**: Low  
**Location**: `src/ui/src/services/pythonBridge.ts`

```typescript
async function shutdown(): Promise<void> {
    // Show shutdown progress
    updateStatus('Shutting down TTS service...');
    
    try {
        await window.api.stopTTSService();
        updateStatus('TTS service stopped');
    } catch (e) {
        console.error('Shutdown error:', e);
    }
    
    // Allow quit to proceed
    window.electron.allowAppQuit();
}
```

## Error Scenarios

### Scenario 1: Service Unresponsive
**Condition**: Service ignores SIGTERM  
**Mitigation**: 
1. Wait 5 seconds
2. Send SIGKILL
3. Log warning
4. Continue with cleanup

### Scenario 2: Active Request Lock
**Condition**: Service stuck processing request  
**Mitigation**:
1. Send SIGTERM (allow completion)
2. Wait for timeout
3. Either: wait for completion OR force kill
4. User notified if graceful complete

### Scenario 3: GPU Driver Hang
**Condition**: GPU unresponsive  
**Mitigation**:
1. Attempt cleanup with timeout
2. Log driver error
3. Force process kill
4. Warn user: "GPU may require restart"

## Resource Tracking

| Resource | Lifecycle | Cleanup Action |
|----------|-----------|----------------|
| TTS Service Process | App start → App quit | SIGTERM → SIGKILL |
| Chapter Scripts | Per-request | Cancel on window close |
| Audio Playback | Per-clip | SIGKILL on cancel |
| GPU Memory | Service start → Service stop | torch.cuda.empty_cache() |
| WebSocket Connections | Per-request | Close gracefully |

## Timing Requirements

| Phase | Timeout | Fallback |
|-------|---------|----------|
| Graceful SIGTERM | 5 seconds | SIGKILL |
| Request completion | 30 seconds | Force close |
| GPU release | 2 seconds | Warn user |
| Total shutdown | 10 seconds | Force exit |

## References

- `src/ui/electron/main.ts` - Process tracking, IPC handlers
- `src/ui/electron/main.ts` - app.on('before-quit')
- `src/scripts/tts_service.py` - Service main, signal handling
- `src/ui/src/services/pythonBridge.ts` - UI bridge, cancellation
- PyTorch CUDA memory management: `torch.cuda.empty_cache()`
- Python `atexit` module for cleanup hooks
