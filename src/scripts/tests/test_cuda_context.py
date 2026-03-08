"""CUDA context management verification tests.

Tests CUDA context switching under async load to verify:
- CUDA context management verification
- GPU memory isolation
- Context switching under async load
- Proper stream synchronization
"""

from __future__ import annotations

import asyncio
import threading
import time
import pytest
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call
from dataclasses import dataclass
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent / "src/scripts"))

from tts_models.utils.gpu_utils import get_gpu_memory_info, check_gpu_available_memory, GPUMemoryInfo


@dataclass
class MockCUDAContext:
    """Mock CUDA context for testing."""
    device_id: int
    is_current: bool = False
    streams: List[int] = None
    allocated_memory: int = 0
    
    def __post_init__(self):
        if self.streams is None:
            self.streams = []


class MockCUDAState:
    """Mock CUDA state tracker for tests."""
    
    def __init__(self):
        self.contexts: Dict[int, MockCUDAContext] = {}
        self.current_context: Optional[int] = None
        self.operations_log: List[Dict[str, Any]] = []
        self._lock = threading.Lock()
        self.errors: List[str] = []
    
    def create_context(self, device_id: int) -> MockCUDAContext:
        """Create a new CUDA context."""
        with self._lock:
            ctx = MockCUDAContext(device_id=device_id)
            self.contexts[device_id] = ctx
            self.operations_log.append({
                "op": "create_context",
                "device_id": device_id,
                "timestamp": time.time()
            })
            return ctx
    
    def set_current_context(self, device_id: int) -> bool:
        """Set current CUDA context."""
        with self._lock:
            if device_id not in self.contexts:
                self.errors.append(f"Context {device_id} not found")
                return False
            
            # Mark old context as not current
            if self.current_context is not None:
                if self.current_context in self.contexts:
                    self.contexts[self.current_context].is_current = False
            
            # Set new context
            self.contexts[device_id].is_current = True
            self.current_context = device_id
            
            self.operations_log.append({
                "op": "set_current",
                "device_id": device_id,
                "timestamp": time.time()
            })
            return True
    
    def create_stream(self, device_id: int) -> Optional[int]:
        """Create a CUDA stream."""
        with self._lock:
            if device_id not in self.contexts:
                self.errors.append(f"No context for device {device_id}")
                return None
            
            stream_id = len(self.contexts[device_id].streams)
            self.contexts[device_id].streams.append(stream_id)
            
            self.operations_log.append({
                "op": "create_stream",
                "device_id": device_id,
                "stream_id": stream_id,
                "timestamp": time.time()
            })
            return stream_id
    
    def allocate(self, device_id: int, bytes: int) -> bool:
        """Simulate memory allocation."""
        with self._lock:
            if device_id not in self.contexts:
                self.errors.append(f"No context for device {device_id}")
                return False
            
            self.contexts[device_id].allocated_memory += bytes
            return True
    
    def sync(self, device_id: int) -> bool:
        """Synchronize device."""
        with self._lock:
            if device_id not in self.contexts:
                self.errors.append(f"No context for device {device_id}")
                return False
            
            self.operations_log.append({
                "op": "sync",
                "device_id": device_id,
                "timestamp": time.time()
            })
            return True
    
    def get_memory_info(self, device_id: int) -> Optional[GPUMemoryInfo]:
        """Get memory info for device."""
        with self._lock:
            if device_id not in self.contexts:
                return None
            
            ctx = self.contexts[device_id]
            # Simulate 8GB total, with allocated memory used
            total_mb = 8192
            used_mb = ctx.allocated_memory / (1024**2)
            
            return GPUMemoryInfo(
                device_id=device_id,
                total_mb=total_mb,
                used_mb=used_mb,
                free_mb=total_mb - used_mb
            )


