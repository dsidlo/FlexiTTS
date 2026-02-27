"""Tests for TTS interface module."""

import pytest
import sys
from pathlib import Path
from unittest.mock import Mock

# Remove any mocks from sys.modules to ensure real imports
tts_modules_to_remove = [k for k in sys.modules.keys() if k.startswith('tts_')]
for mod in tts_modules_to_remove:
    del sys.modules[mod]

# Import the real classes after clearing mocks
from tts_interface import (
    TTSInterface, 
    TTSError, 
    TTSConnectionError,
    TTSGenerationError,
    CharacterNotSupportedError,
    TTSResult
)


class TestTTSError:
    """Test TTS exception classes."""
    
    def test_tts_error_is_exception(self):
        error = TTSError("test error")
        assert str(error) == "test error"
        assert isinstance(error, Exception)
    
    def test_tts_connection_error_is_tts_error(self):
        error = TTSConnectionError("connection failed")
        assert isinstance(error, TTSError)
        assert isinstance(error, Exception)
    
    def test_tts_generation_error_is_tts_error(self):
        error = TTSGenerationError("generation failed")
        assert isinstance(error, TTSError)
        assert isinstance(error, Exception)
    
    def test_character_not_supported_error_is_tts_error(self):
        error = CharacterNotSupportedError("char not supported")
        assert isinstance(error, TTSError)
        assert isinstance(error, Exception)


class TestTTSResult:
    """Test TTSResult dataclass."""
    
    def test_tts_result_creation(self):
        import numpy as np
        audio = [np.zeros(1000)]
        result = TTSResult(
            audio_segments=audio,
            sample_rate=24000,
            duration=0.5
        )
        assert result.sample_rate == 24000
        assert len(result.audio_segments) == 1
        assert result.duration == 0.5
    
    def test_tts_result_optional_duration(self):
        import numpy as np
        result = TTSResult(
            audio_segments=[np.zeros(1000)],
            sample_rate=24000
        )
        assert result.sample_rate == 24000
        assert result.duration is None
        assert len(result.audio_segments) == 1


class TestTTSInterface:
    """Test TTSInterface abstract base class."""
    
    def test_tts_interface_is_abstract(self):
        """Test that TTSInterface cannot be instantiated directly."""
        with pytest.raises(TypeError):
            TTSInterface()
    
    def test_concrete_implementation(self):
        """Test creating a concrete implementation."""
        class ConcreteTTS(TTSInterface):
            def generate(self, text, speaker, emotion, language, output_path, instruct="", char_config=None):
                return ([], 24000)
            
            def supports_character(self, char_config):
                return True
            
            def close(self):
                pass
        
        provider = ConcreteTTS()
        assert provider.supports_character({}) is True
        result = provider.generate("test", "spk", "neutral", "en", Path("/tmp/test.wav"))
        assert result == ([], 24000)
