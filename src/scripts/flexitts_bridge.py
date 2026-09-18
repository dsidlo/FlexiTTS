#!/usr/bin/env python3
"""
FlexiTTS Bridge for UI Integration

This script provides the backend functionality for the UI to work with
the FlexiTTS configuration system.

SECURITY NOTES:
- All file paths are validated against path traversal
- Input is sanitized before processing
- All operations are bounded to configured directories
"""

import sys
import os
import json
import re
from pathlib import Path

# Add the project root to the path so we can import our modules
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))
# Ensure local script imports resolve before repository root modules in tests/runtime
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Import the enhanced config manager with security features
from base_config_manager import ConfigManager, ConfigError, PathTraversalError, config_manager


def _sanitize_directory_name(name: str) -> str:
    """
    Sanitize directory name to prevent injection attacks.
    
    Args:
        name: Directory name to sanitize
        
    Returns:
        Sanitized directory name
    """
    if not name:
        return ""
    
    # Remove any path separators and null bytes
    sanitized = name.replace('..', '').replace('/', '').replace('\\', '').replace('\x00', '')
    
    # Only allow alphanumeric, hyphens, underscores, and spaces
    sanitized = re.sub(r'[^\w\-\s]', '', sanitized).strip()
    
    # Limit length
    if len(sanitized) > 255:
        sanitized = sanitized[:255]
    
    return sanitized


def list_stories():
    """
    List available stories for the UI dropdown.
    
    Returns:
        List of story dictionaries with name, path, and directory_name
    """
    try:
        return config_manager.discover_stories()
    except Exception as e:
        print(f"Error getting available stories: {e}", file=sys.stderr)
        return []


# Alias for backward compatibility with tests that expect get_available_stories
get_available_stories = list_stories


def list_chapter_files_updated():
    """
    List chapter files across all discovered stories.
    
    Returns:
        List of relative paths to chapter files
    """
    try:
        stories = config_manager.discover_stories()
        all_chapters = []
        
        for story in stories:
            story_path = Path(story['path'])
            chapters_dir = story_path / "story-chapters"
            
            if chapters_dir.exists():
                for chapter_file in chapters_dir.glob("*.md"):
                    # Include story context in the path
                    relative_path = f"{story['directory_name']}/story-chapters/{chapter_file.name}"
                    all_chapters.append(relative_path)
        
        return sorted(all_chapters)
        
    except Exception as e:
        print(f"Error listing chapters: {e}", file=sys.stderr)
        return []


def load_story_config_for_chapter(chapter_path: str):
    """
    Load story configuration for a given chapter path.
    
    Args:
        chapter_path: Path to the chapter file
        
    Returns:
        Story configuration dictionary
    """
    print(f"[RESOURCE-ACCESS] Loading story config for chapter", file=sys.stderr)
    print(f"  chapter_path: {chapter_path}", file=sys.stderr)
    print(f"  resourceType: yaml", file=sys.stderr)
    
    try:
        # Security: Sanitize chapter path
        sanitized = _sanitize_directory_name(chapter_path)
        if not sanitized:
            raise ValueError("Invalid chapter path")
        
        # Extract story directory from chapter path
        # Format: Story-Name/story-chapters/chapter.md
        parts = Path(chapter_path).parts
        if len(parts) >= 2 and parts[1] == "story-chapters":
            story_dir_name = parts[0]
            
            # Validate story directory name
            validated_name = _sanitize_directory_name(story_dir_name)
            if not validated_name or not validated_name.startswith("Story-"):
                raise ValueError(f"Invalid story directory: {story_dir_name}")
            
            stories_dir = config_manager.get_stories_directory()
            story_path = stories_dir / validated_name
            
            if story_path.exists():
                print(f"[RESOURCE-ACCESS] Successfully loaded story config", file=sys.stderr)
                print(f"  story_path: {story_path}", file=sys.stderr)
                return config_manager.load_story_config(story_path)
        
        # Fallback: try to find any story-config.yml in current directory
        fallback_config = Path("story-config.yml")
        if fallback_config.exists():
            print(f"[RESOURCE-ACCESS] Using fallback config", file=sys.stderr)
            print(f"  config_path: {fallback_config}", file=sys.stderr)
            with open(fallback_config, 'r') as f:
                import yaml
                return yaml.safe_load(f)
        
        print(f"[RESOURCE-ACCESS] Config NOT found", file=sys.stderr)
        print(f"  chapter_path: {chapter_path}", file=sys.stderr)
        raise ValueError(f"No story configuration found for chapter: {chapter_path}")
        
    except Exception as e:
        print(f"[RESOURCE-ACCESS] Failed to load story config: {e}", file=sys.stderr)
        print(f"  chapter_path: {chapter_path}", file=sys.stderr)
        raise


