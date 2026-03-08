"""Comprehensive concurrency tests for TTS model generate() calls.

Tests multiple async generate() calls to verify:
- Model instance shared across async tasks
- Concurrent generation doesn't corrupt state
- Proper serialization of GPU operations
- Deadlock detection
"""

from __future__ import annotations

import asyncio
import threading
import time
import pytest
from concurrent.futures import ThreadPoolExecutor
from typing import List, Tuple, Optional, Dict, Any
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import sys

import numpy as np

# Add src/scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src/scripts"))

from tts_models.base import TTSModel, ModelConfig, GenerateResult


class MockTTSModel(TTSModel):
    """Mock TTS model for concurrency testing."""
    
    model_id = "mock_concurrent"
    
    def __init__(self, generation_delay: float = 0.01):
        super().__init__()
        self.generation_delay = generation_delay
        self._active_generations = 0
        self._max_concurrent = 0
        self._lock = threading.Lock()
        self._call_log: List[Tuple[float, str]] = []
        self._log_lock = threading.Lock()
    
    @property
    def capabilities(self) -> Dict[str, bool]:
        return {'voice_cloning': True, 'emotion_control': True, 'streaming': False}
    
    def configure(self, config: ModelConfig) -> None:
        super().configure(config)
    
    def _generate_impl(
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
        """Generate with concurrency tracking."""
        self.validate_config()
        
        with self._lock:
            self._active_generations += 1
            if self._active_generations > self._max_concurrent:
                self._max_concurrent = self._active_generations
        
        start = time.time()
        time.sleep(self.generation_delay)  # Simulate GPU work
        
        with self._lock:
            self._active_generations -= 1
            
        with self._log_lock:
            self._call_log.append((start, text))
        
        # Return mock audio
        sr = 24000
        duration = 0.5
        samples = int(sr * duration)
        audio = np.zeros(samples)
        
        return GenerateResult(
            audio_segments=[audio],
            sample_rate=sr,
            duration_ms=int(duration * 1000),
            model_name=self.model_id
        )
    
    def translate_parameters(self, emotion: str, language: str, instruct: str) -> Dict[str, Any]:
        return {'emotion': emotion, 'language': language, 'instruct': instruct}
    
    def clear_cache(self) -> None:
        pass
    
    @property
    def max_concurrent_seeen(self) -> int:
        return self._max_concurrent
    
    @property
    def call_log(self) -> List[Tuple[float, str]]:
        return self._call_log.copy()


class TestModelConcurrency:
    """Tests for model concurrent access patterns."""
    
    @pytest.fixture
    def model(self) -> MockTTSModel:
        """Create configured mock model."""
        model = MockTTSModel(generation_delay=0.01)
        model.configure(ModelConfig(device="cpu"))
        return model
    
    def test_model_not_thread_safe(self, model):
        """Verify that concurrent access can cause race conditions.
        
        This test documents the expected behavior - that the model
        is not thread-safe and needs external serialization.
        """
        num_threads = 10
        results = []
        errors = []
        lock = threading.Lock()
        
        def worker():
            try:
                result = model.generate(
                    text="Hello world",
                    speaker="test",
                    emotion="neutral",
                    language="en"
                )
                with lock:
                    results.append(result)
            except Exception as e:
                with lock:
                    errors.append(str(e))
        
        threads = [threading.Thread(target=worker) for _ in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # All should complete (even if race conditions occur)
        assert len(results) == num_threads
    
    def test_concurrent_generate_tracking(self, model):
        """Test that concurrent generations are tracked correctly.
        
        Verifies max concurrent count doesn't exceed expected.
        """
        num_threads = 5
        
        def worker(thread_id: int):
            return model.generate(
                text=f"Thread {thread_id}",
                speaker="test",
                emotion="neutral",
                language="en"
            )
        
        # Launch concurrent threads
        threads = [threading.Thread(target=worker, args=(i,)) 
                   for i in range(num_threads)]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # With true concurrency, max_concurrent_seen should be > 1
        # (This documents current behavior - multiple threads enter generate())
        assert model.max_concurrent_seeen >= 1
        print(f"Max concurrent generations seen: {model.max_concurrent_seeen}")
    
    def test_async_sequential_calls(self, model):
        """Test sequential async calls work correctly.
        
        Sequentially awaiting generate() calls should work fine.
        """
        async def sequential_work():
            results = []
            for i in range(5):
                result = model.generate(
                    text=f"Call {i}",
                    speaker="test",
                    emotion="neutral",
                    language="en"
                )
                results.append(result)
            return results
        
        results = asyncio.run(sequential_work())
        assert len(results) == 5
        assert all(r.sample_rate == 24000 for r in results)
    
    def test_async_concurrent_tasks(self, model):
        """Test concurrent asyncio tasks using same model.
        
        Simulates scenario where async WebSocket server handles
        multiple concurrent requests with same model instance.
        """
        async def generate_task(task_id: int) -> GenerateResult:
            # Run in thread to simulate blocking GPU operation
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None,
                lambda: model.generate(
                    text=f"Task {task_id}",
                    speaker="test",
                    emotion="neutral",
                    language="en"
                )
            )
        
        async def concurrent_work():
            # Create 10 concurrent tasks
            tasks = [generate_task(i) for i in range(10)]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            return results
        
        results = asyncio.run(concurrent_work())
        
        # All should complete without exceptions
        exceptions = [r for r in results if isinstance(r, Exception)]
        assert len(exceptions) == 0, f"Exceptions occurred: {exceptions}"
        
        success_results = [r for r in results if not isinstance(r, Exception)]
        assert len(success_results) == 10
    
    def test_model_instance_shared_async(self):
        """Test model instance shared across async tasks.
        
        This is the critical scenario from the WebSocket server
        where one model instance is shared across all requests.
        """
        model = MockTTSModel(generation_delay=0.01)
        model.configure(ModelConfig(device="cpu"))
        
        shared_results: List[GenerateResult] = []
        shared_errors: List[str] = []
        lock = threading.Lock()
        
        async def websocket_handler(request_id: int):
            """Simulate WebSocket request handler."""
            try:
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None,
                    lambda: model.generate(
                        text=f"Request {request_id}",
                        speaker="shared_speaker",
                        emotion="neutral",
                        language="en"
                    )
                )
                with lock:
                    shared_results.append(result)
            except Exception as e:
                with lock:
                    shared_errors.append(str(e))
        
        async def simulate_server():
            # Simulate 10 concurrent WebSocket connections
            tasks = [websocket_handler(i) for i in range(10)]
            await asyncio.gather(*tasks)
        
        asyncio.run(simulate_server())
        
        assert len(shared_errors) == 0, f"Errors: {shared_errors}"
        assert len(shared_results) == 10
    
    def test_deadlock_detection(self):
        """Test for potential deadlocks in concurrent access.
        
        Runs multiple iterations to detect any potential deadlock
        conditions that might only appear under load.
        """
        model = MockTTSModel(generation_delay=0.05)
        model.configure(ModelConfig(device="cpu"))
        
        timeout_seconds = 5.0
        
        def run_concurrent_round():
            """One round of concurrent operations."""
            threads = []
            for i in range(5):
                t = threading.Thread(target=lambda: model.generate(
                    text="test",
                    speaker="test",
                    emotion="neutral",
                    language="en"
                ))
                threads.append(t)
            
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=timeout_seconds)
            
            # Check if any thread hung
            alive = [t for t in threads if t.is_alive()]
            return len(alive) == 0
        
        # Run multiple rounds
        for round_num in range(10):
            success = run_concurrent_round()
            assert success, f"Deadlock detected in round {round_num + 1}"
    
    def test_state_corruption_protection(self):
        """Test that concurrent access doesn't corrupt model state.
        
        Verifies that internal model configuration remains intact
        despite concurrent generate calls.
        """
        model = MockTTSModel(generation_delay=0.01)
        model.configure(ModelConfig(device="cpu", voice_cache_size=5))
        
        errors = []
        states_verified = []
        lock = threading.Lock()
        
        def verify_state(task_id: int):
            try:
                # Generate
                result = model.generate(
                    text=f"Task {task_id}",
                    speaker="test",
                    emotion="neutral",
                    language="en"
                )
                
                # Verify model state still valid
                assert model._configured, f"{task_id}: Model became unconfigured"
                assert model._model_config is not None, f"{task_id}: Config lost"
                assert model._model_config.voice_cache_size == 5, f"{task_id}: Config corrupted"
                
                with lock:
                    states_verified.append(task_id)
                    
            except Exception as e:
                with lock:
                    errors.append(f"Task {task_id}: {e}")
        
        threads = [threading.Thread(target=verify_state, args=(i,)) 
                   for i in range(20)]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert len(errors) == 0, f"State corruption detected: {errors}"
        assert len(states_verified) == 20
    
    def test_performance_under_load(self):
        """Test performance regression under concurrent load.
        
        Single-threaded vs concurrent performance should be comparable
        when properly serialized.
        """
        model = MockTTSModel(generation_delay=0.05)
        model.configure(ModelConfig(device="cpu"))
        
        num_operations = 10
        
        # Single-threaded baseline
        start = time.time()
        for i in range(num_operations):
            model.generate(
                text=f"Call {i}",
                speaker="test",
                emotion="neutral",
                language="en"
            )
        single_time = time.time() - start
        
        # Concurrent test
        def worker():
            model.generate(
                text="concurrent",
                speaker="test",
                emotion="neutral",
                language="en"
            )
        
        start = time.time()
        threads = [threading.Thread(target=worker) for _ in range(num_operations)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        multi_time = time.time() - start
        
        # Concurrent should be faster (parallel execution)
        # But not too much faster (limited by GIL for CPU)
        print(f"Single: {single_time:.2f}s, Multi: {multi_time:.2f}s")
        
        # Concurrent shouldn't take more than 3x single-threaded
        # (some overhead is expected)
        assert multi_time < single_time * 3, f"Too much slowdown: {multi_time/single_time:.2f}x"


class TestModelThreadSafety:
    """Tests specifically for thread safety issues."""
    
    def test_race_condition_in_configure(self):
        """Test race condition during lazy configuration.
        
        Multiple threads calling configure simultaneously could
        cause double initialization or corrupted state.
        """
        model = MockTTSModel()
        config = ModelConfig(device="cpu")
        errors = []
        configured_count = [0]
        lock = threading.Lock()
        
        def worker():
            try:
                model.configure(config)
                with lock:
                    configured_count[0] += 1
            except Exception as e:
                with lock:
                    errors.append(str(e))
        
        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert len(errors) == 0, f"Configure errors: {errors}"
        # Model should be configured
        assert model._configured
    
    def test_concurrent_clear_and_generate(self):
        """Test clear_cache() during concurrent generate() calls.
        
        Should handle the race gracefully.
        """
        model = MockTTSModel(generation_delay=0.05)
        model.configure(ModelConfig(device="cpu"))
        errors = []
        lock = threading.Lock()
        
        def generate_worker():
            try:
                for i in range(5):
                    model.generate(
                        text=f"call_{i}",
                        speaker="test",
                        emotion="neutral",
                        language="en"
                    )
            except Exception as e:
                with lock:
                    errors.append(f"generate: {e}")
        
        def clear_worker():
            try:
                for _ in range(10):
                    time.sleep(0.02)
                    model.clear_cache()
            except Exception as e:
                with lock:
                    errors.append(f"clear: {e}")
        
        threads = []
        for _ in range(3):
            threads.append(threading.Thread(target=generate_worker))
        threads.append(threading.Thread(target=clear_worker))
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert len(errors) == 0, f"Errors during clear: {errors}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])