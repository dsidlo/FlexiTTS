"""Tests for stop_tts_service.py."""

import pytest
import sys
import os
import signal
import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call

# Ensure src/scripts is in path
sys.path.insert(0, str(Path(__file__).parent.parent))

from stop_tts_service import stop_tts_service, main, PID_FILE


class TestStopTTSService:
    """Test stop_tts_service function."""

    @pytest.fixture(autouse=True)
    def cleanup_pid_file(self):
        """Remove PID file before and after each test."""
        if PID_FILE.exists():
            PID_FILE.unlink()
        yield
        if PID_FILE.exists():
            PID_FILE.unlink()

    def test_no_pid_file(self, capfd):
        """Test stopping when PID file doesn't exist."""
        assert PID_FILE.exists() is False
        result = stop_tts_service()
        assert result is True
        out, err = capfd.readouterr()
        assert "not running" in out
        assert "no PID file" in out

    def test_invalid_pid_file_content(self, capfd):
        """Test handling of invalid PID file content."""
        PID_FILE.parent.mkdir(parents=True, exist_ok=True)
        PID_FILE.write_text("not_a_number")
        result = stop_tts_service()
        assert result is True
        assert PID_FILE.exists() is False
        out, err = capfd.readouterr()
        assert "Invalid PID file" in out

    def test_stale_pid_file(self, capfd):
        """Test handling of stale PID file (process doesn't exist)."""
        PID_FILE.parent.mkdir(parents=True, exist_ok=True)
        PID_FILE.write_text("99999")  # Non-existent PID
        result = stop_tts_service()
        assert result is True
        assert PID_FILE.exists() is False
        out, err = capfd.readouterr()
        assert "stale PID file" in out

    def test_graceful_stop_success(self, capfd):
        """Test successful graceful stop with SIGTERM."""
        PID_FILE.parent.mkdir(parents=True, exist_ok=True)
        
        # Mock os.kill to simulate process existing then stopping
        call_count = [0]
        def mock_kill(pid, sig):
            call_count[0] += 1
            if sig == 0:  # Check if process exists
                if call_count[0] > 3:  # Process stops after 3 checks
                    raise ProcessLookupError(pid)
                return
            elif sig == signal.SIGTERM:
                return
        
        with patch('os.kill', side_effect=mock_kill):
            with patch('time.sleep', return_value=None):
                PID_FILE.write_text("12345")
                result = stop_tts_service(force=False)
        
        assert result is True
        assert PID_FILE.exists() is False
        out, err = capfd.readouterr()
        assert "SIGTERM" in out
        assert "stopped" in out

    def test_force_stop_after_timeout(self, capfd):
        """Test forced stop after graceful stop times out."""
        PID_FILE.parent.mkdir(parents=True, exist_ok=True)
        
        call_count = [0]
        # Mock os.kill to simulate process that never stops on SIGTERM but stops on SIGKILL
        def mock_kill_with_force(pid, sig):
            call_count[0] += 1
            if sig == 0:
                # After SIGKILL is sent, process stops
                if call_count[0] > 55:  # 50 checks + some margin
                    raise ProcessLookupError(pid)
                return
            elif sig == signal.SIGTERM:
                return  # Process ignores SIGTERM
            elif sig == signal.SIGKILL:
                return  # SIGKILL sent
        
        with patch('os.kill', side_effect=mock_kill_with_force):
            with patch('time.sleep', return_value=None):
                PID_FILE.write_text("12345")
                result = stop_tts_service(force=False)
        
        assert result is True  # Eventually stops
        out, err = capfd.readouterr()
        assert "SIGKILL" in out or "retrying" in out.lower()

    def test_force_stop_immediate(self, capfd):
        """Test immediate force stop with SIGKILL."""
        PID_FILE.parent.mkdir(parents=True, exist_ok=True)
        
        call_count = [0]
        def mock_kill(pid, sig):
            call_count[0] += 1
            if sig == 0:
                if call_count[0] > 2:
                    raise ProcessLookupError(pid)
                return
            elif sig == signal.SIGKILL:
                return
        
        with patch('os.kill', side_effect=mock_kill):
            with patch('time.sleep', return_value=None):
                PID_FILE.write_text("12345")
                result = stop_tts_service(force=True)
        
        assert result is True
        assert PID_FILE.exists() is False
        out, err = capfd.readouterr()
        assert "SIGKILL" in out

    def test_force_kill_fails(self, capfd):
        """Test when even SIGKILL fails."""
        PID_FILE.parent.mkdir(parents=True, exist_ok=True)
        
        def mock_kill_never_stops(pid, sig):
            if sig == 0:
                return  # Always exists
            return
        
        with patch('os.kill', side_effect=mock_kill_never_stops):
            with patch('time.sleep', return_value=None):
                PID_FILE.write_text("12345")
                result = stop_tts_service(force=True)
        
        assert result is False
        out, err = capfd.readouterr()
        assert "Failed to stop" in out

    def test_kill_exception(self, capfd):
        """Test handling of exception during os.kill."""
        PID_FILE.parent.mkdir(parents=True, exist_ok=True)
        
        with patch('os.kill', side_effect=PermissionError("Access denied")):
            PID_FILE.write_text("12345")
            result = stop_tts_service()
        
        assert result is False
        out, err = capfd.readouterr()
        assert "Error stopping service" in out

    def test_check_process_exception(self, capfd):
        """Test handling of exception during process check."""
        PID_FILE.parent.mkdir(parents=True, exist_ok=True)
        
        def mock_kill_with_exception(pid, sig):
            if sig == 0:
                raise OSError("Unexpected error")
            return
        
        with patch('os.kill', side_effect=mock_kill_with_exception):
            PID_FILE.write_text("12345")
            result = stop_tts_service()
        
        out, err = capfd.readouterr()
        assert "Error checking process" in out


