#!/usr/bin/env python3
"""Check if TTS service is running."""
import sys
from pathlib import Path

def check_tts_service():
    """Check if TTS service is running by looking for PID file."""
    pid_file = Path("/tmp/tts_service.pid")
    
    if not pid_file.exists():
        print("false")
        sys.exit(1)
    
    try:
        pid = int(pid_file.read_text().strip())
        
        # Check if process is actually running
        import os
        os.kill(pid, 0)
        print("running")
        sys.exit(0)
    except (ProcessLookupError, ValueError, OSError):
        print("false")
        sys.exit(1)

if __name__ == "__main__":
    check_tts_service()
