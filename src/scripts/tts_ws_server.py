#!/usr/bin/env python3
"""TTS WebSocket Server - Provides real TTS generation via WebSocket."""

import asyncio
import json
import logging
import os
import sys
import threading
import time
import uuid
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

# Try to import websockets
try:
    import websockets
    try:
        from websockets.server import serve as ws_serve
    except ImportError:
        from websockets import serve as ws_serve

    try:
        from websockets.exceptions import ConnectionClosed as ws_ConnectionClosed
    except ImportError:
        from websockets import ConnectionClosed as ws_ConnectionClosed

    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False
    class MockWebServer:
        pass

    async def mock_serve(*args, **kwargs):
        raise RuntimeError("websockets library is not installed. Please install it with 'pip install websockets'.")

    ws_serve = mock_serve
    ws_ConnectionClosed = Exception

# Import TTS models
try:
    from tts_models import create_model, ModelConfig
    from tts_models.utils import get_gpu_memory_info
    TTS_MODELS_AVAILABLE = True
except (ImportError, ModuleNotFoundError) as e:
    TTS_MODELS_AVAILABLE = False

# Setup logging with immediate flush
class ImmediateFlushHandler(logging.StreamHandler):
    """Log handler that flushes immediately after each emit."""
    def emit(self, record):
        super().emit(record)
        self.flush()

handler = ImmediateFlushHandler()
handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger = logging.getLogger('tts_service')
logger.handlers = []
logger.addHandler(handler)
logger.setLevel(logging.INFO)

# Debug log file for detailed client/server tracing
DEBUG_LOG_FILE = Path("/tmp/FlexiTTS.log")

def debug_log(component: str, message: str, data: Optional[Dict] = None, level: str = "INFO"):
    """Log with unique identifier [component] for traceability.
    
    Logs to both service logger and debug log file.
    """
    import traceback
    import inspect
    
    # Get caller info
    frame = inspect.currentframe()
    if frame and frame.f_back:
        line_no = frame.f_back.f_lineno
    else:
        line_no = 0
    
    log_id = f"[{component}:{line_no}]"
    full_message = f"{log_id} {message}"
    
    if data:
        try:
            data_str = json.dumps(data, default=str)[:500]  # Limit data size
            full_message += f" | DATA: {data_str}"
        except:
            full_message += f" | DATA: {str(data)[:500]}"
    
    # Log to service logger
    if level == "ERROR":
        logger.error(full_message)
    elif level == "WARN":
        logger.warning(full_message)
    elif level == "DEBUG":
        logger.debug(full_message)
    else:
        logger.info(full_message)
    
    # Also write to debug log file
    try:
        timestamp = datetime.now().isoformat()
        with open(DEBUG_LOG_FILE, "a") as f:
            f.write(f"[{timestamp}] {level} {full_message}\n")
    except Exception as e:
        pass  # Silent fail - console logging already done

def log_exception(component: str, context: str, exception: Exception, extra_data: Optional[Dict] = None):
    """Log exception with full traceback and unique identifier."""
    import traceback
    
    tb_str = traceback.format_exc()
    data = {
        'error_type': type(exception).__name__,
        'error_message': str(exception),
        'traceback': tb_str,
        **(extra_data or {})
    }
    
    debug_log(component, f"EXCEPTION in {context}", data, level="ERROR")

# Default port
DEFAULT_PORT = 8765
PID_FILE = Path("/tmp/FlexiTTS_tts_service.pid")

# GPU log file path (separate from main log)
GPU_LOG_FILE = Path("/tmp/FlexiTTS_tts-service-gpu.log")

# Story directory - use from environment or config, default to Story-Entanglement
story_dir = os.environ.get('FLEXITTS_CURRENT_STORY', 'Story-Entanglement')