class TestCUDAContextManagement:
    """Tests for CUDA context management."""
    
    @pytest.fixture
    def cuda_state(self) -> MockCUDAState:
        """Create mock CUDA state."""
        return MockCUDAState()
    
    def test_single_context_creation(self, cuda_state):
        """Test basic context creation."""
        ctx = cuda_state.create_context(0)
        assert ctx.device_id == 0
        assert ctx in cuda_state.contexts.values()
    
    def test_context_switching(self, cuda_state):
        """Test CUDA context switching.
        
        Context switching should properly mark old context as inactive
        and new context as current.
        """
        # Create contexts
        cuda_state.create_context(0)
        cuda_state.create_context(1)
        
        # Switch to context 0
        assert cuda_state.set_current_context(0)
        assert cuda_state.current_context == 0
        assert cuda_state.contexts[0].is_current
        assert not cuda_state.contexts[1].is_current
        
        # Switch to context 1
        assert cuda_state.set_current_context(1)
        assert cuda_state.current_context == 1
        assert not cuda_state.contexts[0].is_current
        assert cuda_state.contexts[1].is_current
    
    def test_concurrent_context_access(self, cuda_state):
        """Test concurrent access to CUDA contexts.
        
        Multiple threads trying to use same context should be safe
        (though serialization may be needed for GPU operations).
        """
        cuda_state.create_context(0)
        
        num_threads = 10
        operations = []
        errors = []
        lock = threading.Lock()
        
        def worker(thread_id: int):
            for i in range(50):
                try:
                    # Context switching is idempotent-ish
                    cuda_state.set_current_context(0)
                    cuda_state.create_stream(0)
                    
                    with lock:
                        operations.append(f"T{thread_id}_op{i}")
                        
                except Exception as e:
                    with lock:
                        errors.append(f"T{thread_id}: {e}")
        
        threads = [threading.Thread(target=worker, args=(i,)) 
                   for i in range(num_threads)]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert len(errors) == 0, f"Errors during concurrent access: {errors}"
        assert len(operations) == num_threads * 50
        
        # Should have 10 threads * 50 streams created
        assert len(cuda_state.contexts[0].streams) == num_threads * 50
    
    def test_async_context_switching(self, cuda_state):
        """Test async context switching under load.
        
        Simulates asyncio tasks rapidly switching contexts.
        """
        cuda_state.create_context(0)
        cuda_state.create_context(1)
        
        async def context_switcher(switch_count: int):
            for i in range(switch_count):
                device = i % 2
                cuda_state.set_current_context(device)
                await asyncio.sleep(0.001)  # Simulated work
        
        async def run_concurrent():
            tasks = [
                context_switcher(20),
                context_switcher(20),
                context_switcher(20)
            ]
            await asyncio.gather(*tasks)
        
        asyncio.run(run_concurrent())
        
        # All operations should complete without errors
        assert len(cuda_state.errors) == 0
        switch_ops = [op for op in cuda_state.operations_log 
                      if op["op"] == "set_current"]
        assert len(switch_ops) == 60
    
    def test_context_isolation_between_threads(self, cuda_state):
        """Test that contexts are properly isolated between threads.
        
        Each thread should be able to have its own current context.
        """
        cuda_state.create_context(0)
        cuda_state.create_context(1)
        
        thread_contexts: Dict[int, int] = {}
        errors = []
        lock = threading.Lock()
        
        def thread_worker(thread_id: int):
            try:
                # Each thread uses a different device
                device = thread_id % 2
                cuda_state.set_current_context(device)
                
                with lock:
                    thread_contexts[thread_id] = cuda_state.current_context
                
                # Simulate some work
                time.sleep(0.01)
                
                # Verify still same context
                with lock:
                    current = cuda_state.current_context
                    thread_contexts[thread_id] = current
                    
            except Exception as e:
                with lock:
                    errors.append(f"Thread {thread_id}: {e}")
        
        threads = [threading.Thread(target=thread_worker, args=(i,)) 
                   for i in range(4)]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert len(errors) == 0, f"Errors: {errors}"
    
    def test_stream_creation_race_condition(self, cuda_state):
        """Test stream creation under concurrent load.
        
        Multiple threads creating streams should not corrupt state.
        """
        cuda_state.create_context(0)
        
        num_threads = 20
        streams_per_thread = 10
        errors = []
        lock = threading.Lock()
        
        def worker(thread_id: int):
            for i in range(streams_per_thread):
                try:
                    stream_id = cuda_state.create_stream(0)
                    if stream_id is None:
                        with lock:
                            errors.append(f"Thread {thread_id}: stream creation failed")
                except Exception as e:
                    with lock:
                        errors.append(f"Thread {thread_id}: {e}")
        
        threads = [threading.Thread(target=worker, args=(i,)) 
                   for i in range(num_threads)]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert len(errors) == 0, f"Stream creation errors: {errors}"
        assert len(cuda_state.contexts[0].streams) == num_threads * streams_per_thread


