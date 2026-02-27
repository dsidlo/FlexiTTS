"""Tests for RemoteTTSProvider."""

import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import numpy as np

# Remove any tts_ modules for fresh import
tts_modules = [k for k in sys.modules.keys() if k.startswith('tts_')]
for mod in tts_modules:
    del sys.modules[mod]

# Set up websockets mock
if 'websockets' not in sys.modules:
    ws_mock = Mock()
    ws_mock.connect = AsyncMock()
    sys.modules['websockets'] = ws_mock
    sys.modules['websockets'].connect = ws_mock.connect

if 'asyncio' not in sys.modules:
    asyncio_mock = Mock()
    asyncio_mock.run = Mock(return_value=([np.zeros(1000)], 24000))
    asyncio_mock.sleep = AsyncMock()
    asyncio_mock.wait_for = AsyncMock()
    asyncio_mock.TimeoutError = TimeoutError
    sys.modules['asyncio'] = asyncio_mock

if 'numpy' not in sys.modules:
    sys.modules['numpy'] = np

if 'soundfile' not in sys.modules:
    sf_mock = Mock()
    sf_mock.read = Mock(return_value=(np.zeros(1000), 24000))
    sf_mock.write = Mock()
    sys.modules['soundfile'] = sf_mock

# Import after mocks
import tts_service
from tts_service import RemoteTTSProvider
from tts_interface import TTSError, TTSConnectionError, TTSGenerationError


class TestRemoteTTSProvider:
    """Test RemoteTTSProvider class."""
    
    @pytest.fixture
    def provider(self):
        """Create provider with mocked websockets."""
        with patch.object(tts_service, 'WEBSOCKETS_AVAILABLE', True):
            with patch.object(tts_service, 'websockets'):
                return RemoteTTSProvider(
                    service_url="ws://localhost:8080",
                    max_retries=2
                )
    
    def test_init_validates_url(self):
        """Test init validates WebSocket URL."""
        with patch.object(tts_service, 'WEBSOCKETS_AVAILABLE', True):
            with patch.object(tts_service, 'websockets'):
                with pytest.raises(ValueError):
                    RemoteTTSProvider(service_url="http://localhost:8080")
    
    def test_init_requires_websockets(self):
        """Test init requires websockets library."""
        with patch.object(tts_service, 'WEBSOCKETS_AVAILABLE', False):
            with pytest.raises(TTSConnectionError, match="websockets library required"):
                RemoteTTSProvider(service_url="ws://localhost:8080")
    
    def test_supports_character_always_true(self, provider):
        """Test supports_character always returns True."""
        # When no fallback, returns True
        assert provider.supports_character({"any": "config"}) is True
    
    def test_init_creates_with_fallback(self):
        """Test init with fallback provider."""
        with patch.object(tts_service, 'WEBSOCKETS_AVAILABLE', True):
            with patch.object(tts_service, 'websockets'):
                fallback = Mock()
                provider = RemoteTTSProvider(
                    service_url="ws://localhost:8080",
                    fallback_provider=fallback,
                    max_retries=3,
                    timeout=30.0
                )
                assert provider.service_url == "ws://localhost:8080"
                assert provider.fallback_provider is fallback
                assert provider.max_retries == 3


class TestRemoteTTSProviderURLValidation:
    """Test URL validation."""
    
    def test_validates_ws_url(self):
        """Test ws:// URLs are accepted."""
        with patch.object(tts_service, 'WEBSOCKETS_AVAILABLE', True):
            with patch.object(tts_service, 'websockets'):
                # Should work
                RemoteTTSProvider("ws://localhost:8080")
                RemoteTTSProvider("wss://secure.host:443/tts")
    
    def test_rejects_http_url(self):
        """Test http:// URLs are rejected."""
        with patch.object(tts_service, 'WEBSOCKETS_AVAILABLE', True):
            with pytest.raises(ValueError):
                RemoteTTSProvider("http://localhost:8080")
    
    def test_rejects_https_url(self):
        """Test https:// URLs are rejected."""
        with patch.object(tts_service, 'WEBSOCKETS_AVAILABLE', True):
            with pytest.raises(ValueError):
                RemoteTTSProvider("https://localhost:8080")


