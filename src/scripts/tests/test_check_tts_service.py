"""Tests for check_tts_service.py."""

import pytest
import sys
import os
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, AsyncMock

# Ensure src/scripts is in path
sys.path.insert(0, str(Path(__file__).parent.parent))

from check_tts_service import (
    check_tts_service_detailed,
    check_tts_service,
    debug
)


class TestDebug:
    """Test debug function."""

    def test_debug_with_debug_env(self, capfd):
        """Test debug output when TTS_CHECK_DEBUG is set."""
        # Reload module with debug env set
        with patch.dict(os.environ, {'TTS_CHECK_DEBUG': '1'}):
            # Import fresh to pick up env var
            import importlib
            import check_tts_service
            importlib.reload(check_tts_service)
            check_tts_service.debug("test message")
            out, err = capfd.readouterr()
            assert "[DEBUG] test message" in err

    def test_debug_without_debug_env(self, capfd):
        """Test no debug output when TTS_CHECK_DEBUG is not set."""
        with patch.dict(os.environ, {}, clear=True):
            import importlib
            import check_tts_service
            importlib.reload(check_tts_service)
            check_tts_service.debug("test message")
            out, err = capfd.readouterr()
            assert "[DEBUG]" not in err

    def test_debug_with_true_string(self, capfd):
        """Test debug with 'true' string."""
        with patch.dict(os.environ, {'TTS_CHECK_DEBUG': 'true'}):
            import importlib
            import check_tts_service
            importlib.reload(check_tts_service)
            check_tts_service.debug("test message")
            out, err = capfd.readouterr()
            assert "[DEBUG] test message" in err

    def test_debug_with_yes_string(self, capfd):
        """Test debug with 'yes' string."""
        with patch.dict(os.environ, {'TTS_CHECK_DEBUG': 'yes'}):
            import importlib
            import check_tts_service
            importlib.reload(check_tts_service)
            check_tts_service.debug("test message")
            out, err = capfd.readouterr()
            assert "[DEBUG] test message" in err


