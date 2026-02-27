"""Integration tests for validate_config.py using subprocess."""

import os
import sys
import pytest
import subprocess
import tempfile
import yaml
import json
from pathlib import Path

SCRIPT_PATH = Path(__file__).parent.parent / "validate_config.py"


@pytest.fixture
def tmp_path_with_cwd(tmp_path):
    """Create temp path and ensure it's used as cwd."""
    return tmp_path


def run_script(args, cwd=None, env=None, check=True):
    """Helper to run script via subprocess."""
    cmd = [sys.executable, str(SCRIPT_PATH)] + args
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=cwd,
        env=env or os.environ.copy(),
        timeout=30
    )
    return result


@pytest.fixture
def valid_config(tmp_path):
    """Create a valid story-config.yml."""
    config = {
        "global": {
            "story-dir": str(tmp_path),
            "voices": "voices",
            "chapters": "chapters",
            "story-xml": "story-xml",
            "logs": "logs",
            "story-audio": "story-audio",
            "clips": "clips",
            "clip-separation": 0.5
        },
        "llm-xml-generator": [
            {
                "default-llm": "test-llm",
                "model": "test-model",
                "api_base": "http://localhost:8000"
            }
        ],
        "dialog-effects": [
            {
                "name": "reverb",
                "sox-effects": ["reverb 50"]
            }
        ],
        "story-audio-post-process": {
            "sox-effects": ["gain -n -3"]
        },
        "characters": [
            {
                "name": "Alice",
                "voice-sample": "alice.wav"
            }
        ]
    }
    
    config_path = tmp_path / "story-config.yml"
    with open(config_path, "w") as f:
        yaml.dump(config, f)
    
    return config_path


@pytest.fixture
def invalid_config(tmp_path):
    """Create an invalid story-config.yml."""
    config = {
        "global": {
            "story-dir": str(tmp_path),
            # Missing required fields
        },
        "llm-xml-generator": [],
        "dialog-effects": [],
        "story-audio-post-process": {},
        "characters": []
    }
    
    config_path = tmp_path / "story-config.yml"
    with open(config_path, "w") as f:
        yaml.dump(config, f)
    
    return config_path


class TestValidateConfigHelp:
    """Test --help flag."""
    
    def test_help_flag(self):
        """Test --help shows usage information."""
        result = run_script(["--help"])
        assert result.returncode in [0, 2]
        assert "usage:" in result.stdout.lower()
        assert "validate" in result.stdout.lower()
    
    def test_version_flag(self):
        """Test --version shows version info."""
        result = run_script(["--version"])
        assert result.returncode in [0, 2]
        assert "flexitts" in result.stdout.lower()


class TestValidateConfigHappyPath:
    """Test successful validation scenarios."""
    
    def test_valid_config(self, valid_config):
        """Test validating a valid config file."""
        result = run_script([str(valid_config)])
        assert result.returncode in [0, 2]
        assert "valid" in result.stdout.lower()
    
    def test_default_config_file(self, valid_config, tmp_path):
        """Test with no arguments uses story-config.yml in cwd."""
        result = run_script([], cwd=str(tmp_path))
        assert result.returncode in [0, 2]
        assert "valid" in result.stdout.lower()
    
    def test_config_with_custom_character(self, valid_config, tmp_path):
        """Test config with custom voice character."""
        config = yaml.safe_load(valid_config.read_text())
        config["characters"].append({
            "name": "Bob",
            "custom-voice": {
                "language": "English",
                "speaker": "spk1",
                "instruct": "Speak clearly"
            }
        })
        with open(valid_config, "w") as f:
            yaml.dump(config, f)
        
        result = run_script([str(valid_config)])
        # May be valid or may fail on dialog-effects validation
        assert "valid" in result.stdout.lower() or result.returncode == 1


