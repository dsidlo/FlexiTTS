#!/usr/bin/env python3
"""Start the TTS service in the background."""
import subprocess
import sys
import os
from pathlib import Path

def start_tts_service():
    """Start TTS service as a background process."""
    script_dir = Path(__file__).parent
    tts_service_script = script_dir / "tts_ws_server.py"
    
    if not tts_service_script.exists():
        print(f"error: TTS service script not found at {tts_service_script}", file=sys.stderr)
        sys.exit(1)
    
    try:
        # Start service with nohup so it continues running
        # Redirect output to log file
        log_file = Path("/tmp/tts_service.log")
        
        process = subprocess.Popen(
            [sys.executable, str(tts_service_script)],
            stdout=open(log_file, 'w'),
            stderr=subprocess.STDOUT,
            start_new_session=True,
            cwd=script_dir.parent.parent  # Run from project root
        )
        
        # Write PID file immediately
        pid_file = Path("/tmp/tts_service.pid")
        pid_file.write_text(str(process.pid))
        
        # Wait briefly to ensure process didn't fail immediately
        try:
            process.wait(timeout=2)
            # If we get here, process exited quickly
            if process.returncode != 0:
                print(f"error: Service exited with code {process.returncode}", file=sys.stderr)
                sys.exit(1)
        except subprocess.TimeoutExpired:
            # Process is still running after 2 seconds - good sign
            pass
        
        print(f"started: PID {process.pid}")
        sys.exit(0)
    except Exception as e:
        print(f"error: Failed to start TTS service: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    start_tts_service()
