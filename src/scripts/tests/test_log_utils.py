"""Tests for log_utils.py."""

import pytest
import sys
import logging
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call

# Ensure src/scripts is in path
sys.path.insert(0, str(Path(__file__).parent.parent))

from log_utils import (
    setup_script_logging,
    redirect_std_streams,
    _StreamToLogger,
    LOG_FILE
)


class TestSetupScriptLogging:
    """Test setup_script_logging function."""

    @pytest.fixture(autouse=True)
    def cleanup_log_file(self):
        """Remove log file before and after each test."""
        if LOG_FILE.exists():
            LOG_FILE.unlink()
        yield
        if LOG_FILE.exists():
            LOG_FILE.unlink()

    def test_creates_logger(self):
        """Test that logger is created."""
        logger = setup_script_logging("test_script")
        assert logger.name == "test_script"
        assert isinstance(logger, logging.Logger)
        assert logger.level == logging.INFO
        assert logger.propagate is False

    def test_returns_existing_logger_with_handlers(self):
        """Test returning existing logger if already configured."""
        # First call
        logger1 = setup_script_logging("test_existing")
        
        # Second call should return same logger
        logger2 = setup_script_logging("test_existing")
        
        assert logger1 is logger2

    def test_creates_log_directory(self):
        """Test that log directory is created if it doesn't exist."""
        # Use a temporary directory
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_log = Path(tmpdir) / "logs" / "FlexiTTS.log"
            
            with patch('log_utils.LOG_FILE', temp_log):
                assert not temp_log.parent.exists()
                logger = setup_script_logging("test_dir")
                assert temp_log.parent.exists()

    def test_log_file_handler_configuration(self):
        """Test that log file handler is properly configured."""
        logger = setup_script_logging("test_handler")
        
        assert len(logger.handlers) > 0
        handler = logger.handlers[0]
        assert isinstance(handler, logging.FileHandler)
        assert handler.baseFilename.endswith("FlexiTTS.log")
        assert handler.mode == 'a'
        assert handler.encoding == 'utf-8'

    def test_formatter_configuration(self):
        """Test that formatter is properly configured."""
        logger = setup_script_logging("test_format")
        
        handler = logger.handlers[0]
        formatter = handler.formatter
        assert isinstance(formatter, logging.Formatter)
        
        # Check format includes expected components
        assert "%(asctime)s" in formatter._fmt
        assert "%(levelname)s" in formatter._fmt
        assert "%(message)s" in formatter._fmt

    def test_logs_to_file(self):
        """Test that logs are written to file."""
        logger = setup_script_logging("test_output")
        
        test_message = "Test log message 12345"
        logger.info(test_message)
        
        # Read log file and verify message was written
        log_content = LOG_FILE.read_text()
        assert test_message in log_content

    def test_multiple_loggers(self):
        """Test that different loggers can be created."""
        logger1 = setup_script_logging("script1")
        logger2 = setup_script_logging("script2")
        
        assert logger1.name == "script1"
        assert logger2.name == "script2"
        assert logger1 is not logger2

    def test_logger_level(self):
        """Test that logger level is set correctly."""
        logger = setup_script_logging("test_level")
        assert logger.level == logging.INFO
        
        # Test that INFO and above are logged
        assert logger.isEnabledFor(logging.INFO)
        assert logger.isEnabledFor(logging.WARNING)
        assert logger.isEnabledFor(logging.ERROR)


