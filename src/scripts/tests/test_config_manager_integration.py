#!/usr/bin/env python3
"""
Enhanced integration tests for FlexiTTS configuration management.
Focuses on hierarchical configuration loading and story discovery.
"""

import pytest
import tempfile
import shutil
import json
import yaml
import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, List, Any

import sys
sys.path.append(str(Path(__file__).parent.parent))

from config_manager import ConfigManager


class TestConfigManagerIntegration:
    """Comprehensive integration tests for ConfigManager."""

    @pytest.fixture
    def temp_config_env(self):
        """Create a temporary configuration environment."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir) / ".config" / "FlexiTTS"
            stories_dir = Path(temp_dir) / "Stories"
            
            # Create directory structure
            config_dir.mkdir(parents=True, exist_ok=True)
            stories_dir.mkdir(parents=True, exist_ok=True)
            
            # Create main config
            main_config = {
                'FlexiTTS': {
                    'stories-dir': str(stories_dir),
                    'story-dir-prefix': 'Story-',
                    'default-voice-provider': 'elevenlabs',
                    'global-audio-settings': {
                        'sample-rate': 44100,
                        'bit-depth': 16
                    }
                }
            }
            
            main_config_path = config_dir / "FlexiTTS.yaml"
            with open(main_config_path, 'w') as f:
                yaml.dump(main_config, f)
            
            # Create test stories
            for story_name in ['Adventure', 'Mystery', 'Romance']:
                story_dir = stories_dir / f"Story-{story_name}"
                story_dir.mkdir()
                
                # Create story config
                story_config = {
                    'global': {
                        'story-dir': '.',
                        'voices': 'voices',
                        'chapters': 'story-chapters',
                        'story-xml': 'story-xml',
                        'logs': 'logs',
                        'story-audio': 'story-audio',
                        'clips': 'story-audio/clips',
                        'clip-separation': 500
                    },
                    'characters': [
                        {
                            'name': f'Hero{story_name}',
                            'voice-sample': f'voices/hero_{story_name.lower()}.wav',
                            'gender': 'male' if story_name != 'Romance' else 'female',
                            'age': 'adult',
                            'style': 'adventurous'
                        },
                        {
                            'name': f'Narrator{story_name}',
                            'voice-sample': f'voices/narrator_{story_name.lower()}.wav',
                            'gender': 'neutral',
                            'age': 'adult',
                            'style': 'narrative'
                        }
                    ]
                }
                
                story_config_path = story_dir / "story-config.yml"
                with open(story_config_path, 'w') as f:
                    yaml.dump(story_config, f)
                
                # Create directory structure
                for dir_name in ['voices', 'story-chapters', 'story-xml', 'logs', 'story-audio']:
                    (story_dir / dir_name).mkdir()
                
                # Create some test files
                (story_dir / 'story-chapters' / 'chapter01.md').write_text(f"# Chapter 1 of {story_name}")
                (story_dir / 'voices' / f'hero_{story_name.lower()}.wav').write_bytes(b'fake_audio_data')
            
            yield {
                'temp_dir': Path(temp_dir),
                'config_dir': config_dir,
                'stories_dir': stories_dir,
                'main_config_path': main_config_path
            }

    def test_hierarchical_config_loading(self, temp_config_env):
        """Test complete configuration hierarchy loading."""
        with patch.dict('os.environ', {'HOME': str(temp_config_env['temp_dir'])}):
            config_manager = ConfigManager()
            
            # Test main config loading
            main_config = config_manager.load_main_config()
            assert 'FlexiTTS' in main_config
            assert main_config['FlexiTTS']['story-dir-prefix'] == 'Story-'
            assert main_config['FlexiTTS']['default-voice-provider'] == 'elevenlabs'
            
            # Test story discovery
            stories = config_manager.discover_stories()
            assert len(stories) == 3
            story_names = [story['name'] for story in stories]
            assert 'Adventure' in story_names
            assert 'Mystery' in story_names
            assert 'Romance' in story_names
            
            # Test individual story loading
            adventure_path = None
            for story in stories:
                if story['name'] == 'Adventure':
                    adventure_path = story['path']
                    break
            
            assert adventure_path is not None
            story_config = config_manager.load_story_config(adventure_path)
            assert 'global' in story_config
            assert 'characters' in story_config
            assert len(story_config['characters']) == 2

    def test_story_discovery_performance(self, temp_config_env):
        """Validate story discovery under load."""
        stories_dir = temp_config_env['stories_dir']
        
        # Create many story directories
        for i in range(50):
            story_dir = stories_dir / f"Story-Performance{i:03d}"
            story_dir.mkdir()
            
            story_config = {
                'global': {'story-dir': '.'},
                'characters': [{'name': f'Character{i}', 'voice-sample': f'voice{i}.wav'}]
            }
            
            with open(story_dir / "story-config.yml", 'w') as f:
                yaml.dump(story_config, f)
        
        with patch.dict('os.environ', {'HOME': str(temp_config_env['temp_dir'])}):
            config_manager = ConfigManager()
            
            # Measure discovery time
            start_time = time.time()
            stories = config_manager.discover_stories()
            discovery_time = time.time() - start_time
            
            # Should discover all stories (3 original + 50 new = 53)
            assert len(stories) == 53
            
            # Should complete within performance threshold (< 100ms per requirement)
            assert discovery_time < 0.1, f"Discovery took {discovery_time:.3f}s, exceeding 100ms threshold"

    def test_config_validation_comprehensive(self, temp_config_env):
        """End-to-end configuration validation."""
        with patch.dict('os.environ', {'HOME': str(temp_config_env['temp_dir'])}):
            config_manager = ConfigManager()
            
            # Test valid story validation
            stories = config_manager.discover_stories()
            for story in stories:
                assert config_manager.validate_story_config(story['path']) == True
            
            # Test invalid story validation
            invalid_story_dir = temp_config_env['stories_dir'] / "Story-Invalid"
            invalid_story_dir.mkdir()
            
            # Create invalid config (missing required fields)
            invalid_config = {'incomplete': 'config'}
            with open(invalid_story_dir / "story-config.yml", 'w') as f:
                yaml.dump(invalid_config, f)
            
            assert config_manager.validate_story_config(str(invalid_story_dir)) == False
            
            # Test corrupted YAML
            corrupted_story_dir = temp_config_env['stories_dir'] / "Story-Corrupted"
            corrupted_story_dir.mkdir()
            
            with open(corrupted_story_dir / "story-config.yml", 'w') as f:
                f.write("invalid: yaml: content: ][")
            
            assert config_manager.validate_story_config(str(corrupted_story_dir)) == False

    def test_migration_scenarios(self, temp_config_env):
        """Test configuration migration paths."""
        # Create old-style configuration in a legacy story directory
        legacy_story_dir = temp_config_env['temp_dir'] / "LegacyStory"
        legacy_story_dir.mkdir(parents=True, exist_ok=True)
        old_config_path = legacy_story_dir / "story-config.yml"
        
        # Old-style config missing required fields (e.g., missing 'characters')
        old_config = {
            'global': {
                'story-dir': 'legacy-story',
                'voices': 'old-voices'
            }
            # Missing 'characters' section - needs migration
        }
        
        with open(old_config_path, 'w') as f:
            yaml.dump(old_config, f)
        
        with patch.dict('os.environ', {'HOME': str(temp_config_env['temp_dir'])}):
            config_manager = ConfigManager(test_mode=True)
            config_manager.add_test_whitelist(str(temp_config_env['temp_dir']))
            
            # Test migration detection on legacy story directory (missing 'characters')
            assert config_manager.needs_migration(str(legacy_story_dir)), "Should detect migration needed for legacy config (missing characters)"
            
            # Test migration execution
            migration_result = config_manager.migrate_legacy_config(str(old_config_path))
            assert migration_result['success'] == True, f"Migration failed: {migration_result.get('error', 'unknown error')}"
            assert 'new_story_path' in migration_result
            
            # Verify migrated story exists and is valid
            migrated_stories = config_manager.discover_stories()
            migrated_story_names = [s['name'] for s in migrated_stories]
            assert 'LegacyStory' in migrated_story_names, f"Should find migrated story in {migrated_story_names}"

    def test_concurrent_story_access(self, temp_config_env):
        """Test concurrent access to story configurations."""
        import threading
        import concurrent.futures
        
        with patch.dict('os.environ', {'HOME': str(temp_config_env['temp_dir'])}):
            config_manager = ConfigManager()
            stories = config_manager.discover_stories()
            
            results = []
            errors = []
            
            def load_story_config(story_path):
                try:
                    config = config_manager.load_story_config(story_path)
                    results.append(config)
                    return config
                except Exception as e:
                    errors.append(e)
                    return None
            
            # Test concurrent loading
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                futures = []
                for _ in range(20):  # Load each story multiple times concurrently
                    for story in stories:
                        future = executor.submit(load_story_config, story['path'])
                        futures.append(future)
                
                concurrent.futures.wait(futures)
            
            # All loads should succeed
            assert len(errors) == 0, f"Concurrent access errors: {errors}"
            assert len(results) == 20 * len(stories)  # 20 loads per story
            
            # All results should be valid configurations
            for result in results:
                assert 'global' in result
                assert 'characters' in result

    def test_error_recovery_mechanisms(self, temp_config_env):
        """Test error recovery during configuration operations."""
        with patch.dict('os.environ', {'HOME': str(temp_config_env['temp_dir'])}):
            config_manager = ConfigManager(test_mode=True)
            
            # Test recovery from corrupted main config
            main_config_path = temp_config_env['main_config_path']
            
            # Backup original
            with open(main_config_path, 'r') as f:
                original_config = f.read()
            
            # Corrupt the main config
            with open(main_config_path, 'w') as f:
                f.write("corrupted: yaml: content: ][")
            
            # Should fall back to defaults
            fallback_config = config_manager.load_main_config()
            assert fallback_config is not None
            assert 'FlexiTTS' in fallback_config
            
            # Should recover when config is fixed
            with open(main_config_path, 'w') as f:
                f.write(original_config)
            
            recovered_config = config_manager.load_main_config(force_reload=True)
            assert recovered_config['FlexiTTS']['story-dir-prefix'] == 'Story-'

    def test_large_story_collection_handling(self, temp_config_env):
        """Test handling of large story collections."""
        stories_dir = temp_config_env['stories_dir']
        
        # Create a large number of stories with varying complexity
        for i in range(100):
            story_dir = stories_dir / f"Story-Large{i:03d}"
            story_dir.mkdir()
            
            # Create stories with varying numbers of characters
            character_count = (i % 10) + 1
            characters = []
            for j in range(character_count):
                characters.append({
                    'name': f'Character{j}',
                    'voice-sample': f'voice{j}.wav',
                    'gender': 'male' if j % 2 == 0 else 'female',
                    'age': 'adult',
                    'style': f'style{j}'
                })
            
            story_config = {
                'global': {
                    'story-dir': '.',
                    'voices': 'voices',
                    'chapters': 'story-chapters'
                },
                'characters': characters
            }
            
            with open(story_dir / "story-config.yml", 'w') as f:
                yaml.dump(story_config, f)
        
        with patch.dict('os.environ', {'HOME': str(temp_config_env['temp_dir'])}):
            config_manager = ConfigManager()
            
            # Test discovery performance with large collection
            start_time = time.time()
            stories = config_manager.discover_stories()
            discovery_time = time.time() - start_time
            
            # Should discover all stories (3 original + 100 new = 103)
            assert len(stories) >= 103
            
            # Should still meet performance requirements
            assert discovery_time < 0.5, f"Large collection discovery took {discovery_time:.3f}s"
            
            # Test loading a subset efficiently
            sample_stories = stories[:10]
            start_time = time.time()
            for story in sample_stories:
                config = config_manager.load_story_config(story['path'])
                assert 'characters' in config
            loading_time = time.time() - start_time
            
            # Should load 10 stories quickly
            assert loading_time < 0.2, f"Loading 10 stories took {loading_time:.3f}s"


class TestConfigManagerEdgeCases:
    """Test edge cases and error conditions."""

    def test_missing_directories(self):
        """Test handling of missing configuration directories."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict('os.environ', {'HOME': str(temp_dir)}):
                config_manager = ConfigManager(test_mode=True)
                config_manager.add_test_whitelist(str(temp_dir))
                
                # Should create missing directories
                main_config = config_manager.load_main_config()
                assert main_config is not None
                
                # Should handle missing stories directory gracefully
                stories = config_manager.discover_stories()
                assert isinstance(stories, list)
                assert len(stories) == 0

    def test_permission_errors(self):
        """Test handling of permission errors."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir) / ".config" / "FlexiTTS"
            config_dir.mkdir(parents=True, exist_ok=True)
            
            # Create config file with restricted permissions
            main_config_path = config_dir / "FlexiTTS.yaml"
            main_config_path.write_text("FlexiTTS:\n  stories-dir: /tmp\n")
            main_config_path.chmod(0o000)  # No permissions
            
            try:
                with patch.dict('os.environ', {'HOME': str(temp_dir)}):
                    # Create test mode config manager to bypass XDG path validation
                    config_manager = ConfigManager(test_mode=True)
                    config_manager.add_test_whitelist(str(config_dir.parent))
                    
                    # Should handle permission error gracefully
                    config = config_manager.load_main_config()
                    assert config is not None  # Should fall back to defaults
            finally:
                # Restore permissions for cleanup
                main_config_path.chmod(0o644)

    def test_malformed_yaml_handling(self):
        """Test handling of various YAML format errors."""
        test_cases = [
            "invalid: yaml: content: ][",  # Invalid syntax
            "key without value:",           # Missing value
            "- item1\n- item2\nkey: value", # Mixed structures
            "",                             # Empty file
            "null",                         # Null content
            "123",                          # Non-dict root
        ]
        
        with tempfile.TemporaryDirectory() as temp_dir:
            for i, invalid_yaml in enumerate(test_cases):
                config_dir = Path(temp_dir) / f"test{i}" / ".config" / "FlexiTTS"
                config_dir.mkdir(parents=True, exist_ok=True)
                
                main_config_path = config_dir / "FlexiTTS.yaml"
                main_config_path.write_text(invalid_yaml)
                
                with patch.dict('os.environ', {'HOME': str(Path(temp_dir) / f"test{i}")}):
                    # Create test mode config manager to bypass XDG path validation
                    config_manager = ConfigManager(test_mode=True)
                    config_manager.add_test_whitelist(str(config_dir.parent))
                    
                    # Should not crash, should return default config
                    config = config_manager.load_main_config()
                    assert config is not None
                    assert 'FlexiTTS' in config


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
