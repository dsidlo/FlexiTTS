# TTS Service Client Monitoring Approaches

**Date:** March 7, 2026  
**Author:** AI Assistant  
**Status:** Reference Document / Implementation Guide

## Problem Statement

Traditional timeout-based monitoring of TTS (Text-to-Speech) generation is unreliable because:

- **Variable processing time**: TTS latency depends on text length, model state (cold vs warm), GPU load, and text complexity
- **Indeterminate completion**: No fixed duration guarantees generation success
- **Poor user experience**: Users see frozen UI with no feedback during long generations
- **Resource waste**: Timeouts may abort valid but slow generations

## Proposed Solutions

### 1. Progress Streaming via WebSocket (Recommended Primary)

**Concept:** Stream granular progress updates from server to client throughout generation.

**Protocol:**
```
Client → Server: {"action": "generate", "text": "..."}
Server → Client: {"type": "progress", "status": "loading_model", "percent": 0}
Server → Client: {"type": "progress", "status": "tokenizing", "percent": 10}
Server → Client: {"type": "progress", "status": "generating", "percent": 50, "chunks": "5/10"}
Server → Client: {"type": "progress", "status": "synthesizing", "percent": 80}
Server → Client: {"type": "complete", "duration_ms": 4230, "audio_size": 123456}
Server → Client: <binary audio data>
```

**Benefits:**
- Real-time feedback enables progress bars
- No timeout needed - client knows work is active
- Actionable error messages at specific stages
- Can estimate remaining time from progress velocity

**Drawbacks:**
- Requires WebSocket with message ordering guarantees
- More complex server state management

---

### 2. Chunked/Incremental Generation

**Concept:** Split long text into segments and generate/stream incrementally.

**Implementation:**
```python
text = "This is a very long dialog that spans multiple sentences..."
chunks = segment_text(text, max_chunk_size=100)  # ~100 chars per chunk

for i, chunk in enumerate(chunks):
    # Stream progress
    await websocket.send({"type": "chunk_start", "chunk": i, "total": len(chunks)})
    
    # Generate this chunk
    audio_chunk = model.generate(chunk)
    
    # Stream audio immediately (enables playback while generating)
    await websocket.send(audio_chunk)
```

**Benefits:**
- **Streaming playback**: Audio starts while remaining text generates
- Predictable per-chunk timeouts (100 chars ≈ 2-3s max)
- Natural pause points for cancellation
- Lower memory footprint (processes chunks sequentially)

**Drawbacks:**
- May introduce audio artifacts at chunk boundaries
- Requires sentence-aware splitting (complex for some languages)

---

### 3. Heartbeat/Ping-Pong Protocol

**Concept:** Periodic bidirectional keepalive to detect stalled generation.

**Protocol:**
```javascript
// Client sends heartbeat every 5s
const heartbeat = setInterval(() => {
    ws.send(JSON.stringify({type: "ping", timestamp: Date.now()}));
}, 5000);

// Server must respond
ws.onmessage = (msg) => {
    if (msg.type === "pong") {
        // Generation is still active
        clearTimeout(stalledTimeout);
        stalledTimeout = setTimeout(onStalled, STALLED_THRESHOLD);
    }
};
```

**Benefits:**
- Distinguishes slow generation from crashed/frozen generation
- Network connectivity detection
- Simple to implement on top of existing WebSocket

**Drawbacks:**
- Adds message overhead
- Doesn't provide progress information

---

### 4. Text-Length-Based Dynamic Timeout

**Concept:** Calculate expected duration from empirical data and text characteristics.

**Algorithm:**
```python
def estimate_generation_time(text_length: int, model_warm: bool) -> float:
    """Estimate TTS generation time in seconds."""
    if model_warm:
        base_time = 2.0  # seconds for model initialization
        ms_per_char = 15  # ~15ms per char for cached model
    else:
        base_time = 30.0  # cold start overhead
        ms_per_char = 50  # ~50ms per char for first run
    
    estimated = base_time + (text_length * ms_per_char / 1000)
    return estimated * 1.5  # 50% safety margin

# Example usage:
timeout = estimate_generation_time(len(text), is_cached)
```

**Benefits:**
- Timeout scales with actual work required
- Based on empirical measurements (can be tuned)
- Simple drop-in replacement for fixed timeout

**Drawbacks:**
- Still uses timeout paradigm (can fail on outliers)
- Requires calibration for each model/hardware combination

---

### 5. Hybrid Approach (Keepalive + Progress)

**Concept:** Combine short keepalive intervals with progress streaming for robustness.

