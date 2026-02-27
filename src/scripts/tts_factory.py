"""Factory for creating TTS providers.

This module provides a factory function to create either local or remote
TTS providers based on configuration, implementing the Factory pattern.
"""

import os
from pathlib import Path
from typing import Any, Dict, Optional

from tts_interface import TTSInterface
from tts_local import LocalTTSProvider
from tts_service import RemoteTTSProvider


class TTSProviderFactory:
    """Factory for creating TTS provider instances.
    
    Provides methods to create local or remote TTS providers based on
    configuration options. Supports caching of providers for reuse.
    
    Example:
        >>> factory = TTSProviderFactory()
        >>> 
        >>> # Create local provider
        >>> local = factory.create_provider()
        >>> 
        >>> # Create remote provider
        >>> remote = factory.create_provider(service_url="ws://localhost:8080")
    """
    
    def __init__(self):
        """Initialize the factory with empty cache."""
        self._cache: Dict[str, TTSInterface] = {}
        self._local_provider: Optional[LocalTTSProvider] = None
    
    def create_provider(
        self,
        service_url: Optional[str] = None,
        voices_dir: Optional[Path] = None,
        enable_fallback: bool = True,
        config: Optional[Dict[str, Any]] = None
    ) -> TTSInterface:
        """Create a TTS provider based on configuration.
        
        Args:
            service_url: WebSocket URL for remote service. If None, creates
                        local provider.
            voices_dir: Directory containing voice reference samples.
            enable_fallback: For remote providers, enable fallback to local
                            if connection fails.
            config: Additional configuration options.
            
        Returns:
            TTSInterface implementation (LocalTTSProvider or RemoteTTSProvider).
            
        Raises:
            ValueError: If service_url is invalid.
            TTSError: If provider creation fails.
            
        Example:
            >>> factory = TTSProviderFactory()
            >>> 
            >>> # Local provider (default)
            >>> provider = factory.create_provider()
            >>> 
            >>> # Remote provider
            >>> provider = factory.create_provider(
            ...     service_url="ws://tts-server:8080"
            ... )
            >>> 
            >>> # Remote with fallback
            >>> provider = factory.create_provider(
            ...     service_url="ws://tts-server:8080",
            ...     enable_fallback=True
            ... )
        """
        if service_url is None:
            return self._create_local_provider(voices_dir)
        
        return self._create_remote_provider(
            service_url, voices_dir, enable_fallback, config
        )
    
    def _create_local_provider(
        self,
        voices_dir: Optional[Path] = None
    ) -> LocalTTSProvider:
        """Create or return cached local TTS provider.
        
        Args:
            voices_dir: Directory containing voice samples.
            
        Returns:
            LocalTTSProvider instance (cached).
        """
        # Return cached local provider if available
        if self._local_provider is not None:
            return self._local_provider
        
        # Resolve voices directory
        if voices_dir is None:
            voices_dir = Path(os.environ.get("VOICES_DIR", "voices"))
        
        # Create new local provider
        self._local_provider = LocalTTSProvider(voices_dir=voices_dir)
        return self._local_provider
    
    def _create_remote_provider(
        self,
        service_url: str,
        voices_dir: Optional[Path] = None,
        enable_fallback: bool = True,
        config: Optional[Dict[str, Any]] = None
    ) -> RemoteTTSProvider:
        """Create remote TTS provider with optional fallback.
        
        Args:
            service_url: WebSocket URL for remote service.
            voices_dir: Directory for voice samples (used by fallback).
            enable_fallback: Enable local fallback on connection failure.
            config: Additional configuration.
            
        Returns:
            RemoteTTSProvider instance with optional fallback.
        """
        config = config or {}
        
        # Create fallback provider if enabled
        fallback = None
        if enable_fallback:
            fallback = self._create_local_provider(voices_dir)
        
        # Get retry and timeout config
        max_retries = config.get("max_retries", 4)
        timeout = config.get("timeout", 30.0)
        
        # Create remote provider
        return RemoteTTSProvider(
            service_url=service_url,
            fallback_provider=fallback,
            max_retries=max_retries,
            timeout=timeout
        )
    
    def close_all(self) -> None:
        """Close all cached providers and clear cache."""
        if self._local_provider is not None:
            self._local_provider.close()
            self._local_provider = None
        
        self._cache.clear()
    
    @staticmethod
    def from_command_line(
        service_url: Optional[str] = None,
        voices_dir: Optional[str] = None
    ) -> TTSInterface:
        """Quick factory method from command-line arguments.
        
        Convenience method to create a provider directly from CLI args.
        
        Args:
            service_url: --tts-service URL (or None for local).
            voices_dir: Path to voices directory.
            
        Returns:
            Configured TTSInterface instance.
            
        Example:
            >>> # In your main script:
            >>> provider = TTSProviderFactory.from_command_line(
            ...     args.tts_service,
            ...     args.voices_dir
            ... )
        """
        factory = TTSProviderFactory()
        
        voices_path = Path(voices_dir) if voices_dir else None
        
        return factory.create_provider(
            service_url=service_url,
            voices_dir=voices_path,
            enable_fallback=True
        )


# Convenience function for simple use cases
def create_tts_provider(
    service_url: Optional[str] = None,
    voices_dir: Optional[Path] = None
) -> TTSInterface:
    """Create a TTS provider.
    
    Simple factory function for creating TTS providers without
    managing a factory instance.
    
    Args:
        service_url: WebSocket URL for remote service, or None for local.
        voices_dir: Directory containing voice reference samples.
        
    Returns:
        TTSInterface implementation.
    """
    return TTSProviderFactory().create_provider(service_url, voices_dir)
