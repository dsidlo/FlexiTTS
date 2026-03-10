#!/usr/bin/env python3
"""
Test suite for Story Dropdown configuration and discovery features.

Tests written for TDD approach - should fail until Developer implements the code.

This module tests:
1. Config Loading: FlexiTTS.yaml loading, creation, and path expansion
2. Story Discovery: Directory scanning, prefix handling, and metadata extraction
3. IPC Handlers: Bridge commands for story retrieval
"""

import pytest
import tempfile
import shutil
import json
import yaml
import os
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, List, Any

import sys
# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Ensure yaml module is real before importing base_config_manager
# (test isolation: other tests may have mocked yaml in sys.modules)
if 'yaml' in sys.modules and hasattr(sys.modules['yaml'], 'safe_load'):
    pass  # yaml is already the real module
else:
    # Remove any mock yaml and reimport the real one
    if 'yaml' in sys.modules:
        del sys.modules['yaml']
    import yaml  # This will import the real yaml

# Import base ConfigManager (avoid circular import in enhanced config_manager)
from base_config_manager import ConfigManager, config_manager


class TestConfigLoading:
    """Tests for FlexiTTS.yaml configuration loading and management."""
    
    @pytest.fixture
    def temp_config_env(self):
        """Create a temporary configuration environment for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            config_dir = temp_path / ".config" / "FlexiTTS"
            stories_dir = temp_path / "Stories"
            
            # Create directory structure
            config_dir.mkdir(parents=True, exist_ok=True)
            stories_dir.mkdir(parents=True, exist_ok=True)
            
            yield {
                "temp_path": temp_path,
                "config_dir": config_dir,
                "stories_dir": stories_dir,
                "main_config_path": config_dir / "FlexiTTS.yaml"
            }
    
    def test_load_main_config_creates_default(self, temp_config_env):
        """
        Test that load_main_config creates a default config when FlexiTTS.yaml doesn't exist.
        
        Precondition: ~/.config/FlexiTTS/FlexiTTS.yaml does not exist
        Expected: Creates default config with stories-dir = CWD/Stories
        Validation: File exists and contains valid YAML structure
        """
        # Setup - create a fresh config manager in test mode pointing to temp location
        cm = ConfigManager(test_mode=True)
        cm._main_config_path = temp_config_env["main_config_path"]
        # Whitelist the temp config directory for security bypass
        cm.add_test_whitelist(str(temp_config_env["config_dir"].parent))
        
        # Ensure config file doesn't exist
        assert not temp_config_env["main_config_path"].exists(), "Config should not exist initially"
        
        # Execute - load the config (should create default)
        config = cm.load_main_config()
        
        # Verify - config file was created
        assert temp_config_env["main_config_path"].exists(), "Config file should be created"
        
        # Verify - config has expected structure
        assert "FlexiTTS" in config, "Config should have FlexiTTS root key"
        assert "stories-dir" in config["FlexiTTS"], "Config should have stories-dir"
        assert "story-dir-prefix" in config["FlexiTTS"], "Config should have story-dir-prefix"
        
        # Verify - default values are reasonable
        assert config["FlexiTTS"]["story-dir-prefix"] == "Story-", "Default prefix should be 'Story-'"
    
    def test_load_main_config_parses_existing(self, temp_config_env):
        """
        Test that load_main_config correctly parses an existing FlexiTTS.yaml.
        
        Precondition: Valid FlexiTTS.yaml exists with custom stories-dir
        Expected: Returns configuration dict with parsed values
        Validation: stories-dir path matches what was saved
        """
        # Setup - create a custom config file
        custom_config = {
            "FlexiTTS": {
                "stories-dir": str(temp_config_env["stories_dir"]),
                "story-dir-prefix": "CustomStory-",
                "custom-key": "custom-value"
            }
        }
        
        with open(temp_config_env["main_config_path"], 'w') as f:
            yaml.dump(custom_config, f)
        
        # Execute - create test mode config manager with whitelist
        cm = ConfigManager(test_mode=True)
        cm._main_config_path = temp_config_env["main_config_path"]
        cm.add_test_whitelist(str(temp_config_env["config_dir"].parent))
        config = cm.load_main_config()
        
        # Verify - parsed values match what was saved
        assert config["FlexiTTS"]["stories-dir"] == str(temp_config_env["stories_dir"])
        assert config["FlexiTTS"]["story-dir-prefix"] == "CustomStory-"
        assert config["FlexiTTS"]["custom-key"] == "custom-value"
    
    def test_get_stories_directory_expands_tilde(self, temp_config_env):
        """
        Test that get_stories_directory correctly expands ~ to home directory.
        
        Precondition: stories-dir set to '~/workspace/Stories' in config
        Expected: Returns Path with expanded home directory
        Validation: Path.is_absolute() == True and path contains home directory
        """
        # Setup - create config with tilde path
        config_with_tilde = {
            "FlexiTTS": {
                "stories-dir": "~/workspace/FlexiTTS/Stories",
                "story-dir-prefix": "Story-"
            }
        }
        
        with open(temp_config_env["main_config_path"], 'w') as f:
            yaml.dump(config_with_tilde, f)
        
        # Execute - create test mode config manager
        cm = ConfigManager(test_mode=True)
        cm._main_config_path = temp_config_env["main_config_path"]
        cm.add_test_whitelist(str(temp_config_env["config_dir"].parent))
        cm.load_main_config()
        stories_dir = cm.get_stories_directory()
        
        # Verify - path is expanded and absolute
        assert stories_dir.is_absolute(), "Path should be absolute after expansion"
        assert "workspace/FlexiTTS/Stories" in str(stories_dir), "Path should contain the expected directory structure"
        assert not str(stories_dir).startswith("~"), "Tilde should be expanded"


class TestStoryDiscovery:
    """Tests for story discovery and scanning functionality."""
    
    @pytest.fixture
    def temp_stories_env(self):
        """Create a temporary stories directory with test stories."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            stories_dir = temp_path / "Stories"
            stories_dir.mkdir(parents=True, exist_ok=True)
            
            # Create config file pointing to stories directory
            config_dir = temp_path / ".config" / "FlexiTTS"
            config_dir.mkdir(parents=True, exist_ok=True)
            
            main_config = {
                "FlexiTTS": {
                    "stories-dir": str(stories_dir),
                    "story-dir-prefix": "Story-"
                }
            }
            
            config_path = config_dir / "FlexiTTS.yaml"
            with open(config_path, 'w') as f:
                yaml.dump(main_config, f)
            
            yield {
                "temp_path": temp_path,
                "stories_dir": stories_dir,
                "config_path": config_path
            }
    
    def test_discovers_only_story_prefixed_directories(self, temp_stories_env):
        """
        Test that discover_stories only returns directories with the Story- prefix.
        
        Setup: Stories/ contains [Story-Adventure, mystery, Story-Romance, notes.txt]
        Expected: Returns only Story-Adventure and Story-Romance
        Validation: len(stories) == 2 and no non-prefixed items
        """
        # Setup - create directories and files
        (temp_stories_env["stories_dir"] / "Story-Adventure").mkdir()
        (temp_stories_env["stories_dir"] / "mystery").mkdir()
        (temp_stories_env["stories_dir"] / "Story-Romance").mkdir()
        (temp_stories_env["stories_dir"] / "notes.txt").write_text("notes")
        (temp_stories_env["stories_dir"] / "Story-Invalid").write_text("not a directory")
        
        # Execute - use test mode with whitelist
        cm = ConfigManager(test_mode=True)
        cm._main_config_path = temp_stories_env["config_path"]
        cm.add_test_whitelist(str(temp_stories_env["temp_path"]))
        stories = cm.discover_stories()
        
        # Verify - only prefixed directories are returned
        assert len(stories) == 2, f"Should find exactly 2 stories, found {len(stories)}"
        
        story_names = [s["directory_name"] for s in stories]
        assert "Story-Adventure" in story_names, "Should find Story-Adventure"
        assert "Story-Romance" in story_names, "Should find Story-Romance"
        assert "mystery" not in story_names, "Should not find 'mystery' (no prefix)"
        assert "notes.txt" not in story_names, "Should not find files"
        assert "Story-Invalid" not in story_names, "Should not find files with prefix"
    
    def test_removes_prefix_for_display_name(self, temp_stories_env):
        """
        Test that discover_stories removes the prefix for display names.
        
        Setup: story-dir-prefix = 'Story-'
        Expected: Story-Adventure display_name = 'Adventure'
        Validation: name field lacks prefix but directory_name keeps it
        """
        # Setup - create story directories
        (temp_stories_env["stories_dir"] / "Story-The_Hobbit").mkdir()
        (temp_stories_env["stories_dir"] / "Story-AI_Revolution").mkdir()
        
        # Execute - use test mode with whitelist
        cm = ConfigManager(test_mode=True)
        cm._main_config_path = temp_stories_env["config_path"]
        cm.add_test_whitelist(str(temp_stories_env["temp_path"]))
        stories = cm.discover_stories()
        
        # Verify - display names don't have prefix but directory names do
        for story in stories:
            assert story["directory_name"].startswith("Story-"), "directory_name should keep prefix"
            assert not story["name"].startswith("Story-"), f"display name should not have prefix: {story['name']}"
            
            # Verify the prefix was actually removed (not just checked)
            expected_name = story["directory_name"][len("Story-"):]
            assert story["name"] == expected_name, f"Expected {expected_name}, got {story['name']}"
    
    def test_empty_stories_directory(self, temp_stories_env):
        """
        Test that discover_stories handles empty stories directory gracefully.
        
        Setup: stories-dir exists but is empty
        Expected: Returns empty list, no errors
        Validation: len(stories) == 0 and no exceptions
        """
        # Setup - ensure stories dir exists but is empty
        assert temp_stories_env["stories_dir"].exists()
        assert len(list(temp_stories_env["stories_dir"].iterdir())) == 0
        
        # Execute - use test mode with whitelist
        cm = ConfigManager(test_mode=True)
        cm._main_config_path = temp_stories_env["config_path"]
        cm.add_test_whitelist(str(temp_stories_env["temp_path"]))
        
        try:
            stories = cm.discover_stories()
            # Verify
            assert stories == [], "Should return empty list for empty directory"
            assert len(stories) == 0, "Should have 0 stories"
        except Exception as e:
            pytest.fail(f"Should not raise exception for empty directory: {e}")