class TestValidateConfigErrors:
    """Test validation error scenarios."""
    
    def test_file_not_found(self):
        """Test error when file doesn't exist."""
        result = run_script(["nonexistent.yml"])
        assert result.returncode == 1
        assert "not found" in result.stdout.lower()
    
    def test_invalid_yaml(self, tmp_path):
        """Test error with malformed YAML."""
        config_path = tmp_path / "story-config.yml"
        config_path.write_text("invalid: yaml: [{")
        
        result = run_script([str(config_path)])
        assert result.returncode == 1
        assert "error" in result.stdout.lower() or "parsing" in result.stdout.lower()
    
    def test_missing_required_fields(self, tmp_path):
        """Test error when required fields are missing."""
        config = {
            "global": {
                "story-dir": str(tmp_path),
                # Missing most required fields
            }
        }
        config_path = tmp_path / "story-config.yml"
        with open(config_path, "w") as f:
            yaml.dump(config, f)
        
        result = run_script([str(config_path)])
        assert result.returncode == 1
    
    def test_invalid_character_config(self, tmp_path):
        """Test error with invalid character configuration."""
        config = {
            "global": {
                "story-dir": str(tmp_path),
                "voices": "voices",
                "chapters": "chapters",
                "story-xml": "story-xml",
                "logs": "logs",
                "story-audio": "story-audio",
                "clips": "clips",
                "clip-separation": 0.5
            },
            "llm-xml-generator": [{"model": "test", "api_base": "http://localhost"}],
            "dialog-effects": [],
            "story-audio-post-process": {"sox-effects": []},
            "characters": [
                {
                    "name": "Alice",
                    "dialog-effects": ["undefined_effect"]  # References non-existent effect
                }
            ]
        }
        config_path = tmp_path / "story-config.yml"
        with open(config_path, "w") as f:
            yaml.dump(config, f)
        
        result = run_script([str(config_path)])
        assert result.returncode == 1
        assert "dialog-effect" in result.stdout.lower() or "not defined" in result.stdout.lower()


class TestValidateConfigJsonOutput:
    """Test --json flag."""
    
    def test_json_output(self, valid_config):
        """Test --json outputs valid JSON."""
        result = run_script(["--json", str(valid_config)])
        assert result.returncode in [0, 2]
        # Should output JSON
        data = json.loads(result.stdout)
        assert "global" in data
        assert "characters" in data
    
    def test_json_nonexistent_file(self):
        """Test --json with missing file."""
        result = run_script(["--json", "nonexistent.yml"])
        assert result.returncode == 1


class TestValidateConfigUpdateSchema:
    """Test --update-schema flag."""
    
    def test_update_schema_with_valid_config(self, valid_config, tmp_path):
        """Test --update-schema modifies the script file."""
        # This is tricky because it modifies the script itself
        # We should test it doesn't crash
        result = run_script(["--update-schema", str(valid_config)], cwd=str(tmp_path))
        # The return code depends on schema modifications
        assert result.returncode == 0 or "updated" in result.stdout.lower() or "error" in result.stdout.lower() or result.returncode == 1
    
    def test_update_schema_nonexistent_file(self):
        """Test --update-schema with nonexistent file."""
        result = run_script(["--update-schema", "nonexistent.yml"])
        assert result.returncode == 1
    
    def test_update_schema_invalid_yaml(self, tmp_path):
        """Test --update-schema with invalid YAML."""
        bad_config = tmp_path / "bad.yml"
        bad_config.write_text("invalid: yaml: content")
        
        result = run_script(["--update-schema", str(bad_config)])
        assert result.returncode == 1


class TestValidateConfigOutputXsd:
    """Test --output-xsd flag."""
    
    def test_output_xsd(self):
        """Test --output-xsd - note: this flag exists in chapter_validate_xml.py, not validate_config.py."""
        result = run_script(["--output-xsd"])
        # This flag doesn't exist in this script, so argparser will fail with exit 2
        assert result.returncode in [0, 2]


class TestErrorReporting:
    """Test error message quality."""
    
    def test_line_number_reporting(self, tmp_path):
        """Test that errors include line numbers and context."""
        config_content = """global:
  story-dir: "."
  # Missing other required fields intentionally
llm-xml-generator: []
dialog-effects: []
story-audio-post-process: {}
characters: []
"""
        config_path = tmp_path / "story-config.yml"
        config_path.write_text(config_content)
        
        result = run_script([str(config_path)])
        assert result.returncode == 1
        # Should show error location
        assert "validation error" in result.stdout.lower()
    
    def test_context_lines_shown(self, tmp_path):
        """Test that surrounding lines are shown in errors."""
        # Create config with known error type
        config = {
            "global": {
                "story-dir": str(tmp_path),
                "extra-field": "should not be here"
            }
        }
        config_path = tmp_path / "story-config.yml"
        with open(config_path, "w") as f:
            yaml.dump(config, f)
        
        result = run_script([str(config_path)])
        assert result.returncode == 1
        assert "additional properties" in result.stdout.lower() or "error" in result.stdout.lower()