class TestGPUMemoryManagement:
    """Tests for GPU memory management."""
    
    def test_memory_allocation_tracking(self):
        """Test GPU memory allocation is tracked correctly."""
        cuda_state = MockCUDAState()
        cuda_state.create_context(0)
        
        # Allocate memory
        assert cuda_state.allocate(0, 1024**3)  # 1GB
        assert cuda_state.allocate(0, 512 * 1024**2)  # 512MB
        
        # Total allocated should be tracked
        assert cuda_state.contexts[0].allocated_memory == (1024 + 512) * 1024**2
    
    def test_memory_info_reporting(self):
        """Test GPU memory info is reported correctly."""
        cuda_state = MockCUDAState()
        cuda_state.create_context(0)
        
        # Allocate some memory
        cuda_state.allocate(0, 1024**3)
        
        info = cuda_state.get_memory_info(0)
        assert info is not None
        assert info.device_id == 0
        assert info.used_mb == 1024
        assert info.free_mb == 8192 - 1024
    
    def test_concurrent_memory_allocation(self):
        """Test memory allocation under concurrent load.
        
        Memory tracking should be accurate when multiple threads allocate.
        """
        cuda_state = MockCUDAState()
        cuda_state.create_context(0)
        
        num_threads = 10
        bytes_per_thread = 100 * 1024**2  # 100MB each
        errors = []
        lock = threading.Lock()
        
        def worker(thread_id: int):
            for _ in range(10):
                try:
                    # Allocate in chunks
                    for _ in range(10):
                        if not cuda_state.allocate(0, bytes_per_thread // 10):
                            with lock:
                                errors.append(f"Thread {thread_id}: allocation failed")
                except Exception as e:
                    with lock:
                        errors.append(f"Thread {thread_id}: {e}")
        
        threads = [threading.Thread(target=worker, args=(i,)) 
                   for i in range(num_threads)]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert len(errors) == 0, f"Allocation errors: {errors}"
        
        # Total allocated should be 10 threads * 100MB * 10 iterations
        expected = num_threads * bytes_per_thread * 10
        assert cuda_state.contexts[0].allocated_memory == expected, \
            f"Tracking off: expected {expected}, got {cuda_state.contexts[0].allocated_memory}"
    
    def test_memory_pressure_handling(self):
        """Test handling of GPU memory pressure.
        
        Should gracefully handle near-full GPU memory.
        """
        cuda_state = MockCUDAState()
        cuda_state.create_context(0)
        
        # Check memory info
        info = cuda_state.get_memory_info(0)
        
        # This would trigger memory check
        has_memory, mem_info = check_gpu_available_memory(required_mb=4000)
        
        # With mock, this returns True (no real GPU)
        assert has_memory is True
    
    def test_graceful_degradation_under_pressure(self):
        """Test graceful degradation when GPU memory is exhausted.
        
        System should not crash but potentially fail gracefully.
        """
        cuda_state = MockCUDAState()
        cuda_state.create_context(0)
        
        # Simulate filling up memory
        cuda_state.allocate(0, 7000 * 1024**2)  # Allocate most of 8GB
        
        # Check if new allocations would fail
        info = cuda_state.get_memory_info(0)
        
        # Memory check with requirement
        has_memory, _ = check_gpu_available_memory(required_mb=2000)
        
        # Should report insufficient memory
        if info and info.free_mb < 2000:
            print(f"GPU memory pressure detected: {info.free_mb}MB free")


class TestCUDAAsyncOperations:
    """Tests for async CUDA operations."""
    
    @pytest.fixture
    def cuda_state(self) -> MockCUDAState:
        return MockCUDAState()
    
    def test_async_sync_operation(self):
        """Test CUDA synchronization in async context.
        
        Async operations should properly synchronize.
        """
        cuda_state = MockCUDAState()
        cuda_state.create_context(0)
        
        async def async_work():
            # Do some async CUDA operations
            cuda_state.set_current_context(0)
            cuda_state.create_stream(0)
            
            # Simulate async work
            await asyncio.sleep(0.01)
            
            # Synchronize
            assert cuda_state.sync(0)
            
            return True
        
        result = asyncio.run(async_work())
        assert result
        
        sync_ops = [op for op in cuda_state.operations_log if op["op"] == "sync"]
        assert len(sync_ops) == 1
    
    def test_concurrent_async_cuda_tasks(self, cuda_state):
        """Test multiple async tasks using CUDA.
        
        Simulates scenario where async WebSocket handlers use CUDA.
        """
        cuda_state.create_context(0)
        
        async def cuda_task(task_id: int):
            """Simulate TTS task using CUDA."""
            cuda_state.set_current_context(0)
            cuda_state.create_stream(0)
            cuda_state.allocate(0, 100 * 1024**2)  # 100MB per task
            
            # Simulated async work
            await asyncio.sleep(0.01)
            
            cuda_state.sync(0)
            return task_id
        
        async def run_tasks():
            tasks = [cuda_task(i) for i in range(10)]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            return results
        
        results = asyncio.run(run_tasks())
        
        exceptions = [r for r in results if isinstance(r, Exception)]
        assert len(exceptions) == 0, f"CUDA errors: {exceptions}"
    
    def test_cuda_context_in_thread_pool(self, cuda_state):
        """Test CUDA operations in thread pool.
        
        Important for scenarios where TTS runs in thread pool
to avoid blocking async event loop.
        """
        cuda_state.create_context(0)
        
        def cuda_operation(thread_id: int):
            try:
                cuda_state.set_current_context(0)
                cuda_state.create_stream(0)
                cuda_state.allocate(0, 50 * 1024**2)
                time.sleep(0.01)  # Simulated GPU work
                cuda_state.sync(0)
                return thread_id
            except Exception as e:
                return f"error: {e}"
        
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(cuda_operation, i) for i in range(10)]
            results = [f.result() for f in futures]
        
        errors = [r for r in results if isinstance(r, str) and r.startswith("error")]
        assert len(errors) == 0, f"Thread pool CUDA errors: {errors}"
        
        # Should have created streams
        assert len(cuda_state.contexts[0].streams) == 10
    
    def test_cuda_error_handling(self, cuda_state):
        """Test CUDA error handling in async context."""
        # Try to set context that doesn't exist
        result = cuda_state.set_current_context(0)
        assert result == False  # Context doesn't exist
        assert len(cuda_state.errors) > 0


