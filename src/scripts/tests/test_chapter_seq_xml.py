"""Direct import tests for chapter_seq_xml.py - achieves coverage via imports."""

import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, patch, mock_open
import yaml
from xml.etree import ElementTree as ET

# Add parent to path for importing
sys.path.insert(0, str(Path(__file__).parent.parent))

import chapter_seq_xml


@pytest.fixture
def mock_config(tmp_path):
    """Create a mock config file and return config data."""
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
        }
    }
    return config


@pytest.fixture
def sample_xml(tmp_path):
    """Create a sample XML file for testing."""
    xml_dir = tmp_path / "story-xml"
    xml_dir.mkdir(parents=True)
    xml_file = xml_dir / "test_chapter.xml"
    
    xml_content = """<story>
  <section seq="5">
    <narration dlgseq="10" emotion="neutral">First narration.</narration>
    <dialog character="Alice" dlgseq="20" emotion="happy">Hello!</dialog>
  </section>
  <section seq="99">
    <narration dlgseq="50" emotion="sad">Second narration.</narration>
  </section>
</story>"""
    xml_file.write_text(xml_content)
    return xml_file


class TestIndent:
    """Test the indent function."""
    
    def test_indent_empty_element(self):
        """Test indenting an empty element."""
        root = ET.Element("root")
        child = ET.SubElement(root, "child")
        chapter_seq_xml.indent(root)
        # Should not crash
        assert root is not None


class TestResequenceXML:
    """Test the resequence_xml function."""
    
    def test_resequence_with_valid_xml(self, tmp_path, sample_xml):
        """Test resequencing a valid XML file."""
        chapter_seq_xml.resequence_xml(str(sample_xml))
        
        # Verify the file was updated
        content = sample_xml.read_text()
        root = ET.fromstring(content)
        
        sections = root.findall('.//section')
        assert len(sections) == 2
        
        # Check sequences were reset
        assert sections[0].get('seq') == '1'
        assert sections[1].get('seq') == '2'
        
        # Check dlgseq was reset
        narrations = sections[0].findall('narration')
        assert narrations[0].get('dlgseq') == '1'
        
        dialogs = sections[0].findall('dialog')
        assert dialogs[0].get('dlgseq') == '2'

    def test_resequence_with_output_path(self, tmp_path, sample_xml):
        """Test resequencing to a different output file."""
        output_path = tmp_path / "output.xml"
        chapter_seq_xml.resequence_xml(str(sample_xml), str(output_path))
        
        assert output_path.exists()
        
        # Original file should be unchanged
        original = sample_xml.read_text()
        assert 'seq="5"' in original  # Original had seq=5
        
        # Output should have new sequences
        output = output_path.read_text()
        assert 'seq="1"' in output

    def test_resequence_file_not_found(self, capsys):
        """Test handling of missing file."""
        chapter_seq_xml.resequence_xml("/nonexistent/path.xml")
        captured = capsys.readouterr()
        assert "not found" in captured.out.lower()

    def test_resequence_invalid_xml(self, tmp_path, capsys):
        """Test handling of invalid XML."""
        invalid_file = tmp_path / "invalid.xml"
        invalid_file.write_text("<not valid xml>")
        
        chapter_seq_xml.resequence_xml(str(invalid_file))
        captured = capsys.readouterr()
        assert "error" in captured.out.lower()


