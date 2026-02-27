"""Abstract base interface for TTS providers.

This module defines the contract that all TTS implementations must follow,
enabling both local (Qwen3-TTS + SoX) and remote (WebSocket) TTS services
to be used interchangeably.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


class TTSInterface(ABC):
    """Abstract base class for TTS providers.
    
    All TTS implementations (local and remote) must inherit from this
    class and implement the required methods.
    
    Example:
        >>> provider = LocalTTSProvider(config)
        >>> wavs, sr = provider.generate(
        ...     text="Hello world",
        ...     speaker="narrator",
        ...     emotion="neutral",
        ...     language="English",
        ...     output_path=Path("output.wav")
        ... )
    """
    
    @abstractmethod
    def generate(
        self,
        text: str,
        speaker: str,
        emotion: str,
        language: str,
        output_path: Path,
        instruct: str = "",
        char_config: Optional[Dict[str, Any]] = None
    ) -> tuple[List[Any], int]:
        """Generate audio from text.
        
        Args:
            text: The text to convert to speech.
            speaker: The speaker identifier.
            emotion: The emotional tone to use.
            language: The language code.
            output_path: Where to save the generated audio.
            instruct: Additional instruction/prompt for the TTS model.
            char_config: Character-specific configuration (optional).
            
        Returns:
            A tuple of (list of audio segments, sample_rate).
            
        Raises:
            TTSError: If generation fails.
        """
        pass
    
    @abstractmethod
    def supports_character(self, char_config: Dict[str, Any]) -> bool:
        """Check if this provider supports a given character configuration.
        
        Args:
            char_config: Character configuration from story-config.yml.
            
        Returns:
            True if this provider can handle the character.
        """
        pass
    
    @abstractmethod
    def close(self) -> None:
        """Release resources and cleanup.
        
        Should be called when done with the provider to free GPU memory
        and close any open connections.
        """
        pass


class TTSError(Exception):
    """Base exception for TTS-related errors."""
    pass


class TTSConnectionError(TTSError):
    """Exception raised when TTS service connection fails."""
    pass


class TTSGenerationError(TTSError):
    """Exception raised when TTS generation fails."""
    pass


class CharacterNotSupportedError(TTSError):
    """Exception raised when character configuration is not supported."""
    pass


@dataclass
class TTSResult:
    """Result of a TTS generation operation.
    
    Attributes:
        audio_segments: List of audio data arrays.
        sample_rate: Sample rate in Hz.
        duration: Total duration in seconds (optional).
    """
    audio_segments: List[Any]
    sample_rate: int
    duration: Optional[float] = None
