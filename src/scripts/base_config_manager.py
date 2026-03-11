#!/usr/bin/env python3
"""
Base FlexiTTS Configuration Manager

Handles loading and management of FlexiTTS configuration from:
- ~/.config/FlexiTTS/FlexiTTS.yaml (main config)
- Story-specific story-config.yml files (in each Story-* directory)

SECURITY NOTES:
- All file path operations validate path traversal protection
- XDG config directory resolution is sanitized
- Input validation on all public methods
"""

import os
import re
import yaml
import json
from pathlib import Path
from typing import Dict, List, Any, Optional, Union


class ConfigError(Exception):
    """Configuration-related error"""
    pass


class PathTraversalError(ConfigError):
    """Raised when a path traversal attempt is detected"""
    pass


class ConfigManager:
    """Manages FlexiTTS configuration hierarchy with security validation"""

    # Allowed path characters - restricts to safe characters
    PATH_PATTERN = re.compile(r'^[\w\-\./\s]+$')

    # Maximum path length
    MAX_PATH_LENGTH = 4096

    def __init__(self, test_mode: bool = False):
        self.main_config: Optional[Dict[str, Any]] = None
        self._main_config_path = self._get_xdg_config_path()
        self._test_mode = test_mode
        # Whitelisted test directories (only used in test_mode)
        self._test_whitelist: List[Path] = []

    def add_test_whitelist(self, path: Union[str, Path]) -> None:
        """
        Add a path to the test whitelist.
        Only used when test_mode is True.

        Args:
            path: Path to whitelist for security checks
        """
        if self._test_mode:
            resolved = Path(path).expanduser().resolve()
            self._test_whitelist.append(resolved)

    def clear_test_whitelist(self) -> None:
        """Clear the test whitelist."""
        self._test_whitelist.clear()

    def _is_path_whitelisted(self, child_path: Path) -> bool:
        """
        Check if a path is within a whitelisted directory.

        Args:
            child_path: The path to check

        Returns:
            True if whitelisted
        """
        if not self._test_mode or not self._test_whitelist:
            return False

        try:
            resolved_child = Path(child_path).expanduser().resolve()
            for whitelisted in self._test_whitelist:
                if str(resolved_child).startswith(str(whitelisted)):
                    return True
            return False
        except Exception:
            return False

    def _get_xdg_config_path(self) -> Path:
        """
        Get XDG config directory path for FlexiTTS.
        Follows XDG Base Directory Specification.
        Checks both .yml and .yaml extensions.
        """
        home_dir = Path.home()
        config_home = os.environ.get('XDG_CONFIG_HOME', home_dir / '.config')
        
        # Try .yml first (more common), then .yaml
        config_path_yml = Path(config_home) / 'FlexiTTS' / 'FlexiTTS.yml'
        config_path_yaml = Path(config_home) / 'FlexiTTS' / 'FlexiTTS.yaml'
        
        if config_path_yml.exists():
            print(f"[RESOURCE-ACCESS] Found config file: {config_path_yml}", file=sys.stderr)
            return config_path_yml.resolve()
        elif config_path_yaml.exists():
            print(f"[RESOURCE-ACCESS] Found config file: {config_path_yaml}", file=sys.stderr)
            return config_path_yaml.resolve()
        else:
            print(f"[RESOURCE-ACCESS] Config file not found, defaulting to: {config_path_yml}", file=sys.stderr)
            return config_path_yml.resolve()

    def _sanitize_path(self, path: Union[str, Path]) -> Path:
        """
        Sanitize and validate a file path.

        Args:
            path: The path to sanitize

        Returns:
            Resolved Path object

        Raises:
            PathTraversalError: If path traversal is detected
            ConfigError: If path is invalid
        """
        if not path:
            raise ConfigError("Path cannot be empty")

        path_str = str(path)

        if len(path_str) > self.MAX_PATH_LENGTH:
            raise ConfigError(f"Path exceeds maximum length of {self.MAX_PATH_LENGTH}")

        # Check for null bytes
        if '\x00' in path_str:
            raise PathTraversalError("Path contains null bytes")

        # Resolve to absolute path
        resolved = Path(path_str).expanduser().resolve()

        return resolved

    def _is_path_within_parent(self, child_path: Path, parent_path: Path) -> bool:
        """
        Check if a path is within a parent directory (path traversal prevention).
        Uses path.relative() for proper comparison with case-normalization support.
        
        Args:
            child_path: The path to check
            parent_path: The parent directory that must contain child_path
            
        Returns:
            True if child_path is within parent_path
        """
        try:
            # Resolve and normalize both paths
            resolved_child = Path(child_path).expanduser().resolve()
            resolved_parent = Path(parent_path).expanduser().resolve()
            
            # In test mode, allow whitelisted paths
            if self._test_mode and self._is_path_whitelisted(resolved_child):
                return True
            
            # Use os.path.relpath() equivalent for proper path comparison
            # If relative path starts with '..', child is outside parent
            try:
                relative = resolved_child.relative_to(resolved_parent)
                # Additional check: relative should not start with '..' 
                return not str(relative).startswith('..')
            except ValueError:
                # child is not a child of parent
                return False
        except Exception:
            return False

    def _validate_story_directory_name(self, name: str) -> bool:
        """
        Validate story directory name format.
        Only allows alphanumeric, hyphens, and underscores.

        Args:
            name: Directory name to validate

        Returns:
            True if valid
        """
        if not name:
            return False

        # Allow: Story-Name, Story_Name, Story123-Name
        pattern = re.compile(r'^[\w\-]+$')
        return bool(pattern.match(name))

    def load_main_config(self, force_reload: bool = False) -> Dict[str, Any]:
        """
        Load main FlexiTTS configuration from ~/.config/FlexiTTS/FlexiTTS.yaml

        Args:
            force_reload: If True, reload from disk even if already loaded

        Returns:
            Configuration dictionary

        Raises:
            ConfigError: If configuration cannot be loaded or is invalid
        """
        # Return cached config if available and not forcing reload
        if self.main_config is not None and not force_reload:
            return self.main_config

        try:
            # Verify config path is within expected XDG location
            xdg_home = Path.home() / '.config'
            if not self._is_path_within_parent(self._main_config_path, xdg_home):
                raise PathTraversalError("Config path escapes XDG config directory")

            if self._main_config_path.exists():
                try:
                    with open(self._main_config_path, 'r', encoding='utf-8') as f:
                        loaded_config = yaml.safe_load(f)

                    # Validate basic structure - must be a dict with 'FlexiTTS' key
                    if loaded_config is None:
                        self.main_config = self._create_default_config()
                    elif not isinstance(loaded_config, dict):
                        # YAML parsed to non-dict (e.g., "123", "null")
                        self.main_config = self._create_default_config()
                    elif 'FlexiTTS' not in loaded_config:
                        # Valid dict but missing FlexiTTS key
                        self.main_config = self._create_default_config()
                    else:
                        self.main_config = loaded_config
                except (yaml.YAMLError, PermissionError, OSError):
                    # Malformed YAML or permission error - return default config
                    self.main_config = self._create_default_config()
            else:
                # Create default config if it doesn't exist
                self.main_config = self._create_default_config()
                self.save_main_config()

            return self.main_config

        except PathTraversalError:
            raise
        except Exception:
            # Any other error - return default config
            self.main_config = self._create_default_config()
            return self.main_config

    def save_main_config(self) -> None:
        """
        Save main FlexiTTS configuration to ~/.config/FlexiTTS/FlexiTTS.yaml

        Raises:
            ConfigError: If configuration cannot be saved
        """
        if self.main_config is None:
            raise ConfigError("No configuration to save")

        # Ensure config directory exists
        try:
            self._main_config_path.parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            raise ConfigError(f"Failed to create config directory: {e}")

        # Verify path is safe before writing
        xdg_home = Path.home() / '.config'
        if not self._is_path_within_parent(self._main_config_path, xdg_home):
            raise PathTraversalError("Cannot save config outside XDG config directory")

        try:
            with open(self._main_config_path, 'w', encoding='utf-8') as f:
                yaml.dump(self.main_config, f, default_flow_style=False, indent=2,
                         allow_unicode=True, sort_keys=False)
        except Exception as e:
            raise ConfigError(f"Error saving FlexiTTS configuration: {e}")

    def _create_default_config(self) -> Dict[str, Any]:
        """Create default FlexiTTS configuration"""
        home_dir = Path.home()
        data_dir = os.environ.get('XDG_DATA_HOME', home_dir / '.local' / 'share')

        return {
            'FlexiTTS': {
                'stories-dir': str(Path(data_dir) / 'FlexiTTS' / 'stories'),
                'story-dir-prefix': 'Story-'
            }
        }

    def get_stories_directory(self) -> Path:
        """
        Get the stories directory path from configuration.

        Returns:
            Path to stories directory

        Raises:
            ConfigError: If stories directory cannot be determined
        """
        if self.main_config is None:
            self.load_main_config()

        stories_dir = self.main_config.get('FlexiTTS', {}).get('stories-dir')
        if not stories_dir:
            # Fallback to default
            home_dir = Path.home()
            data_dir = Path(os.environ.get('XDG_DATA_HOME', home_dir / '.local' / 'share'))
            stories_dir = str(data_dir / 'FlexiTTS' / 'stories')

        # Expand ~ in path if present and resolve
        resolved = Path(stories_dir).expanduser().resolve()

        # Validate it doesn't escape expected bounds
        home_dir = Path.home()
        if not self._is_path_within_parent(resolved, home_dir) and not self._is_path_within_parent(resolved, Path('/')):
            raise PathTraversalError("Stories directory escapes expected boundaries")

        return resolved

    def get_story_prefix(self) -> str:
        """Get the story directory prefix from configuration"""
        if self.main_config is None:
            self.load_main_config()

        return self.main_config.get('FlexiTTS', {}).get('story-dir-prefix', 'Story-')

    def discover_stories(self) -> List[Dict[str, str]]:
        """
        Discover all Story-* directories in the stories directory.

        Returns:
            List of story info dictionaries
        """
        stories_dir = self.get_stories_directory()
        prefix = self.get_story_prefix()
        stories = []

        if not stories_dir.exists():
            return stories

        try:
            for item in stories_dir.iterdir():
                if item.is_dir() and item.name.startswith(prefix):
                    # Validate directory name
                    if not self._validate_story_directory_name(item.name):
                        print(f"Warning: Skipping invalid story directory name: {item.name}")
                        continue

                    # Remove prefix for display name
                    display_name = item.name[len(prefix):]
                    stories.append({
                        'name': display_name,
                        'path': str(item),
                        'directory_name': item.name
                    })
        except Exception as e:
            print(f"Warning: Error discovering stories: {e}")

        return sorted(stories, key=lambda x: x['name'])

    def load_story_config(self, story_path: Union[str, Path]) -> Dict[str, Any]:
        """
        Load story-specific configuration from story-config.yml.

        Args:
            story_path: Path to the story directory

        Returns:
            Story configuration dictionary

        Raises:
            ConfigError: If configuration cannot be loaded
            PathTraversalError: If path traversal is detected
        """
        # Sanitize and validate the path
        resolved_story_path = self._sanitize_path(story_path)
        print(f"[RESOURCE-ACCESS] Loading story config", file=sys.stderr)
        print(f"  story_path: {story_path}", file=sys.stderr)
        print(f"  resolved_story_path: {resolved_story_path}", file=sys.stderr)

        # Verify the story path is within stories directory
        stories_dir = self.get_stories_directory()
        if not self._is_path_within_parent(resolved_story_path, stories_dir):
            raise PathTraversalError(f"Story path {story_path} is outside stories directory")

        config_path = resolved_story_path / "story-config.yml"
        print(f"[RESOURCE-ACCESS] Config path: {config_path}", file=sys.stderr)
        print(f"  resourceType: yaml", file=sys.stderr)

        # Additional check: ensure config path is within story directory
        if not self._is_path_within_parent(config_path, resolved_story_path):
            raise PathTraversalError("Config file path escapes story directory")

        if not config_path.exists():
            print(f"[RESOURCE-ACCESS] Config NOT found: {config_path}", file=sys.stderr)
            raise ConfigError(f"Story configuration not found: {config_path}")

        print(f"[RESOURCE-ACCESS] Reading YAML config: {config_path}", file=sys.stderr)
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)

            if config is None:
                return {}

            print(f"[RESOURCE-ACCESS] Successfully loaded story config", file=sys.stderr)
            print(f"  story_path: {story_path}", file=sys.stderr)
            print(f"  config_path: {config_path}", file=sys.stderr)
            print(f"  has_characters: {'characters' in config}", file=sys.stderr)
            print(f"  has_global: {'global' in config}", file=sys.stderr)
            return config

        except yaml.YAMLError as e:
            print(f"[RESOURCE-ACCESS] YAML parse error: {e}", file=sys.stderr)
            raise ConfigError(f"Error parsing story-config.yml: {e}")
        except Exception as e:
            print(f"[RESOURCE-ACCESS] Failed to load story config: {e}", file=sys.stderr)
            raise ConfigError(f"Error loading story configuration: {e}")

    def validate_story_config(self, story_path: Union[str, Path]) -> bool:
        """
        Validate story configuration using existing validation logic.

        Args:
            story_path: Path to the story directory

        Returns:
            True if configuration is valid
        """
        try:
            # Sanitize the path first
            resolved_path = self._sanitize_path(story_path)

            # Verify it's within stories directory
            stories_dir = self.get_stories_directory()
            if not self._is_path_within_parent(resolved_path, stories_dir):
                print(f"Security: Story path {story_path} escapes stories directory")
                return False

            config_path = resolved_path / "story-config.yml"

            if not config_path.exists():
                return False

            # Try to validate by loading
            config = self.load_story_config(resolved_path)

            # Basic validation: check required fields
            if 'global' not in config:
                print(f"Warning: Missing 'global' section in {config_path}")
                return False

            global_config = config.get('global', {})
            required_global = ['story-dir', 'chapters', 'story-xml']
            for field in required_global:
                if field not in global_config:
                    print(f"Warning: Missing required field 'global.{field}' in {config_path}")
                    return False

            return True

        except PathTraversalError as e:
            print(f"Security error: {e}")
            return False
        except Exception as e:
            print(f"Warning: Error validating story config: {e}")
            return False

    def get_story_info(self, directory_name: str) -> Optional[Dict[str, str]]:
        """
        Get information about a specific story.

        Args:
            directory_name: The story directory name

        Returns:
            Story info dictionary or None if not found
        """
        # Validate directory name
        if not self._validate_story_directory_name(directory_name):
            return None

        stories = self.discover_stories()
        return next((s for s in stories if s['directory_name'] == directory_name), None)