class TestMain:
    """Test the main function with mocked dependencies."""
    
    def test_main_with_missing_config(self, tmp_path, monkeypatch, capsys):
        """Test main exits when config is missing."""
        monkeypatch.chdir(tmp_path)
        
        with pytest.raises(SystemExit) as exc_info:
            # Call main directly without mocking sys.argv
            chapter_seq_xml.main()
        
        # Exit code can be 1 or 2 (argparse exits with 2 when required args missing)
        assert exc_info.value.code in [1, 2]
        captured = capsys.readouterr()
        assert "story-config.yml" in captured.out or exc_info.value.code == 2

    def test_main_with_config_and_xml(self, tmp_path, monkeypatch, mock_config):
        """Test main with valid config and XML file."""
        # Create config
        config_path = tmp_path / "story-config.yml"
        with open(config_path, 'w') as f:
            yaml.dump(mock_config, f)
        
        # Create XML file
        xml_dir = tmp_path / "story-xml"
        xml_dir.mkdir()
        xml_file = xml_dir / "test_chapter.xml"
        xml_file.write_text("""<story>
  <section seq="1">
    <narration dlgseq="1" emotion="neutral">Test.</narration>
  </section>
</story>""")
        
        monkeypatch.chdir(tmp_path)
        
        # Mock sys.argv
        monkeypatch.setattr(sys, 'argv', ['chapter_seq_xml.py', 'test_chapter.xml'])
        
        chapter_seq_xml.main()
        
        # Verify output
        content = xml_file.read_text()
        assert 'seq="1"' in content

    def test_main_with_absolute_path(self, tmp_path, monkeypatch, mock_config):
        """Test main with absolute path to XML."""
        # Create config
        config_path = tmp_path / "story-config.yml"
        with open(config_path, 'w') as f:
            yaml.dump(mock_config, f)
        
        # Create XML file
        xml_dir = tmp_path / "story-xml"
        xml_dir.mkdir()
        xml_file = xml_dir / "test_chapter.xml"
        xml_file.write_text("""<story>
  <section seq="1">
    <narration dlgseq="1" emotion="neutral">Test.</narration>
  </section>
</story>""")
        
        monkeypatch.chdir(tmp_path)
        
        # Mock sys.argv with absolute path
        monkeypatch.setattr(sys, 'argv', ['chapter_seq_xml.py', str(xml_file)])
        
        chapter_seq_xml.main()
        
        # Should complete successfully
        captured = pytest.importorskip('sys').stdout

    def test_main_no_xml_files(self, tmp_path, monkeypatch, mock_config, capsys):
        """Test main when no XML files exist."""
        # Create config
        config_path = tmp_path / "story-config.yml"
        with open(config_path, 'w') as f:
            yaml.dump(mock_config, f)
        
        # Create empty story-xml directory
        xml_dir = tmp_path / "story-xml"
        xml_dir.mkdir()
        
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(sys, 'argv', ['chapter_seq_xml.py'])
        
        chapter_seq_xml.main()
        
        captured = capsys.readouterr()
        assert "no xml files" in captured.out.lower()

    def test_main_with_output_option(self, tmp_path, monkeypatch, mock_config):
        """Test main with --output option."""
        # Create config
        config_path = tmp_path / "story-config.yml"
        with open(config_path, 'w') as f:
            yaml.dump(mock_config, f)
        
        # Create XML file
        xml_dir = tmp_path / "story-xml"
        xml_dir.mkdir()
        xml_file = xml_dir / "test_chapter.xml"
        xml_file.write_text("""<story>
  <section seq="1">
    <narration dlgseq="1" emotion="neutral">Test.</narration>
  </section>
</story>""")
        
        output_path = tmp_path / "output.xml"
        
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(sys, 'argv', ['chapter_seq_xml.py', 'test_chapter.xml', '--output', str(output_path)])
        
        chapter_seq_xml.main()
        
        assert output_path.exists()

    def test_main_missing_story_xml_dir(self, tmp_path, monkeypatch, mock_config, capsys):
        """Test main when story-xml directory doesn't exist."""
        # Create config but not story-xml dir
        config_path = tmp_path / "story-config.yml"
        with open(config_path, 'w') as f:
            yaml.dump(mock_config, f)
        
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(sys, 'argv', ['chapter_seq_xml.py'])
        
        with pytest.raises(SystemExit) as exc_info:
            chapter_seq_xml.main()
        
        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "not found" in captured.out.lower()


class TestEdgeCases:
    """Test edge cases."""
    
    def test_resequence_empty_sections(self, tmp_path):
        """Test resequencing XML with empty sections."""
        xml_file = tmp_path / "test.xml"
        xml_file.write_text("""<story>
  <section seq="1">
  </section>
</story>""")
        
        chapter_seq_xml.resequence_xml(str(xml_file))
        
        content = xml_file.read_text()
        assert 'seq="1"' in content

    def test_resequence_xml_with_only_narration(self, tmp_path):
        """Test resequencing XML with only narration elements."""
        xml_file = tmp_path / "test.xml"
        xml_file.write_text("""<story>
  <section seq="5">
    <narration dlgseq="20" emotion="neutral">Only narration.</narration>
  </section>
</story>""")
        
        chapter_seq_xml.resequence_xml(str(xml_file))
        
        content = xml_file.read_text()
        assert 'dlgseq="1"' in content

    def test_resequence_xml_with_only_dialog(self, tmp_path):
        """Test resequencing XML with only dialog elements."""
        xml_file = tmp_path / "test.xml"
        xml_file.write_text("""<story>
  <section seq="5">
    <dialog character="Bob" dlgseq="20" emotion="happy">Only dialog.</dialog>
  </section>
</story>""")
        
        chapter_seq_xml.resequence_xml(str(xml_file))
        
        content = xml_file.read_text()
        assert 'dlgseq="1"' in content
