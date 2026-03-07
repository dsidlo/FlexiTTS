"""Qwen3-TTS model adapter."""
from __future__ import annotations

import threading
import os
import sys
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, TYPE_CHECKING

import numpy as np
import soundfile as sf

from ...base import TTSModel, ModelConfig, GenerateResult, ParameterTranslator
from .voice_cache import LRUVoiceCache
from .translator import Qwen3Translator

if TYPE_CHECKING:
    import torch
    from qwen_tts import Qwen3TTSModel

logger = logging.getLogger('tts_models.qwen3')


class Qwen3Model(TTSModel, ParameterTranslator):
    """Qwen3-TTS adapter implementing the TTSModel interface.
    
    Thread Safety Status: THREAD-SAFE
    
    Implements comprehensive thread safety:
    - Per-model thread lock (_model_lock) for model state access
    - Per-model CUDA lock (_cuda_lock) for GPU operations
    - Uses base class generate_lock for generate() serialization
    - Thread-safe voice cache via LRUVoiceCache
    
    All internal model operations are protected against concurrent access,
    preventing CUDA context errors and ensuring data consistency.
    
    Attributes:
        base_model: The base Qwen3TTSModel for voice cloning.
        custom_model: The custom voice Qwen3TTSModel (if needed).
        device: Device string ('cuda:0' or 'cpu').
        dtype: Torch dtype for model inference.
        _voice_cache: LRU cache for voice cloning prompts.
        _model_lock: threading.Lock for model state protection.
        _cuda_lock: threading.Lock for CUDA operation serialization.
    """
    
    model_id = "qwen3"
    
    # Language code mappings
    LANGUAGE_MAP = Qwen3Translator.LANGUAGE_MAP
    
    @property
    def capabilities(self) -> Dict[str, bool]:
        return {
            'voice_cloning': True,
            'emotion_control': True,
            'streaming': False,
            'multi_speaker': True,
        }
    
    def __init__(self):
        super().__init__()
        self._base_model: Optional[Any] = None
        self._custom_model: Optional[Any] = None
        self._device: Optional[str] = None
        self._dtype: Optional[Any] = None
        self._voice_cache: Optional[LRUVoiceCache] = None
        self._translator = Qwen3Translator()
        
        # Per-model locks for thread safety
        self._model_lock = threading.Lock()  # Protects model state
        self._cuda_lock = threading.Lock()     # Serializes CUDA operations
    
    def configure(self, config: ModelConfig) -> None:
        """Configure Qwen3-TTS with lazy GPU initialization.
        
        This is where heavy GPU dependencies are imported - NOT at module level.
        """
        super().configure(config)
        
        # Lazy imports - only when configuring
        import torch
        try:
            from qwen_tts import Qwen3TTSModel
        except ImportError:
            sys.path.append(os.path.join(os.getcwd(), "Qwen3-TTS"))
            from qwen_tts import Qwen3TTSModel
        
        self._torch = torch
        self._Qwen3TTSModel = Qwen3TTSModel
        
        # Device configuration
        if config.device == "auto":
            self._device = "cuda:0" if torch.cuda.is_available() else "cpu"
        else:
            self._device = config.device
        
        if config.dtype:
            self._dtype = getattr(torch, config.dtype)
        else:
            self._dtype = torch.bfloat16 if torch.cuda.is_available() else torch.float32
        
        # Initialize voice cache with configurable size
        cache_size = config.voice_cache_size
        self._voice_cache = LRUVoiceCache(maxsize=cache_size)
        logger.info(f"Qwen3Model configured: device={self._device}, voice_cache_size={cache_size}")
    
    def _create_base_model(self) -> Any:
        """Create the base Qwen3-TTS model with thread safety."""
        logger.info("Loading Qwen3 base model...")
        return self._Qwen3TTSModel.from_pretrained(
            "Qwen/Qwen3-TTS-12Hz-1.7B-Base",
            device_map=self._device,
            dtype=self._dtype,
            attn_implementation="eager",
        )
    
    def _create_custom_model(self) -> Any:
        """Create the custom voice Qwen3-TTS model with thread safety."""
        logger.info("Loading Qwen3 custom model...")
        return self._Qwen3TTSModel.from_pretrained(
            "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice",
            device_map=self._device,
            dtype=self._dtype,
            attn_implementation="eager",
        )
    
    def _ensure_base_model(self) -> Any:
        """Ensure base model is loaded (thread-safe)."""
        if self._base_model is None:
            self._base_model = self._create_base_model()
        return self._base_model
    
    def _ensure_custom_model(self) -> Any:
        """Ensure custom model is loaded (thread-safe)."""
        if self._custom_model is None:
            self._custom_model = self._create_custom_model()
        return self._custom_model
    
    def translate_parameters(
        self,
        emotion: str,
        language: str,
        instruct: str
    ) -> Dict[str, Any]:
        """Translate generic params to Qwen3-TTS format with 2K char limit."""
        return self._translator.translate_parameters(emotion, language, instruct)
    
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
        """Internal generate implementation with CUDA lock protection."""
        self.validate_config()
        
        # Enforce 2K character limit
        if len(text) > 2000:
            logger.warning(f"Text exceeds 2K limit ({len(text)} chars), truncating")
            text = text[:1997] + "..."
        
        # Translate parameters
        params = self.translate_parameters(emotion, language, instruct)
        
        # Route to appropriate generation mode with CUDA lock
        with self._cuda_lock:
            if custom_voice_config:
                wavs, sr = self._generate_custom_voice(text, custom_voice_config, params)
            elif voice_sample:
                wavs, sr = self._generate_voice_clone(text, voice_sample, params)
            else:
                raise ValueError("Qwen3-TTS requires either voice_sample or custom_voice_config")
        
        # Save to output path if provided
        if output_path:
            sf.write(str(output_path), wavs[0], sr)
            logger.info(f"Audio saved to {output_path}")
        
        # Calculate duration
        duration_ms = int(len(wavs[0]) / sr * 1000) if wavs else 0
        
        return GenerateResult(
            audio_segments=wavs,
            sample_rate=sr,
            duration_ms=duration_ms,
            model_name=self.model_id
        )
    
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
        """Generate audio using Qwen3-TTS (thread-safe via base class lock).
        
        This method is automatically protected by the base class generate_lock
        to ensure thread-safe TTS generation.
        
        Args:
            text: Text to speak (max 2K chars enforced).
            speaker: Speaker identifier.
            emotion: Emotional tone.
            language: Language code.
            output_path: Output file path.
            instruct: Instruction/prompt for the model.
            voice_sample: Path to voice sample (for cloning mode).
            custom_voice_config: Custom voice config (for custom mode).
            
        Returns:
            GenerateResult with audio segments and sample rate.
        """
        return super().generate(
            text, speaker, emotion, language, output_path,
            instruct, voice_sample, custom_voice_config
        )
    
    def _generate_voice_clone(
        self,
        text: str,
        voice_sample: str,
        params: Dict[str, Any]
    ) -> tuple[List[np.ndarray], int]:
        """Generate using voice cloning mode."""
        base_model = self._ensure_base_model()
        
        # Get or create voice clone prompt
        prompt_items = self._voice_cache.get(voice_sample)
        if prompt_items is None:
            logger.info(f"Creating voice clone prompt for {voice_sample}")
            prompt_items = base_model.create_voice_clone_prompt(
                ref_audio=voice_sample,
                ref_text="",
                x_vector_only_mode=True,
            )
            self._voice_cache.put(voice_sample, prompt_items)
        
        # Generate audio
        wavs, sr = base_model.generate_voice_clone(
            text=text,
            language=params['language'],
            voice_clone_prompt=prompt_items,
            instruct=params['instruct'],
        )
        
        return wavs, sr
    
    def _generate_custom_voice(
        self,
        text: str,
        custom_voice_config: Dict,
        params: Dict[str, Any]
    ) -> tuple[List[np.ndarray], int]:
        """Generate using custom voice mode."""
        custom_model = self._ensure_custom_model()
        
        spk = custom_voice_config.get('speaker')
        base_instruct = custom_voice_config.get('instruct', '')
        
        # Combine instructions
        if base_instruct:
            final_instruct = f"{base_instruct}. {params['instruct']}"
        else:
            final_instruct = params['instruct']
        
        wavs, sr = custom_model.generate_custom_voice(
            text=text,
            speaker=spk,
            language=params['language'],
            instruct=final_instruct,
        )
        
        return wavs, sr
    
    def clear_cache(self) -> None:
        """Clear internal caches to free memory."""
        if self._voice_cache:
            self._voice_cache.clear()
            logger.info("Voice cache cleared")
    
    def close(self) -> None:
        """Release model resources and clear CUDA cache (thread-safe)."""
        logger.info("Qwen3Model closing, releasing resources...")
        
        with self._model_lock:
            self.clear_cache()
            
            if self._base_model is not None:
                del self._base_model
                self._base_model = None
            
            if self._custom_model is not None:
                del self._custom_model
                self._custom_model = None
            
            if self._torch and self._torch.cuda.is_available():
                with self._cuda_lock:
                    self._torch.cuda.empty_cache()
                    logger.info("CUDA cache cleared")
    
    def get_voice_cache_stats(self) -> dict:
        """Get voice cache statistics."""
        return self._voice_cache.stats if self._voice_cache else {}
