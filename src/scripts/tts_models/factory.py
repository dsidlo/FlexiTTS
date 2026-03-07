"""Factory for creating TTS model instances."""
from __future__ import annotations

import importlib
import threading
from pathlib import Path
from typing import Dict, Type, Optional
import logging

from .base import TTSModel, ModelConfig
from .utils.gpu_utils import check_gpu_available_memory

logger = logging.getLogger('tts_models.factory')


class ModelFactory:
    """Factory for creating TTS model instances.
    
    Thread Safety Status: THREAD-SAFE
    
    All factory operations are protected by a class-level RLock
    to ensure thread-safe singleton behavior.
    """
    
    _registry: Dict[str, Type[TTSModel]] = {}
    _instances: Dict[str, TTSModel] = {}
    _lock = threading.RLock()  # Re-entrant lock to prevent deadlock with auto-registration
    
    # Minimum VRAM required per model (MB)
    _MODEL_MEMORY_REQUIREMENTS = {
        'qwen3': 4000,
        'qwen3-base': 4000,
        'turtle': 2000,
    }
    
    @classmethod
    def register(cls, model_id: str, model_class: Type[TTSModel]) -> None:
        """Register a model class (thread-safe)."""
        with cls._lock:
            if not issubclass(model_class, TTSModel):
                raise TypeError(f"Model must subclass TTSModel: {model_class}")
            cls._registry[model_id] = model_class
    
    @classmethod
    def create(
        cls,
        model_id: str,
        config: Optional[ModelConfig] = None,
        use_cache: bool = False
    ) -> TTSModel:
        """Create model instance with GPU memory check (thread-safe)."""
        with cls._lock:
            # Auto-discover if not registered
            if model_id not in cls._registry:
                cls._auto_discover(model_id)
            
            if model_id not in cls._registry:
                available = list(cls._registry.keys())
                raise ValueError(f"Unknown model '{model_id}'. Available: {available}")
            
            # Check GPU memory before loading
            required_mb = cls._MODEL_MEMORY_REQUIREMENTS.get(model_id, 4000)
            has_memory, gpu_info = check_gpu_available_memory(required_mb)
            
            if not has_memory:
                raise MemoryError(
                    f"Model '{model_id}' requires {required_mb}MB GPU memory. "
                    f"Available: {gpu_info.free_mb:.0f}MB. "
                    f"Consider clearing model cache or freeing GPU memory."
                )
            
            # Return cached instance if requested
            if use_cache and model_id in cls._instances:
                logger.info(f"Returning cached model: {model_id}")
                return cls._instances[model_id]
            
            model_class = cls._registry[model_id]
            instance = model_class()
            
            if config:
                instance.configure(config)
            
            if use_cache:
                cls._instances[model_id] = instance
                logger.info(f"Cached model instance: {model_id}")
            
            return instance
    
    @classmethod
    def _auto_discover(cls, model_id: str) -> None:
        """Auto-import adapter modules."""
        adapter_map = {
            'qwen3': 'tts_models.adapters.qwen3',
            'qwen3-base': 'tts_models.adapters.qwen3',
        }
        
        if model_id in adapter_map:
            try:
                module_path = adapter_map[model_id]
                module = importlib.import_module(module_path)
                # Module should auto-register on import
                logger.info(f"Auto-discovered model: {model_id}")
            except ImportError as e:
                raise ImportError(f"Model '{model_id}' not available: {e}")
    
    @classmethod
    def list_available(cls) -> Dict[str, Type[TTSModel]]:
        """List all registered models."""
        return dict(cls._registry)
    
    @classmethod
    def clear_cache(cls) -> None:
        """Clear cached model instances (free GPU memory, thread-safe)."""
        with cls._lock:
            for instance in cls._instances.values():
                if hasattr(instance, 'close'):
                    instance.close()
            count = len(cls._instances)
            cls._instances.clear()
            logger.info(f"Cleared {count} cached model instances")


# Public API
# TODO: Remove deprecated references once migration is complete
create_model = ModelFactory.create
list_models = ModelFactory.list_available
clear_model_cache = ModelFactory.clear_cache


def register_model(model_id: str):
    """Decorator to register TTS model classes."""
    def decorator(cls):
        ModelFactory.register(model_id, cls)
        cls._model_id = model_id
        return cls
    return decorator
