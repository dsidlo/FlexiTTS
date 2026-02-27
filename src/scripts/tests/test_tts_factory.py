"""Tests for TTS factory module."""

import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Remove any existing tts_ modules to ensure fresh imports
tts_modules = [k for k in sys.modules.keys() if k.startswith('tts_')]
for mod in tts_modules:
    del sys.modules[mod]

# Ensure mocks are in place before importing
if 'torch' not in sys.modules:
    torch_mock = Mock()
    torch_mock.cuda = Mock()
    torch_mock.cuda.is_available = Mock(return_value=False)
    sys.modules['torch'] = torch_mock

if 'qwen_tts' not in sys.modules:
    qwen_mock = Mock()
    mock_model = Mock()
    mock_model.generate_voice_clone = Mock(return_value=([], 24000))
    qwen_mock.Qwen3TTSModel = Mock()
    qwen_mock.Qwen3TTSModel.from_pretrained = Mock(return_value=mock_model)
    sys.modules['qwen_tts'] = qwen_mock

if 'websockets' not in sys.modules:
    ws_mock = Mock()
    sys.modules['websockets'] = ws_mock

if 'asyncio' not in sys.modules:
    asyncio_mock = Mock()
    asyncio_mock.run = Mock(return_value=([], 24000))
    sys.modules['asyncio'] = asyncio_mock

# Now import the modules under test
import tts_factory
from tts_factory import TTSProviderFactory, create_tts_provider


class TestTTSProviderFactory:
    """Test TTSProviderFactory class."""
    
    def test_create_local_provider(self):
        """Test factory creates LocalTTSProvider when no service URL."""
        factory = TTSProviderFactory()
        
        # Clear factory cache
        factory._local_provider = None
        
        # Patch the class in the module where it's used
        with patch.object(tts_factory, 'LocalTTSProvider') as mock_local:
            mock_instance = Mock()
            mock_local.return_value = mock_instance
            
            provider = factory.create_provider(service_url=None)
            
            mock_local.assert_called_once()
            assert provider is mock_instance
    
    def test_create_remote_provider(self):
        """Test factory creates RemoteTTSProvider when service URL given."""
        factory = TTSProviderFactory()
        
        # Clear cache
        factory._local_provider = None
        
        with patch.object(tts_factory, 'RemoteTTSProvider') as mock_remote:
            with patch.object(tts_factory, 'LocalTTSProvider') as mock_local:
                mock_remote_instance = Mock()
                mock_local_instance = Mock()
                mock_remote.return_value = mock_remote_instance
                mock_local.return_value = mock_local_instance
                
                provider = factory.create_provider(
                    service_url="ws://localhost:8080",
                    enable_fallback=False
                )
                
                # Remote should be created
                mock_remote.assert_called_once()
                assert provider is mock_remote_instance
    
    def test_local_provider_caching(self):
        """Test local provider is cached."""
        factory = TTSProviderFactory()
        
        # Clear cache
        factory._local_provider = None
        
        with patch.object(tts_factory, 'LocalTTSProvider') as mock_local:
            mock_instance = Mock()
            mock_local.return_value = mock_instance
            
            # Create provider twice
            p1 = factory.create_provider(service_url=None)
            p2 = factory.create_provider(service_url=None)
            
            # Should only create once (cached)
            assert mock_local.call_count == 1
            assert factory._local_provider is p1
            assert p1 is p2
    
    def test_close_all_releases_resources(self):
        """Test close_all clears cache and calls close."""
        factory = TTSProviderFactory()
        
        # Clear cache
        factory._local_provider = None
        
        with patch.object(tts_factory, 'LocalTTSProvider') as mock_local:
            mock_provider = Mock()
            mock_local.return_value = mock_provider
            
            factory.create_provider(service_url=None)
            factory.close_all()
            
            mock_provider.close.assert_called_once()
            assert factory._local_provider is None


class TestCreateTTSProvider:
    """Test create_tts_provider convenience function."""
    
    def test_create_local(self):
        """Test creates local provider."""
        with patch.object(tts_factory, 'TTSProviderFactory') as mock_factory_class:
            mock_factory = Mock()
            mock_provider = Mock()
            mock_factory_class.return_value = mock_factory
            mock_factory.create_provider.return_value = mock_provider
            
            provider = create_tts_provider()
            
            mock_factory_class.assert_called_once()
            mock_factory.create_provider.assert_called_once_with(None, None)
            assert provider is mock_provider
    
    def test_create_remote(self):
        """Test creates remote provider."""
        with patch.object(tts_factory, 'TTSProviderFactory') as mock_factory_class:
            mock_factory = Mock()
            mock_provider = Mock()
            mock_factory_class.return_value = mock_factory
            mock_factory.create_provider.return_value = mock_provider
            
            provider = create_tts_provider("ws://host:8080")
            
            mock_factory_class.assert_called_once()
            mock_factory.create_provider.assert_called_once_with("ws://host:8080", None)
            assert provider is mock_provider


class TestTTSProviderFactoryFromCommandLine:
    """Test command line factory method."""
    
    def test_from_command_line_creates_provider(self):
        """Test from_command_line creates provider."""
        with patch.object(tts_factory, 'LocalTTSProvider') as mock_local:
            mock_local.return_value = Mock()
            
            provider = TTSProviderFactory.from_command_line(
                service_url=None,
                voices_dir=None
            )
            assert provider is not None
    
    def test_from_command_line_with_voices_dir(self):
        """Test from_command_line with voices directory."""
        with patch.object(tts_factory, 'LocalTTSProvider') as mock_local:
            mock_local.return_value = Mock()
            
            provider = TTSProviderFactory.from_command_line(
                service_url=None,
                voices_dir="/path/to/voices"
            )
            assert provider is not None
            # Verify Path was used correctly
            call_args = mock_local.call_args
            assert call_args is not None