def log_gpu_stats(
    model_name: str,
    cached_models_count: int = 0
) -> None:
    """Log GPU memory stats to dedicated log file.

    Format: timestamp, model_name, gpu_memory_used_mb, gpu_memory_free_mb, cached_models_count
    """
    try:
        info = get_gpu_memory_info(0) if TTS_MODELS_AVAILABLE else None
        timestamp = datetime.now().isoformat()

        # Create header if file doesn't exist
        header = ""
        if not GPU_LOG_FILE.exists():
            header = "timestamp,model_name,gpu_memory_used_mb,gpu_memory_free_mb,gpu_memory_total_mb,cached_models_count\n"

        # Ensure directory exists
        GPU_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

        with open(GPU_LOG_FILE, "a") as f:
            if header:
                f.write(header)

            if info:
                f.write(f"{timestamp},{model_name},{info.used_mb:.0f},{info.free_mb:.0f},{info.total_mb:.0f},{cached_models_count}\n")
            else:
                f.write(f"{timestamp},{model_name},0,0,0,{cached_models_count}\n")

        if info:
            logger.debug(f"GPU stats logged: {info.used_mb:.0f}/{info.total_mb:.0f} MB used")

    except Exception as e:
        logger.warning(f"Failed to log GPU stats: {e}")