**Protocol:**
```python
async def generate_with_hybrid_monitoring(websocket, text):
    last_progress = time.time()
    
    async def guarded_receive():
        while True:
            try:
                # Short timeout for progress detection
                message = await asyncio.wait_for(
                    websocket.recv(), 
                    timeout=30.0  # Expect progress every 30s
                )
                last_progress = time.time()
                return message
            except asyncio.TimeoutError:
                # Send keepalive before considering stalled
                await websocket.send({"type": "keepalive_query"})
                if time.time() - last_progress > 180:  # 3 min max
                    raise TimeoutError("Generation stalled")
    
    # Stream progress during generation
    for progress in model.generate_streaming(text):
        await websocket.send({"type": "progress", **progress})
```

**Benefits:**
- Best of both worlds: progress visibility + stall detection
- Self-healing: adapts to variable generation speeds
- Clear failure boundaries

**Drawbacks:**
- Most complex implementation
- Requires both server and client changes

---

### 6. Reactive Approach with Cancellation

**Concept:** Use long timeout with user-initiated cancellation.

**Implementation:**
```typescript
// Client
const controller = new AbortController();
const generationId = uuid();

ws.send({...request, id: generationId});

// UI shows: "Generating... [Cancel]" with elapsed time
// User can cancel at any time:
cancelButton.onclick = () => {
    ws.send({type: "cancel", id: generationId});
    controller.abort();
};

// Server handles cancellation:
if msg.type == "cancel":
    abort_generation(msg.id)
    cleanup_resources()
```

**Benefits:**
- User in control of timeout
- Useful for truly unbounded generation scenarios
- Simple mental model

**Drawbacks:**
- Relies on user action for resource management
- Poor UX if generation legitimately takes 5+ minutes

---

## Recommendation

### Primary: Hybrid Approach (#5)

**Implementation Priority: HIGH**

**Rationale:**
1. **Robustness**: Detects both slow progress and complete stalls
2. **UX**: Provides visibility into generation state
3. **Flexibility**: Adapts to variable workloads without hardcoded timeouts

**Implementation Sketch:**

```python
# Server-side (tts_ws_server.py)
async def handle_generation(websocket, request):
    text = request["text"]
    expected_time = estimate_time(len(text))
    
    # Send initial acknowledgment
    await websocket.send({
        "type": "ack", 
        "expected_time": expected_time,
        "text_length": len(text)
    })
    
    last_update = asyncio.get_event_loop().time()
    
    async def progress_callback(stage, percent):
        nonlocal last_update
        await websocket.send({
            "type": "progress",
            "stage": stage,
            "percent": percent,
            "timestamp": time.time()
        })
        last_update = asyncio.get_event_loop().time()
    
    # Run generation with monitoring
    try:
        future = asyncio.create_task(
            model.generate(text, progress_callback=progress_callback)
        )
        
        # Monitor for stalls
        while not future.done():
            await asyncio.sleep(5)
            if asyncio.get_event_loop().time() - last_update > 30:
                await websocket.send({"type": "keepalive"})
                # If generation truly stuck, future will timeout
        
        result = await asyncio.wait_for(future, timeout=expected_time * 2)
        await websocket.send({"type": "complete", "audio": result})
        
    except asyncio.TimeoutError:
        await websocket.send({"type": "error", "message": "Generation timeout"})
```

**Client-side expectations:**
- Show progress bar/indicator for `stage` and `percent`
- Display "Still working..." if no update for 30s
- Treat as error if no update for 3+ minutes
- Allow cancellation at any time

### Secondary: Chunked Generation (#2)

**Implementation Priority: MEDIUM**

Use for very long texts (>1000 characters) where streaming playback provides significant UX benefit.

### Fallback: Dynamic Timeout (#4)

**Implementation Priority: LOW**

Keep as simple fallback if WebSocket changes are too complex initially.

---

## Migration Path

| Phase | Approach | Effort | Impact |
|-------|----------|--------|--------|
| 1 | Dynamic Timeout (#4) | 1 hour | Low - replaces fixed timeout |
| 2 | Heartbeat (#3) | 2 hours | Medium - adds stall detection |
| 3 | Progress Streaming (#1) | 4 hours | High - full progress visibility |
| 4 | Hybrid (#5) | 6 hours | High - most robust solution |

## References

- WebSocket RFC 6455: https://tools.ietf.org/html/rfc6455
- asyncio timeout patterns: https://docs.python.org/3/library/asyncio-task.html#timeouts
- TTS latency benchmarks: [add model-specific data here]

---

**Document History:**
- 2026-03-07: Initial version