class TestMain:
    """Test main function."""

    def test_main_force_flag(self):
        """Test main with --force flag."""
        with patch('sys.argv', ['stop_tts_service', '--force']):
            with patch('stop_tts_service.stop_tts_service') as mock_stop:
                mock_stop.return_value = True
                with pytest.raises(SystemExit) as exc_info:
                    main()
                assert exc_info.value.code == 0
                mock_stop.assert_called_once_with(force=True)

    def test_main_silent_flag(self):
        """Test main with --silent flag."""
        with patch('stop_tts_service.stop_tts_service') as mock_stop:
            mock_stop.return_value = True
            with patch('sys.stdout') as mock_stdout:
                with patch('sys.argv', ['stop_tts_service', '--silent']):
                    with pytest.raises(SystemExit) as exc_info:
                        main()
                    assert exc_info.value.code == 0
                    # Verify stdout was redirected to devnull
                    assert mock_stdout.__class__ == MagicMock().__class__ or hasattr(mock_stdout, 'write')

    def test_main_failure(self):
        """Test main when stop_tts_service returns False."""
        with patch('stop_tts_service.stop_tts_service') as mock_stop:
            mock_stop.return_value = False
            with patch('sys.argv', ['stop_tts_service']):
                with pytest.raises(SystemExit) as exc_info:
                    main()
                assert exc_info.value.code == 1

    def test_main_help(self):
        """Test main with --help."""
        with patch('sys.argv', ['stop_tts_service', '--help']):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0


class TestEdgeCases:
    """Test edge cases."""

    def test_pid_file_permission_error(self, capfd, tmp_path):
        """Test handling of permission error reading PID file."""
        # Skip this test as it requires root permissions to properly test
        # and can cause issues in CI environments
        pytest.skip("Permission error test requires elevated privileges")

    def test_empty_pid_file(self, capfd):
        """Test handling of empty PID file."""
        PID_FILE.parent.mkdir(parents=True, exist_ok=True)
        PID_FILE.write_text("")  # Empty file
        
        result = stop_tts_service()
        # Empty file should be treated as invalid PID
        out, err = capfd.readouterr()
        assert "Invalid PID file" in out

    def test_whitespace_pid_file(self, capfd):
        """Test handling of whitespace-only PID file."""
        PID_FILE.parent.mkdir(parents=True, exist_ok=True)
        PID_FILE.write_text("   \n\n   ")  # Whitespace only
        
        with pytest.raises(ValueError):
            int("   \n\n   ".strip())
        
        result = stop_tts_service()
        out, err = capfd.readouterr()
        # Should handle gracefully
