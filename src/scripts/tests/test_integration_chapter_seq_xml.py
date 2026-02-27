"""Integration tests for chapter_seq_xml.py using subprocess."""

import os
import sys
import pytest
import subprocess
import tempfile
import yaml
from pathlib import Path
from unittest.mock import Mock, patch

SCRIPT_PATH = Path(__file__).parent.parent / "chapter_seq_xml.py"


@pytest.fixture
def mock_env(tmp_path):
    """Create mock environment with story-config.yml and directories."""
    # Create story-config.yml
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
                "api_base": "http://localhost:8000",
                "api_key": "test-key"
            }
        ],
        "dialog-effects": [],
        "story-audio-post-process": {"sox-effects": []},
        "characters": []
    }
    
    config_path = tmp_path / "story-config.yml"
    with open(config_path, "w") as f:
        yaml.dump(config, f)
    
    # Create story-xml directory
    xml_dir = tmp_path / "story-xml"
    xml_dir.mkdir()
    
    # Create a valid XML file
    xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<story>
  <section seq="1">
    <narration dlgseq="1" emotion="neutral">This is a test narration.</narration>
    <dialog character="Alice" dlgseq="2" emotion="happy">Hello there!</dialog>
  </section>
  <section seq="2">
    <narration dlgseq="1" emotion="sad">Another narration.</narration>
  </section>
</story>
"""
    xml_file = xml_dir / "test_chapter.xml"
    with open(xml_file, "w") as f:
        f.write(xml_content)
    
    return {
        "tmp_path": tmp_path,
        "xml_dir": xml_dir,
        "xml_file": xml_file,
        "config_path": config_path
    }


def run_script(args, cwd=None, env=None):
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


class TestChapterSeqXMLHelp:
    """Test --help flag."""
    
    def test_help_flag(self):
        """Test --help shows usage information."""
        result = run_script(["--help"])
        assert result.returncode == 0
        assert "usage:" in result.stdout.lower()
        assert "re-sequence xml" in result.stdout.lower()
        assert "--output" in result.stdout


class TestChapterSeqXMLErrors:
    """Test error conditions."""
    
    def test_no_config_file(self, tmp_path):
        """Test error when story-config.yml not found."""
        result = run_script(["test.xml"], cwd=str(tmp_path))
        assert result.returncode == 1
        assert "story-config.yml" in result.stderr or "story-config.yml" in result.stdout
    
    def test_missing_xml_file(self, mock_env):
        """Test error when XML file not found."""
        result = run_script(["nonexistent.xml"], cwd=str(mock_env["tmp_path"]))
        assert result.returncode == 1
    
    def test_invalid_xml_file(self, mock_env):
        """Test error with malformed XML."""
        xml_file = mock_env["xml_dir"] / "invalid.xml"
        xml_file.write_text("<not valid xml>")
        
        result = run_script(["invalid.xml"], cwd=str(mock_env["tmp_path"]))
        # Should print error but not crash
        assert "error" in result.stdout.lower() or result.returncode == 1


class TestChapterSeqXMLHappyPath:
    """Test successful execution paths."""
    
    def test_resequence_xml_inplace(self, mock_env):
        """Test resequencing XML file in place."""
        result = run_script(["test_chapter.xml"], cwd=str(mock_env["tmp_path"]))
        assert result.returncode == 0
        assert "successfully" in result.stdout.lower()
        
        # Verify XML was updated
        content = mock_env["xml_file"].read_text()
        assert 'seq="1"' in content
        assert 'dlgseq="1"' in content
        assert 'dlgseq="2"' in content
    
    def test_resequence_xml_with_output(self, mock_env):
        """Test resequencing with explicit output file."""
        output_path = mock_env["tmp_path"] / "output.xml"
        result = run_script(
            ["test_chapter.xml", "--output", str(output_path)],
            cwd=str(mock_env["tmp_path"])
        )
        assert result.returncode == 0
        assert output_path.exists()
        
        # Verify output file has correct structure
        content = output_path.read_text()
        assert 'seq="1"' in content
    
    def test_resequence_by_absolute_path(self, mock_env):
        """Test with absolute path to XML file."""
        result = run_script([str(mock_env["xml_file"])], cwd=str(mock_env["tmp_path"]))
        assert result.returncode == 0
        assert "successfully" in result.stdout.lower()
    
    def test_no_arguments_uses_first_xml(self, mock_env):
        """Test running with no arguments finds first XML in story-xml."""
        result = run_script([], cwd=str(mock_env["tmp_path"]))
        assert result.returncode == 0
        assert "test_chapter.xml" in result.stdout


class TestChapterSeqXMLLogic:
    """Test the actual resequencing logic."""
    
    def test_correct_sequence_assignment(self, mock_env):
        """Test that sections and dialogs get correct sequence numbers."""
        # Create XML with out-of-order sequences
        xml_content = """<story>
  <section seq="5">
    <narration dlgseq="10" emotion="neutral">First</narration>
    <dialog character="Bob" dlgseq="20" emotion="angry">Second</dialog>
  </section>
  <section seq="99">
    <narration dlgseq="50" emotion="happy">Third</narration>
  </section>
</story>
"""
        mock_env["xml_file"].write_text(xml_content)
        
        result = run_script(["test_chapter.xml"], cwd=str(mock_env["tmp_path"]))
        assert result.returncode == 0
        
        content = mock_env["xml_file"].read_text()
        # Check sequences were renumbered starting from 1
        assert '<section seq="1">' in content
        assert '<section seq="2">' in content
        assert '<narration dlgseq="1"' in content  # First narration in section 1
        assert 'dlgseq="2"' in content  # Dialog in section 1 is second element
        assert 'emotion="angry"' in content


class TestEdgeCases:
    """Test edge cases."""
    
    def test_empty_story_xml_dir(self, mock_env):
        """Test behavior when story-xml directory is empty."""
        # Remove all XML files
        for f in mock_env["xml_dir"].glob("*.xml"):
            f.unlink()
        
        result = run_script([], cwd=str(mock_env["tmp_path"]))
        # Should gracefully handle no XML files found
        assert "no xml files" in result.stdout.lower() or result.returncode == 0
    
    def test_nonexistent_story_xml_dir(self, mock_env):
        """Test when story-xml directory doesn't exist."""
        import shutil
        shutil.rmtree(mock_env["xml_dir"])
        
        result = run_script([], cwd=str(mock_env["tmp_path"]))
        assert result.returncode == 1
        assert "not found" in result.stdout.lower() or "not found" in result.stderr.lower()
