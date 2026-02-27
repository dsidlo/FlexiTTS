"""Tests for LocalTTSProvider."""

import pytest
import sys
import numpy as np
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Remove any existing tts_ modules
tts_modules = [k for k in sys.modules.keys() if k.startswith('tts_')]
for mod in tts_modules:
    del sys.modules[mod]

# Set up mocks before importing
if 'torch' not in sys.modules:
    torch_mock = Mock()
    torch_mock.cuda = Mock()
    torch_mock.cuda.is_available = Mock(return_value=False)
    torch_mock.bfloat16 = Mock()
    torch_mock.float32 = Mock()
    sys.modules['torch'] = torch_mock

if 'qwen_tts' not in sys.modules:
    qwen_mock = Mock()
    mock_model = Mock()
    mock_model.generate_voice_clone = Mock(return_value=([np.zeros(1000)], 24000))
    mock_model.generate_custom_voice = Mock(return_value=([np.zeros(1000)], 24000))
    mock_model.create_voice_clone_prompt = Mock(return_value="mock_prompt")
    qwen_mock.Qwen3TTSModel = Mock()
    qwen_mock.Qwen3TTSModel.from_pretrained = Mock(return_value=mock_model)
    sys.modules['qwen_tts'] = qwen_mock

if 'soundfile' not in sys.modules:
    sf_mock = Mock()
    sys.modules['soundfile'] = sf_mock

# Now import
from tts_local import LocalTTSProvider
from tts_interface import TTSError, CharacterNotSupportedError


class TestLocalTTSProvider:
    """Test LocalTTSProvider class."""
    
    @pytest.fixture
    def mock_base_model(self):
        """Create mocked base model."""
        model = Mock()
        model.create_voice_clone_prompt = Mock(return_value="prompt_data")
        model.generate_voice_clone = Mock(return_value=([np.zeros(1000)], 24000))
        return model
    
    @pytest.fixture
    def mock_custom_model(self):
        """Create mocked custom model."""
        model = Mock()
        model.generate_custom_voice = Mock(return_value=([np.zeros(1000)], 24000))
        return model
    
    @pytest.fixture
    def provider(self, mock_base_model, mock_custom_model):
        """Create provider with mocked models."""
        return LocalTTSProvider(
            base_model=mock_base_model,
            custom_model=mock_custom_model,
            voices_dir=Path("/voices")
        )
    
    def test_init_creates_base_model(self):
        """Test provider initializes base model."""
        with patch('tts_local.Qwen3TTSModel') as mock_model_class:
            mock_instance = Mock()
            mock_model_class.from_pretrained.return_value = mock_instance
            
            provider = LocalTTSProvider(voices_dir=Path("/voices"))
            assert provider.voices_dir == Path("/voices")
            assert provider._voice_prompts == {}
    
    def test_supports_character_with_voice_sample(self):
        """Test supports_character with voice-sample."""
        with patch('tts_local.Qwen3TTSModel'):
            provider = LocalTTSProvider(voices_dir=Path("/voices"))
            char_config = {"voice-sample": "sample.wav"}
            assert provider.supports_character(char_config) is True
    
    def test_supports_character_with_custom_voice(self):
        """Test supports_character with custom-voice."""
        with patch('tts_local.Qwen3TTSModel'):
            provider = LocalTTSProvider(voices_dir=Path("/voices"))
            char_config = {"custom-voice": {"speaker": "spk1"}}
            assert provider.supports_character(char_config) is True
    
    def test_supports_character_with_neither(self):
        """Test supports_character with neither option."""
        with patch('tts_local.Qwen3TTSModel'):
            provider = LocalTTSProvider(voices_dir=Path("/voices"))
            char_config = {"other": "value"}
            assert provider.supports_character(char_config) is False
    
    def test_generate_voice_clone_success(self, provider, mock_base_model):
        """Test successful voice clone generation."""
        char_config = {"voice-sample": "ref.wav"}
        output_path = Path("/out/test.wav")
        
        with patch.object(provider, '_load_voice_prompt', return_value="cached"):
            result = provider.generate(
                text="Hello",
                speaker="test",
                emotion="neutral",
                language="English",
                output_path=output_path,
                instruct="speak clearly",
                char_config=char_config
            )
        
        assert len(result) == 2
        assert result[1] == 24000
    
    def test_generate_no_char_config_raises(self, provider):
        """Test generate without char_config raises."""
        with pytest.raises(CharacterNotSupportedError):
            provider.generate(
                text="Hello",
                speaker="test",
                emotion="neutral",
                language="English",
                output_path=Path("/out.wav"),
                char_config=None
            )
    
    def test_generate_custom_voice_success(self, provider, mock_custom_model):
        """Test custom voice generation."""
        char_config = {"custom-voice": {"speaker": "spk1", "language": "English"}}
        output_path = Path("/out/test.wav")
        
        result = provider.generate(
            text="Hello",
            speaker="test",
            emotion="happy",
            language="English",
            output_path=output_path,
            instruct="",
            char_config=char_config
        )
        
        assert len(result) == 2
        assert result[1] == 24000
    
    def test_close_releases_resources(self, provider):
        """Test close releases models."""
        provider.close()
        assert provider.base_model is None
        assert provider.custom_model is None
        assert provider._voice_prompts == {}


class TestLocalTTSProviderVoicePrompt:
    """Test voice prompt caching."""
    
    def test_load_voice_prompt_caches(self):
        """Test voice prompt is cached."""
        with patch('tts_local.Qwen3TTSModel'):
            provider = LocalTTSProvider(voices_dir=Path("/voices"))
            provider._voice_prompts["sample.wav"] = "cached_prompt"
            result = provider._load_voice_prompt("sample.wav")
            assert result == "cached_prompt"