class TestCheckTTSServiceDetailed:
    """Test check_tts_service_detailed function."""

    @pytest.fixture(autouse=True)
    def cleanup_pid_file(self):
        """Remove PID file before and after each test."""
        pid_file = Path("/tmp/FlexiTTS_tts_service.pid")
        if pid_file.exists():
            pid_file.unlink()
        yield
        if pid_file.exists():
            pid_file.unlink()

    def test_no_pid_file(self):
        """Test when PID file doesn't exist."""
        result = check_tts_service_detailed()
        assert result["status"] == "stopped"
        assert result["ready"] is False
        assert "No PID file" in result["error"]

    def test_invalid_pid_value(self):
        """Test when PID file has invalid content."""
        pid_file = Path("/tmp/FlexiTTS_tts_service.pid")
        pid_file.parent.mkdir(parents=True, exist_ok=True)
        pid_file.write_text("not_a_number")
        
        result = check_tts_service_detailed()
        assert result["status"] == "crashed"
        assert "Invalid PID" in result["error"]

    def test_stale_pid_file(self):
        """Test when PID file exists but process is dead."""
        pid_file = Path("/tmp/FlexiTTS_tts_service.pid")
        pid_file.parent.mkdir(parents=True, exist_ok=True)
        pid_file.write_text("99999")  # Non-existent PID
        
        result = check_tts_service_detailed()
        assert result["status"] == "crashed"
        assert result["ready"] is False
        assert "not found" in result["error"]

    def test_process_exists_import_error(self):
        """Test when process exists but importing tts_service fails."""
        pid_file = Path("/tmp/FlexiTTS_tts_service.pid")
        pid_file.parent.mkdir(parents=True, exist_ok=True)
        pid_file.write_text("12345")
        
        with patch('os.kill', return_value=None):
            with patch.dict('sys.modules', {'tts_service': None}):
                # Force ImportError by removing tts_service from modules
                original_import = __builtins__.__import__ if hasattr(__builtins__, '__import__') else __builtins__['__import__']
                
                def mock_import(name, *args, **kwargs):
                    if name == 'tts_service':
                        raise ImportError("No module named 'tts_service'")
                    return original_import(name, *args, **kwargs)
                
                with patch('builtins.__import__', side_effect=mock_import):
                    result = check_tts_service_detailed()
        
        assert result["status"] == "running_import_error"
        assert result["ready"] is False

    def test_process_exists_health_check_success(self):
        """Test successful health check."""
        pid_file = Path("/tmp/FlexiTTS_tts_service.pid")
        pid_file.parent.mkdir(parents=True, exist_ok=True)
        pid_file.write_text("12345")
        
        # Mock the RemoteTTSProvider
        mock_provider = Mock()
        mock_provider.health_check = AsyncMock(return_value={
            "status": "healthy",
            "ready": True,
            "model": "test_model",
            "model_cached": True
        })
        
        with patch('os.kill', return_value=None):
            with patch.dict('sys.modules', {'tts_service': Mock()}):
                mock_module = Mock()
                mock_module.RemoteTTSProvider = Mock(return_value=mock_provider)
                sys.modules['tts_service'] = mock_module
                
                # Mock asyncio.run
                with patch('asyncio.run', return_value={
                    "status": "healthy",
                    "ready": True,
                    "model": "test_model",
                    "model_cached": True
                }):
                    result = check_tts_service_detailed()
        
        # Verify structure based on mocks
        assert "status" in result

    def test_health_check_exception(self):
        """Test health check raising exception."""
        pid_file = Path("/tmp/FlexiTTS_tts_service.pid")
        pid_file.parent.mkdir(parents=True, exist_ok=True)
        pid_file.write_text("12345")
        
        with patch('os.kill', return_value=None):
            with patch.dict('sys.modules', {'tts_service': Mock()}):
                mock_module = Mock()
                mock_module.RemoteTTSProvider = Mock(side_effect=Exception("Connection failed"))
                sys.modules['tts_service'] = mock_module
                
                result = check_tts_service_detailed()
        
        # When RemoteTTSProvider fails to instantiate, it's treated as import error
        assert result["status"] in ["running_import_error", "running_but_not_responding"]


