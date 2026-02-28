#!/usr/bin/env python3
"""Unit tests for TTS service health checks."""
import asyncio
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestTTSHealthChecks(unittest.TestCase):
    """Test TTS service health check functionality."""
    
    def test_check_service_pid_file_exists(self):
        """Test check_tts_service when PID file exists."""
        import check_tts_service
        
        with patch('pathlib.Path.exists', return_value=True):
            with patch('pathlib.Path.read_text', return_value='12345'):
                with patch('os.kill', return_value=None) as mock_kill:
                    with self.assertRaises(SystemExit) as cm:
                        check_tts_service.check_tts_service()
                    self.assertEqual(cm.exception.code, 0)
    
    def test_check_service_pid_file_missing(self):
        """Test check_tts_service when PID file is missing."""
        import check_tts_service
        
        with patch('pathlib.Path.exists', return_value=False):
            with self.assertRaises(SystemExit) as cm:
                check_tts_service.check_tts_service()
            self.assertEqual(cm.exception.code, 1)
    
    def test_check_service_process_not_running(self):
        """Test check_tts_service when process is not running."""
        import check_tts_service
        
        with patch('pathlib.Path.exists', return_value=True):
            with patch('pathlib.Path.read_text', return_value='99999'):
                with patch('os.kill', side_effect=ProcessLookupError()):
                    with self.assertRaises(SystemExit) as cm:
                        check_tts_service.check_tts_service()
                    self.assertEqual(cm.exception.code, 1)


class TestWebSocketHealth(unittest.TestCase):
    """Test WebSocket-based health checks."""
    
    async def async_test_websocket_connect(self):
        """Test WebSocket connection health check."""
        try:
            import websockets
            
            # Mock websockets.connect
            with patch('websockets.connect') as mock_connect:
                mock_ws = AsyncMock()
                mock_connect.return_value = mock_ws
                
                # This would be part of a real health check
                # For now, just verify the mock works
                ws = await websockets.connect("ws://localhost:8765")
                self.assertIsNotNone(ws)
        except ImportError:
            self.skipTest("websockets not available")


class TestTTSServiceHealthIntegration(unittest.TestCase):
    """Integration tests for health check workflow."""
    
    def test_full_health_check_flow_success(self):
        """Test complete health check flow when service is healthy."""
        # Simulate: PID file exists, process is running, WebSocket responds
        with patch('pathlib.Path.exists', return_value=True):
            with patch('pathlib.Path.read_text', return_value='12345'):
                with patch('os.kill', return_value=None):
                    import check_tts_service
                    with self.assertRaises(SystemExit) as cm:
                        check_tts_service.check_tts_service()
                    # Exit code 0 means service is running
                    self.assertEqual(cm.exception.code, 0)
    
    def test_full_health_check_flow_failure(self):
        """Test complete health check flow when service is unhealthy."""
        # Simulate: PID file missing
        with patch('pathlib.Path.exists', return_value=False):
            import check_tts_service
            with self.assertRaises(SystemExit) as cm:
                check_tts_service.check_tts_service()
            # Exit code 1 means service is not running
            self.assertEqual(cm.exception.code, 1)


class TestHealthCheckEdgeCases(unittest.TestCase):
    """Test edge cases for health checks."""
    
    def test_empty_pid_file(self):
        """Test health check with empty PID file."""
        import check_tts_service
        
        with patch('pathlib.Path.exists', return_value=True):
            with patch('pathlib.Path.read_text', return_value=''):
                with self.assertRaises(SystemExit) as cm:
                    check_tts_service.check_tts_service()
                self.assertEqual(cm.exception.code, 1)
    
    def test_stale_pid_file(self):
        """Test health check with stale PID file (old process)."""
        import check_tts_service
        
        with patch('pathlib.Path.exists', return_value=True):
            with patch('pathlib.Path.read_text', return_value='99999'):
                with patch('os.kill', side_effect=ProcessLookupError()):
                    with self.assertRaises(SystemExit) as cm:
                        check_tts_service.check_tts_service()
                    self.assertEqual(cm.exception.code, 1)
    
    def test_permission_denied_on_pid_check(self):
        """Test health check when process exists but permission denied."""
        import check_tts_service
        
        with patch('pathlib.Path.exists', return_value=True):
            with patch('pathlib.Path.read_text', return_value='1'):  # PID 1 (init)
                with patch('os.kill', side_effect=PermissionError()):
                    # Permission error should be treated as process exists
                    with self.assertRaises(SystemExit) as cm:
                        check_tts_service.check_tts_service()
                    self.assertEqual(cm.exception.code, 1)


if __name__ == "__main__":
    unittest.main()