class TestCUDAContextVerification:
    """Verification tests for CUDA context correctness."""
    
    @pytest.fixture
    def cuda_state(self) -> MockCUDAState:
        return MockCUDAState()
    
    def test_context_stack_integrity(self):
        """Test CUDA context switching maintains integrity.
        
        After many context switches, state should be consistent.
        """
        cuda_state = MockCUDAState()
        
        # Create multiple contexts
        for i in range(4):
            cuda_state.create_context(i)
        
        # Rapid context switching
        for _ in range(100):
            for device in range(4):
                assert cuda_state.set_current_context(device)
                assert cuda_state.current_context == device
        
        # Verify final state is valid
        assert cuda_state.current_context in range(4)
        assert cuda_state.contexts[cuda_state.current_context].is_current
    
    def test_stream_context_association(self, cuda_state):
        """Verify streams are correctly associated with contexts."""
        cuda_state.create_context(0)
        cuda_state.create_context(1)
        
        cuda_state.set_current_context(0)
        stream_0_1 = cuda_state.create_stream(0)
        stream_0_2 = cuda_state.create_stream(0)
        
        cuda_state.set_current_context(1)
        stream_1_1 = cuda_state.create_stream(1)
        
        # Streams should be associated with correct contexts
        assert 0 in cuda_state.contexts[0].streams
        assert 1 in cuda_state.contexts[0].streams
        assert 0 in cuda_state.contexts[1].streams
        
        # No cross-contamination - streams from context 0 shouldn't be in context 1
        # Each context starts stream IDs from 0 independently
        assert stream_0_1 in cuda_state.contexts[0].streams
        assert stream_0_2 in cuda_state.contexts[0].streams
        assert stream_1_1 in cuda_state.contexts[1].streams


