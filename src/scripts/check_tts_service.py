#!/usr/bin/env python3
"""Check if TTS service is running and ready."""
import sys
import os
from pathlib import Path

# Add src/scripts to path for importing RemoteTTSProvider
sys.path.insert(0, str(Path(__file__).parent))

def check_tts_service_detailed():
    """Check if TTS service is running and ready."""
    pid_file = Path("/tmp/tts_service.pid")
    
    if not pid_file.exists():
        return {"status": "stopped", "ready": False, "error": "No PID file"}
    
    try:
        pid = int(pid_file.read_text().strip())
        os.kill(pid, 0)
        
        # Try health check
        try:
            from tts_service import RemoteTTSProvider
            import asyncio
            
            provider = RemoteTTSProvider("ws://localhost:8765")
            result = asyncio.run(provider.health_check(timeout=5.0))
            
            return {
                "status": result.get("status", "unknown"),
                "ready": result.get("ready", False),
                "model": result.get("model"),
                "cached": result.get("model_cached"),
                "pid": pid
            }
        except Exception as e:
            return {
                "status": "running_but_not_responding",
                "ready": False,
                "pid": pid,
                "error": str(e)
            }
            
    except (ProcessLookupError, ValueError, OSError):
        return {"status": "crashed", "ready": False, "error": "PID file exists but process not found"}

def check_tts_service():
    """Simple check for compatibility with existing scripts."""
    result = check_tts_service_detailed()
    
    if result["status"] == "stopped":
        print("false")
        sys.exit(1)
    elif result.get("ready"):
        print("ready")
        sys.exit(0)
    elif result["status"] == "running_but_not_responding":
        print("starting")
        sys.exit(0)
    else:
        print(result["status"])
        sys.exit(0)

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
