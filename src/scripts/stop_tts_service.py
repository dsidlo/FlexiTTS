#!/usr/bin/env python3
"""Stop the TTS WebSocket service gracefully."""
import os
import sys
import signal
from pathlib import Path

PID_FILE = Path("/tmp/tts_service.pid")


def stop_tts_service(force: bool = False) -> bool:
    """Stop the TTS service.
    
    Args:
        force: If True, use SIGKILL instead of SIGTERM
        
    Returns:
        True if service was stopped or wasn't running, False on error
    """
    if not PID_FILE.exists():
        print("✓ TTS service not running (no PID file)")
        return True
    
    try:
        pid = int(PID_FILE.read_text().strip())
    except (ValueError, IOError) as e:
        print(f"⚠️  Invalid PID file: {e}")
        PID_FILE.unlink(missing_ok=True)
        return True
    
    # Check if process exists
    try:
        os.kill(pid, 0)  # Signal 0 checks if process exists
    except ProcessLookupError:
        print(f"✓ TTS service not running (stale PID file)")
        PID_FILE.unlink(missing_ok=True)
        return True
    except Exception as e:
        print(f"⚠️  Error checking process: {e}")
    
    # Send shutdown signal
    sig = signal.SIGKILL if force else signal.SIGTERM
    sig_name = "SIGKILL" if force else "SIGTERM"
    
    try:
        print(f"🛑 Sending {sig_name} to TTS service (PID {pid})...")
        os.kill(pid, sig)
        
        # Wait for process to exit (max 5 seconds)
        import time
        for _ in range(50):
            try:
                os.kill(pid, 0)
                time.sleep(0.1)
            except ProcessLookupError:
                print("✓ TTS service stopped")
                PID_FILE.unlink(missing_ok=True)
                return True
        
        # Process still running after 5s
        if not force:
            print("⚠️  Service didn't stop gracefully, retrying with SIGKILL...")
            return stop_tts_service(force=True)
        else:
            print("❌ Failed to stop TTS service")
            return False
            
    except Exception as e:
        print(f"❌ Error stopping service: {e}")
        return False


def main():
    """CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Stop TTS WebSocket Server")
    parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Force kill with SIGKILL"
    )
    parser.add_argument(
        "--silent", "-s",
        action="store_true",
        help="Silent mode (no output)"
    )
    args = parser.parse_args()
    
    if args.silent:
        # Suppress stdout for Electron integration
        sys.stdout = open(os.devnull, 'w')
    
    success = stop_tts_service(force=args.force)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
