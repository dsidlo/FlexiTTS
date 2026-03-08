"""Local TTS provider using Qwen3-TTS model.

This module implements the TTSInterface for local Qwen3-TTS model
execution with voice cloning and custom voice capabilities.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

import numpy as np
import soundfile as sf

if TYPE_CHECKING:
    import torch

# Try to import Qwen3TTSModel for export and module use
try:
    from qwen_tts import Qwen3TTSModel
except ImportError:
    # For testing/mocking - will be mocked
    Qwen3TTSModel = None  # type: ignore

from tts_interface import TTSInterface, TTSError, CharacterNotSupportedError, TTSResult

__all__ = ['LocalTTSProvider', 'Qwen3TTSModel']


class LocalTTSProvider(TTSInterface):
    """Local TTS provider using Qwen3-TTS model.
    
    Supports both voice cloning (with reference audio) and custom voice
    modes. Loads model on GPU if available, otherwise CPU.
    
    Attributes:
        base_model: The base Qwen3TTSModel for voice cloning.
        custom_model: The custom voice Qwen3TTSModel (if needed).
        device: Device string ('cuda:0' or 'cpu').
        dtype: Torch dtype for model inference.
        _voice_prompts: Cache of loaded voice cloning prompts.
    """
    
    def __init__(
        self,
        base_model: Optional[Qwen3TTSModel] = None,
        custom_model: Optional[Qwen3TTSModel] = None,
        voices_dir: Optional[Path] = None
    ):
        """Initialize the local TTS provider.
        
        Args:
            base_model: Pre-loaded base model (optional).
            custom_model: Pre-loaded custom model (optional).
            voices_dir: Directory containing voice reference samples.
            
        Raises:
            TTSError: If model initialization fails.
        """
        # Lazy imports - only when actually instantiating
        import torch
        try:
            from qwen_tts import Qwen3TTSModel
        except ImportError:
            sys.path.append(os.path.join(os.getcwd(), "Qwen3-TTS"))
            from qwen_tts import Qwen3TTSModel
        
        self._Qwen3TTSModel = Qwen3TTSModel
        self.device = "cuda:0" if torch.cuda.is_available() else "cpu"
        self.dtype = torch.bfloat16 if torch.cuda.is_available() else torch.float32
        self.voices_dir = voices_dir or Path("voices")
        self._voice_prompts: Dict[str, Any] = {}
        
        try:
            self.base_model = base_model or self._create_base_model()
        except Exception as e:
            raise TTSError(f"Failed to initialize base model: {e}")
        
        self.custom_model = custom_model
    
    def _create_base_model(self) -> Qwen3TTSModel:
        """Create the base Qwen3-TTS model."""
        return Qwen3TTSModel.from_pretrained(
            "Qwen/Qwen3-TTS-12Hz-1.7B-Base",
            device_map=self.device,
            dtype=self.dtype,
            attn_implementation="eager",
        )
    
    def _create_custom_model(self) -> Qwen3TTSModel:
        """Create the custom voice Qwen3-TTS model."""
        return Qwen3TTSModel.from_pretrained(
            "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice",
            device_map=self.device,
            dtype=self.dtype,
            attn_implementation="eager",
        )
    
    def supports_character(self, char_config: Dict[str, Any]) -> bool:
        """Check if character is supported.
        
        LocalTTSProvider supports:
        - Characters with voice-sample (voice cloning)
        - Characters with custom-voice (speaker ID)
        
        Args:
            char_config: Character configuration.
            
        Returns:
            True if voice-sample or custom-voice is defined.
        """
        return bool(
            char_config.get("voice-sample") or 
            char_config.get("custom-voice")
        )
    
    def _load_voice_prompt(
        self, 
        voice_sample: str
    ) -> Any:
        """Load or get cached voice cloning prompt.
        
        Args:
            voice_sample: Path to voice sample file.
            
        Returns:
            Voice cloning prompt from model.
        """
        if voice_sample not in self._voice_prompts:
            # Try raw path first (in case it's a full path)
            raw_path = Path(voice_sample)
            if raw_path.exists():
                ref_path = raw_path
            else:
                # Fall back to voices_dir relative path
                ref_path = self.voices_dir / voice_sample
            if not ref_path.exists():
                raise CharacterNotSupportedError(
                    f"Voice sample not found: {ref_path}"
                )
            
            self._voice_prompts[voice_sample] = \
                self.base_model.create_voice_clone_prompt(
                    ref_audio=str(ref_path),
                    ref_text="",
                    x_vector_only_mode=True,
                )
        
        return self._voice_prompts[voice_sample]
    
    def _ensure_custom_model(self) -> Qwen3TTSModel:
        """Ensure custom model is loaded.
        
        Returns:
            The custom model instance.
            
        Raises:
            TTSError: If custom model cannot be loaded.
        """
        if self.custom_model is None:
            try:
                self.custom_model = self._create_custom_model()
            except Exception as e:
                raise TTSError(f"Failed to load custom voice model: {e}")
        return self.custom_model
    
    def generate(
        self,
        text: str,
        speaker: str,
        emotion: str,
        language: str,
        output_path: Path,
        instruct: str = "",
        char_config: Optional[Dict[str, Any]] = None,
        story: Optional[str] = None,
        chapter: Optional[str] = None,
        section: Optional[str] = None,
        dialog: Optional[str] = None
    ) -> Tuple[List[np.ndarray], int]:
        """Generate audio using local Qwen3-TTS model.
        
        Args:
            text: Text to speak.
            speaker: Speaker identifier.
            emotion: Emotional tone.
            language: Language code.
            output_path: Output file path.
            instruct: Instruction/prompt for the model.
            char_config: Character configuration.
            story: Story name for tracking (optional, ignored by local provider).
            chapter: Chapter number for tracking (optional, ignored by local provider).
            section: Section number for tracking (optional, ignored by local provider).
            dialog: Dialog sequence for tracking (optional, ignored by local provider).
            
        Returns:
            Tuple of (audio segments list, sample rate).
            
        Raises:
            TTSError: If generation fails.
            CharacterNotSupportedError: If character config is invalid.
        """
        if not char_config:
            raise CharacterNotSupportedError("No character configuration provided")
        
        is_custom = "custom-voice" in char_config
        
        try:
            if is_custom:
                return self._generate_custom_voice(
                    text, emotion, language, instruct, char_config
                )
            else:
                return self._generate_voice_clone(
                    text, emotion, language, instruct, char_config
                )
        except Exception as e:
            if isinstance(e, (TTSError, CharacterNotSupportedError)):
                raise
            raise TTSError(f"TTS generation failed: {e}")
    
    def _generate_voice_clone(
        self,
        text: str,
        emotion: str,
        language: str,
        instruct: str,
        char_config: Dict[str, Any]
    ) -> Tuple[List[np.ndarray], int]:
        """Generate using voice cloning mode."""
        voice_sample = char_config.get("voice-sample")
        if not voice_sample:
            raise CharacterNotSupportedError(
                "voice-sample required for non-custom voice"
            )
        
        prompt_items = self._load_voice_prompt(voice_sample)
        
        wavs, sr = self.base_model.generate_voice_clone(
            text=text,
            language=language,
            voice_clone_prompt=prompt_items,
            instruct=instruct,
        )
        
        return wavs, sr
    
    def _generate_custom_voice(
        self,
        text: str,
        emotion: str,
        language: str,
        instruct: str,
        char_config: Dict[str, Any]
    ) -> Tuple[List[np.ndarray], int]:
        """Generate using custom voice mode."""
        custom_voice = char_config["custom-voice"]
        spk = custom_voice.get("speaker")
        lang = custom_voice.get("language", language)
        base_instruct = custom_voice.get("instruct", "")
        
        if base_instruct:
            final_instruct = f"{base_instruct}. {instruct}"
        else:
            final_instruct = instruct
        
        model = self._ensure_custom_model()
        
        wavs, sr = model.generate_custom_voice(
            text=text,
            speaker=spk,
            language=lang,
            instruct=final_instruct,
        )
        
        return wavs, sr
    
    def close(self) -> None:
        """Release model resources."""
        import torch
        
        if self.base_model is not None:
            del self.base_model
            self.base_model = None
        
        if self.custom_model is not None:
            del self.custom_model
            self.custom_model = None
        
        self._voice_prompts.clear()
        
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
