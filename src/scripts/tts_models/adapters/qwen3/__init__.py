"""Qwen3-TTS adapter."""
from .model import Qwen3Model

# Auto-register on import
from ...factory import register_model
register_model('qwen3')(Qwen3Model)
register_model('qwen3-base')(Qwen3Model)

__all__ = ['Qwen3Model']
