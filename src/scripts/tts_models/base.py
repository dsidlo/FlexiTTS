"""Abstract base class for TTS models."""
from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any, TYPE_CHECKING
from dataclasses import dataclass, field

if TYPE_CHECKING:
    import numpy as np


@dataclass
class GenerateResult:
    """Result of TTS generation."""
    audio_segments: List[Any]  # List[np.ndarray] - deferred import
    sample_rate: int
    duration_ms: Optional[int] = None
    model_name: str = ""


@dataclass
class ModelConfig:
    """Configuration for TTS model initialization."""
    device: str = "auto"  # auto, cpu, cuda:0, etc.
    dtype: Optional[str] = None
    model_path: Optional[str] = None
    cache_dir: Optional[Path] = None
    max_memory_gb: Optional[float] = None
    voice_cache_size: int = 10  # LRU cache size for voice prompts


class TTSModel(ABC):
    """Abstract base class for all TTS models.
    
    Thread Safety Status: THREAD-SAFE
    
    This base class provides thread safety through:
    - threading.Lock for generate() serialization
    - Per-model instance locks for concurrent access protection
    
    All generate() calls are automatically serialized using a lock
to prevent concurrent CUDA context conflicts.
    """
    
    def __init__(self):
        self._configured = False
        self._model_config: Optional[ModelConfig] = None
        self._generate_lock = threading.Lock()  # Thread-safe lock for generate() serialization
    
    @property
    def generate_lock(self) -> threading.Lock:
        """Get the lock for generate() serialization."""
        return self._generate_lock
    
    @property
    @abstractmethod
    def model_id(self) -> str:
        """Unique identifier (e.g., 'qwen3', 'turtle')."""
        pass
    
    @property
    @abstractmethod
    def capabilities(self) -> Dict[str, bool]:
        """Model capabilities."""
        return {
            'voice_cloning': False,
            'emotion_control': False,
            'streaming': False,
            'multi_speaker': False
        }
    
    @abstractmethod
    def configure(self, config: ModelConfig) -> None:
        """Configure model with lazily-loaded GPU dependencies.
        
        This is where imports like 'import torch' happen - NOT at module level.
        """
        self._model_config = config
        self._configured = True
    
    def generate(
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
        """Generate audio from text with thread-safe locking."""
        with self._generate_lock:
            return self._generate_impl(
                text, speaker, emotion, language, output_path,
                instruct, voice_sample, custom_voice_config
            )
    
    @abstractmethod
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
        """Internal generate implementation (subclass override).
        
        This is the actual implementation without locking.
        The generate() method wraps this with generate_lock.
        """
        pass
    
    @abstractmethod
    def translate_parameters(
        self,
        emotion: str,
        language: str,
        instruct: str
    ) -> Dict[str, Any]:
        """Translate generic params to model-specific format."""
        pass
    
    @abstractmethod
    def clear_cache(self) -> None:
        """Clear internal caches to free memory."""
        pass
    
    def validate_config(self) -> None:
        """Ensure model is configured before use."""
        if not self._configured:
            raise RuntimeError(f"{self.model_id} not configured. Call configure() first.")


class ParameterTranslator:
    """Mixin for parameter translation logic."""
    
    # Language code mappings (ISO 639-1 to model-specific)
    LANGUAGE_MAP: Dict[str, str] = {}
    
    # Emotion mappings (generic to model-specific)
    EMOTION_MAP: Dict[str, str] = {}
    
    def translate_language(self, lang: str) -> str:
        """Translate language code."""
        return self.LANGUAGE_MAP.get(lang.lower(), lang)
    
    def translate_emotion(self, emotion: str) -> str:
        """Translate emotion to model format."""
        return self.EMOTION_MAP.get(emotion.lower(), emotion)
