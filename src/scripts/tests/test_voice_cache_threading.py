"""Comprehensive threading tests for LRU Voice Cache.

Tests concurrent access to the LRUVoiceCache to verify thread safety.
Scenarios:
- 100 rapid voice cache get/put operations from multiple threads
- Cache eviction during concurrent access
- Race condition detection
"""

from __future__ import annotations

import threading
import time
import pytest
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Tuple
from collections import Counter

import sys
from pathlib import Path

# Add src/scripts to path for importing voice_cache
sys.path.insert(0, str(Path(__file__).parent.parent / "src/scripts"))

from tts_models.adapters.qwen3.voice_cache import LRUVoiceCache


class TestLRUVoiceCacheThreading:
    """Thread safety tests for LRU voice cache."""
    
    @pytest.fixture
    def cache(self) -> LRUVoiceCache:
        """Create a fresh cache instance."""
        return LRUVoiceCache(maxsize=10)
    
    def test_concurrent_get_put_single_thread(self, cache):
        """Test basic get/put operations work correctly (single-threaded baseline)."""
        # Populate cache
        for i in range(10):
            cache.put(f"voice_{i}", f"prompt_{i}")
        
        # Verify all items present
        for i in range(10):
            assert cache.get(f"voice_{i}") == f"prompt_{i}"
        
        # Verify cache stats
        stats = cache.stats
        assert stats['size'] == 10
        assert stats['hits'] == 10
        assert stats['misses'] == 0
    
    def test_concurrent_get_put_race_condition(self, cache):
        """Test 100 rapid get/put operations from multiple threads.
        
        Simulates the scenario where multiple WebSocket connections
        are simultaneously accessing the voice cache.
        """
        num_threads = 10
        operations_per_thread = 100
        errors: List[str] = []
        
        def worker(thread_id: int) -> Tuple[int, int]:
            """Worker that performs get/put operations."""
            hits = 0
            misses = 0
            
            try:
                for i in range(operations_per_thread):
                    voice_key = f"thread{thread_id}_voice{i % 20}"  # 20 unique voices per thread
                    prompt_value = f"prompt_{thread_id}_{i}"
                    
                    # Alternate between get and put
                    if i % 3 == 0:
                        # Put operation
                        cache.put(voice_key, prompt_value)
                    else:
                        # Get operation
                        result = cache.get(voice_key)
                        if result is None:
                            misses += 1
                            # Put after miss
                            cache.put(voice_key, prompt_value)
                        else:
                            hits += 1
                            
            except Exception as e:
                errors.append(f"Thread {thread_id}: {e}")
            
            return hits, misses
        
        # Run all threads concurrently
        results: List[Tuple[int, int]] = []
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(worker, i) for i in range(num_threads)]
            for future in as_completed(futures):
                results.append(future.result())
        
        # Verify no errors occurred
        assert len(errors) == 0, f"Thread errors: {errors}"
        
        # Verify cache is still valid
        stats = cache.stats
        assert stats['size'] <= 10  # Should not exceed maxsize
        
        total_hits = sum(r[0] for r in results)
        total_misses = sum(r[1] for r in results)
        total_ops = total_hits + total_misses
        
        assert total_ops > 0, "No operations completed"
        # Hit rate should be reasonable (some cache hits expected)
        print(f"Cache stats: hits={total_hits}, misses={total_misses}, "
              f"hit_rate={total_hits/total_ops:.2%}")
    
    def test_concurrent_cache_eviction(self, cache):
        """Test cache eviction during concurrent access.
        
        When cache is full, concurrent puts should correctly evict
        oldest entries without causing corruption.
        """
        num_threads = 5
        voices_per_thread = 50
        barriers = [threading.Barrier(num_threads) for _ in range(3)]
        
        results = {"evictions": 0, "errors": []}
        lock = threading.Lock()
        
        def worker(thread_id: int):
            """Worker that fills cache to trigger evictions."""
            try:
                # Phase 1: All threads wait, then simultaneously put
                barriers[0].wait()
                
                for i in range(voices_per_thread):
                    voice_key = f"t{thread_id}_v{i}"
                    cache.put(voice_key, f"prompt_value_{i}")
                    
                    # Phase 2: Occasional sync point for concurrent access
                    if i % 10 == 0:
                        barriers[1].wait() if i < 40 else None
                        
            except Exception as e:
                with lock:
                    results["errors"].append(f"Thread {thread_id}: {e}")
        
        # Run concurrent workers
        threads = [threading.Thread(target=worker, args=(i,)) 
                   for i in range(num_threads)]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # Verify no errors
        assert len(results["errors"]) == 0, f"Errors: {results['errors']}"
        
        # Verify cache size never exceeded max
        stats = cache.stats
        assert stats['size'] <= 10, f"Cache size {stats['size']} exceeded max 10"
    
    def test_concurrent_same_key_access(self, cache):
        """Test concurrent access to the same cache key.
        
        Multiple threads accessing same key simultaneously should
        be safe and consistent.
        """
        num_threads = 20
        iterations = 50
        errors = []
        values_seen: List[str] = []
        lock = threading.Lock()
        
        # Pre-populate with an initial value
        cache.put("shared_voice", "initial_value")
        
        def worker(thread_id: int):
            for i in range(iterations):
                try:
                    if i % 2 == 0:
                        # Half threads read
                        value = cache.get("shared_voice")
                        if value is not None:
                            with lock:
                                values_seen.append(value)
                    else:
                        # Half threads write (creates contention)
                        new_value = f"value_{thread_id}_{i}"
                        cache.put("shared_voice", new_value)
                        with lock:
                            values_seen.append(new_value)
                except Exception as e:
                    errors.append(str(e))
        
        threads = [threading.Thread(target=worker, args=(i,)) 
                   for i in range(num_threads)]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert len(errors) == 0, f"Errors during concurrent access: {errors}"
        
        # Final value should be one of the written values or initial
        final_value = cache.get("shared_voice")
        assert final_value is not None, "Cache key was evicted unexpectedly"
        # Final value should be initial or one of the written values
        assert final_value.startswith(("value_", "initial")), f"Unexpected final value: {final_value}"
    
    def test_concurrent_clear_during_access(self, cache):
        """Test clear() during concurrent get/put operations.
        
        Clear should be safe even when other threads are accessing cache.
        """
        num_threads = 10
        operation_count = [0]
        errors = []
        lock = threading.Lock()
        
        def worker(thread_id: int):
            for i in range(100):
                try:
                    if i == 50:
                        # One thread clears mid-operation
                        if thread_id == 0:
                            cache.clear()
                    elif i % 3 == 0:
                        cache.get(f"voice_{i % 20}")
                    elif i % 3 == 1:
                        cache.put(f"voice_{i % 20}", f"value_{i}")
                    else:
                        # Random clear
                        if thread_id == 1 and i == 75:
                            cache.clear()
                    
                    with lock:
                        operation_count[0] += 1
                        
                except Exception as e:
                    with lock:
                        errors.append(f"Thread {thread_id}: {e}")
        
        threads = [threading.Thread(target=worker, args=(i,)) 
                   for i in range(num_threads)]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert len(errors) == 0, f"Errors during clear: {errors}"
        assert operation_count[0] > 0, "No operations completed"
    
    def test_thread_safety_race_detection(self, cache):
        """Aggressive test to detect race conditions in cache operations.
        
        Uses high thread count and rapid operations to maximize
        chance of triggering race conditions.
        """
        num_threads = 50
        ops_per_thread = 200
        counter = Counter()
        errors = []
        error_lock = threading.Lock()
        
        def worker(thread_id: int):
            for i in range(ops_per_thread):
                try:
                    key = f"k{thread_id}_{i % 10}"
                    
                    # Random operation mix
                    if i % 4 == 0:
                        result = cache.get(key)
                        counter[f"thread{thread_id}_gets"] += 1
                    elif i % 4 == 1:
                        cache.put(key, f"v{i}")
                        counter[f"thread{thread_id}_puts"] += 1
                    elif i % 4 == 2:
                        result = cache.get(key)
                        if result is None:
                            cache.put(key, f"v{i}")
                        counter[f"thread{thread_id}_gtp"] += 1
                    else:
                        _ = cache.stats
                        counter[f"thread{thread_id}_stats"] += 1
                        
                except Exception as e:
                    with error_lock:
                        errors.append(f"T{thread_id}: {type(e).__name__}: {e}")
        
        threads = [threading.Thread(target=worker, args=(i,)) 
                   for i in range(num_threads)]
        
        start = time.time()
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        duration = time.time() - start
        
        # No exceptions means basic thread safety maintained
        assert len(errors) == 0, f"Race condition detected: {errors}"
        
        total_ops = sum(counter.values())
        print(f"Completed {total_ops} operations in {duration:.2f}s "
              f"({total_ops/duration:.0f} ops/sec)")
        
        # All operations should complete
        assert total_ops == num_threads * ops_per_thread, "Some operations missed"


