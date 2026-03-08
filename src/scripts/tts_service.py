"""Remote TTS provider using WebSocket service.

This module implements the TTSInterface for remote TTS services
via WebSocket connection, enabling distributed TTS processing.
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import soundfile as sf

from tts_interface import (
    TTSInterface,
    TTSConnectionError,
    TTSGenerationError,
    CharacterNotSupportedError
)

# Try to import websockets, provide graceful fallback
try:
    import websockets
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False


class RemoteTTSProvider(TTSInterface):
    """Remote TTS provider using WebSocket service.

    Connects to a WebSocket-based TTS service for audio generation.
    Implements retry logic with exponential backoff and optional fallback
    to local TTS provider.

    Attributes:
        service_url: WebSocket URL of the TTS service.
        fallback_provider: Local TTS provider for fallback (optional).
        max_retries: Maximum number of connection retries.
        timeout: Connection timeout in seconds.
    """

    def __init__(
        self,
        service_url: str,
        fallback_provider: Optional[TTSInterface] = None,
        max_retries: int = 4,
        timeout: float = 30.0
    ):
        """Initialize the remote TTS provider.

        Args:
            service_url: WebSocket URL (ws:// or wss://).
            fallback_provider: Local provider for fallback (optional).
            max_retries: Maximum retry attempts on connection failure.
            timeout: Connection timeout in seconds.

        Raises:
            TTSConnectionError: If websockets library not available.
            ValueError: If service_url is invalid.
        """
        if not WEBSOCKETS_AVAILABLE:
            raise TTSConnectionError(
                "websockets library required. Install: pip install websockets"
            )

        self._validate_url(service_url)

        self.service_url = service_url
        self.fallback_provider = fallback_provider
        self.max_retries = max_retries
        self.timeout = timeout
        self._websocket: Optional[Any] = None

    def _validate_url(self, url: str) -> None:
        """Validate WebSocket URL format.

        Args:
            url: URL to validate.

        Raises:
            ValueError: If URL is invalid.
        """
        if not (url.startswith("ws://") or url.startswith("wss://")):
            raise ValueError(
                f"Invalid WebSocket URL: {url}. Must start with ws:// or wss://"
            )

    async def _connect_with_retry(self) -> Any:
        """Connect to WebSocket service with exponential backoff.

        Returns:
            WebSocket connection object.

        Raises:
            TTSConnectionError: If connection fails after all retries.
        """
        if self._websocket is not None:
            return self._websocket

        for attempt in range(self.max_retries):
            try:
                self._websocket = await asyncio.wait_for(
                    websockets.connect(
                        self.service_url,
                        ping_interval=None,  # Disable pings for long-running generation
                        close_timeout=60
                    ),
                    timeout=self.timeout
                )
                return self._websocket
            except Exception as e:
                if attempt < self.max_retries - 1:
                    wait_time = 2 ** attempt  # 1, 2, 4, 8 seconds
                    await asyncio.sleep(wait_time)
                else:
                    raise TTSConnectionError(
                        f"Failed to connect to TTS service after {self.max_retries} attempts: {e}"
                    )

        raise TTSConnectionError("Failed to connect to TTS service")

    def _try_fallback(
        self,
        text: str,
        speaker: str,
        emotion: str,
        language: str,
        output_path: Path,
        instruct: str = "",
        char_config: Optional[Dict[str, Any]] = None
    ) -> Tuple[List[np.ndarray], int]:
        """Try fallback to local provider if configured.

        Args:
            text: Text to speak.
            speaker: Speaker identifier.
            emotion: Emotion.
            language: Language.
            output_path: Output path.
            instruct: Instruction.
            char_config: Character config.

        Returns:
            Audio segments and sample rate.

        Raises:
            TTSConnectionError: If no fallback configured.
        """
        if self.fallback_provider is None:
            raise TTSConnectionError(
                "WebSocket connection failed and no fallback provider configured"
            )

        return self.fallback_provider.generate(
            text, speaker, emotion, language, output_path, instruct, char_config
        )

    async def health_check(self, timeout: float = 5.0) -> Dict[str, Any]:
        """Check server health and readiness.

        Args:
            timeout: Connection timeout in seconds.

        Returns:
            Dictionary with health status information.

        Raises:
            TTSConnectionError: If health check fails.
        """
        try:
            websocket = await asyncio.wait_for(
                websockets.connect(
                    self.service_url,
                    ping_interval=None
                ),
                timeout=timeout
            )

            try:
                # Send health check request
                await websocket.send(json.dumps({"action": "health"}))

                # Receive response
                response = await asyncio.wait_for(
                    websocket.recv(),
                    timeout=timeout
                )

                if isinstance(response, str):
                    return json.loads(response)
                else:
                    return {"status": "unknown", "ready": False}

            finally:
                await websocket.close()

        except Exception as e:
            return {"status": "unhealthy", "error": str(e), "ready": False}

    def is_ready(self, timeout: float = 5.0) -> bool:
        """Check if server is ready (model loaded).

        Args:
            timeout: Connection timeout in seconds.

        Returns:
            True if server is ready, False otherwise.
        """
        try:
            result = asyncio.run(self.health_check(timeout=timeout))
            return result.get("ready", False) and result.get("status") == "healthy"
        except Exception:
            return False

    def supports_character(self, char_config: Dict[str, Any]) -> bool:
        """Check if character is supported.

        Remote TTS provider supports all characters if connected.
        Falls back to fallback provider's check if available.

        Args:
            char_config: Character configuration.

        Returns:
            True if supported by remote or fallback provider.
        """
        # Remote service theoretically supports any character
        # But check fallback if that's what's being used
        if self.fallback_provider:
            return self.fallback_provider.supports_character(char_config)
        return True

    def generate(
        self,
        text: str,
        speaker: str,
        emotion: str,
        language: str,
        output_path: Path,
        instruct: str = "",
        char_config: Optional[Dict[str, Any]] = None,
        chapter: Optional[str] = None,
        section: Optional[str] = None,
        dialog: Optional[str] = None,
        story: Optional[str] = None
    ) -> Tuple[List[np.ndarray], int]:
        """Generate audio using remote WebSocket service.

        Args:
            text: Text to speak.
            speaker: Speaker identifier.
            emotion: Emotional tone.
            language: Language code.
            output_path: Where to save audio.
            instruct: Instruction for TTS model.
            char_config: Character configuration.
            chapter: Chapter number for alerts.
            section: Section number for alerts.
            dialog: Dialog sequence for alerts.
            story: Story name for alerts.

        Returns:
            Tuple of (audio segments list, sample rate).

        Raises:
            TTSConnectionError: If connection fails and no fallback.
            TTSGenerationError: If generation fails.
        """
        try:
            return asyncio.run(
                self._generate_remote(
                    text, speaker, emotion, language, output_path, instruct, char_config,
                    chapter, section, dialog, story
                )
            )
        except TTSConnectionError as e:
            if self.fallback_provider:
                return self._try_fallback(
                    text, speaker, emotion, language, output_path, instruct, char_config
                )
            raise

    async def _generate_remote(
        self,
        text: str,
        speaker: str,
        emotion: str,
        language: str,
        output_path: Path,
        instruct: str,
        char_config: Optional[Dict[str, Any]],
        chapter: Optional[str] = None,
        section: Optional[str] = None,
        dialog: Optional[str] = None,
        story: Optional[str] = None
    ) -> Tuple[List[np.ndarray], int]:
        """Async internal method for remote generation."""
        websocket = await self._connect_with_retry()

        try:
            # Build request message
            request = {
                "text": text,
                "speaker": speaker,
                "emotion": emotion,
                "language": language,
                "instruct": instruct,
                "output_format": "wav"
            }
            
            # Add context metadata for alerts
            if story:
                request["story"] = story
            if chapter:
                request["chapter"] = chapter
            if section:
                request["section"] = section
            if dialog:
                request["dialog"] = dialog

            # Add character config if provided
            if char_config:
                request["character_config"] = {
                    k: str(v) if isinstance(v, Path) else v
                    for k, v in char_config.items()
                }

            # Send request
            await websocket.send(json.dumps(request))

            # Receive response (multiple messages: metadata + binary data)
            metadata = None
            audio_data = bytearray()

            while True:
                message = await asyncio.wait_for(
                    websocket.recv(),
                    timeout=300.0  # Generation timeout (300s/5min for voice cloning)
                )

                if isinstance(message, str):
                    # Metadata or error
                    msg_data = json.loads(message)
                    if "error" in msg_data:
                        raise TTSGenerationError(msg_data["error"])
                    elif "done" in msg_data:
                        break
                    else:
                        metadata = msg_data
                else:
                    # Binary audio data
                    audio_data.extend(message)

            if not audio_data or not metadata:
                raise TTSGenerationError("No audio data received from service")

            # Convert bytes to numpy array
            with output_path.open("wb") as f:
                f.write(audio_data)

            # Read back to get numpy array
            audio, sr = sf.read(str(output_path))

            # Return as list of segments (single segment for remote)
            if audio.ndim == 1:
                return [audio], sr
            else:
                return [audio[:, 0]], sr  # Take first channel if stereo

        finally:
            # Don't close here - connection pooling
            pass

    def close(self) -> None:
        """Close WebSocket connection and cleanup."""
        if self._websocket is not None:
            try:
                asyncio.run(self._websocket.close())
            except Exception:
                pass  # Ignore close errors
            self._websocket = None

        if self.fallback_provider:
            self.fallback_provider.close()