class TestStreamToLogger:
    """Test _StreamToLogger class."""

    @pytest.fixture
    def mock_logger(self):
        """Create mock logger."""
        return Mock()

    def test_init(self, mock_logger):
        """Test initialization."""
        stream = _StreamToLogger(mock_logger, logging.INFO)
        assert stream.logger is mock_logger
        assert stream.level == logging.INFO
        assert stream._buffer == ''

    def test_write_single_line(self, mock_logger):
        """Test writing a single line with newline."""
        stream = _StreamToLogger(mock_logger, logging.INFO)
        result = stream.write("Hello world\n")
        
        assert result == len("Hello world\n")
        mock_logger.log.assert_called_once_with(logging.INFO, "Hello world")

    def test_write_partial_line(self, mock_logger):
        """Test writing without newline (should buffer)."""
        stream = _StreamToLogger(mock_logger, logging.INFO)
        stream.write("Hello ")
        
        assert stream._buffer == "Hello "
        mock_logger.log.assert_not_called()

    def test_write_complete_partial(self, mock_logger):
        """Test completing a partial line."""
        stream = _StreamToLogger(mock_logger, logging.INFO)
        stream.write("Hello ")
        stream.write("world\n")
        
        mock_logger.log.assert_called_once_with(logging.INFO, "Hello world")

    def test_write_multiple_lines(self, mock_logger):
        """Test writing multiple lines at once."""
        stream = _StreamToLogger(mock_logger, logging.INFO)
        stream.write("Line1\nLine2\nLine3\n")
        
        assert mock_logger.log.call_count == 3
        calls = [
            call(logging.INFO, "Line1"),
            call(logging.INFO, "Line2"),
            call(logging.INFO, "Line3")
        ]
        mock_logger.log.assert_has_calls(calls)

    def test_write_empty_string(self, mock_logger):
        """Test writing empty string."""
        stream = _StreamToLogger(mock_logger, logging.INFO)
        result = stream.write("")
        
        assert result == 0
        mock_logger.log.assert_not_called()

    def test_write_whitespace_only(self, mock_logger):
        """Test writing whitespace only."""
        stream = _StreamToLogger(mock_logger, logging.INFO)
        stream.write("   \n")
        
        # Whitespace should not be logged
        # (since we strip before logging)

    def test_flush_empty_buffer(self, mock_logger):
        """Test flush with empty buffer."""
        stream = _StreamToLogger(mock_logger, logging.INFO)
        stream.flush()
        
        mock_logger.log.assert_not_called()

    def test_flush_with_content(self, mock_logger):
        """Test flush with buffered content."""
        stream = _StreamToLogger(mock_logger, logging.INFO)
        stream.write("Unfinished line")
        stream.flush()
        
        mock_logger.log.assert_called_once_with(logging.INFO, "Unfinished line")

    def test_flush_clears_buffer(self, mock_logger):
        """Test that flush clears the buffer."""
        stream = _StreamToLogger(mock_logger, logging.INFO)
        stream.write("Content")
        stream.flush()
        
        assert stream._buffer == ''

    def test_different_log_levels(self):
        """Test different log levels."""
        mock_logger = Mock()
        
        info_stream = _StreamToLogger(mock_logger, logging.INFO)
        error_stream = _StreamToLogger(mock_logger, logging.ERROR)
        
        info_stream.write("Info message\n")
        error_stream.write("Error message\n")
        
        calls = [
            call(logging.INFO, "Info message"),
            call(logging.ERROR, "Error message")
        ]
        mock_logger.log.assert_has_calls(calls)

    def test_write_preserves_return_value(self, mock_logger):
        """Test that write returns the number of characters written."""
        stream = _StreamToLogger(mock_logger, logging.INFO)
        test_string = "Test message here\n"
        result = stream.write(test_string)
        
        assert result == len(test_string)


class TestRedirectStdStreams:
    """Test redirect_std_streams function."""

    @pytest.fixture(autouse=True)
    def restore_std_streams(self):
        """Restore stdout/stderr after each test."""
        original_stdout = sys.stdout
        original_stderr = sys.stderr
        yield
        sys.stdout = original_stdout
        sys.stderr = original_stderr

    def test_redirects_stdout(self):
        """Test that stdout is redirected."""
        mock_logger = Mock()
        
        original_stdout = sys.stdout
        redirect_std_streams(mock_logger)
        
        assert sys.stdout is not original_stdout
        assert isinstance(sys.stdout, _StreamToLogger)

    def test_redirects_stderr(self):
        """Test that stderr is redirected."""
        mock_logger = Mock()
        
        original_stderr = sys.stderr
        redirect_std_streams(mock_logger)
        
        assert sys.stderr is not original_stderr
        assert isinstance(sys.stderr, _StreamToLogger)

    def test_stdout_logs_to_info(self):
        """Test that stdout writes log at INFO level."""
        mock_logger = Mock()
        redirect_std_streams(mock_logger)
        
        sys.stdout.write("Test message\n")
        
        mock_logger.log.assert_called_with(logging.INFO, "Test message")

    def test_stderr_logs_to_error(self):
        """Test that stderr writes log at ERROR level."""
        mock_logger = Mock()
        redirect_std_streams(mock_logger)
        
        sys.stderr.write("Error message\n")
        
        mock_logger.log.assert_called_with(logging.ERROR, "Error message")

    def test_integration_with_real_logger(self):
        """Test integration with a real logger."""
        logger = setup_script_logging("test_redirect")
        
        original_stdout = sys.stdout
        redirect_std_streams(logger)
        
        test_message = "STDOUT redirected message"
        sys.stdout.write(test_message + "\n")
        
        # Restore and check log file
        sys.stdout = original_stdout
        log_content = LOG_FILE.read_text()
        assert test_message in log_content


