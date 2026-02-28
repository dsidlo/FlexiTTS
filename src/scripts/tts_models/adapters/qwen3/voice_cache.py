"""LRU Voice Prompt Cache for Qwen3-TTS."""
from __future__ import annotations

import threading
from typing import Any, Optional
from collections import OrderedDict
import logging

logger = logging.getLogger('tts_models.voice_cache')


class LRUVoiceCache:
    """LRU cache for voice cloning prompts.
    
    Configured via story-config.yml 'max_voice_cache_size' (default 10).
    
    Thread Safety Status: THREAD-SAFE
    
    All cache operations are protected by a threading.Lock to ensure
    thread-safe access in multi-threaded environments.
    """
    
    def __init__(self, maxsize: int = 10):
        self.maxsize = max(maxsize, 1)
        self._cache: OrderedDict[str, Any] = OrderedDict()
        self._hits = 0
        self._misses = 0
        self._lock = threading.Lock()  # Thread-safe lock for cache operations
    
    def get(self, key: str) -> Optional[Any]:
        """Get item from cache, move to end (most recent)."""
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                self._hits += 1
                logger.debug(f"Voice cache HIT: {key}")
                return self._cache[key]
            self._misses += 1
            logger.debug(f"Voice cache MISS: {key}")
            return None
    
    def put(self, key: str, value: Any) -> None:
        """Add item, evict oldest if at capacity."""
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                return
            
            if len(self._cache) >= self.maxsize:
                oldest = next(iter(self._cache))
                logger.info(f"Voice cache EVICT: {oldest} (maxsize={self.maxsize})")
                del self._cache[oldest]
            
            self._cache[key] = value
            logger.debug(f"Voice cache INSERT: {key} (size={len(self._cache)})")
    
    def clear(self) -> None:
        """Clear all cached prompts."""
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            logger.info(f"Voice cache CLEARED ({count} items)")
    
    @property
    def stats(self) -> dict:
        """Cache statistics."""
        with self._lock:
            total = self._hits + self._misses
            hit_rate = self._hits / total if total > 0 else 0
            return {
                'size': len(self._cache),
                'maxsize': self.maxsize,
                'hits': self._hits,
                'misses': self._misses,
                'hit_rate': hit_rate
            }