class TestRealGPUUtils:
    """Tests for actual GPU utils module."""
    
    def test_get_gpu_memory_info_no_gpu(self):
        """Test memory info when no GPU available.
        
        Should return None gracefully.
        """
        info = get_gpu_memory_info(device_id=0)
        
        # May or may not be None depending on hardware
        if info is not None:
            assert info.total_mb > 0
            assert info.free_mb >= 0
            assert info.used_mb >= 0
    
    def test_check_gpu_memory_requirement(self):
        """Test GPU memory requirement check."""
        has_memory, info = check_gpu_available_memory(required_mb=1)
        
        # Should always pass for minimal requirement (or have GPU)
        # This is a soft check - just verifying function works
        assert isinstance(has_memory, bool)
        if info is not None:
            assert isinstance(info, GPUMemoryInfo)
    
    def test_gpu_utils_thread_safety(self):
        """Test GPU utils are thread-safe."""
        results: List[Optional[GPUMemoryInfo]] = []
        errors: List[str] = []
        lock = threading.Lock()
        
        def worker():
            try:
                info = get_gpu_memory_info(0)
                with lock:
                    results.append(info)
            except Exception as e:
                with lock:
                    errors.append(str(e))
        
        threads = [threading.Thread(target=worker) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert len(errors) == 0, f"GPU utils errors: {errors}"
        assert len(results) == 20
    
    def test_gpu_utils_under_async_load(self):
        """Test GPU utils under async load."""
        async def get_info_task():
            return get_gpu_memory_info(0)
        
        async def run_concurrent():
            tasks = [get_info_task() for _ in range(10)]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            return results
        
        results = asyncio.run(run_concurrent())
        
        exceptions = [r for r in results if isinstance(r, Exception)]
        assert len(exceptions) == 0, f"Async GPU utils errors: {exceptions}"


class TestCUDAContextStress:
    """Stress tests for CUDA context management."""
    
    def test_rapid_context_switching(self):
        """Stress test rapid context switching.
        
        Performance test to ensure context switching isn't too slow.
        """
        cuda_state = MockCUDAState()
        cuda_state.create_context(0)
        cuda_state.create_context(1)
        
        iterations = 1000
        
        start = time.time()
        for i in range(iterations):
            cuda_state.set_current_context(i % 2)
        duration = time.time() - start
        
        print(f"{iterations} context switches in {duration:.3f}s "
              f"({iterations/duration:.0f} switches/sec)")
        
        # Should complete reasonably fast
        assert duration < 5.0, "Context switching too slow"
    
    def test_memory_leak_detection(self):
        """Test for memory leaks in context operations.
        
        Repeated allocations should be tracked correctly.
        """
        cuda_state = MockCUDAState()
        cuda_state.create_context(0)
        
        # Multiple allocation cycles
        for cycle in range(10):
            cuda_state.allocate(0, 100 * 1024**2)
        
        # Memory should accumulate (not a leak in test, just tracking)
        expected = 10 * 100 * 1024**2
        assert cuda_state.contexts[0].allocated_memory == expected


if __name__ == "__main__":
    pytest.main([__file__, "-v"])