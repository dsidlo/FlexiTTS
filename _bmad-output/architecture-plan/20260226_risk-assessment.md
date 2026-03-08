# TTS Service UI Integration - Risk Assessment

**Date**: 2026-02-26  
**Status**: Exploratory Architecture Study

## Risk Classification

| Severity | Definition | Response |
|----------|------------|----------|
| **Critical** | Blocks release, data loss, system crash | Must mitigate before release |
| **High** | Significant UX impact, workaround exists | Mitigate in current sprint |
| **Medium** | Minor UX impact, edge case | Mitigate in following sprint |
| **Low** | Cosmetic, rare occurrence | Document and monitor |

## Identified Risks

### R1: GPU Memory Exhaustion

**Risk**: Multiple TTS requests exhaust GPU memory  
**Severity**: Critical  
**Probability**: Medium  
**Impact**: Service crash, no TTS possible

**Current State**:
- Each TTS model load consumes ~4GB GPU memory
- `tts_service.py` keeps model loaded continuously
- No memory limit enforcement

**Trigger Conditions**:
1. Multiple concurrent requests queue up
2. Model cache grows without bounds
3. Large batch processing

**Mitigation Strategies**:

1. **Immediate (Sprint 1)**:
   ```python
   # Add request queue with size limit
   MAX_CONCURRENT_REQUESTS = 1
   request_semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
   ```

2. **Short-term (Sprint 2)**:
   ```python
   # Monitor GPU memory
   def check_gpu_memory():
       allocated = torch.cuda.memory_allocated()
       if allocated > 0.9 * total:
           return {"status": "low_memory"}
   ```

3. **Long-term (Sprint 3)**:
   - Implement request batching
   - Add LRU cache for voice clones
   - Consider model quantization (Q4_K_M)

**Fallback Plan**:
- Service crashes → Auto-restart with backoff
- Fallback to LocalTTSProvider (slower but works)
- User notification: "Using fallback TTS mode"

**Test Scenario**:
```python
def test_gpu_memory_pressure():
    # Send 100 concurrent TTS requests
    # Verify service remains stable
    # Check memory reclaimed after completion
```

---

### R2: WebSocket Connection Instability

**Risk**: WebSocket connections drop or fail to establish  
**Severity**: High  
**Probability**: Medium  
**Impact**: TTS requests fail, user sees error

**Current State**:
- RemoteTTSProvider has retry logic (4 attempts)
- Exponential backoff (1s, 2s, 4s, 8s)
- Fallback to local TTS after failures

**Trigger Conditions**:
1. Service crashes mid-request
2. Network issues (rare for localhost)
3. Service restarted while in use
4. Connection timeout on slow GPU

**Mitigation Strategies**:

1. **Enhanced Connection Pooling**:
   ```python
   class RemoteTTSProvider:
       _connection_pool: Dict[str, WebSocket] = {}
       
       async def _get_connection(self):
           # Reuse existing connection
           if self.service_url in self._connection_pool:
               return self._connection_pool[self.service_url]
   ```

2. **Health Check Before Request**:
   ```python
   async def health_check():
       try:
           await asyncio.wait_for(ws.ping(), timeout=1.0)
           return True
       except:
           return False
   ```

3. **Automatic Reconnection**:
   ```python
   # In RemoteTTSProvider.generate()
   if not await self.health_check():
       self._websocket = None  # Force reconnect
       await self._connect_with_retry()
   ```

**Fallback Plan**:
- Connection fails → Switch to LocalTTSProvider
- Log warning: "Using local TTS (slower)"
- Queue service restart in background

**Test Scenario**:
```python
def test_connection_recovery():
    # Start service
    # Kill service mid-request
    # Verify fallback to local TTS
    # Verify service automatically restarts
```

---

### R3: Service Startup Failure

**Risk**: TTS service fails to start  
**Severity**: High  
**Probability**: Low-Medium  
**Impact**: No TTS functionality available

**Current State**:
- Service spawned via `uv run python tts_service.py`
- No dependency checking before spawn
- No validation of Python environment

**Trigger Conditions**:
1. Virtual environment corrupted
2. Missing dependencies (torch, websockets)
3. GPU drivers not installed
4. Port already in use by other process
5. Model files missing

**Mitigation Strategies**:

1. **Pre-flight Checks**:
   ```typescript
   async function validateEnvironment(): Promise<boolean> {
       // Check Python exists
       // Check virtual environment
       // Check GPU availability
       // Check dependencies
   }
   ```