class TestIntegration:
    """Integration tests for log_utils."""

    def test_full_logging_workflow(self):
        """Test the complete logging workflow."""
        logger = setup_script_logging("integration_test")
        
        # Redirect streams
        original_stdout = sys.stdout
        original_stderr = sys.stderr
        
        redirect_std_streams(logger)
        
        # Log messages
        print("Information message")
        print("Error message", file=sys.stderr)
        
        # Restore
        sys.stdout = original_stdout
        sys.stderr = original_stderr
        
        # Check log file
        log_content = LOG_FILE.read_text()
        assert "Information message" in log_content
        assert "Error message" in log_content

    def test_logger_with_special_characters(self):
        """Test logging with special characters."""
        logger = setup_script_logging("special_chars")
        
        special_messages = [
            "Message with unicode: 你好世界",
            "Message with emoji: 🎉🚀",
            "Message with special: <>&\"'",
        ]
        
        for msg in special_messages:
            logger.info(msg)
        
        log_content = LOG_FILE.read_text()
        for msg in special_messages:
            assert msg in log_content

    def test_multiple_scripts_logging(self):
        """Test multiple scripts logging to same file."""
        logger1 = setup_script_logging("script_a")
        logger2 = setup_script_logging("script_b")
        
        logger1.info("Message from script A")
        logger2.info("Message from script B")
        
        log_content = LOG_FILE.read_text()
        assert "Message from script A" in log_content
        assert "Message from script B" in log_content
        assert "[script_a]" in log_content
        assert "[script_b]" in log_content

    def test_log_file_append_mode(self):
        """Test that log file uses append mode."""
        # Write initial log
        logger1 = setup_script_logging("first")
        logger1.info("First message")
        
        # Create new logger for "different script"
        logger2 = setup_script_logging("second")
        logger2.info("Second message")
        
        log_content = LOG_FILE.read_text()
        assert "First message" in log_content
        assert "Second message" in log_content


class TestEdgeCases:
    """Test edge cases."""

    def test_buffer_accumulation(self):
        """Test that buffer accumulates data without newlines."""
        mock_logger = Mock()
        stream = _StreamToLogger(mock_logger, logging.INFO)
        
        stream.write("Part1")
        stream.write("Part2")
        stream.write("Part3\n")
        
        mock_logger.log.assert_called_once_with(logging.INFO, "Part1Part2Part3")

    def test_flush_with_whitespace_only(self):
        """Test flush with only whitespace in buffer."""
        mock_logger = Mock()
        stream = _StreamToLogger(mock_logger, logging.INFO)
        
        stream.write("   \n\t  ")  # Whitespace only
        stream.flush()
        
        # Whitespace-only messages after stripping are empty, so nothing should be logged
        # or log should be called with empty string
        # The behavior depends on implementation - whitespace gets stripped
        assert stream._buffer == ""  # Buffer should be cleared

    def test_unicode_in_buffer(self):
        """Test handling of unicode in buffer."""
        mock_logger = Mock()
        stream = _StreamToLogger(mock_logger, logging.INFO)
        
        stream.write("Unicode: 你好\n")
        
        mock_logger.log.assert_called_once_with(logging.INFO, "Unicode: 你好")

    def test_long_messages(self):
        """Test handling of long messages."""
        mock_logger = Mock()
        stream = _StreamToLogger(mock_logger, logging.INFO)
        
        long_message = "A" * 10000
        stream.write(long_message + "\n")
        
        mock_logger.log.assert_called_once_with(logging.INFO, long_message)

    def test_immediate_newline(self):
        """Test handling of immediate newline."""
        mock_logger = Mock()
        stream = _StreamToLogger(mock_logger, logging.INFO)
        
        stream.write("\n")
        
        # Should handle gracefully (empty line after stripping)
        # The behavior depends on implementation
        assert stream._buffer == ''