class TestRemoteTTSProviderGeneration:
    """Test RemoteTTSProvider generation with fallback."""
    
    def test_generate_uses_fallback_on_error(self):
        """Test generate falls back on error."""
        with patch.object(tts_service, 'WEBSOCKETS_AVAILABLE', True):
            with patch.object(tts_service, 'websockets'):
                # Create a mock asyncio that raises TTSConnectionError
                mock_asyncio = Mock()
                mock_asyncio.run = Mock(side_effect=TTSConnectionError("Failed"))
                
                with patch.object(tts_service, 'asyncio', mock_asyncio):
                    fallback = Mock()
                    fallback.generate.return_value = ([Mock()], 24000)
                    
                    provider = RemoteTTSProvider(
                        service_url="ws://localhost:8080",
                        fallback_provider=fallback
                    )
                    
                    result = provider.generate(
                        text="Hello",
                        speaker="test",
                        emotion="neutral",
                        language="English",
                        output_path=Path("/out.wav"),
                        instruct=""
                    )
                    
                    assert fallback.generate.called
    
    def test_generate_no_fallback_raises(self):
        """Test generate raises when no fallback and connection fails."""
        with patch.object(tts_service, 'WEBSOCKETS_AVAILABLE', True):
            with patch.object(tts_service, 'websockets'):
                mock_asyncio = Mock()
                mock_asyncio.run = Mock(side_effect=TTSConnectionError("Failed"))
                
                with patch.object(tts_service, 'asyncio', mock_asyncio):
                    provider = RemoteTTSProvider(
                        service_url="ws://localhost:8080",
                        fallback_provider=None
                    )
                    
                    with pytest.raises(TTSConnectionError):
                        provider.generate(
                            text="Hello",
                            speaker="test",
                            emotion="neutral",
                            language="English",
                            output_path=Path("/out.wav"),
                            instruct=""
                        )
    
    def test_generate_success(self):
        """Test successful generate."""
        with patch.object(tts_service, 'WEBSOCKETS_AVAILABLE', True):
            with patch.object(tts_service, 'websockets'):
                mock_audio = Mock()
                mock_audio.ndim = 1
                
                mock_asyncio = Mock()
                mock_asyncio.run = Mock(return_value=([mock_audio], 24000))
                
                with patch.object(tts_service, 'asyncio', mock_asyncio):
                    provider = RemoteTTSProvider(
                        service_url="ws://localhost:8080"
                    )
                    
                    result = provider.generate(
                        text="Hello",
                        speaker="test",
                        emotion="neutral",
                        language="English",
                        output_path=Path("/out.wav"),
                        instruct=""
                    )
                    
                    mock_asyncio.run.assert_called_once()


class TestRemoteTTSProviderClose:
    """Test close functionality."""
    
    def test_close_without_websocket(self):
        """Test close when no websocket exists."""
        with patch.object(tts_service, 'WEBSOCKETS_AVAILABLE', True):
            with patch.object(tts_service, 'websockets'):
                provider = RemoteTTSProvider("ws://localhost:8080")
                provider._websocket = None
                
                # Should not raise
                provider.close()
    
    def test_close_with_fallback(self):
        """Test close with fallback provider."""
        with patch.object(tts_service, 'WEBSOCKETS_AVAILABLE', True):
            with patch.object(tts_service, 'websockets'):
                fallback = Mock()
                provider = RemoteTTSProvider(
                    "ws://localhost:8080",
                    fallback_provider=fallback
                )
                
                provider.close()
                fallback.close.assert_called_once()


class TestTryFallback:
    """Test _try_fallback method."""
    
    def test_try_fallback_no_provider(self):
        """Test _try_fallback raises when no fallback."""
        with patch.object(tts_service, 'WEBSOCKETS_AVAILABLE', True):
            with patch.object(tts_service, 'websockets'):
                provider = RemoteTTSProvider("ws://localhost:8080")
                
                with pytest.raises(TTSConnectionError, match="no fallback provider"):
                    provider._try_fallback(
                        text="Hello",
                        speaker="test",
                        emotion="neutral",
                        language="English",
                        output_path=Path("/out.wav"),
                        instruct=""
                    )
    
    def test_try_fallback_with_provider(self):
        """Test _try_fallback uses fallback provider."""
        with patch.object(tts_service, 'WEBSOCKETS_AVAILABLE', True):
            with patch.object(tts_service, 'websockets'):
                fallback = Mock()
                mock_result = ([Mock()], 24000)
                fallback.generate.return_value = mock_result
                
                provider = RemoteTTSProvider(
                    "ws://localhost:8080",
                    fallback_provider=fallback
                )
                
                result = provider._try_fallback(
                    text="Hello",
                    speaker="test",
                    emotion="neutral",
                    language="English",
                    output_path=Path("/out.wav"),
                    instruct="test instruct",
                    char_config={"name": "test"}
                )
                
                assert result is mock_result
                fallback.generate.assert_called_once_with(
                    "Hello", "test", "neutral", "English",
                    Path("/out.wav"), "test instruct", {"name": "test"}
                )


class TestSupportsCharacter:
    """Test supports_character with fallback."""
    
    def test_supports_character_with_fallback(self):
        """Test supports_character delegates to fallback."""
        with patch.object(tts_service, 'WEBSOCKETS_AVAILABLE', True):
            with patch.object(tts_service, 'websockets'):
                fallback = Mock()
                fallback.supports_character.return_value = True
                
                provider = RemoteTTSProvider(
                    "ws://localhost:8080",
                    fallback_provider=fallback
                )
                
                result = provider.supports_character({"voice": "test"})
                
                assert result is True
                fallback.supports_character.assert_called_once_with({"voice": "test"})
    
    def test_supports_character_without_fallback(self):
        """Test supports_character returns True without fallback."""
        with patch.object(tts_service, 'WEBSOCKETS_AVAILABLE', True):
            with patch.object(tts_service, 'websockets'):
                provider = RemoteTTSProvider("ws://localhost:8080")
                
                assert provider.supports_character({}) is True