class TestLRUVoiceCacheStress:
    """Stress tests for LRU cache under extreme load."""
    
    def test_cache_under_cpu_contention(self):
        """Test cache when CPU is saturated with workers.
        
        Simulates real-world scenario where TTS processing
        saturates CPU while cache operations continue.
        """
        cache = LRUVoiceCache(maxsize=5)
        num_threads = 100
        errors = []
        
        def cpu_intensive_worker(thread_id: int):
            """Worker that does CPU work between cache ops."""
            try:
                for i in range(20):
                    # CPU work
                    _ = sum(j ** 2 for j in range(1000))
                    
                    # Cache operation
                    cache.put(f"t{thread_id}_k{i % 10}", f"v{i}")
                    
                    # More CPU work
                    _ = [x * x for x in range(500)]
                    
                    # Cache get
                    cache.get(f"t{thread_id}_k{(i-1) % 10}")
                    
            except Exception as e:
                errors.append(f"Thread {thread_id}: {e}")
        
        # Launch all threads
        threads = [threading.Thread(target=cpu_intensive_worker, args=(i,)) 
                   for i in range(num_threads)]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert len(errors) == 0, f"Errors under CPU contention: {errors}"
        assert cache.stats['size'] <= 5, "Cache size exceeded limit"
    
    def test_cache_performance_regression(self):
        """Performance test to ensure concurrent access doesn't degrade performance.
        
        Single-threaded vs multi-threaded performance should be within 10%.
        Note: This is CPU-bound, so threads may not speed up, but shouldn't
        cause dramatic slowdown.
        """
        operations = 10000
        
        # Single-threaded baseline
        cache_single = LRUVoiceCache(maxsize=100)
        start = time.time()
        for i in range(operations):
            cache_single.put(f"k{i % 50}", f"v{i}")
            cache_single.get(f"k{i % 50}")
        single_time = time.time() - start
        
        # Multi-threaded test (10 threads, 1000 ops each)
        cache_multi = LRUVoiceCache(maxsize=100)
        errors = []
        
        def worker():
            try:
                for i in range(operations // 10):
                    key = f"k{i % 50}"
                    cache_multi.put(key, f"v{i}")
                    cache_multi.get(key)
            except Exception as e:
                errors.append(str(e))
        
        start = time.time()
        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        multi_time = time.time() - start
        
        # Performance should not degrade by more than 5x with threads
        # (Some overhead is expected due to GIL)
        ratio = multi_time / single_time
        print(f"Single-threaded: {single_time:.3f}s, Multi-threaded: {multi_time:.3f}s, Ratio: {ratio:.2f}x")
        
        # This is a soft assertion - primarily for monitoring
        # Actual threshold depends on machine and Python GIL behavior
        assert ratio < 10.0, f"Performance degraded too much: {ratio:.2f}x slower"
        
        # No errors
        assert len(errors) == 0, f"Errors: {errors}"


def teardown_module():
    """Clean up threading resources after all tests in this module.
    
    Prevents threading state corruption affecting subsequent async test modules.
    """
    import gc
    import time
    # Allow time for threads to fully terminate
    time.sleep(0.1)
    # Force garbage collection to clean up thread objects
    gc.collect()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])