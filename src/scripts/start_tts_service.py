#!/usr/bin/env python3
"""Start the TTS service and wait for it to be ready."""
import subprocess
import sys
import os
import time
from pathlib import Path

# Add src/scripts to path for importing RemoteTTSProvider
sys.path.insert(0, str(Path(__file__).parent))

def start_tts_service(wait_ready: bool = True, timeout: int = 180) -> int:
    """Start TTS service as a background process.
    
    Args:
        wait_ready: Wait for server to report ready status.
        timeout: Maximum time to wait for ready status (seconds).
        
    Returns:
        Exit code (0 for success, 1 for failure).
    """
    script_dir = Path(__file__).parent
    tts_service_script = script_dir / "tts_ws_server.py"
    
    if not tts_service_script.exists():
        print(f"❌ error: TTS service script not found at {tts_service_script}", file=sys.stderr)
        return 1
    
    # Check if already running
    pid_file = Path("/tmp/FlexiTTS_tts_service.pid")
    if pid_file.exists():
        try:
            pid = int(pid_file.read_text().strip())
            os.kill(pid, 0)  # Check if process exists
            print(f"⚠️  TTS service already running (PID {pid})")
            
            if wait_ready:
                return wait_for_ready(timeout)
            return 0
        except (ProcessLookupError, ValueError):
            # Process not running, stale PID file
            pid_file.unlink(missing_ok=True)
    
    try:
        # Start service with nohup so it continues running
        # Redirect output to log file
        log_file = Path("/tmp/FlexiTTS.log")
        log_file.unlink(missing_ok=True)  # Clear old log
        
        print(f"🚀 Starting TTS service (timeout: {timeout}s)...")
        
        process = subprocess.Popen(
            [sys.executable, str(tts_service_script)],
            stdout=open(log_file, 'w'),
            stderr=subprocess.STDOUT,
            start_new_session=True,
            cwd=script_dir.parent.parent  # Run from project root
        )
        
        # Write PID file immediately
        pid_file.write_text(str(process.pid))
        
        # Wait briefly to ensure process didn't fail immediately
        try:
            process.wait(timeout=2)
            # If we get here, process exited quickly
            if process.returncode != 0:
                print(f"❌ error: Service exited with code {process.returncode}", file=sys.stderr)
                return 1
        except subprocess.TimeoutExpired:
            # Process is still running after 2 seconds - good sign
            pass
        
        print(f"✓ Service started (PID {process.pid})")
        
        if wait_ready:
            return wait_for_ready(timeout)
        
        return 0
        
    except Exception as e:
        print(f"❌ error: Failed to start TTS service: {e}", file=sys.stderr)
        return 1


def wait_for_ready(timeout: int = 180) -> int:
    """Wait for TTS service to be ready.
    
    Args:
        timeout: Maximum time to wait (seconds).
        
    Returns:
        Exit code (0 for ready, 1 for timeout).
    """
    try:
        from tts_service import RemoteTTSProvider
    except ImportError:
        print("⚠️  Cannot import RemoteTTSProvider, skipping ready check")
        return 0
    
    print("⏳ Waiting for TTS service to be ready...")
    
    provider = RemoteTTSProvider("ws://localhost:8765")
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        try:
            import asyncio
            result = asyncio.run(provider.health_check(timeout=2.0))
            
            if result.get("ready"):
                print(f"✓ TTS service is ready! Model: {result.get('model', 'unknown')}")
                return 0
            elif result.get("status") == "warming_up":
                elapsed = time.time() - start_time
                print(f"  → Still warming up... ({elapsed:.0f}s)")
                time.sleep(2)
            elif result.get("status") == "healthy":
                print("✓ TTS service is running (not warmed up)")
                return 0
            else:
                print(f"  → Waiting... ({result.get('status', 'unknown')})")
                time.sleep(1)
                
        except Exception as e:
            elapsed = time.time() - start_time
            if elapsed > 5:  # Only print after a few seconds
                print(f"  → Waiting for connection... ({elapsed:.0f}s)")
            time.sleep(1)
    
    print(f"❌ Timeout waiting for TTS service (waited {timeout}s)")
    return 1


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Start TTS WebSocket Server")
    parser.add_argument(
        "--no-wait",
        action="store_true",
        help="Don't wait for server to be ready"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=180,
        help="Timeout for ready check (default: 180s)"
    )
    args = parser.parse_args()
    
    exit_code = start_tts_service(
        wait_ready=not args.no_wait,
        timeout=args.timeout
    )
    sys.exit(exit_code)