class TestIPCHandlers:
    """Tests for IPC bridge command handlers."""
    
    @pytest.fixture
    def temp_bridge_env(self):
        """Create a temporary environment for bridge testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            stories_dir = temp_path / "Stories"
            stories_dir.mkdir(parents=True, exist_ok=True)
            
            # Create some test stories
            (stories_dir / "Story-Test1").mkdir()
            (stories_dir / "Story-Test2").mkdir()
            
            # Create config file
            config_dir = temp_path / ".config" / "FlexiTTS"
            config_dir.mkdir(parents=True, exist_ok=True)
            
            main_config = {
                "FlexiTTS": {
                    "stories-dir": str(stories_dir),
                    "story-dir-prefix": "Story-"
                }
            }
            
            config_path = config_dir / "FlexiTTS.yaml"
            with open(config_path, 'w') as f:
                yaml.dump(main_config, f)
            
            yield {
                "temp_path": temp_path,
                "stories_dir": stories_dir,
                "config_path": config_path
            }
    
    def test_get_stories_returns_json_array(self, temp_bridge_env, monkeypatch):
        """
        Test that the bridge 'get-stories' command returns valid JSON array.
        
        Input: python flexitts_bridge.py get-stories
        Expected: JSON array of story objects
        Validation: json.loads succeeds, array has expected structure
        """
        # Setup - patch config_manager to use our temp config
        import flexitts_bridge
        
        # Enable test mode and whitelist the temp path for the global config_manager
        config_manager._test_mode = True
        config_manager.add_test_whitelist(str(temp_bridge_env["temp_path"]))
        
        original_config_path = config_manager._main_config_path
        config_manager._main_config_path = temp_bridge_env["config_path"]
        config_manager.main_config = None  # Force reload
        
        try:
            # Execute - call get_available_stories
            stories = flexitts_bridge.get_available_stories()
            
            # Verify - returns list
            assert isinstance(stories, list), "Should return a list"
            assert len(stories) == 2, f"Should find 2 stories, found {len(stories)}"
            
            # Verify - JSON serialization works
            json_output = json.dumps(stories)
            parsed = json.loads(json_output)
            
            # Verify - structure of story objects
            for story in parsed:
                assert "name" in story, "Story should have 'name' field"
                assert "path" in story, "Story should have 'path' field"
                assert "directory_name" in story, "Story should have 'directory_name' field"
            
        finally:
            # Restore original config
            config_manager._main_config_path = original_config_path
            config_manager.main_config = None
    
    def test_bridge_handles_unknown_command(self):
        """
        Test that the bridge handles unknown commands gracefully.
        
        Input: python flexitts_bridge.py invalid-command
        Expected: Exit code 1, error message printed
        Validation: Unknown command is detected
        """
        import subprocess
        import sys
        
        bridge_path = Path(__file__).parent.parent / "flexitts_bridge.py"
        
        # Execute - run bridge with unknown command
        result = subprocess.run(
            [sys.executable, str(bridge_path), "invalid-command"],
            capture_output=True,
            text=True
        )
        
        # Verify - non-zero exit code
        assert result.returncode == 1, f"Should return exit code 1, got {result.returncode}"
        
        # Verify - error message contains "Unknown command"
        assert "Unknown command" in result.stdout or "unknown" in result.stdout.lower(), \
            f"Should print unknown command message, got: {result.stdout} {result.stderr}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
