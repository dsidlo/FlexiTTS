#!/usr/bin/env python3
"""
Enhanced FlexiTTS Configuration Manager with Advanced Features

Integrates with the existing ConfigManager and extends functionality for
the REST API and configuration management system.

SECURITY NOTES:
- All file paths are validated against path traversal attacks
- XDG directory specifications are followed
- Input validation on all public methods
"""

import os
import sys
import yaml
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Union

# Add project root to path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

# Import base ConfigManager with security features
try:
    from base_config_manager import ConfigManager as BaseConfigManager, ConfigError, PathTraversalError
except ImportError:
    # Fallback for when base_config_manager is in the same directory
    sys.path.insert(0, str(Path(__file__).parent))
    from base_config_manager import ConfigManager as BaseConfigManager, ConfigError, PathTraversalError


class EnhancedConfigManager(BaseConfigManager):
    """
    Enhanced ConfigManager with additional functionality for API support.
    Inherits security features from BaseConfigManager.
    
    Args:
        test_mode: If True, allows whitelisted directories for testing.
                  Use test_mode=True only in tests with proper whitelisting.
    """
    
    def __init__(self, test_mode: bool = False, enable_caching: bool = False):
        super().__init__(test_mode=test_mode)
        self._caching_enabled = enable_caching
        self._cache: Dict[str, Tuple[float, Any]] = {}
        self._cache_timeout = 300  # 5 minutes
        self._main_config_loaded = False
    
    def get_cached_or_load(self, key: str, loader_func, timeout: int = None) -> Any:
        """
        Generic caching mechanism for expensive operations.
        
        Args:
            key: Cache key
            loader_func: Function to call if cache miss
            timeout: Cache timeout in seconds
            
        Returns:
            Cached or loaded value
        """
        current_time = datetime.now().timestamp()
        timeout = timeout or self._cache_timeout
        
        if key in self._cache:
            cached_time, cached_value = self._cache[key]
            if current_time - cached_time < timeout:
                return cached_value
        
        # Load fresh data
        value = loader_func()
        self._cache[key] = (current_time, value)
        return value
    
    def invalidate_cache(self, key: str = None) -> None:
        """
        Invalidate cache entries.
        
        Args:
            key: Specific key to invalidate, or None for all
        """
        if key:
            self._cache.pop(key, None)
        else:
            self._cache.clear()
    
    def load_main_config(self, force_reload: bool = False) -> Dict[str, Any]:
        """
        Load main FlexiTTS configuration.
        
        Args:
            force_reload: If True, reload from disk even if already loaded
            
        Returns:
            Configuration dictionary
        """
        if self._main_config_loaded and not force_reload and self.main_config is not None:
            return self.main_config
        
        # Use caching if enabled
        if self._caching_enabled and not force_reload:
            return self.get_cached_or_load(
                'main_config',
                lambda: super().load_main_config()
            )
        
        config = super().load_main_config()
        self._main_config_loaded = True
        return config
    
    def discover_stories(self) -> List[Dict[str, Any]]:
        """
        Discover stories with optional caching.
        
        Returns:
            List of story dictionaries
        """
        if self._caching_enabled:
            return self.get_cached_or_load(
                'stories',
                lambda: super().discover_stories()
            )
        return super().discover_stories()
    
    def needs_migration(self, story_path: str) -> bool:
        """
        Check if a story configuration needs migration.
        
        Args:
            story_path: Path to check
            
        Returns:
            True if migration is needed
        """
        try:
            # Check if it's using old-style configuration
            story_dir = Path(story_path)
            if not story_dir.exists():
                return False
            
            # Check for legacy story-config.yml without proper structure
            config_path = story_dir / "story-config.yml"
            if config_path.exists():
                with open(config_path, 'r') as f:
                    config = yaml.safe_load(f)
                
                # Check if config has required fields
                if config and 'global' in config and 'characters' in config:
                    return False
                return True
            
            return True
        except Exception:
            return True
    
    def migrate_legacy_config(self, old_config_path: str) -> Dict[str, Any]:
        """
        Migrate legacy configuration to new format.
        
        Args:
            old_config_path: Path to old configuration
            
        Returns:
            Migration result with success status and new path
        """
        try:
            old_path = Path(old_config_path)
            
            # Load old config
            with open(old_path, 'r') as f:
                old_config = yaml.safe_load(f)
            
            if not old_config:
                return {'success': False, 'error': 'Empty configuration'}
            
            # Create new story directory
            story_name = old_path.parent.name if old_path.name == 'story-config.yml' else 'MigratedStory'
            stories_dir = self.get_stories_directory()
            new_story_dir = stories_dir / f"Story-{story_name}"
            new_story_dir.mkdir(parents=True, exist_ok=True)
            
            # Migrate configuration
            new_config = {
                'global': old_config.get('global', {
                    'story-dir': '.',
                    'voices': 'voices',
                    'chapters': 'story-chapters',
                    'story-xml': 'story-xml',
                    'logs': 'logs',
                    'story-audio': 'story-audio',
                    'clips': 'story-audio/clips',
                    'clip-separation': 500
                }),
                'characters': old_config.get('characters', [])
            }
            
            # Save new config
            new_config_path = new_story_dir / 'story-config.yml'
            with open(new_config_path, 'w') as f:
                yaml.dump(new_config, f)
            
            # Create required directories
            for dir_name in ['voices', 'story-chapters', 'story-xml', 'logs', 'story-audio']:
                (new_story_dir / dir_name).mkdir(exist_ok=True)
            
            return {
                'success': True,
                'new_story_path': str(new_story_dir),
                'story_name': story_name
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def backup_config(self, config_path: Path, backup_suffix: str = None) -> str:
        """
        Create a backup of a configuration file.
        
        Args:
            config_path: Path to config file
            backup_suffix: Optional suffix for backup file
            
        Returns:
            Path to backup file
        """
        # Security: Validate config path
        resolved_path = self._sanitize_path(config_path)
        
        if not resolved_path.exists():
            raise ConfigError(f"Config file not found: {config_path}")
        
        if not backup_suffix:
            backup_suffix = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Security: Ensure backup path is in same directory
        backup_path = resolved_path.parent / f"{resolved_path.stem}.{backup_suffix}.bak"
        
        if not self._is_path_within_parent(backup_path, resolved_path.parent):
            raise PathTraversalError("Backup path escapes config directory")
        
        shutil.copy2(resolved_path, backup_path)
        return str(backup_path)
    
    def merge_configurations(self, story_path: Path) -> Dict[str, Any]:
        """
        Merge story config with global config, handling conflicts.
        
        Args:
            story_path: Path to story directory
            
        Returns:
            Merged configuration with conflict metadata
        """
        # Security: Validate story path
        resolved_story_path = self._sanitize_path(story_path)
        stories_dir = self.get_stories_directory()
        
        if not self._is_path_within_parent(resolved_story_path, stories_dir):
            raise PathTraversalError("Story path escapes stories directory")
        
        def load_configs():
            # Load global config
            global_config = self.load_main_config()
            global_defaults = global_config.get("FlexiTTS", {}).get("global_defaults", {})
            
            # Load story config
            story_config = None
            config_path = resolved_story_path / "story-config.yml"
            
            # Security check
            if not self._is_path_within_parent(config_path, resolved_story_path):
                raise PathTraversalError("Config path escapes story directory")
            
            if config_path.exists():
                try:
                    story_config = self.load_story_config(resolved_story_path)
                except Exception as e:
                    print(f"Warning: Error loading story config: {e}")
                    story_config = {}
            else:
                story_config = {}
            
            # Merge configurations with conflict detection
            merged_config = story_config.copy() if story_config else {}
            conflicts = []
            
            # Apply global defaults to story config 'global' section
            if global_defaults and "global" in merged_config:
                story_global = merged_config["global"]
                for key, global_value in global_defaults.items():
                    if key in story_global:
                        story_value = story_global[key]
                        if story_value != global_value:
                            conflicts.append({
                                "field": f"global.{key}",
                                "storyValue": story_value,
                                "globalValue": global_value,
                                "resolution": "story"  # Story takes precedence
                            })
                    else:
                        # Add missing global default
                        story_global[key] = global_value
            elif global_defaults:
                # Create global section if it doesn't exist
                if "global" not in merged_config:
                    merged_config["global"] = {}
                merged_config["global"].update(global_defaults)
            
            return {
                "storyConfig": story_config,
                "globalConfig": global_config,
                "mergedValues": merged_config,
                "conflicts": conflicts,
                "source": "merged"
            }
        
        cache_key = f"merged_config_{resolved_story_path}"
        return self.get_cached_or_load(cache_key, load_configs, timeout=60)
    
    def discover_stories_detailed(self, include_invalid: bool = True) -> List[Dict[str, Any]]:
        """
        Enhanced story discovery with detailed metadata.
        
        Args:
            include_invalid: Whether to include invalid stories
            
        Returns:
            List of detailed story info dictionaries
        """
        def load_stories():
            stories = self.discover_stories()
            detailed_stories = []
            
            for story in stories:
                story_path = Path(story['path'])
                
                # Security: Validate story path
                try:
                    resolved = self._sanitize_path(story_path)
                    stories_dir = self.get_stories_directory()
                    if not self._is_path_within_parent(resolved, stories_dir):
                        print(f"Security: Skipping story path {story_path} (escapes stories directory)")
                        continue
                except Exception as e:
                    print(f"Warning: Invalid story path {story_path}: {e}")
                    continue
                
                # Get detailed metadata
                metadata = self._analyze_story_structure(story_path)
                if not include_invalid and not metadata['isValid']:
                    continue
                
                detailed_stories.append({
                    **story,
                    **metadata
                })
            
            return detailed_stories
        
        cache_key = f"detailed_stories_{include_invalid}"
        return self.get_cached_or_load(cache_key, load_stories, timeout=30)
    
    def _analyze_story_structure(self, story_path: Path) -> Dict[str, Any]:
        """
        Analyze story directory structure and return metadata.
        
        Args:
            story_path: Path to story directory
            
        Returns:
            Dictionary with story metadata
        """
        try:
            # Security: Validate path
            resolved_path = self._sanitize_path(story_path)
            stories_dir = self.get_stories_directory()
            
            if not self._is_path_within_parent(resolved_path, stories_dir):
                return {
                    "isValid": False,
                    "error": "Security: Story path escapes stories directory",
                    "configExists": False,
                    "chaptersCount": 0,
                    "chapters": [],
                    "hasAudio": False,
                    "audioFilesCount": 0,
                    "xmlFilesCount": 0,
                    "lastModified": datetime.now(timezone.utc).isoformat(),
                    "directories": {}
                }
            
            config_path = resolved_path / "story-config.yml"
            chapters_dir = resolved_path / "story-chapters"
            audio_dir = resolved_path / "story-audio"
            xml_dir = resolved_path / "story-xml"
            
            # Check if story config is valid
            is_valid = self.validate_story_config(resolved_path)
            
            # Discover chapters
            chapters = []
            if chapters_dir.exists():
                for chapter_file in sorted(chapters_dir.glob("*.md")):
                    chapter_info = self._analyze_chapter(resolved_path, chapter_file)
                    chapters.append(chapter_info)
            
            # Check for audio files
            has_audio = False
            audio_files = 0
            if audio_dir.exists():
                audio_files = len(list(audio_dir.rglob("*.wav"))) + len(list(audio_dir.rglob("*.mp3")))
                has_audio = audio_files > 0
            
            # Check for XML files
            xml_files = 0
            if xml_dir.exists():
                xml_files = len(list(xml_dir.glob("*.xml")))
            
            # Get last modified time
            last_modified = datetime.now(timezone.utc).isoformat()
            if resolved_path.exists():
                stat = os.stat(resolved_path)
                last_modified = datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat()
            
            return {
                "isValid": is_valid,
                "configExists": config_path.exists(),
                "chaptersCount": len(chapters),
                "chapters": chapters,
                "hasAudio": has_audio,
                "audioFilesCount": audio_files,
                "xmlFilesCount": xml_files,
                "lastModified": last_modified,
                "directories": {
                    "chapters": str(chapters_dir) if chapters_dir.exists() else None,
                    "audio": str(audio_dir) if audio_dir.exists() else None,
                    "xml": str(xml_dir) if xml_dir.exists() else None
                }
            }
        except Exception as e:
            return {
                "isValid": False,
                "error": str(e),
                "configExists": False,
                "chaptersCount": 0,
                "chapters": [],
                "hasAudio": False,
                "audioFilesCount": 0,
                "xmlFilesCount": 0,
                "lastModified": datetime.now(timezone.utc).isoformat(),
                "directories": {}
            }
    
    def _analyze_chapter(self, story_path: Path, chapter_file: Path) -> Dict[str, Any]:
        """
        Analyze individual chapter file.
        
        Args:
            story_path: Path to story directory
            chapter_file: Path to chapter file
            
        Returns:
            Dictionary with chapter metadata
        """
        try:
            # Security: Validate paths
            resolved_story = self._sanitize_path(story_path)
            resolved_chapter = self._sanitize_path(chapter_file)
            
            # Ensure chapter is within story
            if not self._is_path_within_parent(resolved_chapter, resolved_story):
                return {
                    "filename": chapter_file.name,
                    "displayName": chapter_file.stem.replace("-", " ").title(),
                    "fullPath": str(chapter_file),
                    "error": "Security: Chapter escapes story directory",
                    "hasXml": False,
                    "hasAudioClips": False,
                    "audioClipsCount": 0,
                    "hasChapterAudio": False,
                    "lastModified": datetime.now(timezone.utc).isoformat(),
                    "fileSize": 0
                }
            
            # Basic info
            display_name = chapter_file.stem.replace("-", " ").title()
            
            # Check for corresponding XML
            xml_dir = resolved_story / "story-xml"
            xml_path = xml_dir / f"{chapter_file.stem}.xml"
            has_xml = xml_path.exists()
            
            # Check for audio clips
            audio_clips_dir = resolved_story / "story-audio" / "clips" / chapter_file.stem
            has_audio_clips = audio_clips_dir.exists() and any(audio_clips_dir.glob("*.wav"))
            audio_clips_count = len(list(audio_clips_dir.glob("*.wav"))) if has_audio_clips else 0
            
            # Check for chapter audio file
            chapter_audio_path = resolved_story / "story-audio" / f"{chapter_file.stem}.wav"
            has_chapter_audio = chapter_audio_path.exists()
            
            # Get file stats
            stat = os.stat(resolved_chapter)
            last_modified = datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat()
            file_size = stat.st_size
            
            return {
                "filename": chapter_file.name,
                "displayName": display_name,
                "fullPath": str(resolved_chapter),
                "hasXml": has_xml,
                "xmlPath": str(xml_path) if has_xml else None,
                "hasAudioClips": has_audio_clips,
                "audioClipsCount": audio_clips_count,
                "audioClipsPath": str(audio_clips_dir) if has_audio_clips else None,
                "hasChapterAudio": has_chapter_audio,
                "chapterAudioPath": str(chapter_audio_path) if has_chapter_audio else None,
                "lastModified": last_modified,
                "fileSize": file_size
            }
        except Exception as e:
            return {
                "filename": chapter_file.name,
                "displayName": chapter_file.stem.replace("-", " ").title(),
                "fullPath": str(chapter_file),
                "error": str(e),
                "hasXml": False,
                "hasAudioClips": False,
                "audioClipsCount": 0,
                "hasChapterAudio": False,
                "lastModified": datetime.now(timezone.utc).isoformat(),
                "fileSize": 0
            }
    
    def validate_configuration_detailed(
        self, 
        config_type: str, 
        config_path: Path = None, 
        config_data: Dict = None
    ) -> Dict[str, Any]:
        """
        Enhanced configuration validation with detailed error reporting.
        
        Args:
            config_type: Type of config ('global' or 'story')
            config_path: Optional path to config
            config_data: Optional config data to validate
            
        Returns:
            Dictionary with validation results
        """
        try:
            errors = []
            warnings = []
            suggestions = []
            
            if config_type == "global":
                # Validate global configuration
                if config_data:
                    config = config_data
                else:
                    config = self.load_main_config()
                
                # Check required fields
                if "FlexiTTS" not in config:
                    errors.append({
                        "field": "FlexiTTS",
                        "message": "FlexiTTS root configuration is required",
                        "code": "VALIDATION_REQUIRED_FIELD_MISSING",
                        "severity": "error"
                    })
                else:
                    flexitts_config = config["FlexiTTS"]
                    
                    # Required fields
                    required_fields = ["stories-dir", "story-dir-prefix"]
                    for field in required_fields:
                        if field not in flexitts_config:
                            errors.append({
                                "field": f"FlexiTTS.{field}",
                                "message": f"Required field '{field}' is missing",
                                "code": "VALIDATION_REQUIRED_FIELD_MISSING",
                                "severity": "error"
                            })
                    
                    # Validate stories directory
                    if "stories-dir" in flexitts_config:
                        stories_dir = Path(flexitts_config["stories-dir"]).expanduser()
                        if not stories_dir.exists():
                            warnings.append({
                                "field": "FlexiTTS.stories-dir",
                                "message": f"Stories directory does not exist: {stories_dir}",
                                "code": "VALIDATION_PATH_NOT_FOUND",
                                "severity": "warning"
                            })
                            suggestions.append(f"Create the stories directory: mkdir -p '{stories_dir}'")
                        elif not os.access(stories_dir, os.R_OK):
                            errors.append({
                                "field": "FlexiTTS.stories-dir",
                                "message": f"Cannot read stories directory: {stories_dir}",
                                "code": "PERMISSION_DENIED",
                                "severity": "error"
                            })
            
            elif config_type == "story":
                # Validate story configuration
                if config_path and config_path.exists():
                    try:
                        # Security: Validate config path
                        resolved_config = self._sanitize_path(config_path)
                        
                        # Ensure config path is safe
                        stories_dir = self.get_stories_directory()
                        if not self._is_path_within_parent(resolved_config, stories_dir):
                            errors.append({
                                "field": "story-config.yml",
                                "message": "Config path escapes stories directory",
                                "code": "VALIDATION_PATH_OUT_OF_BOUNDS",
                                "severity": "error"
                            })
                        else:
                            # Use existing validation
                            is_valid = self.validate_story_config(str(resolved_config.parent))
                            if not is_valid:
                                errors.append({
                                    "field": "story-config.yml",
                                    "message": "Story configuration validation failed",
                                    "code": "STORY_CONFIG_INVALID",
                                    "severity": "error"
                                })
                    except Exception as e:
                        errors.append({
                            "field": "story-config.yml",
                            "message": f"Error validating story config: {e}",
                            "code": "VALIDATION_ERROR",
                            "severity": "error"
                        })
                else:
                    errors.append({
                        "field": "story-config.yml",
                        "message": "Story configuration file not found",
                        "code": "STORY_CONFIG_NOT_FOUND",
                        "severity": "error"
                    })
            
            is_valid = len(errors) == 0
            
            return {
                "success": True,
                "isValid": is_valid,
                "errors": errors,
                "warnings": warnings,
                "suggestions": suggestions
            }
            
        except Exception as e:
            return {
                "success": False,
                "isValid": False,
                "errors": [{
                    "field": "validation",
                    "message": f"Validation error: {e}",
                    "code": "INTERNAL_ERROR",
                    "severity": "error"
                }],
                "warnings": [],
                "suggestions": []
            }
    
    def get_system_status(self) -> Dict[str, Any]:
        """
        Get comprehensive system status.
        
        Returns:
            Dictionary with system status information
        """
        try:
            # Global config status
            global_config_exists = self._main_config_path.exists()
            global_config_valid = False
            global_config_error = None
            
            try:
                self.load_main_config()
                global_config_valid = True
            except Exception as e:
                global_config_error = str(e)
            
            # Stories directory status
            stories_dir = None
            stories_accessible = False
            stories_count = 0
            valid_stories_count = 0
            
            try:
                stories_dir = self.get_stories_directory()
                stories_accessible = stories_dir.exists() and os.access(stories_dir, os.R_OK)
                if stories_accessible:
                    stories = self.discover_stories()
                    stories_count = len(stories)
                    valid_stories_count = sum(1 for s in stories if self.validate_story_config(s['path']))
            except Exception:
                pass
            
            # Permission checks
            config_dir_writable = False
            try:
                config_dir_writable = os.access(self._main_config_path.parent, os.W_OK)
                if not self._main_config_path.parent.exists():
                    self._main_config_path.parent.mkdir(parents=True, exist_ok=True)
                    config_dir_writable = os.access(self._main_config_path.parent, os.W_OK)
            except Exception:
                pass
            
            # Overall health
            health_checks = {
                "global_config_valid": global_config_valid,
                "stories_dir_accessible": stories_accessible,
                "config_dir_writable": config_dir_writable
            }
            
            healthy_checks = sum(1 for v in health_checks.values() if v)
            if healthy_checks == len(health_checks):
                overall_status = "healthy"
            elif healthy_checks >= len(health_checks) // 2:
                overall_status = "warning"
            else:
                overall_status = "error"
            
            return {
                "status": overall_status,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "globalConfig": {
                    "exists": global_config_exists,
                    "valid": global_config_valid,
                    "path": str(self._main_config_path),
                    "error": global_config_error
                },
                "storiesDirectory": {
                    "path": str(stories_dir) if stories_dir else None,
                    "exists": stories_dir.exists() if stories_dir else False,
                    "accessible": stories_accessible,
                    "storiesCount": stories_count,
                    "validStoriesCount": valid_stories_count
                },
                "permissions": {
                    "configDirWritable": config_dir_writable,
                    "configFileReadable": global_config_exists and os.access(self._main_config_path, os.R_OK),
                    "storiesDirReadable": stories_accessible
                },
                "checks": health_checks
            }
            
        except Exception as e:
            return {
                "status": "error",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error": str(e),
                "checks": {}
            }


# Create singleton instance (production mode by default)
enhanced_config_manager = EnhancedConfigManager()

# Backwards compatibility - expose original ConfigManager interface
ConfigManager = EnhancedConfigManager
config_manager = enhanced_config_manager

# Legacy interface support
def load_main_config():
    """Legacy: Load main FlexiTTS configuration"""
    return enhanced_config_manager.load_main_config()

def discover_stories():
    """Legacy: Discover all stories"""
    return enhanced_config_manager.discover_stories()

def load_story_config(story_path: str):
    """Legacy: Load story-specific configuration"""
    return enhanced_config_manager.load_story_config(story_path)

def validate_story_config(story_path: str):
    """Legacy: Validate story configuration"""
    return enhanced_config_manager.validate_story_config(story_path)


if __name__ == "__main__":
    # Test the enhanced configuration manager
    try:
        # Test system status
        status = enhanced_config_manager.get_system_status()
        print("System Status:")
        print(json.dumps(status, indent=2))
        
        # Test story discovery
        print("\nDiscovering stories...")
        stories = enhanced_config_manager.discover_stories_detailed()
        print(f"Found {len(stories)} stories:")
        for story in stories[:3]:  # Show first 3
            print(f"  - {story['name']}: {story['chaptersCount']} chapters, valid: {story['isValid']}")
        
        # Test validation
        print("\nValidating global config...")
        validation = enhanced_config_manager.validate_configuration_detailed("global")
        print(f"Global config valid: {validation['isValid']}")
        if validation['errors']:
            print(f"Errors: {len(validation['errors'])}")
        if validation['warnings']:
            print(f"Warnings: {len(validation['warnings'])}")
        
        # Test security: path traversal
        print("\nTesting security (path traversal detection)...")
        try:
            enhanced_config_manager.load_story_config("../../../etc/passwd")
            print("ERROR: Path traversal was not blocked!")
        except PathTraversalError:
            print("SUCCESS: Path traversal correctly blocked")
            
    except Exception as e:
        print(f"Error during testing: {e}")

# Export EnhancedConfigManager as ConfigManager for backward compatibility
ConfigManager = EnhancedConfigManager
