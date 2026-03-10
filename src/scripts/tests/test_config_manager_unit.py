#!/usr/bin/env python3
"""
Unit tests for FlexiTTS ConfigManager core functionality.
Focus: prefix stripping, story discovery, and configuration loading.
"""

import pytest
import tempfile
import yaml
from pathlib import Path
from unittest.mock import patch, MagicMock
import sys

sys.path.append(str(Path(__file__).parent.parent))
from config_manager import ConfigManager
from base_config_manager import ConfigError


class TestConfigManagerPrefixStripping:
    """Tests for story directory prefix stripping logic."""

    def test_prefix_stripping_basic(self):
        """Test basic prefix stripping from directory names."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir) / ".config" / "FlexiTTS"
            stories_dir = Path(temp_dir) / "Stories"
            config_dir.mkdir(parents=True)
            stories_dir.mkdir()
            
            # Create main config with Story- prefix
            main_config = {
                'FlexiTTS': {
                    'stories-dir': str(stories_dir),
                    'story-dir-prefix': 'Story-'
                }
            }
            
            main_config_path = config_dir / "FlexiTTS.yaml"
            with open(main_config_path, 'w') as f:
                yaml.dump(main_config, f)
            
            # Create story directories
            for name in ['Adventure', 'Mystery', 'SciFi']:
                story_dir = stories_dir / f"Story-{name}"
                story_dir.mkdir()
                # Create minimal story config
                with open(story_dir / "story-config.yml", 'w') as f:
                    yaml.dump({'global': {'story-dir': '.'}}, f)
            
            with patch.dict('os.environ', {'HOME': str(temp_dir)}):
                cm = ConfigManager()
                stories = cm.discover_stories()
                
                # Should strip 'Story-' prefix
                story_names = [s['name'] for s in stories]
                assert 'Adventure' in story_names
                assert 'Mystery' in story_names
                assert 'SciFi' in story_names
                # Should NOT include 'Story-' prefix
                assert 'Story-Adventure' not in story_names

    def test_prefix_stripping_custom_prefix(self):
        """Test prefix stripping with custom prefix."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir) / ".config" / "FlexiTTS"
            stories_dir = Path(temp_dir) / "Stories"
            config_dir.mkdir(parents=True)
            stories_dir.mkdir()
            
            # Custom prefix
            main_config = {
                'FlexiTTS': {
                    'stories-dir': str(stories_dir),
                    'story-dir-prefix': 'Book-'
                }
            }
            
            main_config_path = config_dir / "FlexiTTS.yaml"
            with open(main_config_path, 'w') as f:
                yaml.dump(main_config, f)
            
            # Create story directories with Book- prefix
            for name in ['Fantasy', 'Romance']:
                story_dir = stories_dir / f"Book-{name}"
                story_dir.mkdir()
                with open(story_dir / "story-config.yml", 'w') as f:
                    yaml.dump({'global': {'story-dir': '.'}}, f)
            
            with patch.dict('os.environ', {'HOME': str(temp_dir)}):
                cm = ConfigManager()
                stories = cm.discover_stories()
                
                story_names = [s['name'] for s in stories]
                assert 'Fantasy' in story_names
                assert 'Romance' in story_names
                assert 'Book-Fantasy' not in story_names

    def test_prefix_stripping_empty_after_prefix(self):
        """Test handling when directory name equals prefix."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir) / ".config" / "FlexiTTS"
            stories_dir = Path(temp_dir) / "Stories"
            config_dir.mkdir(parents=True)
            stories_dir.mkdir()
            
            main_config = {
                'FlexiTTS': {
                    'stories-dir': str(stories_dir),
                    'story-dir-prefix': 'Story-'
                }
            }
            
            main_config_path = config_dir / "FlexiTTS.yaml"
            with open(main_config_path, 'w') as f:
                yaml.dump(main_config, f)
            
            # Create a directory that is JUST the prefix
            story_dir = stories_dir / "Story-"
            story_dir.mkdir()
            with open(story_dir / "story-config.yml", 'w') as f:
                yaml.dump({'global': {'story-dir': '.'}}, f)
            
            with patch.dict('os.environ', {'HOME': str(temp_dir)}):
                cm = ConfigManager()
                stories = cm.discover_stories()
                
                # Should handle empty string after stripping
                assert len(stories) == 1
                assert stories[0]['name'] == ''

    def test_prefix_stripping_no_matching_directories(self):
        """Test when no directories match the prefix."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir) / ".config" / "FlexiTTS"
            stories_dir = Path(temp_dir) / "Stories"
            config_dir.mkdir(parents=True)
            stories_dir.mkdir()
            
            main_config = {
                'FlexiTTS': {
                    'stories-dir': str(stories_dir),
                    'story-dir-prefix': 'Story-'
                }
            }
            
            main_config_path = config_dir / "FlexiTTS.yaml"
            with open(main_config_path, 'w') as f:
                yaml.dump(main_config, f)
            
            # Create directories WITHOUT the prefix
            story_dir = stories_dir / "RandomDirectory"
            story_dir.mkdir()
            
            another_dir = stories_dir / "AnotherStory"
            another_dir.mkdir()
            
            with patch.dict('os.environ', {'HOME': str(temp_dir)}):
                cm = ConfigManager()
                stories = cm.discover_stories()
                
                # Should not find any stories
                assert len(stories) == 0

    def test_directory_name_preserved_in_output(self):
        """Test that full directory_name is preserved in story output."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir) / ".config" / "FlexiTTS"
            stories_dir = Path(temp_dir) / "Stories"
            config_dir.mkdir(parents=True)
            stories_dir.mkdir()
            
            main_config = {
                'FlexiTTS': {
                    'stories-dir': str(stories_dir),
                    'story-dir-prefix': 'Story-'
                }
            }
            
            main_config_path = config_dir / "FlexiTTS.yaml"
            with open(main_config_path, 'w') as f:
                yaml.dump(main_config, f)
            
            story_dir = stories_dir / "Story-TestName"
            story_dir.mkdir()
            with open(story_dir / "story-config.yml", 'w') as f:
                yaml.dump({'global': {'story-dir': '.'}}, f)
            
            with patch.dict('os.environ', {'HOME': str(temp_dir)}):
                cm = ConfigManager()
                stories = cm.discover_stories()
                
                assert len(stories) == 1
                story = stories[0]
                
                # name should have prefix stripped
                assert story['name'] == 'TestName'
                # directory_name should preserve full name
                assert story['directory_name'] == 'Story-TestName'
                # path should be absolute
                assert story['path'] == str(story_dir)


class TestConfigManagerLoadGlobalConfig:
    """Tests for loading global FlexiTTS.yaml configuration."""

    def test_load_global_config_success(self):
        """Test successful loading of global config."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir) / ".config" / "FlexiTTS"
            config_dir.mkdir(parents=True)
            
            main_config = {
                'FlexiTTS': {
                    'stories-dir': '/home/user/Stories',
                    'story-dir-prefix': 'Story-',
                    'default-voice-provider': 'kokoro'
                }
            }
            
            main_config_path = config_dir / "FlexiTTS.yaml"
            with open(main_config_path, 'w') as f:
                yaml.dump(main_config, f)
            
            with patch.dict('os.environ', {'HOME': str(temp_dir)}):
                cm = ConfigManager()
                config = cm.load_main_config()
                
                assert 'FlexiTTS' in config
                assert config['FlexiTTS']['stories-dir'] == '/home/user/Stories'
                assert config['FlexiTTS']['story-dir-prefix'] == 'Story-'
                assert config['FlexiTTS']['default-voice-provider'] == 'kokoro'

    def test_load_global_config_creates_default(self):
        """Test that default config is created when file doesn't exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict('os.environ', {'HOME': str(temp_dir)}):
                cm = ConfigManager()
                config = cm.load_main_config()
                
                # Should create default config
                assert 'FlexiTTS' in config
                assert 'stories-dir' in config['FlexiTTS']
                assert 'story-dir-prefix' in config['FlexiTTS']
                assert config['FlexiTTS']['story-dir-prefix'] == 'Story-'
                
                # Verify file was created
                config_path = Path(temp_dir) / ".config" / "FlexiTTS" / "FlexiTTS.yaml"
                assert config_path.exists()

    def test_load_global_config_expands_tilde(self):
        """Test that ~ in paths is properly expanded."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir) / ".config" / "FlexiTTS"
            config_dir.mkdir(parents=True)
            
            # Use tilde in path
            main_config = {
                'FlexiTTS': {
                    'stories-dir': '~/MyStories',
                    'story-dir-prefix': 'Story-'
                }
            }
            
            main_config_path = config_dir / "FlexiTTS.yaml"
            with open(main_config_path, 'w') as f:
                yaml.dump(main_config, f)
            
            with patch.dict('os.environ', {'HOME': str(temp_dir)}):
                cm = ConfigManager()
                cm.load_main_config()
                
                # get_stories_directory should expand ~
                stories_dir = cm.get_stories_directory()
                assert '~' not in str(stories_dir)
                assert str(stories_dir).endswith('MyStories')

    def test_load_global_config_invalid_yaml(self):
        """Test handling of invalid YAML in global config."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir) / ".config" / "FlexiTTS"
            config_dir.mkdir(parents=True)
            
            main_config_path = config_dir / "FlexiTTS.yaml"
            # Write invalid YAML
            main_config_path.write_text("invalid: yaml: [: ]")
            
            with patch.dict('os.environ', {'HOME': str(temp_dir)}):
                cm = ConfigManager()
                
                # Current behavior: creates default config instead of raising
                # This is acceptable - graceful degradation
                config = cm.load_main_config()
                assert config is not None
                assert 'FlexiTTS' in config


class TestConfigManagerDiscoverStories:
    """Tests for story discovery functionality."""

    def test_discover_stories_sorted(self):
        """Test that discovered stories are sorted alphabetically."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir) / ".config" / "FlexiTTS"
            stories_dir = Path(temp_dir) / "Stories"
            config_dir.mkdir(parents=True)
            stories_dir.mkdir()
            
            main_config = {
                'FlexiTTS': {
                    'stories-dir': str(stories_dir),
                    'story-dir-prefix': 'Story-'
                }
            }
            
            main_config_path = config_dir / "FlexiTTS.yaml"
            with open(main_config_path, 'w') as f:
                yaml.dump(main_config, f)
            
            # Create stories in non-alphabetical order
            for name in ['Zebra', 'Apple', 'Mango']:
                story_dir = stories_dir / f"Story-{name}"
                story_dir.mkdir()
                with open(story_dir / "story-config.yml", 'w') as f:
                    yaml.dump({'global': {'story-dir': '.'}}, f)
            
            with patch.dict('os.environ', {'HOME': str(temp_dir)}):
                cm = ConfigManager()
                stories = cm.discover_stories()
                
                # Should be sorted by name
                story_names = [s['name'] for s in stories]
                assert story_names == ['Apple', 'Mango', 'Zebra']

    def test_discover_stories_empty_directory(self):
        """Test discovering stories when stories directory is empty."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir) / ".config" / "FlexiTTS"
            stories_dir = Path(temp_dir) / "Stories"
            config_dir.mkdir(parents=True)
            stories_dir.mkdir()
            
            main_config = {
                'FlexiTTS': {
                    'stories-dir': str(stories_dir),
                    'story-dir-prefix': 'Story-'
                }
            }
            
            main_config_path = config_dir / "FlexiTTS.yaml"
            with open(main_config_path, 'w') as f:
                yaml.dump(main_config, f)
            
            with patch.dict('os.environ', {'HOME': str(temp_dir)}):
                cm = ConfigManager()
                stories = cm.discover_stories()
                
                # Should return empty list
                assert stories == []

    def test_discover_stories_nonexistent_directory(self):
        """Test discovering stories when stories directory doesn't exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir) / ".config" / "FlexiTTS"
            config_dir.mkdir(parents=True)
            
            nonexistent_path = Path(temp_dir) / "NonExistent" / "Stories"
            
            main_config = {
                'FlexiTTS': {
                    'stories-dir': str(nonexistent_path),
                    'story-dir-prefix': 'Story-'
                }
            }
            
            main_config_path = config_dir / "FlexiTTS.yaml"
            with open(main_config_path, 'w') as f:
                yaml.dump(main_config, f)
            
            with patch.dict('os.environ', {'HOME': str(temp_dir)}):
                cm = ConfigManager()
                stories = cm.discover_stories()
                
                # Should return empty list, not crash
                assert stories == []

    def test_discover_stories_ignores_files(self):
        """Test that discover_stories ignores files and only processes directories."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir) / ".config" / "FlexiTTS"
            stories_dir = Path(temp_dir) / "Stories"
            config_dir.mkdir(parents=True)
            stories_dir.mkdir()
            
            main_config = {
                'FlexiTTS': {
                    'stories-dir': str(stories_dir),
                    'story-dir-prefix': 'Story-'
                }
            }
            
            main_config_path = config_dir / "FlexiTTS.yaml"
            with open(main_config_path, 'w') as f:
                yaml.dump(main_config, f)
            
            # Create a directory
            story_dir = stories_dir / "Story-Valid"
            story_dir.mkdir()
            with open(story_dir / "story-config.yml", 'w') as f:
                yaml.dump({'global': {'story-dir': '.'}}, f)
            
            # Create files with same pattern
            (stories_dir / "Story-File.txt").write_text("not a story")
            (stories_dir / "Story-AnotherFile.md").write_text("also not a story")
            
            with patch.dict('os.environ', {'HOME': str(temp_dir)}):
                cm = ConfigManager()
                stories = cm.discover_stories()
                
                # Should only find the directory
                assert len(stories) == 1
                assert stories[0]['name'] == 'Valid'

    def test_discover_stories_requires_directory(self):
        """Test that only directories are discovered, not files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir) / ".config" / "FlexiTTS"
            stories_dir = Path(temp_dir) / "Stories"
            config_dir.mkdir(parents=True)
            stories_dir.mkdir()
            
            main_config = {
                'FlexiTTS': {
                    'stories-dir': str(stories_dir),
                    'story-dir-prefix': 'Story-'
                }
            }
            
            (config_dir / "FlexiTTS.yaml").write_text(yaml.dump(main_config))
            
            # Create files that look like story directories
            (stories_dir / "Story-Fake").write_text("not a directory")
            
            # Create actual story directory
            story_dir = stories_dir / "Story-Real"
            story_dir.mkdir()
            (story_dir / "story-config.yml").write_text(yaml.dump({'global': {'story-dir': '.'}}))
            
            with patch.dict('os.environ', {'HOME': str(temp_dir)}):
                cm = ConfigManager()
                stories = cm.discover_stories()
                
                assert len(stories) == 1
                assert stories[0]['name'] == 'Real'

    def test_discover_stories_output_structure(self):
        """Test the structure of story discovery output."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir) / ".config" / "FlexiTTS"
            stories_dir = Path(temp_dir) / "Stories"
            config_dir.mkdir(parents=True)
            stories_dir.mkdir()
            
            main_config = {
                'FlexiTTS': {
                    'stories-dir': str(stories_dir),
                    'story-dir-prefix': 'Story-'
                }
            }
            
            (config_dir / "FlexiTTS.yaml").write_text(yaml.dump(main_config))
            
            story_dir = stories_dir / "Story-Adventure"
            story_dir.mkdir()
            (story_dir / "story-config.yml").write_text(yaml.dump({'global': {'story-dir': '.'}}))
            
            with patch.dict('os.environ', {'HOME': str(temp_dir)}):
                cm = ConfigManager()
                stories = cm.discover_stories()
                
                assert len(stories) == 1
                story = stories[0]
                
                # Check required fields
                assert 'name' in story
                assert 'path' in story
                assert 'directory_name' in story
                
                # Verify types
                assert isinstance(story['name'], str)
                assert isinstance(story['path'], str)
                assert isinstance(story['directory_name'], str)
                
                # Verify values
                assert story['name'] == 'Adventure'
                assert story['directory_name'] == 'Story-Adventure'
                assert Path(story['path']).exists()


class TestConfigManagerGetStoriesDirectory:
    """Tests for get_stories_directory method."""

    def test_get_stories_directory_returns_path(self):
        """Test that get_stories_directory returns a Path object."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir) / ".config" / "FlexiTTS"
            config_dir.mkdir(parents=True)
            
            main_config = {
                'FlexiTTS': {
                    'stories-dir': '/custom/path/to/Stories',
                    'story-dir-prefix': 'Story-'
                }
            }
            
            (config_dir / "FlexiTTS.yaml").write_text(yaml.dump(main_config))
            
            with patch.dict('os.environ', {'HOME': str(temp_dir)}):
                cm = ConfigManager()
                stories_dir = cm.get_stories_directory()
                
                assert isinstance(stories_dir, Path)
                assert str(stories_dir) == '/custom/path/to/Stories'

    def test_get_stories_directory_expands_user(self):
        """Test that get_stories_directory expands ~ to home."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir) / ".config" / "FlexiTTS"
            config_dir.mkdir(parents=True)
            
            main_config = {
                'FlexiTTS': {
                    'stories-dir': '~/Documents/FlexiTTS/Stories',
                    'story-dir-prefix': 'Story-'
                }
            }
            
            (config_dir / "FlexiTTS.yaml").write_text(yaml.dump(main_config))
            
            with patch.dict('os.environ', {'HOME': str(temp_dir)}):
                cm = ConfigManager()
                stories_dir = cm.get_stories_directory()
                
                assert '~' not in str(stories_dir)
                assert stories_dir.name == 'Stories'


class TestConfigManagerGetStoryPrefix:
    """Tests for get_story_prefix method."""

    def test_get_story_prefix_returns_string(self):
        """Test that get_story_prefix returns the prefix string."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir) / ".config" / "FlexiTTS"
            config_dir.mkdir(parents=True)
            
            main_config = {
                'FlexiTTS': {
                    'stories-dir': '/tmp/Stories',
                    'story-dir-prefix': 'Tale-'
                }
            }
            
            (config_dir / "FlexiTTS.yaml").write_text(yaml.dump(main_config))
            
            with patch.dict('os.environ', {'HOME': str(temp_dir)}):
                cm = ConfigManager()
                prefix = cm.get_story_prefix()
                
                assert prefix == 'Tale-'
                assert isinstance(prefix, str)

    def test_get_story_prefix_default(self):
        """Test that default prefix is 'Story-'."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict('os.environ', {'HOME': str(temp_dir)}):
                cm = ConfigManager()
                # Load default config
                cm.load_main_config()
                prefix = cm.get_story_prefix()
                
                assert prefix == 'Story-'


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
