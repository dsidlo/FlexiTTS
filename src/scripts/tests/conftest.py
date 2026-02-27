"""Pytest configuration for TTS tests.

Sets up global mocks for heavy dependencies before any test imports.
"""

import sys
from pathlib import Path
from unittest.mock import Mock, MagicMock
import numpy as np
import pytest

# Store original modules to restore later
_original_modules = {}

def _setup_mocks():
    """Set up module-level mocks before any imports."""
    # Mock litellm first (before it's imported by chapter_to_xml)
    litellm_mock = Mock()
    litellm_mock.completion = Mock()
    sys.modules['litellm'] = litellm_mock
    
    # Mock torch and related modules
    torch_mock = Mock()
    torch_mock.cuda = Mock()
    torch_mock.cuda.is_available = Mock(return_value=False)
    torch_mock.bfloat16 = Mock()
    torch_mock.float32 = Mock()
    torch_mock.device = Mock()
    sys.modules['torch'] = torch_mock
    
    # Make numpy available
    sys.modules['numpy'] = np
    
    # Mock soundfile
    sf_mock = Mock()
    sf_mock.read = Mock(return_value=(np.zeros(1000), 24000))
    sf_mock.write = Mock()
    sys.modules['soundfile'] = sf_mock
    
    # Mock qwen_tts
    qwen_tts_mock = Mock()
    qwen_tts_mock.Qwen3TTSModel = Mock()
    mock_model_instance = Mock()
    mock_model_instance.create_voice_clone_prompt = Mock(return_value="mock_prompt")
    mock_model_instance.generate_voice_clone = Mock(return_value=([np.zeros(1000)], 24000))
    mock_model_instance.generate_custom_voice = Mock(return_value=([np.zeros(1000)], 24000))
    qwen_tts_mock.Qwen3TTSModel.from_pretrained = Mock(return_value=mock_model_instance)
    sys.modules['qwen_tts'] = qwen_tts_mock
    sys.modules['qwen_tts'].Qwen3TTSModel = qwen_tts_mock.Qwen3TTSModel
    
    # Mock websockets  
    websockets_mock = Mock()
    websockets_mock.connect = Mock()
    mock_websocket = Mock()
    mock_websocket.send = Mock()
    mock_websocket.recv = Mock()
    mock_websocket.close = Mock()
    websockets_mock.connect = Mock(return_value=mock_websocket)
    sys.modules['websockets'] = websockets_mock
    
    # Mock asyncio for sync testing
    asyncio_mock = Mock()
    asyncio_mock.run = Mock(return_value=([np.zeros(1000)], 24000))
    asyncio_mock.sleep = Mock()
    asyncio_mock.wait_for = Mock(return_value=mock_websocket)
    asyncio_mock.TimeoutError = TimeoutError
    sys.modules['asyncio'] = asyncio_mock

# Set up mocks at module load time
_setup_mocks()


# =============================================================================
# Pytest Fixtures
# =============================================================================

@pytest.fixture(autouse=True)
def reset_tts_modules():
    """Reset tts modules before each test to ensure clean imports."""
    # Remove cached tts modules
    tts_modules = [k for k in list(sys.modules.keys()) if k.startswith('tts_')]
    for mod in tts_modules:
        del sys.modules[mod]
    yield


@pytest.fixture
def mock_base_model():
    """Create mocked base Qwen3TTSModel."""
    model = Mock()
    model.create_voice_clone_prompt = Mock(return_value="mock_prompt")
    model.generate_voice_clone = Mock(return_value=([np.zeros(1000)], 24000))
    return model


@pytest.fixture
def mock_custom_model():
    """Create mocked custom Qwen3TTSModel."""
    model = Mock()
    model.generate_custom_voice = Mock(return_value=([np.zeros(1000)], 24000))
    return model


@pytest.fixture
def mock_websocket():
    """Create mocked WebSocket object."""
    ws = Mock()
    ws.send = Mock()
    ws.recv = Mock()
    ws.close = Mock()
    return ws


@pytest.fixture
def mock_fallback_provider():
    """Create mocked fallback TTS provider."""
    provider = Mock()
    provider.generate = Mock(return_value=([np.zeros(1000)], 24000))
    provider.supports_character = Mock(return_value=True)
    provider.close = Mock()
    return provider