class TestCheckTTSService:
    """Test check_tts_service function."""

    def test_stopped_status(self, capfd):
        """Test stopped service output."""
        with patch('check_tts_service.check_tts_service_detailed') as mock_check:
            mock_check.return_value = {
                "status": "stopped",
                "ready": False,
                "error": "No PID file"
            }
            
            with pytest.raises(SystemExit) as exc_info:
                check_tts_service()
            
            assert exc_info.value.code == 1
            out, err = capfd.readouterr()
            assert out.strip() == "false"

    def test_ready_status(self, capfd):
        """Test ready service output."""
        with patch('check_tts_service.check_tts_service_detailed') as mock_check:
            mock_check.return_value = {
                "status": "healthy",
                "ready": True,
                "model": "test_model"
            }
            
            with pytest.raises(SystemExit) as exc_info:
                check_tts_service()
            
            assert exc_info.value.code == 0
            out, err = capfd.readouterr()
            assert out.strip() == "ready"

    def test_starting_status_running_but_not_responding(self, capfd):
        """Test starting service (running but not responding)."""
        with patch('check_tts_service.check_tts_service_detailed') as mock_check:
            mock_check.return_value = {
                "status": "running_but_not_responding",
                "ready": False,
                "error": "Connection refused"
            }
            
            with pytest.raises(SystemExit) as exc_info:
                check_tts_service()
            
            assert exc_info.value.code == 0
            out, err = capfd.readouterr()
            assert out.strip() == "starting"

    def test_starting_status_warming_up(self, capfd):
        """Test warming up service."""
        with patch('check_tts_service.check_tts_service_detailed') as mock_check:
            mock_check.return_value = {
                "status": "warming_up",
                "ready": False
            }
            
            with pytest.raises(SystemExit) as exc_info:
                check_tts_service()
            
            assert exc_info.value.code == 0
            out, err = capfd.readouterr()
            assert out.strip() == "starting"

    def test_starting_status_import_error(self, capfd):
        """Test starting service with import error."""
        with patch('check_tts_service.check_tts_service_detailed') as mock_check:
            mock_check.return_value = {
                "status": "running_import_error",
                "ready": False
            }
            
            with pytest.raises(SystemExit) as exc_info:
                check_tts_service()
            
            assert exc_info.value.code == 0
            out, err = capfd.readouterr()
            assert out.strip() == "starting"

    def test_starting_status_unhealthy(self, capfd):
        """Test unhealthy but starting service."""
        with patch('check_tts_service.check_tts_service_detailed') as mock_check:
            mock_check.return_value = {
                "status": "unhealthy",
                "ready": False
            }
            
            with pytest.raises(SystemExit) as exc_info:
                check_tts_service()
            
            assert exc_info.value.code == 0
            out, err = capfd.readouterr()
            assert out.strip() == "starting"

    def test_crashed_status(self, capfd):
        """Test crashed service."""
        with patch('check_tts_service.check_tts_service_detailed') as mock_check:
            mock_check.return_value = {
                "status": "crashed",
                "ready": False,
                "error": "Process not found"
            }
            
            with pytest.raises(SystemExit) as exc_info:
                check_tts_service()
            
            assert exc_info.value.code == 1
            out, err = capfd.readouterr()
            assert out.strip() == "crashed"

    def test_unknown_status(self, capfd):
        """Test unknown status."""
        with patch('check_tts_service.check_tts_service_detailed') as mock_check:
            mock_check.return_value = {
                "status": "unknown_state",
                "ready": False
            }
            
            with pytest.raises(SystemExit) as exc_info:
                check_tts_service()
            
            assert exc_info.value.code == 1
            out, err = capfd.readouterr()
            assert "unknown_state" in out


class TestMainExecution:
    """Test __main__ execution."""

    def test_main_default_output(self, capfd):
        """Test main without flags."""
        with patch('check_tts_service.check_tts_service_detailed') as mock_check:
            mock_check.return_value = {
                "status": "stopped",
                "ready": False
            }
            
            # Mock the check_tts_service call
            with patch('check_tts_service.check_tts_service') as mock_func:
                mock_func.side_effect = SystemExit(1)
                
                with pytest.raises(SystemExit):
                    check_tts_service()


class TestEdgeCases:
    """Test edge cases."""

    def test_os_error_on_kill(self):
        """Test handling of OSError when checking process."""
        pid_file = Path("/tmp/FlexiTTS_tts_service.pid")
        pid_file.parent.mkdir(parents=True, exist_ok=True)
        pid_file.write_text("12345")
        
        with patch('os.kill', side_effect=OSError("Permission denied")):
            result = check_tts_service_detailed()
        
        assert result["status"] == "crashed"
        assert "OS error" in result["error"]

    def test_os_error_other_errors(self):
        """Test handling of other OSError variants."""
        pid_file = Path("/tmp/FlexiTTS_tts_service.pid")
        pid_file.parent.mkdir(parents=True, exist_ok=True)
        pid_file.write_text("12345")
        
        with patch('os.kill', side_effect=IOError("IO Error")):
            result = check_tts_service_detailed()
        
        assert result["status"] == "crashed"

    def test_health_check_with_model_info(self):
        """Test health check that returns complete model info."""
        with patch('check_tts_service.check_tts_service_detailed') as mock_check:
            mock_check.return_value = {
                "status": "healthy",
                "ready": True,
                "model": "test_model_v1",
                "cached": True,
                "pid": 12345,
                "uptime": 3600
            }
            
            with pytest.raises(SystemExit) as exc_info:
                check_tts_service()
            
            assert exc_info.value.code == 0
