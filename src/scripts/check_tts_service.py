#!/usr/bin/env python3
"""Check if TTS service is running and ready."""
import sys
import os
from pathlib import Path

# Debugging: log to stderr for visibility
DEBUG = os.environ.get('TTS_CHECK_DEBUG', '').lower() in ('1', 'true', 'yes')
def debug(msg):
    if DEBUG:
        print(f"[DEBUG] {msg}", file=sys.stderr, flush=True)

# Add src/scripts to path for importing RemoteTTSProvider
sys.path.insert(0, str(Path(__file__).parent))
debug(f"Python path: {sys.path[0]}")

def check_tts_service_detailed():
    """Check if TTS service is running and ready."""
    pid_file = Path("/tmp/FlexiTTS_tts_service.pid")
    debug(f"Checking PID file: {pid_file}")
    
    if not pid_file.exists():
        debug("PID file does not exist")
        return {"status": "stopped", "ready": False, "error": "No PID file"}
    
    try:
        pid = int(pid_file.read_text().strip())
        debug(f"PID found: {pid}")
        os.kill(pid, 0)
        debug(f"Process {pid} exists")
        
        # Try health check
        try:
            debug("Attempting WebSocket health check...")
            from tts_service import RemoteTTSProvider
            import asyncio
            
            provider = RemoteTTSProvider("ws://localhost:8765")
            result = asyncio.run(provider.health_check(timeout=5.0))
            debug(f"Health check result: {result}")
            
            return {
                "status": result.get("status", "unknown"),
                "ready": result.get("ready", False),
                "model": result.get("model"),
                "cached": result.get("model_cached"),
                "pid": pid
            }
        except ImportError as e:
            debug(f"Import error: {e}")
            return {
                "status": "running_import_error",
                "ready": False,
                "pid": pid,
                "error": f"Import failed: {e}"
            }
        except Exception as e:
            debug(f"Health check failed: {e}")
            return {
                "status": "running_but_not_responding",
                "ready": False,
                "pid": pid,
                "error": str(e)
            }
            
    except ProcessLookupError:
        debug(f"Process {pid} not found (ProcessLookupError)")
        return {"status": "crashed", "ready": False, "error": f"PID file exists but process {pid} not found"}
    except ValueError as e:
        debug(f"Invalid PID in file: {e}")
        return {"status": "crashed", "ready": False, "error": f"Invalid PID in file: {e}"}
    except OSError as e:
        debug(f"OS error checking process: {e}")
        return {"status": "crashed", "ready": False, "error": f"OS error: {e}"}

def check_tts_service():
    """Simple check for compatibility with existing scripts."""
    result = check_tts_service_detailed()
    status = result["status"]
    ready = result.get("ready", False)
    
    debug(f"Final status: {status}, ready: {ready}")
    
    if status == "stopped":
        print("false")
        sys.exit(1)
    elif ready:
        print("ready")
        sys.exit(0)
    elif status in ("running_but_not_responding", "warming_up", "running_import_error", "unhealthy"):
        # Service is running but not ready yet (warming up, connection issue, or health check failed)
        print("starting")
        sys.exit(0)
    elif status == "crashed":
        # Service crashed or has invalid state
        print("crashed")
        sys.exit(1)
    else:
        print(status)
        sys.exit(1)

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Check TTS service status")
    parser.add_argument(
        "--detailed",
        action="store_true",
        help="Show detailed status"
    )
    args = parser.parse_args()
    
    if args.detailed:
        import json
        result = check_tts_service_detailed()
        print(json.dumps(result, indent=2))
    else:
        check_tts_service()
