"""TTS Models Library - Unified TTS abstraction layer.

Supports multiple TTS backends:
- Qwen3-TTS (current)
- Turtle-TTS (future)

Usage:
    from tts_models import create_model, ModelConfig
    
    config = ModelConfig(device='cuda:0', voice_cache_size=10)
    model = create_model('qwen3', config)
    
    result = model.generate(
        text="Hello world",
        speaker="narrator",
        emotion="neutral",
        language="en",
        output_path=Path("output.wav")
    )
"""

from .base import TTSModel, ModelConfig, GenerateResult
from .factory import ModelFactory, create_model, list_models, clear_model_cache

__all__ = [
    'TTSModel',
    'ModelConfig',
    'GenerateResult',
    'ModelFactory',
    'create_model',
    'list_models',
    'clear_model_cache',
]

__version__ = '1.0.0'
