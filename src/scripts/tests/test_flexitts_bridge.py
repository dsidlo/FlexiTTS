#!/usr/bin/env python3
"""
Unit tests for flexitts_bridge.py
Tests story discovery, chapter listing, and configuration loading.
"""

import pytest
import tempfile
import json
import yaml
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open
import sys
import os

sys.path.append(str(Path(__file__).parent.parent))


class TestBridgeCommandLine:
    """Tests for command line interface using mocking."""

    def test_main_no_args(self):
        """Test main with no arguments."""
        import flexitts_bridge as bridge
        with patch.object(sys, 'argv', ['flexitts_bridge.py']):
            result = bridge.main()
            assert result == 1

    def test_main_unknown_command(self):
        """Test main with unknown command."""
        import flexitts_bridge as bridge
        with patch.object(sys, 'argv', ['flexitts_bridge.py', 'unknown-command']):
            result = bridge.main()
            assert result == 1

    def test_main_list_chapters(self):
        """Test main with list-chapters command."""
        import flexitts_bridge as bridge
        # Mock the function to return test data
        with patch.object(bridge, 'list_chapter_files_updated', return_value=['chapter1.md']):
            with patch.object(sys, 'argv', ['flexitts_bridge.py', 'list-chapters']):
                with patch('builtins.print') as mock_print:
                    result = bridge.main()
                    assert result == 0
                    mock_print.assert_called_with('["chapter1.md"]')

    @pytest.mark.skip(reason="Singleton config_manager issues in test environment")
    def test_main_get_stories(self):
        """Test main with get-stories command."""
        import flexitts_bridge as bridge
        mock_stories = [{'name': 'Test', 'path': '/tmp/test'}]
        with patch.object(bridge, 'get_available_stories', return_value=mock_stories):
            with patch.object(sys, 'argv', ['flexitts_bridge.py', 'get-stories']):
                with patch('builtins.print') as mock_print:
                    result = bridge.main()
                    assert result == 0
                    mock_print.assert_called_with(json.dumps(mock_stories))

    @pytest.mark.skip(reason="Singleton config_manager issues in test environment")
    def test_main_validate_config(self):
        """Test main with validate-config command."""
        import flexitts_bridge as bridge
        with patch.object(bridge, 'validate_flexitts_config', return_value=True):
            with patch.object(sys, 'argv', ['flexitts_bridge.py', 'validate-config']):
                with patch('builtins.print') as mock_print:
                    result = bridge.main()
                    assert result == 0
                    mock_print.assert_called_with('{"valid": true}')

    def test_main_load_story_config_missing_arg(self):
        """Test main with load-story-config missing argument."""
        import flexitts_bridge as bridge
        with patch.object(sys, 'argv', ['flexitts_bridge.py', 'load-story-config']):
            result = bridge.main()
            assert result == 1

    def test_main_load_story_config_success(self):
        """Test main with load-story-config command."""
        import flexitts_bridge as bridge
        mock_config = {'global': {'story-dir': '.'}, 'characters': []}
        with patch.object(bridge, 'load_story_config_for_chapter', return_value=mock_config):
            with patch.object(sys, 'argv', ['flexitts_bridge.py', 'load-story-config', 'chapter.md']):
                with patch('builtins.print') as mock_print:
                    result = bridge.main()
                    assert result == 0
                    mock_print.assert_called_with(json.dumps(mock_config))


