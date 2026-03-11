"""Remote TTS provider using WebSocket service.

This module implements the TTSInterface for remote TTS services
via WebSocket connection, enabling distributed TTS processing.
"""

import asyncio
import contextlib
import json
import logging
import os
import shutil
import sys
import traceback
from datetime import datetime
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


DEBUG_LOG_FILE = Path("/tmp/FlexiTTS.log")
logger = logging.getLogger("tts_service_client")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)


def debug_log(event: str, **kwargs: Any) -> None:
    try:
        details = " ".join(f"{key}={repr(value)}" for key, value in kwargs.items())
        message = f"{event} {details}" if details else event
        logger.info(message)
        with open(DEBUG_LOG_FILE, "a") as f:
            f.write(f"[{datetime.now().isoformat()}] INFO {message}\n")
    except Exception:
        pass


def log_exception(event: str, exc: Exception, **kwargs: Any) -> None:
    try:
        payload = {
            **kwargs,
            "error_type": type(exc).__name__,
            "error": str(exc),
            "traceback": traceback.format_exc(),
        }
        debug_log(event, **payload)
    except Exception:
        pass


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
        for attempt in range(self.max_retries):
            attempt_num = attempt + 1
            try:
                debug_log(
                    "remote_tts:connect_attempt",
                    service_url=self.service_url,
                    attempt=attempt_num,
                    max_retries=self.max_retries,
                    timeout_seconds=self.timeout,
                )
                websocket = await asyncio.wait_for(
                    websockets.connect(
                        self.service_url,
                        ping_interval=None,  # Disable pings for long-running generation
                        close_timeout=60,
                        open_timeout=self.timeout,
                    ),
                    timeout=self.timeout
                )
                debug_log(
                    "remote_tts:connect_success",
                    service_url=self.service_url,
                    attempt=attempt_num,
                )
                return websocket
            except Exception as e:
                log_exception(
                    "remote_tts:connect_failure",
                    e,
                    service_url=self.service_url,
                    attempt=attempt_num,
                    max_retries=self.max_retries,
                    timeout_seconds=self.timeout,
                )
                if attempt < self.max_retries - 1:
                    wait_time = 2 ** attempt  # 1, 2, 4, 8 seconds
                    debug_log(
                        "remote_tts:connect_retry_scheduled",
                        service_url=self.service_url,
                        next_attempt=attempt_num + 1,
                        wait_seconds=wait_time,
                    )
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
            debug_log("remote_tts:health_check_start", service_url=self.service_url, timeout_seconds=timeout)
            websocket = await asyncio.wait_for(
                websockets.connect(
                    self.service_url,
                    ping_interval=None,
                    open_timeout=timeout,
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
                    payload = json.loads(response)
                    debug_log("remote_tts:health_check_success", service_url=self.service_url, response=payload)
                    return payload
                else:
                    debug_log("remote_tts:health_check_non_string_response", service_url=self.service_url, response_type=type(response).__name__)
                    return {"status": "unknown", "ready": False}

            finally:
                await websocket.close()

        except Exception as e:
            log_exception("remote_tts:health_check_failure", e, service_url=self.service_url, timeout_seconds=timeout)
            return {"status": "unhealthy", "error": str(e), "ready": False}

    async def send_alert(
        self,
        message: str,
        alert_type: str = "info",
        metadata: Optional[Dict[str, Any]] = None,
        timeout: float = 5.0,
    ) -> bool:
        """Forward a progress alert to the remote TTS service if available.

        Uses a short-lived dedicated connection so alerts are independent from
        the long-lived generation socket. This avoids concurrent recv/send
        conflicts with the main generation connection.

        Returns:
            True if the alert was acknowledged, False otherwise.
        """
        if not WEBSOCKETS_AVAILABLE:
            return False

        websocket = None
        try:
            debug_log(
                "remote_tts:alert_send_start",
                service_url=self.service_url,
                message=message,
                alert_type=alert_type,
                timeout_seconds=timeout,
            )
            websocket = await asyncio.wait_for(
                websockets.connect(
                    self.service_url,
                    ping_interval=None,
                    close_timeout=10,
                    open_timeout=timeout,
                ),
                timeout=timeout,
            )

            await websocket.send(json.dumps({
                "action": "alert",
                "message": message,
                "alertType": alert_type,
                "metadata": metadata or {},
            }))

            while True:
                response = await asyncio.wait_for(websocket.recv(), timeout=timeout)
                if not isinstance(response, str):
                    continue
                payload = json.loads(response)
                if payload.get("type") == "alert-ack":
                    debug_log(
                        "remote_tts:alert_send_ack",
                        service_url=self.service_url,
                        message=message,
                        forwarded=bool(payload.get("forwarded")),
                        ack_payload=payload,
                    )
                    return bool(payload.get("forwarded"))
        except Exception as e:
            log_exception(
                "remote_tts:alert_send_failure",
                e,
                service_url=self.service_url,
                message=message,
                alert_type=alert_type,
                timeout_seconds=timeout,
            )
            try:
                print(f"[TTS ALERT] send_alert failed: {type(e).__name__}: {e}", file=sys.stderr)
            except Exception:
                pass
            return False
        finally:
            if websocket is not None:
                with contextlib.suppress(Exception):
                    await websocket.close()

    def send_alert_sync(
        self,
        message: str,
        alert_type: str = "info",
        metadata: Optional[Dict[str, Any]] = None,
        timeout: float = 5.0,
    ) -> bool:
        """Sync wrapper for send_alert().

        When called from synchronous code while another event loop may already
        be active or a pooled generation websocket is in use, create a fresh
        provider instance bound to the same URL and use its dedicated short-
        lived alert connection.
        """
        try:
            temp_provider = RemoteTTSProvider(
                service_url=self.service_url,
                fallback_provider=None,
                max_retries=1,
                timeout=timeout,
            )
            return asyncio.run(temp_provider.send_alert(message, alert_type, metadata, timeout=timeout))
        except Exception as e:
            log_exception(
                "remote_tts:alert_send_sync_failure",
                e,
                service_url=self.service_url,
                message=message,
                alert_type=alert_type,
                timeout_seconds=timeout,
            )
            try:
                print(f"[TTS ALERT] send_alert_sync failed: {type(e).__name__}: {e}", file=sys.stderr)
            except Exception:
                pass
            return False

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
            debug_log(
                "remote_tts:generate_start",
                service_url=self.service_url,
                speaker=speaker,
                emotion=emotion,
                language=language,
                output_path=str(output_path),
                chapter=chapter,
                section=section,
                dialog=dialog,
                story=story,
                text_length=len(text or ""),
            )
            return asyncio.run(
                self._generate_remote(
                    text, speaker, emotion, language, output_path, instruct, char_config,
                    chapter, section, dialog, story
                )
            )
        except TTSConnectionError as e:
            log_exception(
                "remote_tts:generate_connection_failure",
                e,
                service_url=self.service_url,
                speaker=speaker,
                chapter=chapter,
                section=section,
                dialog=dialog,
                story=story,
                output_path=str(output_path),
            )
            if self.fallback_provider:
                return self._try_fallback(
                    text, speaker, emotion, language, output_path, instruct, char_config
                )
            raise
        except Exception as e:
            log_exception(
                "remote_tts:generate_failure",
                e,
                service_url=self.service_url,
                speaker=speaker,
                chapter=chapter,
                section=section,
                dialog=dialog,
                story=story,
                output_path=str(output_path),
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
        websocket = None

        try:
            websocket = await self._connect_with_retry()
            debug_log(
                "remote_tts:generate_remote_connected",
                service_url=self.service_url,
                speaker=speaker,
                chapter=chapter,
                section=section,
                dialog=dialog,
                output_path=str(output_path),
            )
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
            debug_log(
                "remote_tts:generate_request_send",
                service_url=self.service_url,
                speaker=speaker,
                chapter=chapter,
                section=section,
                dialog=dialog,
                request_keys=sorted(request.keys()),
                text_length=len(text or ""),
            )
            await websocket.send(json.dumps(request))

            # Receive response metadata only; server writes wav to disk and returns a file path
            metadata = None

            while True:
                message = await asyncio.wait_for(
                    websocket.recv(),
                    timeout=300.0  # Generation timeout (300s/5min for voice cloning)
                )

                if not isinstance(message, str):
                    raise TTSGenerationError(
                        f"Unexpected binary websocket payload from TTS service ({len(message)} bytes); expected metadata only"
                    )

                msg_data = json.loads(message)
                if "error" in msg_data:
                    debug_log(
                        "remote_tts:generate_response_error",
                        service_url=self.service_url,
                        speaker=speaker,
                        chapter=chapter,
                        section=section,
                        dialog=dialog,
                        error=msg_data.get("error"),
                    )
                    raise TTSGenerationError(msg_data["error"])
                elif "done" in msg_data:
                    debug_log(
                        "remote_tts:generate_response_done",
                        service_url=self.service_url,
                        speaker=speaker,
                        chapter=chapter,
                        section=section,
                        dialog=dialog,
                        metadata_received=metadata is not None,
                    )
                    break
                else:
                    metadata = msg_data
                    debug_log(
                        "remote_tts:generate_response_metadata",
                        service_url=self.service_url,
                        speaker=speaker,
                        chapter=chapter,
                        section=section,
                        dialog=dialog,
                        metadata=metadata,
                    )

            if not metadata:
                raise TTSGenerationError("No metadata received from service")

            remote_file_path = metadata.get("file_path")
            if not remote_file_path:
                raise TTSGenerationError("TTS service did not return generated file_path")

            remote_path = Path(remote_file_path)
            if not remote_path.exists():
                raise TTSGenerationError(f"Generated wav file not found: {remote_path}")

            output_path.parent.mkdir(parents=True, exist_ok=True)
            debug_info = {
                "remote_file_path": str(remote_path),
                "remote_file_size_bytes": metadata.get("file_size_bytes"),
                "output_path": str(output_path),
                "speaker": speaker,
                "chapter": chapter,
                "section": section,
                "dialog": dialog,
            }
            try:
                print(f"[REMOTE TTS] adopting generated wav | {json.dumps(debug_info, default=str)}", file=sys.stderr)
            except Exception:
                pass
            adoption_method = "in_place"
            if remote_path.resolve() != output_path.resolve():
                try:
                    os.replace(remote_path, output_path)
                    adoption_method = "replace"
                except OSError as e:
                    if getattr(e, "errno", None) != getattr(os, "EXDEV", 18):
                        raise
                    shutil.copy2(remote_path, output_path)
                    remote_path.unlink()
                    adoption_method = "copy_unlink"
                    debug_log(
                        "remote_tts:generate_file_adopted_cross_device",
                        service_url=self.service_url,
                        speaker=speaker,
                        chapter=chapter,
                        section=section,
                        dialog=dialog,
                        remote_file_path=str(remote_path),
                        output_path=str(output_path),
                    )
            debug_log(
                "remote_tts:generate_file_adopted",
                service_url=self.service_url,
                speaker=speaker,
                chapter=chapter,
                section=section,
                dialog=dialog,
                remote_file_path=str(remote_path),
                output_path=str(output_path),
                adoption_method=adoption_method,
                file_size_bytes=output_path.stat().st_size if output_path.exists() else None,
            )

            # Read back to get numpy array
            audio, sr = sf.read(str(output_path))

            # Return as list of segments (single segment for remote)
            debug_log(
                "remote_tts:generate_complete",
                service_url=self.service_url,
                speaker=speaker,
                chapter=chapter,
                section=section,
                dialog=dialog,
                sample_rate=sr,
                samples=int(audio.shape[0]) if hasattr(audio, 'shape') and len(audio.shape) > 0 else None,
                channels=int(audio.shape[1]) if hasattr(audio, 'shape') and len(audio.shape) > 1 else 1,
            )
            if audio.ndim == 1:
                return [audio], sr
            else:
                return [audio[:, 0]], sr  # Take first channel if stereo

        except Exception as e:
            log_exception(
                "remote_tts:generate_remote_failure",
                e,
                service_url=self.service_url,
                speaker=speaker,
                chapter=chapter,
                section=section,
                dialog=dialog,
                output_path=str(output_path),
            )
            raise
        finally:
            if websocket is not None:
                with contextlib.suppress(Exception):
                    await websocket.close()

    def close(self) -> None:
        """Close provider cleanup resources."""
        if self.fallback_provider:
            self.fallback_provider.close()