2. **Port Conflict Resolution**:
   ```typescript
   function findAvailablePort(start: number): number {
       // Scan ports 8080-8099
       // Return first available
   }
   ```

3. **Graceful Degradation**:
   ```typescript
   if (!serviceStarted) {
       // Show warning banner
       // Disable auto-play
       // Enable manual local TTS only
   }
   ```

**Fallback Plan**:
- Service spawn fails → Use LocalTTSProvider mode
- Show persistent notification: "TTS service unavailable"
- Provide manual "Try Again" button

**Test Scenario**:
```typescript
async function test_service_startup_failure() {
    // Mock spawn failure
    // Verify UI handles gracefully
    // Verify fallback works
}
```

---

### R4: Process Leaks on App Quit

**Risk**: TTS service or Python processes not killed when app closes  
**Severity**: High  
**Probability**: Low  
**Impact**: Orphaned processes, GPU memory leaks

**Current State**:
- `activeProcesses` Map tracks processes
- `before-quit` event tries to cleanup
- No guarantee processes actually exit

**Trigger Conditions**:
1. App force-quit (Cmd+Q / Alt+F4)
2. System shutdown
3. Process hangs (ignores SIGTERM)
4. Electron crash

**Mitigation Strategies**:

1. **Multiple Shutdown Signals**:
   ```typescript
   app.on('before-quit', gracefulShutdown);
   app.on('will-quit', forceKillRemaining);
   process.on('exit', finalCleanup);
   ```

2. **Process Watchdog**:
   ```python
   # In tts_service.py
   import os
   parent_pid = os.getppid()
   
   async def monitor_parent():
       while True:
           if not process_exists(parent_pid):
               await shutdown_gracefully()
           await asyncio.sleep(5)
   ```

3. **Cleanup on Startup**:
   ```typescript
   // Kill orphaned processes from previous run
   spawn('pkill', ['-f', 'tts_service.py']);
   ```

**Fallback Plan**:
- Orphaned process detected on next startup
- Force kill all processes matching 'tts_service.py'
- Log warning about unclean shutdown

**Test Scenario**:
```python
def test_process_cleanup():
    # Start service
    # Kill parent process (simulating crash)
    # Verify service exits within 10 seconds
    # Verify GPU memory released
```

---

### R5: Port Binding Conflicts

**Risk**: TTS service cannot bind to intended port  
**Severity**: Medium  
**Probability**: Low  
**Impact**: Service cannot start

**Current State**:
- Fixed port 8080
- No fallback port mechanism
- No port discovery

**Mitigation Strategies**:

1. **Port Discovery**:
   ```python
   def find_available_port(start=8080, end=8099):
       for port in range(start, end):
           if is_port_available(port):
               return port
       raise NoPortAvailable()
   ```

2. **Configuration**:
   ```yaml
   # story-config.yml
   tts-service:
     port: 8080  # Configurable
     fallback_ports: [8081, 8082, 8083]
   ```

**Fallback Plan**:
- Port 8080 unavailable → Try 8081, 8082, 8083
- All ports busy → Show error + use local TTS

---

### R6: Long-Running Service Stability

**Risk**: Service degrades over time (memory leaks, slowdown)  
**Severity**: Medium  
**Probability**: Medium  
**Impact**: TTS gets slower, eventual crash

**Current State**:
- Service designed to run indefinitely
- No periodic health checks
- No automatic restart policy

**Trigger Conditions**:
1. Memory leak in model caching
2. Queue buildup from slow requests
3. GPU context corruption
4. Gradual slowdown over hours

**Mitigation Strategies**:

1. **Periodic Health Checks**:
   ```typescript
   setInterval(() => {
       const health = await checkServiceHealth();
       if (!health.healthy) {
           await restartService();
       }
   }, 60000);  // Every minute
   ```

2. **Service Recycling**:
   ```typescript
   // After every N requests
   if (requestCount > REQUEST_LIMIT) {
       await restartService();  // Fresh start
   }
   ```

3. **Memory Monitoring**:
   ```python
   # Expose via /health endpoint
   "memory": {
       "gpu_allocated": torch.cuda.memory_allocated(),
       "gpu_reserved": torch.cuda.memory_reserved(),
   }
   ```

**Fallback Plan**:
- Health check fails → Automatic restart
- Restart fails → Use local TTS
- User notified: "TTS service restarted"

---

### R7: Cross-Platform Differences