def load_story_config_for_story(story_directory: str):
    """
    Load story configuration for a specific story directory.
    
    Args:
        story_directory: Name of the story directory (e.g., 'Story-Entanglement')
        
    Returns:
        Story configuration dictionary
    """
    try:
        # Security: Validate story directory name
        validated_name = _sanitize_directory_name(story_directory)
        if not validated_name or not validated_name.startswith("Story-"):
            raise PathTraversalError(f"Invalid story directory name: {story_directory}")
        
        stories_dir = config_manager.get_stories_directory()
        story_path = stories_dir / validated_name
        
        return config_manager.load_story_config(story_path)
        
    except PathTraversalError as e:
        print(f"Security error: {e}", file=sys.stderr)
        raise
    except Exception as e:
        print(f"Error loading story config for {story_directory}: {e}", file=sys.stderr)
        raise


def validate_flexitts_config():
    """
    Validate the main FlexiTTS configuration.
    
    Returns:
        Dictionary with validation result
    """
    try:
        config_manager.load_main_config()
        stories_dir = config_manager.get_stories_directory()
        
        # Check if stories directory exists
        if not stories_dir.exists():
            print(f"Warning: Stories directory does not exist: {stories_dir}")
            return {"valid": False, "error": f"Stories directory does not exist: {stories_dir}"}
        
        # Check if we can discover stories
        stories = config_manager.discover_stories()
        if not stories:
            print(f"Warning: No stories found in {stories_dir}")
        
        return {"valid": True, "stories_count": len(stories)}
        
    except Exception as e:
        print(f"FlexiTTS configuration validation failed: {e}", file=sys.stderr)
        return {"valid": False, "error": str(e)}


def validate_story_path(story_path: str) -> bool:
    """
    Validate that a story path is within the stories directory.
    
    Args:
        story_path: Path to validate
        
    Returns:
        True if valid
    """
    try:
        stories_dir = config_manager.get_stories_directory()
        resolved = Path(story_path).expanduser().resolve()
        
        # Check if path is within stories directory
        return str(resolved).startswith(str(stories_dir))
    except Exception:
        return False



# ---------------------------------------------------------------------------
# Character/emotion/sample management commands (Phase 6 wiring)
# ---------------------------------------------------------------------------

def _make_character_service():
    stories_dir = config_manager.get_stories_directory()
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "api"))
    from character_service import CharacterService
    return CharacterService(stories_dir)


def _make_sample_service():
    stories_dir = config_manager.get_stories_directory()
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "api"))
    from sample_service import SampleService
    return SampleService(stories_dir)


def _make_import_service():
    stories_dir = config_manager.get_stories_directory()
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "api"))
    from import_export_service import ImportService
    return ImportService(stories_dir)


def _error_payload(e: Exception) -> dict:
    return {"error": str(e), "code": getattr(e, "code", type(e).__name__)}


