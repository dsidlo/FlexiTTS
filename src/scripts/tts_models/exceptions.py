"""Exceptions for TTS Models package."""


class TTSModelError(Exception):
    """Base exception for TTS model errors."""
    pass


class GPUOutOfMemoryError(TTSModelError):
    """Raised when GPU does not have enough memory for model."""
    pass


class ModelLoadError(TTSModelError):
    """Raised when model fails to load."""
    pass


class GenerationError(TTSModelError):
    """Raised when audio generation fails."""
    pass


class CacheFullError(TTSModelError):
    """Raised when voice cache is full and cannot evict."""
    pass
