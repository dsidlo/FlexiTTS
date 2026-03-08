#!/usr/bin/env python3
"""Unit tests for TTS service startup logic."""
import os
import sys
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock, call

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestTTSServiceStartup(unittest.TestCase):
    """Test TTS service startup functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.script_dir = Path(__file__).parent.parent
        self.start_script = self.script_dir / "start_tts_service.py"
        self.pid_file = Path("/tmp/tts_service.pid")
        self.log_file = Path("/tmp/tts_service.log")
        
        # Clean up any existing PID file
        if self.pid_file.exists():
            self.pid_file.unlink()
    
    def tearDown(self):
        """Clean up after tests."""
        if self.pid_file.exists():
            self.pid_file.unlink()
    
    @patch('start_tts_service.wait_for_ready')
    @patch('subprocess.Popen')
    def test_start_service_success(self, mock_popen, mock_wait_ready):
        """Test successful service startup."""
        # Mock wait_for_ready to return success
        mock_wait_ready.return_value = 0
        
        # Mock the Popen process
        mock_process = MagicMock()
        mock_process.pid = 12345
        # Raise TimeoutExpired to simulate service staying running
        mock_process.wait.side_effect = subprocess.TimeoutExpired("wait", 2)
        mock_popen.return_value = mock_process
        
        # Import and run the function
        from start_tts_service import start_tts_service
        
        result = start_tts_service(wait_ready=True)
        
        self.assertEqual(result, 0)
        
        # Verify PID file was written
        self.assertTrue(self.pid_file.exists())
        self.assertEqual(self.pid_file.read_text().strip(), "12345")
    
    @patch('subprocess.Popen')
    def test_start_service_immediate_failure(self, mock_popen):
        """Test service startup when process exits immediately."""
        # Mock the Popen process to exit quickly with error
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_process.returncode = 1
        mock_popen.return_value = mock_process
        
        from start_tts_service import start_tts_service
        
        # Process exits immediately - wait_for_ready is not called
        result = start_tts_service(wait_ready=True)
        
        self.assertEqual(result, 1)
    
    def test_start_service_script_not_found(self):
        """Test behavior when service script doesn't exist."""
        # Rename temporarily
        server_script = self.script_dir / "tts_ws_server.py"
        backup_path = server_script.with_suffix('.py.bak')
        
        if server_script.exists():
            server_script.rename(backup_path)
        
        try:
            from start_tts_service import start_tts_service
            
            result = start_tts_service()
            
            self.assertEqual(result, 1)
        finally:
            # Restore
            if backup_path.exists():
                backup_path.rename(server_script)
    
    @patch('start_tts_service.wait_for_ready')
    def test_pid_file_creation(self, mock_wait_ready):
        """Test that PID file is created correctly."""
        mock_wait_ready.return_value = 0
        
        with patch('subprocess.Popen') as mock_popen:
            mock_process = MagicMock()
            mock_process.pid = 54321
            mock_process.wait.side_effect = subprocess.TimeoutExpired("wait", 2)
            mock_popen.return_value = mock_process
            
            from start_tts_service import start_tts_service
            
            result = start_tts_service(wait_ready=True)
            
            self.assertEqual(result, 0)
            self.assertTrue(self.pid_file.exists())
            self.assertEqual(self.pid_file.read_text().strip(), "54321")


class TestCheckTTSService(unittest.TestCase):
    """Test TTS service health check functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.pid_file = Path("/tmp/tts_service.pid")
        
        # Clean up
        if self.pid_file.exists():
            self.pid_file.unlink()
    
    def tearDown(self):
        """Clean up after tests."""
        if self.pid_file.exists():
            self.pid_file.unlink()
    
    def test_check_no_pid_file(self):
        """Test check when PID file doesn't exist."""
        from check_tts_service import check_tts_service
        
        with self.assertRaises(SystemExit) as cm:
            check_tts_service()
        
        self.assertEqual(cm.exception.code, 1)
    
    @patch('os.kill')
    def test_check_running_process(self, mock_kill):
        """Test check when process is running."""
        # Create PID file with fake PID
        self.pid_file.write_text("12345")
        
        from check_tts_service import check_tts_service
        
        with self.assertRaises(SystemExit) as cm:
            check_tts_service()
        
        # os.kill with signal 0 should be called to check if process exists
        mock_kill.assert_called_once_with(12345, 0)
        self.assertEqual(cm.exception.code, 0)
    
    @patch('os.kill')
    def test_check_dead_process(self, mock_kill):
        """Test check when PID exists but process is dead."""
        self.pid_file.write_text("99999")
        
        # Simulate process lookup error
        mock_kill.side_effect = ProcessLookupError()
        
        from check_tts_service import check_tts_service
        
        with self.assertRaises(SystemExit) as cm:
            check_tts_service()
        
        self.assertEqual(cm.exception.code, 1)
    
    def test_check_invalid_pid(self):
        """Test check when PID file has invalid content."""
        self.pid_file.write_text("not_a_number")
        
        from check_tts_service import check_tts_service
        
        with self.assertRaises(SystemExit) as cm:
            check_tts_service()
        
        self.assertEqual(cm.exception.code, 1)


class TestTTSServer(unittest.TestCase):
    """Test TTS WebSocket server functionality."""
    
    @patch('websockets.server.serve')
    def test_server_start_stop(self, mock_serve):
        """Test server start and stop."""
        from tts_ws_server import TTSServer
        
        server = TTSServer(port=8765)
        
        # Mock the server
        mock_server = MagicMock()
        mock_serve.return_value = mock_server
        
        # Test structure (not async functionality in unittest)
        self.assertEqual(server.port, 8765)
    
    @patch.dict('sys.modules', {'websockets': MagicMock()})
    def test_server_default_port(self):
        """Test default port is 8765."""
        mock_websockets = MagicMock()
        mock_websockets.server = MagicMock()
        with patch.dict('sys.modules', {'websockets': mock_websockets, 'websockets.server': mock_websockets.server}):
            from tts_ws_server import TTSServer, DEFAULT_PORT
            
            server = TTSServer()
            self.assertEqual(server.port, DEFAULT_PORT)


if __name__ == "__main__":
    unittest.main()