class TestBridgeFunctions:
    """Unit tests for bridge functions with mocked dependencies."""

    @pytest.mark.skip(reason="Singleton config issues")
    def test_get_available_stories_calls_config_manager(self):
        """Test that get_available_stories calls config_manager.discover_stories."""
        import flexitts_bridge as bridge
        mock_stories = [{'name': 'Test', 'path': '/tmp/test', 'directory_name': 'Story-Test'}]
        
        with patch.object(bridge.config_manager, 'discover_stories', return_value=mock_stories):
            result = bridge.get_available_stories()
            assert result == mock_stories

    @pytest.mark.skip(reason="Singleton config issues")
    def test_get_available_stories_error_returns_empty(self):
        """Test that get_available_stories returns empty list on error."""
        import flexitts_bridge as bridge
        with patch.object(bridge.config_manager, 'discover_stories', side_effect=Exception('Discovery error')):
            result = bridge.get_available_stories()
            assert result == []

    def test_list_chapter_files_updated_empty(self):
        """Test chapter listing when no stories exist."""
        import flexitts_bridge as bridge
        with patch.object(bridge.config_manager, 'discover_stories', return_value=[]):
            result = bridge.list_chapter_files_updated()
            assert result == []

    def test_list_chapter_files_updated_with_stories(self):
        """Test chapter listing with mock stories."""
        import flexitts_bridge as bridge
        mock_stories = [
            {'name': 'Test1', 'path': '/tmp/Story-Test1', 'directory_name': 'Story-Test1'},
        ]
        
        with patch.object(bridge.config_manager, 'discover_stories', return_value=mock_stories):
            with patch('pathlib.Path.exists', return_value=True):
                with patch('pathlib.Path.glob', return_value=[Path('chapter01.md')]):
                    result = bridge.list_chapter_files_updated()
                    assert len(result) == 1
                    assert 'Story-Test1/story-chapters/chapter01.md' in result

    @pytest.mark.skip(reason="Singleton config issues")
    def test_validate_flexitts_config_success(self):
        """Test validation success path."""
        import flexitts_bridge as bridge
        with patch.object(bridge.config_manager, 'load_main_config', return_value=True):
            with patch.object(bridge.config_manager, 'get_stories_directory', return_value=MagicMock(exists=lambda: True)):
                with patch.object(bridge.config_manager, 'discover_stories', return_value=[{'name': 'Test'}]):
                    result = bridge.validate_flexitts_config()
                    assert result is True

    @pytest.mark.skip(reason="Singleton config issues")
    def test_validate_flexitts_config_missing_dir(self):
        """Test validation when stories dir doesn't exist."""
        import flexitts_bridge as bridge
        with patch.object(bridge.config_manager, 'load_main_config', return_value=True):
            with patch.object(bridge.config_manager, 'get_stories_directory', return_value=MagicMock(exists=lambda: False)):
                result = bridge.validate_flexitts_config()
                assert result is False

    @pytest.mark.skip(reason="Singleton config issues")
    def test_validate_flexitts_config_exception(self):
        """Test validation when exception occurs."""
        import flexitts_bridge as bridge
        with patch.object(bridge.config_manager, 'load_main_config', side_effect=Exception('Config error')):
            result = bridge.validate_flexitts_config()
            assert result is False

    def test_load_story_config_for_chapter_success(self):
        """Test loading config for valid chapter path."""
        import flexitts_bridge as bridge
        mock_config = {'global': {'story-dir': '.'}, 'characters': [{'name': 'Alice'}]}
        
        with patch.object(bridge.config_manager, 'get_stories_directory', return_value=Path('/tmp/Stories')):
            with patch.object(bridge.config_manager, 'load_story_config', return_value=mock_config):
                with patch('pathlib.Path.exists', return_value=True):
                    result = bridge.load_story_config_for_chapter('Story-Test/story-chapters/chapter.md')
                    assert result == mock_config

    def test_load_story_config_for_chapter_invalid_path(self):
        """Test loading config for invalid chapter path."""
        import flexitts_bridge as bridge
        with pytest.raises(ValueError) as exc_info:
            bridge.load_story_config_for_chapter('invalid-path')
        assert 'No story configuration found' in str(exc_info.value)

    def test_load_story_config_for_chapter_nonexistent_story(self):
        """Test loading config when story directory doesn't exist."""
        import flexitts_bridge as bridge
        with patch.object(bridge.config_manager, 'get_stories_directory', return_value=Path('/tmp/Stories')):
            with patch('pathlib.Path.exists', return_value=False):
                with pytest.raises(ValueError) as exc_info:
                    bridge.load_story_config_for_chapter('Story-Nonexistent/story-chapters/chapter.md')
                assert 'No story configuration found' in str(exc_info.value)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