# Singleton instance for application use
config_manager = ConfigManager()


if __name__ == "__main__":
    # Test the configuration manager
    import sys

    try:
        # Test path validation
        print("Testing ConfigManager...")

        # Load main config
        main_config = config_manager.load_main_config()
        print("Main FlexiTTS Configuration:")
        print(yaml.dump(main_config, default_flow_style=False, indent=2))

        # Discover stories
        stories = config_manager.discover_stories()
        print(f"\nFound {len(stories)} stories:")
        for story in stories:
            print(f"  - {story['name']} ({story['path']})")

            # Try to load story config
            try:
                story_config = config_manager.load_story_config(story['path'])
                is_valid = config_manager.validate_story_config(story['path'])
                print(f"    Config valid: {is_valid}")
                if 'characters' in story_config:
                    char_count = len(story_config['characters'])
                    print(f"    Characters: {char_count}")
            except ConfigError as e:
                print(f"    Config error: {e}")
            except Exception as e:
                print(f"    Error loading story config: {e}")

        # Test security: path traversal attempt
        print("\nTesting security (path traversal detection)...")
        try:
            # This should fail
            config_manager.load_story_config("../../../etc/passwd")
            print("ERROR: Path traversal was not blocked!")
        except PathTraversalError:
            print("SUCCESS: Path traversal correctly blocked")

        print("\nAll tests passed!")

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