class TTSServer:
    """WebSocket TTS Server with real TTS generation."""

    def __init__(self, port: int = DEFAULT_PORT, default_model: str = "qwen3", warmup: bool = True):
        self.port = port
        self.server = None
        self.default_model = default_model
        self._model_cache: Dict[str, Any] = {}
        self._model_cache_lock = threading.Lock()  # Prevent race conditions
        self._model_ready = False
        self._warmup_enabled = warmup
        self._warmup_thread: Optional[threading.Thread] = None
        self._warmup_error: Optional[str] = None
        self._connected_clients: Set[Any] = set()  # Track connected WebSocket clients
        self._clients_lock = threading.Lock()
        self._alert_queue: List[Dict[str, Any]] = []  # Queue for missed alerts (max 20)
        self._queue_lock = threading.Lock()
        self._max_queue_size = 20
        self._main_loop: Optional[asyncio.AbstractEventLoop] = None  # Main event loop for thread-safe operations

    @property
    def is_ready(self) -> bool:
        """Check if model is loaded and ready."""
        return self._model_ready and self.default_model in self._model_cache

    def _warmup_model_async(self) -> None:
        """Background thread for model warmup."""
        import traceback

        # Log start to file to ensure we have output even if process crashes
        with open("/tmp/FlexiTTS.log", "w") as f:
            f.write(f"Warmup thread started at {datetime.now()}\n")

        if not TTS_MODELS_AVAILABLE:
            msg = "TTS models not available, skipping warmup"
            logger.warning(msg)
            self._warmup_error = msg
            with open("/tmp/FlexiTTS.log", "a") as f:
                f.write(f"ERROR: {msg}\n")
            return

        if not self._warmup_enabled:
            msg = "Model warmup disabled"
            logger.info(msg)
            with open("/tmp/FlexiTTS.log", "a") as f:
                f.write(f"{msg}\n")
            return

        logger.info(f"🚀 Background warmup starting for '{self.default_model}'...")
        logger.info(f"[Warmup] Broadcasting 'Warming up' alert from thread '{threading.current_thread().name}'")
        
        # Broadcast warmup started alert (from background thread, use sync)
        self.broadcast_alert_sync(
            "TTS Service: Warming up",
            "info",
            {"model": self.default_model, "stage": "started"}
        )
        logger.info(f"[Warmup] 'Warming up' alert broadcast scheduled")
        
        start_time = datetime.now()

        try:
            from tts_models import ModelConfig

            logger.info("  → Using device: auto (cuda if available)")
            logger.info(f"  → Loading model '{self.default_model}' (this may take 2-3 minutes on first start)...")

            with open("/tmp/FlexiTTS.log", "a") as f:
                f.write(f"Step 1: Creating config\n")

            config = ModelConfig(device='auto', voice_cache_size=10)

            with open("/tmp/FlexiTTS.log", "a") as f:
                f.write(f"Step 2: Creating model\n")

            model = create_model(self.default_model, config=config, use_cache=False)

            with open("/tmp/FlexiTTS.log", "a") as f:
                f.write(f"Step 3: Caching model\n")

            # Use lock to ensure thread-safe cache update
            with self._model_cache_lock:
                self._model_cache[self.default_model] = model

            # Step 4: Trigger actual model loading with dummy generation
            # (This now works with the fixed adapter)
            with open("/tmp/FlexiTTS.log", "a") as f:
                f.write(f"Step 4: Starting dummy TTS generation to load model weights\n")

            logger.info("  → Triggering actual model load (dummy TTS generation)...")

            try:
                import tempfile

                logger.info("    → Creating temp file for dummy audio output...")
                with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
                    tmp_path = Path(tmp.name)
                    logger.info(f"    ✓ Temp file created: {tmp_path}")

                logger.info("    → Calling model.generate() with dummy text...")
                with open("/tmp/FlexiTTS.log", "a") as f:
                    f.write(f"Step 4a: About to call model.generate() - this may take 30-120 seconds\n")

                gen_start = time.time()
                result = model.generate(
                    text="Test. This is a test of the TTS system.",
                    speaker="test",
                    emotion="neutral",
                    language="English",
                    output_path=tmp_path,
                    custom_voice_config={"speaker": "ryan", "language": "English"}
                )
                gen_elapsed = time.time() - gen_start

                logger.info(f"    ✓ Custom voice generation complete in {gen_elapsed:.1f}s")
                logger.info(f"    ✓ Generated {len(result.audio_segments)} audio segment(s), duration={result.duration_ms}ms")

                with open("/tmp/FlexiTTS.log", "a") as f:
                    f.write(f"Step 4b: Custom voice generation complete in {gen_elapsed:.1f}s\n")

                # Clean up temp file
                tmp_path.unlink(missing_ok=True)

                # Step 5: Also warm up base model for voice cloning
                voice_sample_path = Path(f"{story_dir}/refs/Ayana-voice.wav")
                if voice_sample_path.exists():
                    logger.info("    → Warming up base model (voice cloning)...")
                    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
                        tmp_path2 = Path(tmp.name)

                    try:
                        with open("/tmp/FlexiTTS.log", "a") as f:
                            f.write(f"Step 5a: About to warm up base model with voice_sample\n")

                        gen_start = time.time()
                        result2 = model.generate(
                            text="Voice cloning test.",
                            speaker="test",
                            emotion="neutral",
                            language="English",
                            output_path=tmp_path2,
                            voice_sample=str(voice_sample_path)
                        )
                        gen_elapsed2 = time.time() - gen_start

                        logger.info(f"    ✓ Base model generation complete in {gen_elapsed2:.1f}s")
                        with open("/tmp/FlexiTTS.log", "a") as f:
                            f.write(f"Step 5b: Base model generation complete in {gen_elapsed2:.1f}s\n")
                    finally:
                        tmp_path2.unlink(missing_ok=True)
                else:
                    logger.info("    → Skipping base model warmup (no voice sample available)")

            except Exception as e:
                logger.warning(f"    ⚠ Dummy generation failed (may be expected): {e}")
                with open("/tmp/FlexiTTS.log", "a") as f:
                    f.write(f"Step 4x: Generation failed: {e}\n")

            load_time = (datetime.now() - start_time).total_seconds()
            logger.info(f"✓ Model warmup complete! (took {load_time:.1f}s)")
            logger.info("  → Server ready for TTS generation")
            
            # Broadcast warmup complete alert (from background thread, use sync)
            logger.info(f"[Warmup] Broadcasting 'Ready' alert from thread '{threading.current_thread().name}'")
            self.broadcast_alert_sync(
                "TTS Service: Ready",
                "success",
                {"model": self.default_model, "stage": "complete", "duration_seconds": load_time}
            )
            logger.info(f"[Warmup] 'Ready' alert broadcast scheduled")

            with open("/tmp/FlexiTTS.log", "a") as f:
                f.write(f"SUCCESS: Model loaded in {load_time:.1f}s\n")

            # Log GPU stats after model load
            log_gpu_stats(self.default_model, len(self._model_cache))
            self._model_ready = True

        except Exception as e:
            error_msg = f"❌ Model warmup failed: {e}"
            error_trace = traceback.format_exc()
            logger.error(error_msg)
            logger.error(error_trace)
            self._warmup_error = f"{e}\n{error_trace}"
            self._model_ready = False
            with open("/tmp/FlexiTTS.log", "a") as f:
                f.write(f"ERROR:\n{error_msg}\n{error_trace}\n")

    def start_warmup(self) -> None:
        """Start background model warmup."""
        if self._warmup_enabled and TTS_MODELS_AVAILABLE:
            self._warmup_thread = threading.Thread(
                target=self._warmup_model_async,
                name="ModelWarmup",
                daemon=True
            )
            self._warmup_thread.start()
            logger.info("  → Model warmup started in background thread")
        else:
            logger.info("  → Model warmup skipped (disabled or models unavailable)")
            logger.info("  → First request will trigger model load (2-3 minute delay)")

    async def _add_client(self, websocket: Any) -> None:
        """Add client to connected clients set."""
        with self._clients_lock:
            self._connected_clients.add(websocket)
        logger.info(f"[ClientMgmt] Client added. Total connected: {len(self._connected_clients)}")

    async def _remove_client(self, websocket: Any) -> None:
        """Remove client from connected clients set."""
        with self._clients_lock:
            self._connected_clients.discard(websocket)
        logger.info(f"[ClientMgmt] Client removed. Total connected: {len(self._connected_clients)}")

    def _queue_alert(self, message: str, alert_type: str = "info", metadata: Optional[Dict[str, Any]] = None) -> None:
        """Store alert in queue for future clients."""
        alert_data = {
            "type": "alert",
            "alertType": alert_type,
            "message": message,
            "source": "tts-service",
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata or {}
        }
        with self._queue_lock:
            self._alert_queue.append(alert_data)
            current_size = len(self._alert_queue)
            # Keep only last N alerts
            if len(self._alert_queue) > self._max_queue_size:
                self._alert_queue.pop(0)
                logger.debug(f"[AlertQueue] Alert queued (trimmed): '{message}' (size={current_size}, max={self._max_queue_size})")
            else:
                logger.debug(f"[AlertQueue] Alert queued: '{message}' (size={current_size})")

    async def _send_queued_alerts(self, websocket: Any) -> None:
        """Send queued alerts to newly connected client."""
        with self._queue_lock:
            alerts_to_send = list(self._alert_queue)
            queue_size = len(self._alert_queue)
        
        if alerts_to_send:
            logger.info(f"[AlertQueue] Sending {len(alerts_to_send)}/{queue_size} queued alerts to new client")
        
        sent_count = 0
        for alert in alerts_to_send:
            try:
                await websocket.send(json.dumps(alert))
                sent_count += 1
                logger.debug(f"[AlertQueue] Sent queued alert: {alert['message']}")
            except Exception as e:
                logger.warning(f"[AlertQueue] Failed to send queued alert: {e}")
                break
        
        if sent_count > 0:
            logger.info(f"[AlertQueue] Successfully sent {sent_count} queued alerts")

    def broadcast_alert_sync(self, message: str, alert_type: str = "info", metadata: Optional[Dict[str, Any]] = None) -> None:
        """Schedule an alert to be broadcast from any thread (sync version).
        
        Alerts are queued for clients that connect later, and broadcast
        to currently connected WebSocket clients.
        """
        import threading
        current_thread = threading.current_thread().name
        
        logger.debug(f"[AlertBroadcast] broadcast_alert_sync called from thread '{current_thread}': {message}")
        
        # 1. Always queue the alert so clients connecting later will see it
        self._queue_alert(message, alert_type, metadata)
        logger.debug(f"[AlertBroadcast] Alert queued: {message}")
        
        # 2. Broadcast to connected WebSocket clients
        # Use stored main loop for thread-safe operations from background threads
        if self._main_loop and self._main_loop.is_running():
            try:
                logger.debug(f"[AlertBroadcast] Using stored main loop (running={self._main_loop.is_running()})")
                asyncio.run_coroutine_threadsafe(
                    self.broadcast_alert(message, alert_type, metadata),
                    self._main_loop
                )
                logger.debug(f"[AlertBroadcast] Successfully scheduled alert via main loop")
            except Exception as e:
                logger.warning(f"[AlertBroadcast] Failed to schedule alert via main loop: {e}")
        else:
            # Fallback: try current thread's loop (for calls from main thread)
            logger.debug(f"[AlertBroadcast] Falling back to current thread loop (main_loop={self._main_loop})")
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(self.broadcast_alert(message, alert_type, metadata))
                    logger.debug(f"[AlertBroadcast] Scheduled alert via create_task")
                else:
                    loop.run_until_complete(self.broadcast_alert(message, alert_type, metadata))
                    logger.debug(f"[AlertBroadcast] Executed alert via run_until_complete")
            except Exception as e:
                logger.warning(f"[AlertBroadcast] Failed to schedule alert: {e}")

    async def broadcast_alert(
        self,
        message: str,
        alert_type: str = "info",
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Broadcast an alert message to all connected clients."""
        alert_data = {
            "type": "alert",
            "alertType": alert_type,
            "message": message,
            "source": "tts-service",
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata or {}
        }
        
        message_json = json.dumps(alert_data)
        
        # Use a snapshot of clients to avoid concurrent modification
        with self._clients_lock:
            clients = list(self._connected_clients)
        
        client_count = len(clients)
        logger.debug(f"[AlertBroadcast] Broadcasting to {client_count} clients: {message}")
        
        disconnected = []
        sent_count = 0
        for client in clients:
            try:
                await client.send(message_json)
                sent_count += 1
            except Exception as e:
                logger.warning(f"[AlertBroadcast] Failed to send alert to client: {e}")
                disconnected.append(client)
        
        if sent_count > 0:
            logger.info(f"[AlertBroadcast] Sent '{message}' to {sent_count}/{client_count} clients")
        elif client_count > 0:
            logger.warning(f"[AlertBroadcast] Failed to send to any of {client_count} clients")
        
        # Clean up disconnected clients
        if disconnected:
            with self._clients_lock:
                for client in disconnected:
                    self._connected_clients.discard(client)

    async def handle_request(self, websocket: Any, path: str) -> None:
        """Handle incoming WebSocket connection."""
        client_addr = websocket.remote_address if hasattr(websocket, 'remote_address') else 'unknown'
        logger.info(f"[WebSocket] Client connected: {client_addr}")
        logger.debug(f"[WebSocket] Server state: ready={self.is_ready}, queue_size={len(self._alert_queue)}, clients={len(self._connected_clients)}")

        await self._add_client(websocket)

        # Send any queued alerts (e.g., warmup messages sent before client connected)
        logger.debug(f"[WebSocket] Sending queued alerts to {client_addr}")
        await self._send_queued_alerts(websocket)

        # Send current status immediately on connect so client knows warmup state
        try:
            status_msg = {
                'type': 'status',
                'status': 'ready' if self.is_ready else 'warming_up',
                'ready': self.is_ready,
                'model': self.default_model,
                'cached': self.default_model in self._model_cache,
                'message': 'Model loading in progress...' if not self.is_ready else 'Ready'
            }
            await websocket.send(json.dumps(status_msg))
            logger.info(f"[WebSocket] Sent initial status to {client_addr}: ready={self.is_ready}")
        except Exception as e:
            logger.warning(f"[WebSocket] Failed to send initial status to {client_addr}: {e}")
        
        try:
            async for message in websocket:
                if not isinstance(message, str):
                    logger.warning(f"Received binary data: {len(message)} bytes")
                    continue

                try:
                    data = json.loads(message)

                    # Check if health check
                    if data.get('action') == 'health':
                        status = 'healthy' if self.is_ready else 'warming_up'
                        if self._warmup_error:
                            status = 'error'

                        await websocket.send(json.dumps({
                            'status': status,
                            'model': self.default_model,
                            'ready': self.is_ready,
                            'model_cached': self.default_model in self._model_cache,
                            'warmup_error': self._warmup_error,
                            'message': 'Model loading in progress...' if not self.is_ready else 'Ready'
                        }))
                        return  # Close connection after health check

                    # Handle generation request
                    logger.info(f"Request: speaker={data.get('speaker')}, "
                               f"emotion={data.get('emotion')}, "
                               f"text_len={len(data.get('text', ''))}")

                    # Validate request
                    text = data.get('text', '')
                    if len(text) > 2000:
                        await websocket.send(json.dumps({
                            "error": f"Text too long: {len(text)} chars (max 2000)"
                        }))
                        continue

                    if not text:
                        await websocket.send(json.dumps({
                            "error": "Empty text"
                        }))
                        continue

                    # Check if TTS is available
                    if not TTS_MODELS_AVAILABLE:
                        await websocket.send(json.dumps({
                            "error": "TTS models not available"
                        }))
                        continue

                    try:
                        # Get/create model
                        import time
                        model_start = time.time()
                        model_name = data.get('model', self.default_model)
                        logger.info(f"Getting/creating model: {model_name}")
                        model = self._get_or_create_model(model_name)
                        model_elapsed = time.time() - model_start
                        logger.info(f"Model ready in {model_elapsed:.1f}s")

                        # Generate audio
                        import tempfile
                        import soundfile as sf

                        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
                            tmp_path = Path(tmp.name)

                        try:
                            # Prepare parameters
                            speaker = data.get('speaker', 'narrator')
                            emotion = data.get('emotion', 'neutral')
                            language = data.get('language', 'English')
                            instruct = data.get('instruct', '')

                            # Extract voice configuration from request or character_config
                            # Supports both flat keys and nested character_config
                            char_cfg = data.get('character_config', {})

                            # Look for voice sample (supports both underscore and hyphen)
                            voice_sample = data.get('voice_sample') or data.get('voice-sample') or char_cfg.get('voice-sample')

                            # Look for custom voice config (supports both underscore and hyphen)
                            custom_voice_config = (
                                data.get('custom_voice_config') or
                                data.get('custom-voice') or
                                char_cfg.get('custom-voice')
                            )

                            # Log what we found for debugging
                            if voice_sample:
                                logger.info(f"  Using voice sample: {voice_sample}")
                            elif custom_voice_config:
                                logger.info(f"  Using custom voice: {custom_voice_config.get('speaker', 'unknown')}")
                            else:
                                logger.warning(f"  No voice config found in request. char_cfg keys: {list(char_cfg.keys()) if char_cfg else 'None'}")

                            # Extract generation metadata for alerts
                            metadata = {
                                "story": data.get("story"),
                                "chapter": data.get("chapter"),
                                "section": data.get("section"),
                                "dialog": data.get("dialog"),
                                "character": speaker,
                                "text_length": len(text),
                                "emotion": emotion,
                            }

                            # Broadcast start alert
                            await self.broadcast_alert(
                                "TTS Service: Starting voice generation",
                                "info",
                                metadata
                            )

                            # Generate
                            logger.info(f"Starting generation for text length {len(text)}...")
                            gen_start = time.time()
                            result = model.generate(
                                text=text,
                                speaker=speaker,
                                emotion=emotion,
                                language=language,
                                output_path=tmp_path,
                                instruct=instruct,
                                voice_sample=voice_sample,
                                custom_voice_config=custom_voice_config
                            )

                            # Get generated audio
                            sr = result.sample_rate
                            wavs = result.audio_segments

                            # Save audio
                            with open(tmp_path, 'rb') as f:
                                audio_data = f.read()

                            # Send metadata
                            await websocket.send(json.dumps({
                                "status": "success",
                                "model": model_name,
                                "sample_rate": sr,
                                "format": "wav",
                                "segments": len(wavs),
                                "text_length": len(text),
                                "duration_ms": result.duration_ms
                            }))

                            gen_elapsed = time.time() - gen_start
                            logger.info(f"Generation complete in {gen_elapsed:.1f}s")

                            # Send binary audio data
                            await websocket.send(audio_data)

                            # Send done signal
                            await websocket.send(json.dumps({"done": True, "generation_time": gen_elapsed}))

                            # Broadcast completion alert
                            await self.broadcast_alert(
                                f"TTS Service: Generation complete ({gen_elapsed:.1f}s)",
                                "success",
                                {**metadata, "duration_seconds": gen_elapsed}
                            )

                            # Log GPU stats
                            log_gpu_stats(model_name, len(self._model_cache))

                        finally:
                            tmp_path.unlink(missing_ok=True)

                    except MemoryError as e:
                        logger.error(f"GPU OOM: {e}")
                        await websocket.send(json.dumps({
                            "error": "GPU out of memory. Try reducing batch size."
                        }))

                    except ValueError as e:
                        logger.error(f"TTS error: {e}")
                        await websocket.send(json.dumps({
                            "error": f"TTS generation failed: {str(e)}"
                        }))

                    except Exception as e:
                        logger.exception("Generation failed")
                        await websocket.send(json.dumps({
                            "error": f"Generation failed: {str(e)}"
                        }))

                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON: {e}")
                    await websocket.send(json.dumps({
                        "error": f"Invalid JSON: {str(e)}"
                    }))

        except ws_ConnectionClosed:
            logger.info(f"Client disconnected: {client_addr}")
        except Exception as e:
            logger.error(f"Error handling request: {e}")
        finally:
            await self._remove_client(websocket)

    def _get_or_create_model(self, model_name: str) -> Any:
        """Get cached model or create new one with thread-safe locking."""
        # Fast path: check cache without locking
        if model_name in self._model_cache:
            return self._model_cache[model_name]

        # Slow path: need to create model, use lock to prevent duplicates
        with self._model_cache_lock:
            # Double-check after acquiring lock (another thread may have created it)
            if model_name in self._model_cache:
                return self._model_cache[model_name]

            logger.info(f"Creating model: {model_name}")

            if not TTS_MODELS_AVAILABLE:
                raise RuntimeError("TTS models not available")

            from tts_models import ModelConfig
            config = ModelConfig(device='auto', voice_cache_size=10)

            model = create_model(model_name, config=config, use_cache=False)
            self._model_cache[model_name] = model

            # Log GPU stats after model creation
            log_gpu_stats(model_name, len(self._model_cache))

        return self._model_cache[model_name]

    def clear_model_cache(self):
        """Clear cached models to free GPU memory."""
        for name, model in self._model_cache.items():
            logger.info(f"Closing model: {name}")
            model.close()
        self._model_cache.clear()
        self._model_ready = False

        # Log GPU stats after clearing
        log_gpu_stats("cleared", 0)

    async def start(self) -> None:
        """Start the WebSocket server."""
        logger.info(f"Starting TTS server on ws://localhost:{self.port}")

        # Store reference to main event loop for thread-safe operations
        self._main_loop = asyncio.get_event_loop()
        logger.info(f"  → Stored main event loop: {self._main_loop}")

        # Log initial GPU stats
        if TTS_MODELS_AVAILABLE:
            log_gpu_stats("startup", 0)

        # Start background model warmup (server starts immediately)
        self.start_warmup()

        self.server = await ws_serve(
            self.handle_request,
            "localhost",
            self.port,
            ping_interval=None,  # Disable automatic pings for long-running generation
            close_timeout=120   # Allow 120s for graceful close
        )

        # Write PID file
        PID_FILE.write_text(str(os.getpid()))
        logger.info(f"✓ Server accepting connections (PID {os.getpid()})")

        # Keep running until interrupted
        await self.server.wait_closed()

    def stop(self) -> None:
        """Stop the server and release resources."""
        logger.info("Stopping TTS server...")

        # Clear model cache
        try:
            self.clear_model_cache()
        except Exception as e:
            logger.warning(f"Error clearing cache: {e}")

        if self.server:
            self.server.close()

        PID_FILE.unlink(missing_ok=True)
        logger.info("Server stopped")


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="TTS WebSocket Server")
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"Port to listen on (default: {DEFAULT_PORT})"
    )
    parser.add_argument(
        "--model",
        type=str,
        default="qwen3",
        help="Default TTS model (default: qwen3)"
    )
    parser.add_argument(
        "--no-warmup",
        action="store_true",
        help="Skip model warmup on startup (model will load on first request)"
    )
    args = parser.parse_args()

    server = TTSServer(
        port=args.port,
        default_model=args.model,
        warmup=not args.no_warmup
    )

    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
        server.stop()
    except Exception as e:
        logger.error(f"Server error: {e}")
        server.stop()
        sys.exit(1)


if __name__ == "__main__":
    main()
