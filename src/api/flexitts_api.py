#!/usr/bin/env python3
"""
FlexiTTS Configuration Management REST API

Provides HTTP endpoints for managing FlexiTTS configuration, story discovery,
and configuration merging operations as defined in the API specification.
"""

import os
import sys
import json
import asyncio
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import yaml

# FastAPI imports
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

# Import project modules
from src.scripts.config_manager import ConfigManager
from src.scripts.validate_config import validate_story_config


# Pydantic Models for API
class GlobalConfigRequest(BaseModel):
    config: Dict[str, Any]
    createDirectories: Optional[bool] = False
    backup: Optional[bool] = False

class ValidationRequest(BaseModel):
    type: str = Field(..., regex="^(global|story|merged)$")
    config: Optional[Dict[str, Any]] = None
    storyId: Optional[str] = None
    strict: Optional[bool] = False

class StoryMetadata(BaseModel):
    id: str
    displayName: str
    fullPath: str
    configPath: str
    isValid: bool
    chapters: List[Dict[str, Any]]
    lastModified: str
    hasAudioClips: bool

class ErrorResponse(BaseModel):
    success: bool = False
    error: Dict[str, Any]


class FlexiTTSAPI:
    """FlexiTTS Configuration Management API Server"""
    
    def __init__(self):
        self.app = FastAPI(
            title="FlexiTTS Configuration API",
            description="REST API for FlexiTTS configuration management",
            version="1.0.0"
        )
        self.config_manager = ConfigManager()
        self.websocket_connections: List[WebSocket] = []
        self.setup_routes()
        self.setup_middleware()
    
    def setup_middleware(self):
        """Configure CORS and other middleware"""
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["http://localhost:*", "http://127.0.0.1:*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    
    def setup_routes(self):
        """Register all API routes"""
        
        @self.app.get("/api/config/global")
        async def get_global_config():
            """Retrieve global FlexiTTS configuration"""
            try:
                config = self.config_manager.load_main_config()
                config_path = str(self.config_manager._main_config_path)
                
                # Get last modified time
                last_modified = datetime.now(timezone.utc).isoformat()
                if Path(config_path).exists():
                    stat = os.stat(config_path)
                    last_modified = datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat()
                
                return {
                    "success": True,
                    "config": config,
                    "configPath": config_path,
                    "lastModified": last_modified
                }
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/api/config/global")
        async def save_global_config(request: GlobalConfigRequest):
            """Create or update global configuration"""
            try:
                # Backup existing config if requested
                backup_path = None
                if request.backup and self.config_manager._main_config_path.exists():
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    backup_path = str(self.config_manager._main_config_path.with_suffix(f".{timestamp}.bak"))
                    import shutil
                    shutil.copy2(self.config_manager._main_config_path, backup_path)
                
                # Update and save configuration
                self.config_manager.main_config = request.config
                self.config_manager.save_main_config()
                
                # Broadcast change via WebSocket
                await self._broadcast_config_change("global", str(self.config_manager._main_config_path))
                
                return {
                    "success": True,
                    "message": "Global configuration saved successfully",
                    "configPath": str(self.config_manager._main_config_path),
                    "backupPath": backup_path
                }
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.put("/api/config/global/validate")
        async def validate_global_config(request: GlobalConfigRequest):
            """Validate global configuration without saving"""
            try:
                # Basic validation - check required fields
                errors = []
                warnings = []
                
                if "FlexiTTS" not in request.config:
                    errors.append({
                        "field": "FlexiTTS",
                        "message": "FlexiTTS root key is required",
                        "code": "VALIDATION_REQUIRED_FIELD_MISSING",
                        "severity": "error"
                    })
                
                flexitts_config = request.config.get("FlexiTTS", {})
                
                # Check required fields
                required_fields = ["stories-dir", "story-dir-prefix"]
                for field in required_fields:
                    if field not in flexitts_config:
                        errors.append({
                            "field": f"FlexiTTS.{field}",
                            "message": f"Field '{field}' is required",
                            "code": "VALIDATION_REQUIRED_FIELD_MISSING",
                            "severity": "error"
                        })
                
                # Check if stories directory exists (warning only)
                stories_dir = flexitts_config.get("stories-dir")
                if stories_dir and not Path(stories_dir).expanduser().exists():
                    warnings.append({
                        "field": "FlexiTTS.stories-dir",
                        "message": f"Stories directory does not exist: {stories_dir}",
                        "code": "VALIDATION_PATH_NOT_FOUND",
                        "severity": "warning"
                    })
                
                return {
                    "success": True,
                    "isValid": len(errors) == 0,
                    "errors": errors,
                    "warnings": warnings,
                    "validatedConfig": request.config if len(errors) == 0 else None
                }
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/api/stories")
        async def get_stories(
            includeInvalid: bool = True,
            includeChapters: bool = True,
            sortBy: str = "name",
            sortOrder: str = "asc"
        ):
            """Discover and return all available stories"""
            try:
                start_time = time.time()
                
                # Get basic story list
                stories = self.config_manager.discover_stories()
                story_metadata = []
                
                for story in stories:
                    story_path = Path(story['path'])
                    config_path = story_path / "story-config.yml"
                    
                    # Validate story configuration
                    is_valid = self._validate_story_structure(story_path)
                    
                    if not includeInvalid and not is_valid:
                        continue
                    
                    # Get chapters if requested
                    chapters = []
                    if includeChapters:
                        chapters = self._discover_story_chapters(story_path)
                    
                    # Check for audio clips
                    has_audio = self._check_story_audio(story_path)
                    
                    # Get last modified time
                    last_modified = datetime.now(timezone.utc).isoformat()
                    if story_path.exists():
                        stat = os.stat(story_path)
                        last_modified = datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat()
                    
                    story_metadata.append({
                        "id": story['directory_name'],
                        "displayName": story['name'],
                        "fullPath": story['path'],
                        "configPath": str(config_path),
                        "isValid": is_valid,
                        "chapters": chapters,
                        "lastModified": last_modified,
                        "hasAudioClips": has_audio
                    })
                
                # Sort results
                reverse = sortOrder.lower() == "desc"
                if sortBy == "lastModified":
                    story_metadata.sort(key=lambda x: x["lastModified"], reverse=reverse)
                elif sortBy == "displayName":
                    story_metadata.sort(key=lambda x: x["displayName"].lower(), reverse=reverse)
                else:  # default to name
                    story_metadata.sort(key=lambda x: x["displayName"].lower(), reverse=reverse)
                
                discovery_time = int((time.time() - start_time) * 1000)
                
                return {
                    "success": True,
                    "stories": story_metadata,
                    "totalCount": len(story_metadata),
                    "storiesDir": str(self.config_manager.get_stories_directory()),
                    "discoveryTime": discovery_time
                }
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/api/stories/{story_id}")
        async def get_story_detail(story_id: str):
            """Get detailed information about a specific story"""
            try:
                story_path = self._find_story_path(story_id)
                if not story_path:
                    raise HTTPException(status_code=404, detail=f"Story not found: {story_id}")
                
                # Load raw story config
                config_path = story_path / "story-config.yml"
                raw_config = None
                if config_path.exists():
                    with open(config_path, 'r') as f:
                        raw_config = yaml.safe_load(f)
                
                # Create story metadata
                story = self._create_story_metadata(story_path, story_id)
                
                # Get merged configuration
                merged_config = self._merge_story_config(story_path)
                
                return {
                    "success": True,
                    "story": story,
                    "rawConfig": raw_config,
                    "mergedConfig": merged_config
                }
            except Exception as e:
                if isinstance(e, HTTPException):
                    raise
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/api/stories/{story_id}/config")
        async def get_story_config(
            story_id: str,
            includeRaw: bool = False,
            includeGlobal: bool = False
        ):
            """Get merged configuration for a specific story"""
            try:
                story_path = self._find_story_path(story_id)
                if not story_path:
                    raise HTTPException(status_code=404, detail=f"Story not found: {story_id}")
                
                merged_config = self._merge_story_config(story_path)
                
                # Config sources info
                config_sources = {
                    "storyConfigPath": str(story_path / "story-config.yml"),
                    "globalConfigPath": str(self.config_manager._main_config_path),
                    "storyConfigExists": (story_path / "story-config.yml").exists(),
                    "globalConfigExists": self.config_manager._main_config_path.exists()
                }
                
                return {
                    "success": True,
                    "storyId": story_id,
                    "config": merged_config,
                    "configSources": config_sources
                }
            except Exception as e:
                if isinstance(e, HTTPException):
                    raise
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/api/stories/{story_id}/chapters")
        async def get_story_chapters(
            story_id: str,
            includeAudio: bool = True,
            format: str = "detailed"
        ):
            """Get chapters for a specific story"""
            try:
                story_path = self._find_story_path(story_id)
                if not story_path:
                    raise HTTPException(status_code=404, detail=f"Story not found: {story_id}")
                
                chapters = self._discover_story_chapters(story_path, include_audio=includeAudio)
                chapters_dir = story_path / "story-chapters"
                
                return {
                    "success": True,
                    "storyId": story_id,
                    "chapters": chapters,
                    "chaptersDir": str(chapters_dir),
                    "totalChapters": len(chapters)
                }
            except Exception as e:
                if isinstance(e, HTTPException):
                    raise
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/api/stories/{story_id}/refresh")
        async def refresh_story(story_id: str):
            """Refresh cached metadata for a specific story"""
            try:
                start_time = time.time()
                story_path = self._find_story_path(story_id)
                if not story_path:
                    raise HTTPException(status_code=404, detail=f"Story not found: {story_id}")
                
                # Recreate story metadata (this refreshes cache)
                story = self._create_story_metadata(story_path, story_id)
                refresh_time = int((time.time() - start_time) * 1000)
                
                return {
                    "success": True,
                    "message": f"Story {story_id} refreshed successfully",
                    "story": story,
                    "refreshTime": refresh_time
                }
            except Exception as e:
                if isinstance(e, HTTPException):
                    raise
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/api/config/validate")
        async def validate_config(request: ValidationRequest):
            """Validate configuration files and story structure"""
            try:
                if request.type == "global":
                    return await validate_global_config(GlobalConfigRequest(config=request.config or {}))
                elif request.type == "story":
                    if not request.storyId:
                        raise HTTPException(status_code=400, detail="storyId required for story validation")
                    
                    story_path = self._find_story_path(request.storyId)
                    if not story_path:
                        raise HTTPException(status_code=404, detail=f"Story not found: {request.storyId}")
                    
                    return self._validate_story_config(story_path, strict=request.strict)
                elif request.type == "merged":
                    if not request.storyId:
                        raise HTTPException(status_code=400, detail="storyId required for merged validation")
                    
                    story_path = self._find_story_path(request.storyId)
                    if not story_path:
                        raise HTTPException(status_code=404, detail=f"Story not found: {request.storyId}")
                    
                    return self._validate_merged_config(story_path, strict=request.strict)
            except Exception as e:
                if isinstance(e, HTTPException):
                    raise
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/api/system/info")
        async def get_system_info():
            """Get system information and configuration status"""
            try:
                # Load global config to check status
                config_valid = True
                try:
                    self.config_manager.load_main_config()
                except:
                    config_valid = False
                
                stories_dir = self.config_manager.get_stories_directory()
                stories = self.config_manager.discover_stories()
                valid_stories = sum(1 for s in stories if self._validate_story_structure(Path(s['path'])))
                
                # Check permissions
                can_read_config = self.config_manager._main_config_path.exists() and os.access(self.config_manager._main_config_path, os.R_OK)
                can_write_config = os.access(self.config_manager._main_config_path.parent, os.W_OK)
                can_access_stories = stories_dir.exists() and os.access(stories_dir, os.R_OK)
                
                return {
                    "success": True,
                    "version": "1.0.0",
                    "configStatus": {
                        "globalConfigExists": self.config_manager._main_config_path.exists(),
                        "globalConfigValid": config_valid,
                        "storiesDir": str(stories_dir),
                        "storiesDiscovered": len(stories),
                        "validStories": valid_stories
                    },
                    "permissions": {
                        "canReadConfig": can_read_config,
                        "canWriteConfig": can_write_config,
                        "canAccessStoriesDir": can_access_stories
                    },
                    "paths": {
                        "globalConfigPath": str(self.config_manager._main_config_path),
                        "storiesDir": str(stories_dir),
                        "configDir": str(self.config_manager._main_config_path.parent)
                    }
                }
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/api/system/health")
        async def health_check():
            """Health check endpoint"""
            try:
                # Check global config
                global_config_check = "pass"
                try:
                    self.config_manager.load_main_config()
                except:
                    global_config_check = "fail"
                
                # Check stories directory
                stories_dir_check = "pass"
                try:
                    stories_dir = self.config_manager.get_stories_directory()
                    if not stories_dir.exists():
                        stories_dir_check = "fail"
                except:
                    stories_dir_check = "fail"
                
                # Check file permissions
                permissions_check = "pass"
                try:
                    if not os.access(self.config_manager._main_config_path.parent, os.W_OK):
                        permissions_check = "fail"
                except:
                    permissions_check = "fail"
                
                # Overall status
                checks_passed = sum(1 for c in [global_config_check, stories_dir_check, permissions_check] if c == "pass")
                if checks_passed == 3:
                    status = "healthy"
                elif checks_passed >= 2:
                    status = "warning"
                else:
                    status = "error"
                
                return {
                    "success": True,
                    "status": status,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "checks": {
                        "globalConfig": global_config_check,
                        "storiesDirectory": stories_dir_check,
                        "filePermissions": permissions_check
                    },
                    "uptime": int(time.time())  # Simple uptime placeholder
                }
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.websocket("/api/ws")
        async def websocket_endpoint(websocket: WebSocket):
            """WebSocket endpoint for real-time notifications"""
            await websocket.accept()
            self.websocket_connections.append(websocket)
            
            try:
                while True:
                    # Keep connection alive
                    await websocket.receive_text()
            except WebSocketDisconnect:
                self.websocket_connections.remove(websocket)
    
    def _find_story_path(self, story_id: str) -> Optional[Path]:
        """Find the path for a story by its ID"""
        try:
            stories = self.config_manager.discover_stories()
            for story in stories:
                if story['directory_name'] == story_id:
                    return Path(story['path'])
            return None
        except Exception:
            return None
    
    def _create_story_metadata(self, story_path: Path, story_id: str) -> Dict[str, Any]:
        """Create metadata for a story"""
        config_path = story_path / "story-config.yml"
        is_valid = self._validate_story_structure(story_path)
        chapters = self._discover_story_chapters(story_path)
        has_audio = self._check_story_audio(story_path)
        
        # Get last modified time
        last_modified = datetime.now(timezone.utc).isoformat()
        if story_path.exists():
            stat = os.stat(story_path)
            last_modified = datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat()
        
        return {
            "id": story_id,
            "displayName": story_id.replace(self.config_manager.get_story_prefix(), ""),
            "fullPath": str(story_path),
            "configPath": str(config_path),
            "isValid": is_valid,
            "chapters": chapters,
            "lastModified": last_modified,
            "hasAudioClips": has_audio
        }
    
    def _validate_story_structure(self, story_path: Path) -> bool:
        """Validate basic story structure"""
        try:
            config_path = story_path / "story-config.yml"
            return config_path.exists() and story_path.is_dir()
        except Exception:
            return False
    
    def _discover_story_chapters(self, story_path: Path, include_audio: bool = True) -> List[Dict[str, Any]]:
        """Discover chapters in a story directory"""
        chapters = []
        chapters_dir = story_path / "story-chapters"
        
        if not chapters_dir.exists():
            return chapters
        
        try:
            for chapter_file in sorted(chapters_dir.glob("*.md")):
                # Get display name (remove extension, clean up)
                display_name = chapter_file.stem.replace("-", " ").title()
                
                # Check for audio
                has_audio = False
                if include_audio:
                    audio_dir = story_path / "story-audio" / "clips" / chapter_file.stem
                    has_audio = audio_dir.exists() and any(audio_dir.glob("*.wav"))
                
                # Get XML path
                xml_path = None
                story_xml_dir = story_path / "story-xml"
                if story_xml_dir.exists():
                    xml_file = story_xml_dir / f"{chapter_file.stem}.xml"
                    if xml_file.exists():
                        xml_path = str(xml_file)
                
                # Get audio path
                audio_path = None
                if has_audio:
                    audio_path = str(story_path / "story-audio" / "clips" / chapter_file.stem)
                
                # Get last modified
                last_modified = datetime.fromtimestamp(
                    os.stat(chapter_file).st_mtime, timezone.utc
                ).isoformat()
                
                chapters.append({
                    "filename": chapter_file.name,
                    "displayName": display_name,
                    "fullPath": str(chapter_file),
                    "hasAudio": has_audio,
                    "xmlPath": xml_path,
                    "audioPath": audio_path,
                    "lastModified": last_modified
                })
        except Exception as e:
            print(f"Error discovering chapters: {e}")
        
        return chapters
    
    def _check_story_audio(self, story_path: Path) -> bool:
        """Check if story has generated audio clips"""
        try:
            audio_dir = story_path / "story-audio"
            if not audio_dir.exists():
                return False
            
            # Check for audio files
            return any(audio_dir.rglob("*.wav")) or any(audio_dir.rglob("*.mp3"))
        except Exception:
            return False
    
    def _merge_story_config(self, story_path: Path) -> Dict[str, Any]:
        """Merge story config with global defaults"""
        try:
            # Load global config
            global_config = self.config_manager.load_main_config()
            
            # Load story config
            story_config = None
            config_path = story_path / "story-config.yml"
            if config_path.exists():
                with open(config_path, 'r') as f:
                    story_config = yaml.safe_load(f)
            
            # Simple merge (story config overrides global defaults)
            merged = {}
            if story_config:
                merged = story_config.copy()
            
            # Apply global defaults if they exist
            global_defaults = global_config.get("FlexiTTS", {}).get("global_defaults", {})
            if global_defaults and "global" in merged:
                for key, value in global_defaults.items():
                    if key not in merged["global"]:
                        merged["global"][key] = value
            
            return {
                "source": "merged",
                "storyConfig": story_config,
                "globalConfig": global_config,
                "mergedValues": merged,
                "conflicts": []  # TODO: Implement conflict detection
            }
        except Exception as e:
            raise ValueError(f"Error merging configuration: {e}")
    
    def _validate_story_config(self, story_path: Path, strict: bool = False) -> Dict[str, Any]:
        """Validate story configuration"""
        try:
            config_path = story_path / "story-config.yml"
            if not config_path.exists():
                return {
                    "success": True,
                    "isValid": False,
                    "errors": [{
                        "field": "story-config.yml",
                        "message": "Story configuration file not found",
                        "code": "STORY_CONFIG_NOT_FOUND",
                        "severity": "error"
                    }],
                    "warnings": []
                }
            
            # Use existing validation if available
            is_valid = True
            errors = []
            warnings = []
            
            try:
                # Try to load and parse
                with open(config_path, 'r') as f:
                    config = yaml.safe_load(f)
                
                # Basic validation
                if not isinstance(config, dict):
                    errors.append({
                        "field": "root",
                        "message": "Configuration must be a dictionary/object",
                        "code": "VALIDATION_INVALID_TYPE",
                        "severity": "error"
                    })
                    is_valid = False
                
            except yaml.YAMLError as e:
                errors.append({
                    "field": "yaml",
                    "message": f"YAML parsing error: {e}",
                    "code": "GLOBAL_CONFIG_PARSE_ERROR",
                    "severity": "error"
                })
                is_valid = False
            
            return {
                "success": True,
                "isValid": is_valid,
                "errors": errors,
                "warnings": warnings
            }
        except Exception as e:
            raise ValueError(f"Error validating story config: {e}")
    
    def _validate_merged_config(self, story_path: Path, strict: bool = False) -> Dict[str, Any]:
        """Validate merged configuration"""
        try:
            merged = self._merge_story_config(story_path)
            return {
                "success": True,
                "isValid": True,
                "errors": [],
                "warnings": [],
                "validatedConfig": merged["mergedValues"]
            }
        except Exception as e:
            return {
                "success": True,
                "isValid": False,
                "errors": [{
                    "field": "merged",
                    "message": str(e),
                    "code": "VALIDATION_MERGE_ERROR",
                    "severity": "error"
                }],
                "warnings": []
            }
    
    async def _broadcast_config_change(self, config_type: str, config_path: str):
        """Broadcast configuration change to WebSocket clients"""
        message = {
            "type": f"config:{config_type}:changed",
            "data": {
                "configPath": config_path,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "changes": ["updated"]  # TODO: Track specific changes
            }
        }
        
        # Send to all connected WebSocket clients
        for websocket in self.websocket_connections[:]:  # Copy to avoid modification during iteration
            try:
                await websocket.send_text(json.dumps(message))
            except Exception:
                # Remove disconnected clients
                self.websocket_connections.remove(websocket)


def create_app() -> FastAPI:
    """Factory function to create FastAPI app"""
    api = FlexiTTSAPI()
    return api.app


if __name__ == "__main__":
    import uvicorn
    
    # Create the app
    app = create_app()
    
    # Run the server
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8000,
        log_level="info",
        reload=False
    )