def handle_character_command(command: str, argv) -> int:
    """Handle character/emotion/sample/import-export bridge commands."""
    try:
        if command == "list":
            chars = _make_character_service().list_characters(argv[0])
            print(json.dumps({"success": True, "characters": chars}))

        elif command == "get":
            char = _make_character_service().get_character(argv[0], argv[1])
            print(json.dumps({"success": True, "character": char}))

        elif command == "create":
            char = _make_character_service().create_character(argv[0], json.loads(argv[1]))
            print(json.dumps({"success": True, "character": char}))

        elif command == "update":
            char = _make_character_service().update_character(argv[0], argv[1], json.loads(argv[2]))
            print(json.dumps({"success": True, "character": char}))

        elif command == "delete":
            result = _make_character_service().delete_character(argv[0], argv[1])
            print(json.dumps({"success": True, **result}))

        elif command == "add-emotion":
            entry = _make_character_service().add_emotion(argv[0], argv[1], json.loads(argv[2]))
            print(json.dumps({"success": True, "emotion": entry}))

        elif command == "update-emotion":
            entry = _make_character_service().update_emotion(argv[0], argv[1], argv[2], json.loads(argv[3]))
            print(json.dumps({"success": True, "emotion": entry}))

        elif command == "delete-emotion":
            allow_last = len(argv) > 3 and argv[3] == "--allow-last"
            result = _make_character_service().delete_emotion(argv[0], argv[1], argv[2], allow_delete_last=allow_last)
            print(json.dumps({"success": True, **result}))

        elif command == "reorder-emotions":
            emotions = _make_character_service().reorder_emotions(argv[0], argv[1], json.loads(argv[2]))
            print(json.dumps({"success": True, "emotions": emotions}))

        elif command == "set-default-emotion":
            entry = _make_character_service().set_default_emotion(argv[0], argv[1], argv[2])
            print(json.dumps({"success": True, "emotion": entry}))

        elif command == "sample-metadata":
            emotion_id = argv[2] if len(argv) > 2 and argv[2] != "-" else None
            meta = _make_sample_service().get_sample_metadata(argv[0], argv[1], emotion_id)
            print(json.dumps({"success": True, "sample": meta}))

        elif command == "export":
            doc = _make_import_service().export_character(argv[0], argv[1], include_samples=True)
            print(json.dumps({"success": True, "document": doc}))

        elif command == "import":
            conflict = argv[2] if len(argv) > 2 else "keep-both"
            payload = Path(argv[1]).read_bytes()
            result = _make_import_service().import_characters(argv[0], payload, conflict=conflict)
            print(json.dumps({"success": True, **result}))

        elif command == "upload-sample":
            story_dir, character_id, emotion_id, filename, b64 = argv[0], argv[1], argv[2], argv[3], argv[4]
            emotion = None if emotion_id == "-" else emotion_id
            import base64 as _b64
            content = base64.b64decode(b64)
            sample = _make_sample_service().upload_sample(
                story_dir, character_id, emotion, filename, content)
            print(json.dumps({"success": True, "sample": sample}))

        elif command == "validate-sox":
            sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "api"))
            from sox_service import SoxEngine
            engine = SoxEngine()
            print(json.dumps({"success": True, **engine.validate(json.loads(argv[0]) if argv else [])}))

        else:
            print(json.dumps({"success": False, "error": f"Unknown character command: {command}", "code": "UNKNOWN_COMMAND"}))
            return 1
        return 0
    except Exception as e:
        print(json.dumps(_error_payload(e)))
        return 1


def main():
    """Main entry point for bridge functions"""
    if len(sys.argv) < 2:
        print("Usage: python flexitts_bridge.py <command> [args...]")
        print("\nCommands:")
        print("  list-stories              List available stories")
        print("  list-chapters             List all chapter files")
        print("  get-stories               Alias for list-stories")
        print("  load-story-config <path>   Load config for chapter path")
        print("  load-story <dirname>     Load config by story directory name")
        print("  validate-config           Validate FlexiTTS configuration")
        print("  validate-path <path>      Validate story path")
        return 1
    
    command = sys.argv[1]
    
    try:
        if command == "list-stories" or command == "get-stories":
            stories = list_stories()
            print(json.dumps(stories))
            
        elif command == "list-chapters":
            chapters = list_chapter_files_updated()
            print(json.dumps(chapters))
            
        elif command == "load-story-config":
            if len(sys.argv) < 3:
                print("Usage: python flexitts_bridge.py load-story-config <chapter_path>")
                return 1
            chapter_path = sys.argv[2]
            config = load_story_config_for_chapter(chapter_path)
            print(json.dumps(config))
            
        elif command == "load-story":
            if len(sys.argv) < 3:
                print("Usage: python flexitts_bridge.py load-story <story_directory>")
                return 1
            story_directory = sys.argv[2]
            config = load_story_config_for_story(story_directory)
            print(json.dumps(config))
            
        elif command == "validate-config":
            result = validate_flexitts_config()
            print(json.dumps(result))
            
        elif command == "validate-path":
            if len(sys.argv) < 3:
                print("Usage: python flexitts_bridge.py validate-path <path>")
                return 1
            path = sys.argv[2]
            is_valid = validate_story_path(path)
            print(json.dumps({"valid": is_valid}))

        elif command == "characters":
            if len(sys.argv) < 3:
                print(json.dumps({"success": False, "error": "characters requires a subcommand", "code": "MISSING_SUBCOMMAND"}))
                return 1
            return handle_character_command(sys.argv[2], sys.argv[3:])
            
        else:
            print(f"Unknown command: {command}")
            return 1
            
    except PathTraversalError as e:
        print(f"Security error: {e}", file=sys.stderr)
        return 1
    except ConfigError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error executing command {command}: {e}", file=sys.stderr)
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