**Risk**: Behavior differs between macOS, Windows, Linux  
**Severity**: Medium  
**Probability**: Medium  
**Impact**: Platform-specific bugs

**Current State**:
- Audio playback uses platform-specific commands (>afplay, aplay, PowerShell)
- Process signals vary (SIGTERM handling)
- Path separators differ

**Areas of Concern**:
1. Windows: SIGTERM not supported (use taskkill)
2. Linux: Audio playback dependencies (aplay)
3. macOS: afplay always available
4. GPU drivers: CUDA vs ROCm vs Metal

**Mitigation Strategies**:

1. **Platform Abstraction**:
   ```typescript
   class ProcessManager {
       async kill(pid: number): Promise<void> {
           if (process.platform === 'win32') {
               spawn('taskkill', ['/PID', pid, '/F']);
           } else {
               process.kill(pid, 'SIGTERM');
           }
       }
   }
   ```

2. **Feature Detection**:
   ```typescript
   async function detectAudioPlayer(): Promise<string> {
       if (await commandExists('afplay')) return 'afplay';
       if (await commandExists('aplay')) return 'aplay';
       return null; // No native player
   }
   ```

**Testing Requirements**:
- Test on all 3 platforms
- CI/CD matrix builds
- Manual QA on target platforms

---

### R8: Dependency Version Conflicts

**Risk**: Python dependency versions conflict  
**Severity**: Medium  
**Probability**: Low  
**Impact**: Service won't start or behaves unexpectedly

**Current State**:
- Dependencies managed by uv
- websockets library optional (try/except)
- No runtime version checking

**Trigger Conditions**:
1. websockets 12.x vs 11.x API changes
2. torch version mismatch (CUDA compatibility)
3. numpy version affecting soundfile

**Mitigation Strategies**:

1. **Version Pinning**:
   ```toml
   # pyproject.toml
   dependencies = [
       "websockets>=11.0,<13.0",
       "torch>=2.0",
   ]
   ```

2. **Runtime Version Check**:
   ```python
   import websockets
   if websockets.__version__ < "11.0":
       raise ImportError("websockets >= 11.0 required")
   ```

---

## Risk Matrix

```
Impact
   │
 H │ R1: GPU Memory
   │ R3: Startup Failure
   │
 M │ R2: WebSocket Instability  R4: Process Leaks
   │ R7: Cross-Platform Diffs   R6: Service Stability
   │
 L │ R5: Port Conflicts         R8: Dependency Issues
   │
   └───────────────────────────────────────────────
     L        M                H
                Probability
```

## Risk Mitigation Priorities

### Sprint 1 (Must Have)
1. **R1**: GPU Memory - Add request semaphore
2. **R3**: Startup Failure - Pre-flight checks
3. **R4**: Process Leaks - Multiple shutdown signals

### Sprint 2 (Should Have)
4. **R2**: WebSocket - Connection pooling enhancement
5. **R7**: Cross-Platform - Platform abstraction layer

### Sprint 3 (Nice to Have)
6. **R6**: Service Stability - Periodic health checks
7. **R5**: Port Conflicts - Port discovery
8. **R8**: Dependencies - Version pinning

## Monitoring & Alerting

### Metrics to Track

| Metric | Warning Threshold | Critical Threshold |
|--------|-------------------|-------------------|
| GPU Memory Usage | > 80% | > 95% |
| Service Uptime | < 99% | < 95% |
| Request Latency | > 5s | > 30s |
| Connection Errors | > 1% | > 5% |
| Process Restarts | > 1/hour | > 5/hour |

### Alerts

```python
# Log warnings
def log_warning(metric, value, threshold):
    logger.warning(f"{metric}: {value} (threshold: {threshold})")

# Example
if gpu_memory > 0.80:
    log_warning("GPU_MEMORY_HIGH", gpu_memory, 0.80)
```

## Acceptance Criteria for Risk Mitigation

Before release, verify:

- [ ] R1: GPU memory stays below 90% under load
- [ ] R1: Service responds to memory pressure
- [ ] R2: Request completes despite service restart
- [ ] R3: App starts successfully with broken TTS service
- [ ] R4: No orphaned processes after force-quit
- [ ] R7: All features work on macOS, Windows, Linux
- [ ] All risks with Severity=High have mitigations implemented

## References

- GPU Memory Management: PyTorch CUDA documentation
- Process Lifecycle: Node.js child_process API
- WebSocket Reliability: websockets library docs
- Electron Lifecycle: Electron app event documentation
