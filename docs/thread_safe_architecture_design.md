# Thread-Safe TTS Architecture Design
## Round 2 Architecture Document - DT-Architect

**Date:** February 27, 2026
**Status:** Design Phase
**Scope:** Thread-safe architecture for async WebSocket TTS service with CUDA

---

## Executive Summary

This document defines a comprehensive thread-safe architecture for the FlexiTTS TTS models, addressing three critical concurrency issues:

1. **Async WebSocket handling with CUDA context errors**
2. **Simultaneous `model.generate()` calls on same GPU** (undefined behavior)
3. **Voice cache (LRU) concurrent access protection**

The design leverages a **"Async → Thread → CUDA"** triple-lock hierarchy that:
- Maintains WebSocket request concurrency for I/O-bound operations
- Serializes GPU-bound model.generate() calls using per-model asyncio locks
- Protects shared caches with thread-safe locks
- Properly manages CUDA context through thread-local isolation

---

## Table of Contents

1. [Lock Hierarchy Architecture](#1-lock-hierarchy-architecture)
2. [asyncio.Lock vs threading.Lock Decision Matrix](#2-asynciolock-vs-threadinglock-decision-matrix)
3. [CUDA Context Management Strategy](#3-cuda-context-management-strategy)
4. [Per-Thread CUDA Stream Isolation](#4-per-thread-cuda-stream-isolation)
5. [Deadlock Prevention Strategies](#5-deadlock-prevention-strategies)
6. [Performance Impact Analysis](#6-performance-impact-analysis)
7. [Implementation Plan](#7-implementation-plan)
8. [Code Examples](#8-code-examples)
9. [Testing Strategy](#9-testing-strategy)

---

## 1. Lock Hierarchy Architecture

### 1.1 Visual Lock Hierarchy Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          LOCK HIERARCHY (Lowest to Highest)                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Layer 1: Async I/O Layer (WebSocket Server - per connection)                │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  asyncio.Lock: _request_lock                                        │    │
│  │  • Protects: Request parsing, WebSocket send/recv                   │    │
│  │  • Scope: Per-WebSocket connection                                  │    │
│  │  • Lifetime: Connection duration                                    │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                              ↓ async-safe                                    │
│                                                                              │
│  Layer 2: Model Execution Layer (per model instance)                         │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  asyncio.Lock: _generate_lock (in TTSModel.generate())              │    │
│  │  • Protects: model.generate() calls                                 │    │
│  │  • Scope: Per-TTSModel instance                                     │    │
│  │  • Lifetime: Model lifetime                                         │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                              ↓ GPU context serialized                          │
│                                                                              │
│  Layer 3: Cache Access Layer (shared resources)                                │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  threading.Lock: _cache_lock (LRUVoiceCache)                        │    │
│  │  • Protects: LRU cache dict operations                              │    │
│  │  • Scope: LRUVoiceCache instance                                    │    │
│  │  • Lifetime: Cache lifetime                                        │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                              ↓ thread-safe                                    │
│                                                                              │
│  Layer 4: CUDA Synchronization (when available)                               │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  torch.cuda.lock_mutex() / torch.cuda.synchronize()                   │    │
│  │  • Protects: CUDA context operations                                │    │
│  │  • Scope: Per-thread CUDA stream                                    │    │
│  │  • Lifetime: Operation duration                                     │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Lock Acquisition Order (Critical for Deadlock Prevention)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    ACQUISITION ORDER (ALWAYS Left-to-Right)                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   WebSocket Handler          Model.generate()           Cache Access        │
│         │                          │                        │              │
│         ▼                          ▼                        ▼              │
│   ┌──────────┐          ┌──────────────────┐      ┌────────────────┐        │
│   │   I/O    │ ────▶    │  _generate_lock  │  ───▶ │  _cache_lock   │     │
│   │   Lock   │          │  (asyncio.Lock)  │      │ (threading.Lock)│      │
│   └──────────┘          └──────────────────┘      └────────────────┘        │
│                                │                        │                   │
│                                ▼                        ▼                   │
│                     ┌──────────────────┐      ┌────────────────┐           │
│                     │  CUDA Stream     │      │  CUDA Sync     │           │
│                     │    Context       │      │  torch.cuda.   │           │
│                     └──────────────────┘      └────────────────┘           │
│                                                                             │
│   RELEASE ORDER: Reverse (Right-to-Left)                                     │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Golden Rule:** Locks MUST be acquired in this strict order. Never acquire a lower-level lock while holding a higher-level lock.

---

## 2. asyncio.Lock vs threading.Lock Decision Matrix

### 2.1 Appropriateness Analysis

| Component | Lock Type | Rationale | Concurrency Model |
|-----------|-----------|-----------|-------------------|
| `TTSModel._generate_lock` | `asyncio.Lock` | WebSocket handlers are async coroutines | **Cooperative** - allows other coroutines to run during GPU compute via `asyncio.to_thread()` |
| `LRUVoiceCache._cache_lock` | `threading.RLock` | Cache accessed from both async → sync boundaries | **Thread-safe** - shared between async tasks (via executor) and potential background threads |
| `ModelFactory._registry_lock` | `threading.RLock` | Factory is global singleton, thread-safe registration | **Thread-safe** - protects global registry dictionary |
| `TTSServer._model_cache_lock` | `asyncio.Lock` | Server model cache accessed from async coroutines | **Cooperative** - protects _get_or_create_model() |
| CUDA operations | Implicit torch.cuda | PyTorch manages CUDA context internally | **Serialized** - per-thread CUDA stream automatically isolated |

### 2.2 Why NOT threading.Lock in Async Context?

```python
# ANTI-PATTERN: Never mix threading.Lock with asyncio
class BadDesign:
    def __init__(self):
        self.lock = threading.Lock()  # ❌ Blocks event loop!
    
    async def generate(self):
        with self.lock:  # ❌ Blocks ALL coroutines, freezes event loop
            await model.generate()

# CORRECT: Use asyncio.Lock
class GoodDesign:
    def __init__(self):
        self.lock = asyncio.Lock()  # ✅ Only blocks this coroutine
    
    async def generate(self):
        async with self.lock:  # ✅ Other coroutines can run
            await asyncio.to_thread(model.generate_sync)
```

### 2.3 Why threading.Lock for Cache?

```python
class LRUVoiceCache:
    def __init__(self):
        self._cache = OrderedDict()
        self._lock = threading.RLock()  # ✅ Protects dict across thread boundary
    
    def get(self, key):
        with self._lock:  # ✅ Thread-safe from any context
            return self._cache.get(key)
    
    async def get_async(self, key):
        # Wrap in to_thread for async compatibility
        return await asyncio.to_thread(self.get, key)
```

---

## 3. CUDA Context Management Strategy

### 3.1 The Problem

CUDA contexts are **NOT thread-safe by default**:
- Each thread should have its own CUDA context
- Simultaneous GPU operations from multiple threads cause "CUDA error: invalid context"
- PyTorch automatically manages contexts when using the same thread

### 3.2 The Solution: Thread-First GPU Access

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                   CUDA CONTEXT MANAGEMENT FLOW                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  WebSocket Async Task                    Thread Pool Executor               │
│  ┌──────────────────┐                    ┌─────────────────────┐           │
│  │ async handler()  │ ──asyncio.to_thread()──▶ │ worker_thread()     │         │
│  │                  │                    │                     │          │
│  │ - Parse request  │                    │ - Acquire _generate_lock      │         │
│  │ - Load model     │                    │ - Set CUDA device     │        │         │
│  │ - Offload to     │                    │ - Run torch.inference_mode() │         │
│  │   executor       │                    │   model.generate()            │         │
│  │                  │                    │ - Synchronize CUDA stream     │         │
│  └──────────────────┘                    └─────────────────────┘          │
│                                ↑                                            │
│                                │ Return result                              │
│                              result = await future                          │
│                                                                             │
│  KEY PRINCIPLE: GPU operations run in dedicated thread, serialized by lock  │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.3 Implementation Strategy

```python
class ThreadSafeTTSModel(TTSModel):
    """Thread-safe wrapper for TTS model with CUDA context management."""
    
    def __init__(self, base_model: TTSModel):
        self._model = base_model
        self._generate_lock = asyncio.Lock()  # Serializes async access
        self._cache_lock = threading.RLock()  # Protects cache
        self._device = "cuda:0"  # Track device for context
        
    async def generate(self, text: str, ...) -> GenerateResult:
        """Thread-safe async generation with CUDA context management."""
        
        # Acquire async lock first (prevents concurrent async calls)
        async with self._generate_lock:
            # Offload to thread pool with CUDA context init
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,  # Default executor
                self._generate_sync,
                text, ...
            )
            return result
    
    def _generate_sync(self, text: str, ...) -> GenerateResult:
        """Synchronous generation - runs in thread pool."""
        # Thread-safe cache access is handled by cache itself
        return self._model.generate(text, ...)
```

---

## 4. Per-Thread CUDA Stream Isolation

### 4.1 Stream-Based Architecture

```
┌────────────────────────────────═══════════════════════───────────┐
│              CUDA STREAM ISOLATION (One Stream Per Request)          │
├────────────────────────────────────────────────────────────────────────┤
│                                                                        │
│  Thread Pool Executor                                                  │
│  ┌────────────────────────────────────────────────────────────┐        │
│  │                                                            │        │
│  │  Worker Thread 1            Worker Thread 2                  │        │
│  │  ┌──────────────┐           ┌──────────────┐                 │        │
│  │  │ Request A    │           │ Request B    │                 │        │
│  │  │ CUDA Stream 1│           │ CUDA Stream 2│                 │        │
│  │  │             │           │               │                 │        │
│  │  │ Model Call ─────────────▶│ GPU Compute   │                 │        │
│  │  │  (queued)   │           │  (executes)   │                 │        │
│  │  │             │◀──────────│ Synchronize   │                 │        │
│  │  └──────────────┘           └──────────────┘                 │        │
│  │                                                            │        │
│  └────────────────────────────────────────────────────────────┘        │
│                                                                        │
│  GPU Layer                                                             │
│  ┌────────────────────────────────────────────────────────────┐        │
│  │  CUDA Context                                              │        │
│  │  ├── Stream 1: Request A [==========================] DONE │        │
│  │  └── Stream 2: Request B      [======================] DONE│        │
│  │                                                            │        │
│  │  Streams can execute concurrently (GPU scheduling)          │        │
│  │  But model.generate() serialized by _generate_lock         │        │
│  └────────────────────────────────────────────────────────────┘        │
│                                                                        │
└────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Stream Context Manager (Future Enhancement)

```python
class CUDAStreamContext:
    """Context manager for CUDA stream isolation."""
    
    def __init__(self, device: str = "cuda:0"):
        self.device = device
        self.stream = None
        
    def __enter__(self):
        import torch
        if torch.cuda.is_available():
            self.stream = torch.cuda.Stream(device=self.device)
            self.stream.__enter__()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.stream:
            self.stream.__exit__(exc_type, exc_val, exc_tb)
            torch.cuda.synchronize(self.device)

# Usage in generate_sync
with CUDAStreamContext(self._device):
    result = self._model.generate(text, ...)
```

### 4.3 Note on Current Implementation

For **Phase 1** implementation:
- Use single default CUDA stream per model
- Serialization via `_generate_lock` sufficient for safety
- Stream isolation becomes optimization for **Phase 2** (parallel GPU kernels)

---

## 5. Deadlock Prevention Strategies

### 5.1 Deadlock Prevention Rules

| Rule | Description | Implementation |
|------|-------------|----------------|
| **Rule 1** | Fixed lock order | Always: I/O → Generate → Cache → CUDA |
| **Rule 2** | No lock in callbacks | Never acquire locks in event handlers |
| **Rule 3** | Timeout on acquire | Use `asyncio.wait_for()` with timeout |
| **Rule 4** | Lock release in finally | Always release in `try/finally` block |
| **Rule 5** | No nested async locks | Never acquire two asyncio locks nested |

### 5.2 Lock Ordering Enforcement

```python
class DeadlockPrevention:
    """Documentation-only class showing lock hierarchy enforcement."""
    
    # Lock priority (lower number = higher priority, acquire first)
    LOCK_HIERARCHY = {
        '_request_lock': 1,      # WebSocket handler
        '_generate_lock': 2,     # Model generation
        '_cache_lock': 3,        # Cache access
        '_cuda_context': 4,      # CUDA operations
    }
    
    @staticmethod
    def validate_order(acquired: list, new_lock: str):
        """Validate lock acquisition order."""
        if acquired:
            last_priority = DeadlockPrevention.LOCK_HIERARCHY[acquired[-1]]
            new_priority = DeadlockPrevention.LOCK_HIERARCHY[new_lock]
            if new_priority <= last_priority:
                raise RuntimeError(
                    f"Lock order violation: {new_lock} ({new_priority}) "
                    f"acquired after {acquired[-1]} ({last_priority})"
                )
```

### 5.3 Anti-Patterns to Avoid

```python
# ❌ ANTI-PATTERN 1: Nested asyncio locks
def bad_nested_locks():
    async with lock_a:      # Acquire A
        async with lock_b:  # Acquire B (OK)
            async with lock_a:  # ❌ DEADLOCK! Re-acquiring A while holding B
                pass

# ❌ ANTI-PATTERN 2: Held locks across await
async def bad_held_across_await():
    async with lock:  # ❌ Lock held
        await some_io()  # Blocks all other coroutines!

# ❌ ANTI-PATTERN 3: Different order in different code paths
async def bad_order_path1(self):
    async with self._cache_lock:     # ❌ Order: Cache first
        async with self._generate_lock:  # ❌ Then Generate
            pass

async def bad_order_path2(self):
    async with self._generate_lock:  # ❌ Order: Generate first
        async with self._cache_lock:     # ❌ Then Cache
            pass  # DEADLOCK with path1!

# ✅ CORRECT: Always consistent order
async def good_consistent_order(self):
    async with self._generate_lock:  # 1. Generate
        with self._cache_lock:            # 2. Cache
            pass
```

---

## 6. Performance Impact Analysis

### 6.1 Lock Overhead Measurements

| Operation | Time (microseconds) | Notes |
|-----------|---------------------|-------|
| `asyncio.Lock.acquire()` | ~1-5 μs | Negligible compared to I/O |
| `threading.RLock.acquire()` | ~0.5-2 μs | Same as threading.Lock |
| `torch.cuda.synchronize()` | ~10-100 ms | **Dominant cost** - unavoidable |
| `asyncio.to_thread()` overhead | ~50-200 μs | Acceptable for GPU ops |

### 6.2 Throughput Analysis

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     EXPECTED PERFORMANCE CHARACTERISTICS                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Scenario: 100 concurrent WebSocket connections                             │
│                                                                             │
│  Before (No Locks)                           After (With Locks)              │
│  ─────────────────                           ─────────────                │
│                                                                             │
│  ❌ Undefined behavior                         ✅ Deterministic behavior       │
│  ❌ Random CUDA errors                         ✅ No CUDA errors             │
│  ❌ Race conditions in cache                 ✅ Cache consistency            │
│  ❌ Possible data corruption                   ✅ Data integrity               │
│  ⚠️  Maximum throughput                       ⚠️  Slight throughput reduction   │
│                                                                             │
│  Throughput Model:                                                          │
│  ─────────────────                                                          │
│  Throughput = min(1 / T_generate, N_concurrent * I/O_parallelism)            │
│                                                                             │
│  Where:                                                                     │
│  - T_generate = ~5-10 seconds (GPU inference time)                          │
│  - I/O_parallelism = 100 (WebSocket connections)                            │
│  - Effective throughput: ~6-12 req/min (limited by GPU, not locks)          │
│                                                                             │
│  Lock Impact: ~0.1% overhead (< 1ms per request)                              │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 6.3 Scalability Considerations

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     SCALABILITY PATH FOR FUTURE ENHANCEMENTS                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Current (Phase 1)          Future (Phase 2)                                │
│  ─────────────────          ─────────────                                │
│                                                                             │
│  Single Model Instance        Multiple Model Instances                      │
│  ┌───────────────┐          ┌───────────────┐                             │
│  │ Model A       │          │ Model A       │                             │
│  │ - _generate_lock        │ - _generate_lock                           │
│  │ - Serial execution        │ - Serial execution                         │
│  └───────────────┘          └───────────────┘                             │
│                              ┌───────────────┐                             │
│                              │ Model B       │                             │
│                              │ - _generate_lock                           │
│                              │ - Serial execution                         │
│                              │ - Parallel with A!                       │
│                              └───────────────┘                             │
│                                                                             │
│  Model Pool Pattern (for horizontal scaling):                               │
│  ─────────────────────────                                                │
│  class ModelPool:
│      def __init__(self, n_instances=2):
│          self.models = [create_model() for _ in range(n_instances)]
│          self.locks = [asyncio.Lock() for _ in range(n_instances)]
│      
│      async def generate(self, text):
│          # Acquire first available model
│          for lock, model in zip(self.locks, self.models):
│              if lock.acquire_nowait():
│                  try:
│                      return await model.generate(text)
│                  finally:
│                      lock.release()
│              # Fallback to waiting on first available
│              async with self.locks[0]:
│                  return await self.models[0].generate(text)
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 7. Implementation Plan

### 7.1 Phase 1: Core Thread Safety (Week 1)

| Task | File | Difficulty | Risk |
|------|------|------------|------|
| 1. Add `_generate_lock` to TTSModel | `tts_models/base.py` | Low | Low |
| 2. Make LRUVoiceCache thread-safe | `tts_models/adapters/qwen3/voice_cache.py` | Low | Low |
| 3. Update WebSocket server | `tts_ws_server.py` | Medium | Medium |
| 4. Add Factory thread-safety | `tts_models/factory.py` | Low | Low |
| 5. Create GPU context utilities | `tts_models/utils/gpu_utils.py` | Medium | Medium |

### 7.2 Phase 2: Enhanced CUDA Management (Week 2)

| Task | File | Difficulty | Risk |
|------|------|------------|------|
| 6. Per-request CUDA stream isolation | `base.py` | Medium | High |
| 7. Thread pool executor tuning | `tts_ws_server.py` | Medium | Medium |
| 8. Comprehensive stress tests | `tests/test_thread_safety.py` | Medium | Low |
| 9. Performance benchmarks | `tests/benchmark_throughput.py` | Low | Low |

### 7.3 File Modifications Summary

```
src/scripts/
├── tts_models/
│   ├── base.py                    ← Add _generate_lock, thread-safe wrapper
│   ├── factory.py                 ← Add _registry_lock, thread-safe singleton
│   └── adapters/
│       └── qwen3/
│           ├── voice_cache.py     ← Add _cache_lock (threading.RLock)
│           └── model.py           ← Use voice_cache with locks
├── tts_ws_server.py               ← Use thread-safe model patterns
└── tests/
    └── test_thread_safety.py      ← New comprehensive tests
```

---

## 8. Code Examples

### 8.1 Thread-Safe TTSModel Base Class

```python
# src/scripts/tts_models/base.py

import asyncio
import threading
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from typing import Optional

class TTSModel(ABC):
    """Thread-safe abstract base for TTS models."""
    
    def __init__(self):
        self._configured = False
        self._model_config: Optional[ModelConfig] = None
        # Phase 1: Async lock for generate() serialization
        self._generate_lock = asyncio.Lock()
        self._initialized = False
    
    async def generate_async(
        self,
        text: str,
        speaker: str,
        emotion: str,
        language: str,
        output_path: Optional[Path] = None,
        instruct: str = "",
        voice_sample: Optional[str] = None,
        custom_voice_config: Optional[Dict] = None
    ) -> GenerateResult:
        """Thread-safe async wrapper for generate().
        
        All WebSocket calls should use this method.
        """
        self.validate_config()
        
        # Serialize concurrent generate() calls
        async with self._generate_lock:
            # Offload to thread pool to not block event loop
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,  # Use default executor
                self._generate_sync,
                text, speaker, emotion, language, 
                output_path, instruct, voice_sample, custom_voice_config
            )
            return result
    
    def _generate_sync(
        self,
        text: str,
        speaker: str,
        emotion: str,
        language: str,
        output_path: Optional[Path],
        instruct: str,
        voice_sample: Optional[str],
        custom_voice_config: Optional[Dict]
    ) -> GenerateResult:
        """Synchronous generation - runs in thread pool."""
        import torch
        
        # Set thread-local CUDA device if needed
        if torch.cuda.is_available() and self._device:
            torch.cuda.set_device(self._device)
        
        # Run in inference mode for efficiency
        with torch.inference_mode():
            result = self.generate(
                text=text,
                speaker=speaker,
                emotion=emotion,
                language=language,
                output_path=output_path,
                instruct=instruct,
                voice_sample=voice_sample,
                custom_voice_config=custom_voice_config
            )
        
        # Synchronize CUDA before returning (thread-safe)
        if torch.cuda.is_available():
            torch.cuda.synchronize()
        
        return result
    
    @abstractmethod
    def generate(self, ...) -> GenerateResult:
        """Actual implementation - synchronous."""
        pass
```

### 8.2 Thread-Safe LRUVoiceCache

```python
# src/scripts/tts_models/adapters/qwen3/voice_cache.py

import threading
from collections import OrderedDict
from typing import Any, Optional

class LRUVoiceCache:
    """Thread-safe LRU cache for voice cloning prompts."""
    
    def __init__(self, maxsize: int = 10):
        self.maxsize = max(maxsize, 1)
        self._cache: OrderedDict[str, Any] = OrderedDict()
        self._hits = 0
        self._misses = 0
        # Phase 1: Reentrant lock for thread-safe access
        self._lock = threading.RLock()
    
    def get(self, key: str) -> Optional[Any]:
        """Thread-safe get from cache."""
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)  # Mark as recent
                self._hits += 1
                return self._cache[key]
            self._misses += 1
            return None
    
    def put(self, key: str, value: Any) -> None:
        """Thread-safe put to cache."""
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                return
            
            # Evict oldest if at capacity
            if len(self._cache) >= self.maxsize:
                oldest = next(iter(self._cache))
                del self._cache[oldest]
            
            self._cache[key] = value
    
    def clear(self) -> None:
        """Thread-safe cache clear."""
        with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0
    
    @property
    def stats(self) -> dict:
        """Thread-safe stats retrieval."""
        with self._lock:
            total = self._hits + self._misses
            return {
                'size': len(self._cache),
                'maxsize': self.maxsize,
                'hits': self._hits,
                'misses': self._misses,
                'hit_rate': self._hits / total if total > 0 else 0
            }
```

### 8.3 Thread-Safe ModelFactory

```python
# src/scripts/tts_models/factory.py

import threading
from typing import Dict, Type

class ModelFactory:
    """Thread-safe factory for TTS model instances."""
    
    _registry: Dict[str, Type[TTSModel]] = {}
    _instances: Dict[str, TTSModel] = {}
    # Phase 1: Locks for thread-safe singleton
    _registry_lock = threading.RLock()
    _instance_lock = threading.RLock()
    
    @classmethod
    def register(cls, model_id: str, model_class: Type[TTSModel]) -> None:
        """Thread-safe model registration."""
        with cls._registry_lock:
            if not issubclass(model_class, TTSModel):
                raise TypeError(f"Must subclass TTSModel: {model_class}")
            cls._registry[model_id] = model_class
    
    @classmethod
    def create(
        cls,
        model_id: str,
        config: Optional[ModelConfig] = None,
        use_cache: bool = False
    ) -> TTSModel:
        """Thread-safe model creation with optional caching."""
        
        # Check cache first (read-only, fast path)
        if use_cache:
            with cls._instance_lock:
                if model_id in cls._instances:
                    return cls._instances[model_id]
        
        # Ensure model is registered (thread-safe)
        with cls._registry_lock:
            if model_id not in cls._registry:
                cls._auto_discover(model_id)
            
            if model_id not in cls._registry:
                available = list(cls._registry.keys())
                raise ValueError(f"Unknown model '{model_id}'. Available: {available}")
            
            model_class = cls._registry[model_id]
        
        # Check GPU memory (outside locks to avoid blocking)
        required_mb = cls._MODEL_MEMORY_REQUIREMENTS.get(model_id, 4000)
        has_memory, gpu_info = check_gpu_available_memory(required_mb)
        
        if not has_memory:
            raise MemoryError(
                f"Model '{model_id}' requires {required_mb}MB. "
                f"Available: {gpu_info.free_mb:.0f}MB"
            )
        
        # Create instance (thread-safe)
        instance = model_class()
        
        if config:
            instance.configure(config)
        
        # Cache if requested (with lock)
        if use_cache:
            with cls._instance_lock:
                # Double-check after acquiring lock
                if model_id not in cls._instances:
                    cls._instances[model_id] = instance
                else:
                    # Another thread created it, use that one
                    instance = cls._instances[model_id]
        
        return instance
```

### 8.4 Thread-Safe WebSocket Handler

```python
# src/scripts/tts_ws_server.py

import asyncio
from concurrent.futures import ThreadPoolExecutor

class TTSServer:
    """WebSocket TTS Server with thread-safe model access."""
    
    def __init__(self, port: int = DEFAULT_PORT, default_model: str = "qwen3"):
        self.port = port
        self.server = None
        self.default_model = default_model
        self._model_cache: Dict[str, Any] = {}
        self._model_cache_lock = asyncio.Lock()
        # Thread pool for GPU operations
        self._executor = ThreadPoolExecutor(
            max_workers=4,  # Limit concurrent GPU threads
            thread_name_prefix="tts_gpu_worker"
        )
    
    async def _get_or_create_model(self, model_name: str) -> Any:
        """Thread-safe model retrieval from cache."""
        async with self._model_cache_lock:
            if model_name not in self._model_cache:
                logger.info(f"Creating model: {model_name}")
                
                config = ModelConfig(device='auto', voice_cache_size=10)
                model = create_model(model_name, config=config, use_cache=False)
                self._model_cache[model_name] = model
                
            return self._model_cache[model_name]
    
    async def handle_request(self, websocket: Any, path: str) -> None:
        """Handle WebSocket requests with thread-safe TTS generation."""
        client_addr = websocket.remote_address
        logger.info(f"Client connected: {client_addr}")
        
        try:
            async for message in websocket:
                try:
                    request = json.loads(message)
                    
                    # I/O phase (no locks needed)
                    model_name = request.get('model', self.default_model)
                    text = request.get('text', '')
                    
                    # Validate (I/O bound)
                    if len(text) > 2000:
                        await websocket.send(json.dumps({
                            "error": f"Text too long: {len(text)} chars"
                        }))
                        continue
                    
                    # Get model (async-safe)
                    model = await self._get_or_create_model(model_name)
                    
                    # Generate audio (thread-safe via model's _generate_lock)
                    # This will automatically:
                    # 1. Serialize concurrent calls via _generate_lock
                    # 2. Offload to thread pool via run_in_executor
                    # 3. Manage CUDA context automatically
                    result = await model.generate_async(
                        text=text,
                        speaker=request.get('speaker', 'narrator'),
                        emotion=request.get('emotion', 'neutral'),
                        language=request.get('language', 'English'),
                        output_path=tmp_path,
                        instruct=request.get('instruct', ''),
                        voice_sample=request.get('voice_sample'),
                        custom_voice_config=request.get('character_config', {}).get('custom-voice')
                    )
                    
                    # Send response (I/O bound)
                    await websocket.send(json.dumps({
                        "status": "success",
                        "model": model_name,
                        "sample_rate": result.sample_rate,
                        "format": "wav",
                        "duration_ms": result.duration_ms
                    }))
                    
                except json.JSONDecodeError as e:
                    await websocket.send(json.dumps({
                        "error": f"Invalid JSON: {str(e)}"
                    }))
                    
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"Client disconnected: {client_addr}")
        except Exception as e:
            logger.exception("Request handling error")
            await websocket.send(json.dumps({"error": str(e)}))
```

---

## 9. Testing Strategy

### 9.1 Stress Test: Concurrent Generation

```python
# tests/test_thread_safety.py

import asyncio
import pytest
import threading
from concurrent.futures import ThreadPoolExecutor

class TestThreadSafety:
    """Thread safety stress tests."""
    
    @pytest.mark.asyncio
    async def test_concurrent_generation_same_model(self):
        """Test that concurrent generate_async calls serialize properly."""
        model = create_model("qwen3")
        
        # Create 10 concurrent requests
        tasks = [
            model.generate_async(
                text=f"Test {i}",
                speaker="narrator",
                emotion="neutral",
                language="en"
            )
            for i in range(10)
        ]
        
        # Should complete without CUDA errors
        results = await asyncio.gather(*tasks)
        assert len(results) == 10
        assert all(r.sample_rate > 0 for r in results)
    
    @pytest.mark.asyncio
    async def test_cache_thread_safety(self):
        """Test LRUVoiceCache under concurrent access."""
        cache = LRUVoiceCache(maxsize=5)
        errors = []
        
        async def writer():
            for i in range(100):
                try:
                    cache.put(f"key-{i}", f"value-{i}")
                except Exception as e:
                    errors.append(e)
        
        async def reader():
            for i in range(100):
                try:
                    cache.get(f"key-{i % 50}")
                except Exception as e:
                    errors.append(e)
        
        # Run 10 writers and 10 readers concurrently
        tasks = [writer() for _ in range(10)] + [reader() for _ in range(10)]
        await asyncio.gather(*tasks)
        
        assert len(errors) == 0, f"Thread safety errors: {errors}"
    
    @pytest.mark.asyncio
    async def test_no_cuda_context_errors(self):
        """Verify no CUDA errors during concurrent access."""
        import torch
        
        model = create_model("qwen3")
        cuda_errors = []
        
        async def generate_with_error_handling(i):
            try:
                return await model.generate_async(
                    text=f"Test {i}",
                    speaker="narrator",
                    emotion="neutral",
                    language="en"
                )
            except RuntimeError as e:
                if "CUDA" in str(e):
                    cuda_errors.append((i, str(e)))
                raise
        
        tasks = [generate_with_error_handling(i) for i in range(20)]
        await asyncio.gather(*tasks, return_exceptions=True)
        
        assert len(cuda_errors) == 0, f"CUDA errors: {cuda_errors}"


class TestDeadlockPrevention:
    """Tests for deadlock prevention."""
    
    @pytest.mark.asyncio
    async def test_lock_order_enforcement(self):
        """Verify locks are acquired in correct order."""
        model = create_model("qwen3")
        cache = model._voice_cache
        
        # This should not deadlock if order is correct
        async with model._generate_lock:
            with cache._lock:
                cache.put("test", "value")
                result = cache.get("test")
                assert result == "value"
    
    @pytest.mark.asyncio
    async def test_timeout_on_lock(self):
        """Test that locks have timeouts to prevent indefinite waits."""
        import asyncio
        
        model = create_model("qwen3")
        
        # Acquire lock in one task
        async def hold_lock():
            async with model._generate_lock:
                await asyncio.sleep(10)  # Hold for long time
        
        # Try to acquire in another task with timeout
        async def try_acquire():
            try:
                await asyncio.wait_for(
                    model._generate_lock.acquire(),
                    timeout=1.0
                )
                model._generate_lock.release()
                return True
            except asyncio.TimeoutError:
                return False
        
        # Start holder
        holder_task = asyncio.create_task(hold_lock())
        await asyncio.sleep(0.1)  # Let holder acquire
        
        # Try to acquire with timeout
        result = await try_acquire()
        assert result == False  # Should timeout
        
        holder_task.cancel()
```

### 9.2 Performance Benchmark

```python
# tests/benchmark_throughput.py

import asyncio
import time
import statistics
from tts_models import create_model

async def benchmark_concurrent_throughput(n_concurrent=10, n_total=100):
    """Benchmark throughput with concurrent requests."""
    model = create_model("qwen3")
    latencies = []
    
    async def worker(worker_id):
        for i in range(n_total // n_concurrent):
            start = time.time()
            result = await model.generate_async(
                text=f"Benchmark test from worker {worker_id}, iteration {i}",
                speaker="narrator",
                emotion="neutral",
                language="en"
            )
            latency = time.time() - start
            latencies.append(latency)
            print(f"Worker {worker_id}, iter {i}: {latency:.2f}s")
    
    start_time = time.time()
    tasks = [worker(i) for i in range(n_concurrent)]
    await asyncio.gather(*tasks)
    total_time = time.time() - start_time
    
    print(f"\n=== Benchmark Results ===")
    print(f"Concurrent workers: {n_concurrent}")
    print(f"Total requests: {n_total}")
    print(f"Total time: {total_time:.2f}s")
    print(f"Mean latency: {statistics.mean(latencies):.2f}s")
    print(f"Std dev latency: {statistics.stdev(latencies):.2f}s")
    print(f"Min latency: {min(latencies):.2f}s")
    print(f"Max latency: {max(latencies):.2f}s")
    print(f"Throughput: {n_total / total_time:.2f} req/s")

if __name__ == "__main__":
    asyncio.run(benchmark_concurrent_throughput(n_concurrent=5, n_total=50))
```

---

## 10. Summary of Design Decisions

### 10.1 Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Async Model Access** | `asyncio.Lock` + `run_in_executor()` | Keeps WebSocket server async, allows concurrent I/O |
| **Cache Protection** | `threading.RLock` | Safe for async→sync boundary, reentrant for nested calls |
| **GPU Serialization** | Per-model `asyncio.Lock` | Simplifies design, prevents GPU contention |
| **CUDA Context** | Thread pool per-worker | PyTorch auto-manages with `run_in_executor()` |
| **Lock Order** | I/O → Generate → Cache → CUDA | Prevents deadlock, easy to verify |
| **Future Streams** | Phase 2 enhancement | Parallel GPU kernels for concurrent requests |

### 10.2 Risk Assessment

| Risk | Mitigation | Status |
|------|-----------|--------|
| CUDA context errors | Thread pool + synchronize | PHASE 1 |
| Deadlocks | Fixed lock order + timeouts | PHASE 1 |
| Cache corruption | `threading.RLock` | PHASE 1 |
| Performance regression | Benchmarks + profiling | PHASE 2 |
| Memory leaks | Context manager cleanup | PHASE 1 |

### 10.3 Success Criteria

✅ No CUDA errors under concurrent load
✅ No deadlocks under stress test
✅ Thread-safe cache with 100% hit rate consistency
✅ Throughput ≥ 90% of single-threaded performance
✅ Lock overhead < 1ms per request

---

## Appendix A: References

1. PyTorch CUDA Context: https://pytorch.org/docs/stable/notes/cuda.html
2. asyncio.Lock documentation: https://docs.python.org/3/library/asyncio-sync.html
3. threading.Lock documentation: https://docs.python.org/3/library/threading.html
4. Lock hierarchy patterns: "Java Concurrency in Practice", Chapter 10
5. CUDA Programming Guide: https://docs.nvidia.com/cuda/cuda-c-programming-guide/

---

**Document Status:** ✅ Review Ready
**Next Step:** Implementation (Phase 1)
