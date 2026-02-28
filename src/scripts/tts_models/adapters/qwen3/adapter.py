"""Qwen3-TTS adapter with lazy GPU imports and voice cache."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any, TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np
    import torch
    from qwen_tts import Qwen3TTSModel

from ...base import TTSModel
from ...exceptions import GPUOutOfMemoryError, ModelLoadError, GenerationError
from .voice_cache import VoicePromptCache


class Qwen3TTSAdapter(TTSModel):
    """Qwen3-TTS model adapter with lazy GPU initialization.
    
    Supports voice cloning and custom voice generation.
    Uses LRU cache for voice prompts with configurable size.
    
    Attributes:
        name: Model identifier.
        supports_voice_cloning: True.
        supports_custom_voices: True.
    """
    
    name = "qwen3"
    supports_voice_cloning = True
    supports_emotions = True
    supports_custom_voices = True
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize adapter without loading models."""
        super().__init__(config)
        
        # Model references (loaded lazily in configure())
        self._base_model: Optional[Any] = None
        self._custom_model: Optional[Any] = None
        self._device: Optional[str] = None
        self._dtype: Optional[Any] = None
        self._torch = None
        self._voices_dir: Path = Path("voices")
        
        # Initialize voice cache with size from config
        cache_size = self._config.get("max_voice_cache_size", 10)
        self._voice_cache = VoicePromptCache(maxsize=cache_size)
    
    @property
    def device(self) -> str:
        """Return current device."""
        return self._device or "cpu"
    
    def _import_qwen_tts(self):
        """Lazy import of qwen_tts module."""
        try:
            from qwen_tts import Qwen3TTSModel
            return Qwen3TTSModel
        except ImportError:
            sys.path.append(os.path.join(os.getcwd(), "Qwen3-TTS"))
            from qwen_tts import Qwen3TTSModel
            return Qwen3TTSModel
    
    def configure(self, config: Dict[str, Any]) -> None:
        """Configure model with lazy GPU library imports.
        
        Args:
            config: Dict with device, dtype, voices_dir, base_model_path,
                   custom_model_path, max_voice_cache_size.
                   
        Raises:
            GPUOutOfMemoryError: If not enough GPU memory.
            ModelLoadError: If model fails to load.
        """
        # Lazy import of torch - only when configuring
        import torch
        self._torch = torch
        
        # Set device and dtype
        self._device = config.get(
            "device",
            "cuda:0" if torch.cuda.is_available() else "cpu"
        )
        self._dtype = config.get(
            "dtype",
            torch.bfloat16 if torch.cuda.is_available() else torch.float32
        )
        self._voices_dir = Path(config.get("voices_dir", "voices"))
        
        # Resize cache if config changed
        new_size = config.get("max_voice_cache_size")
        if new_size is not None and new_size != self._voice_cache.maxsize:
            self._voice_cache.resize(new_size)
        
        # Load models
        try:
            Qwen3TTSModel = self._import_qwen_tts()
            
            base_path = config.get(
                "base_model_path",
                "Qwen/Qwen3-TTS-12Hz-1.7B-Base"
            )
            self._base_model = Qwen3TTSModel.from_pretrained(
                base_path,
                device_map=self._device,
                dtype=self._dtype,
                attn_implementation="eager",
            )
            
            custom_path = config.get(
                "custom_model_path",
                "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice"
            )
            if custom_path:
                self._custom_model = Qwen3TTSModel.from_pretrained(
                    custom_path,
                    device_map=self._device,
                    dtype=self._dtype,
                    attn_implementation="eager",
                )
            
            self._model_loaded = True
            
        except RuntimeError as e:
            if "out of memory" in str(e).lower():
                raise GPUOutOfMemoryError(
                    f"GPU out of memory loading Qwen3-TTS: {e}"
                ) from e
            raise ModelLoadError(f"Failed to load Qwen3-TTS model: {e}") from e
    
    def translate_parameters(
        self,
        emotion: str,
        language: str,
        instruct: str
    ) -> Dict[str, Any]:
        """Translate generic params to Qwen3-TTS format.
        
        Qwen3 uses: "Speak in a {emotion} tone." format.
        """
        lang_map = {
            "en": "English",
            "zh": "Chinese",
            "es": "Spanish",
            "fr": "French",
            "de": "German",
        }
        
        # Emotion adds to instruction
        if emotion and emotion.lower() not in ("neutral", ""):
            emotion_instruction = f"Speak in a {emotion} tone."
        else:
            emotion_instruction = instruct
        
        qwen_lang = lang_map.get(language.lower(), language)
        
        return {
            "language": qwen_lang,
            "instruct": emotion_instruction,
            "emotion": emotion,
        }
    
    def get_gpu_memory_used(self) -> int:
        """Return GPU memory used in MB."""
        if self._torch is None or not self._torch.cuda.is_available():
            return 0
        return self._torch.cuda.memory_allocated() // (1024 * 1024)
    
    def get_gpu_memory_free(self) -> int:
        """Return free GPU memory in MB."""
        if self._torch is None or not self._torch.cuda.is_available():
            return 0
        return (
            self._torch.cuda.get_device_properties(0).total_memory -
            self._torch.cuda.memory_allocated()
        ) // (1024 * 1024)
    
    def _load_voice_prompt(self, voice_sample: str) -> Any:
        """Load or get cached voice prompt."""
        # Check cache first
        cached = self._voice_cache.get(voice_sample)
        if cached is not None:
            return cached
        
        # Load from file
        ref_path = self._voices_dir / voice_sample
        if not ref_path.exists():
            raise GenerationError(f"Voice sample not found: {ref_path}")
        
        prompt = self._base_model.create_voice_clone_prompt(
            ref_audio=str(ref_path),
            ref_text="",
            x_vector_only_mode=True,
        )
        
        # Cache it
        self._voice_cache.set(voice_sample, prompt)
        return prompt
    
    def _ensure_custom_model(self) -> Any:
        """Ensure custom model is loaded."""
        if self._custom_model is None:
            raise GenerationError(
                "Custom voice model not loaded. Call configure() first."
            )
        return self._custom_model
    
    def generate(
        self,
        text: str,
        speaker: str,
        emotion: str,
        language: str,
        output_path: Path,
        instruct: str = "",
        voice_sample: Optional[str] = None,
        custom_voice_config: Optional[Dict[str, Any]] = None
    ) -> Tuple[List[Any], int]:
        """Generate audio from text.
        
        Args:
            text: Text to speak (max 2000 chars).
            speaker: Speaker identifier.
            emotion: Emotional tone.
            language: Language code.
            output_path: Where to save WAV.
            instruct: Additional instruction.
            voice_sample: Path to voice sample for cloning.
            custom_voice_config: Dict with speaker, language, instruct.
            
        Returns:
            Tuple of (audio_segments, sample_rate).
            
        Raises:
            GenerationError: If generation fails.
        """
        # Text length check
        if len(text) > 2000:
            raise GenerationError(
                f"Text too long: {len(text)} chars (max 2000)"
            )
        
        if not self._model_loaded:
            raise GenerationError("Model not configured. Call configure() first.")
        
        try:
            if custom_voice_config:
                return self._generate_custom_voice(
                    text, speaker, emotion, language, instruct,
                    custom_voice_config
                )
            elif voice_sample:
                return self._generate_voice_clone(
                    text, speaker, emotion, language, instruct,
                    voice_sample
                )
            else:
                raise GenerationError(
                    "Must provide voice_sample or custom_voice_config"
                )
        except Exception as e:
            if isinstance(e, GenerationError):
                raise
            raise GenerationError(f"TTS generation failed: {e}") from e
    
    def _generate_voice_clone(
        self,
        text: str,
        speaker: str,
        emotion: str,
        language: str,
        instruct: str,
        voice_sample: str
    ) -> Tuple[List[Any], int]:
        """Generate using voice cloning mode."""
        params = self.translate_parameters(emotion, language, instruct)
        prompt = self._load_voice_prompt(voice_sample)
        
        wavs, sr = self._base_model.generate_voice_clone(
            text=text,
            language=params["language"],
            voice_clone_prompt=prompt,
            instruct=params["instruct"],
        )
        
        return wavs, sr
    
    def _generate_custom_voice(
        self,
        text: str,
        speaker: str,
        emotion: str,
        language: str,
        instruct: str,
        custom_voice_config: Dict[str, Any]
    ) -> Tuple[List[Any], int]:
        """Generate using custom voice mode."""
        model = self._ensure_custom_model()
        params = self.translate_parameters(emotion, language, instruct)
        
        spk = custom_voice_config.get("speaker")
        base_instruct = custom_voice_config.get("instruct", "")
        
        # Combine instructions
        if base_instruct:
            final_instruct = f"{base_instruct}. {params['instruct']}".strip(". ") + "."
        else:
            final_instruct = params["instruct"]
        
        lang = custom_voice_config.get("language", params["language"])
        
        wavs, sr = model.generate_custom_voice(
            text=text,
            speaker=spk,
            language=lang,
            instruct=final_instruct,
        )
        
        return wavs, sr
    
    def close(self) -> None:
        """Release model resources."""
        self.clear_cache()
        
        if self._base_model is not None:
            del self._base_model
            self._base_model = None
        
        if self._custom_model is not None:
            del self._custom_model
            self._custom_model = None
        
        self._model_loaded = False
        
        if self._torch and self._torch.cuda.is_available():
            self._torch.cuda.empty_cache()
