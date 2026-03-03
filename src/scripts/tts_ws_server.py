#!/usr/bin/env python3
"""TTS WebSocket Server - Provides real TTS generation via WebSocket."""

import asyncio
import json
import logging
import os
import sys
import uuid
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, Optional

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

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('tts_service')

# Default port
DEFAULT_PORT = 8765
PID_FILE = Path("/tmp/tts_service.pid")

# GPU log file path
GPU_LOG_FILE = Path("story-entanglement/logs/tts-gpu-service.log")


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
    
    def __init__(self, port: int = DEFAULT_PORT, default_model: str = "qwen3"):
        self.port = port
        self.server = None
        self.default_model = default_model
        self._model_cache: Dict[str, Any] = {}
        
    def _get_or_create_model(self, model_name: str) -> Any:
        """Get cached model or create new one with GPU check."""
        if model_name not in self._model_cache:
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
    
    async def handle_request(self, websocket: Any, path: str) -> None:
        """Handle incoming WebSocket connection with TTS generation."""
        client_addr = websocket.remote_address if hasattr(websocket, 'remote_address') else 'unknown'
        logger.info(f"Client connected: {client_addr}")
        
        try:
            async for message in websocket:
                if not isinstance(message, str):
                    logger.warning(f"Received binary data: {len(message)} bytes")
                    continue
                
                # Parse JSON request
                try:
                    request = json.loads(message)
                    logger.info(f"Request: speaker={request.get('speaker')}, "
                               f"emotion={request.get('emotion')}, "
                               f"text_len={len(request.get('text', ''))}")
                    
                    # Validate request
                    text = request.get('text', '')
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
                        model_name = request.get('model', self.default_model)
                        model = self._get_or_create_model(model_name)
                        
                        # Generate audio
                        import tempfile
                        import soundfile as sf
                        
                        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
                            tmp_path = Path(tmp.name)
                        
                        try:
                            # Prepare parameters
                            speaker = request.get('speaker', 'narrator')
                            emotion = request.get('emotion', 'neutral')
                            language = request.get('language', 'English')
                            instruct = request.get('instruct', '')
                            voice_sample = request.get('voice_sample')
                            custom_voice_config = request.get('character_config', {}).get('custom-voice')
                            
                            # Generate
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
                            
                            # Save audio (generate already saved, but re-read for sending)
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
                            
                            # Send binary audio data
                            await websocket.send(audio_data)
                            
                            # Send done signal
                            await websocket.send(json.dumps({"done": True}))
                            
                            # Log GPU stats after generation
                            log_gpu_stats(model_name, len(self._model_cache))
                            
                        finally:
                            # Cleanup temp file
                            tmp_path.unlink(missing_ok=True)
                        
                    except MemoryError as e:
                        logger.error(f"GPU OOM: {e}")
                        await websocket.send(json.dumps({
                            "error": "GPU out of memory. Try reducing batch size or clearing cache."
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
            try:
                await websocket.send(json.dumps({
                    "error": f"Server error: {str(e)}"
                }))
            except:
                pass
    
    def clear_model_cache(self):
        """Clear cached models to free GPU memory."""
        for name, model in self._model_cache.items():
            logger.info(f"Closing model: {name}")
            model.close()
        self._model_cache.clear()
        
        # Log GPU stats after clearing
        log_gpu_stats("cleared", 0)
    
    async def start(self) -> None:
        """Start the WebSocket server."""
        logger.info(f"Starting TTS server on ws://localhost:{self.port}")
        
        # Log initial GPU stats
        if TTS_MODELS_AVAILABLE:
            log_gpu_stats("startup", 0)
        
        self.server = await ws_serve(
            self.handle_request,
            "localhost",
            self.port
        )
        
        # Write PID file
        PID_FILE.write_text(str(os.getpid()))
        logger.info(f"Server started with PID {os.getpid()}")
        
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
    args = parser.parse_args()
    
    server = TTSServer(port=args.port, default_model=args.model)
    
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
