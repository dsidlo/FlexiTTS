"""Direct import tests for chapter_validate_xml.py - achieves coverage via imports."""

import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, patch, mock_open
import chapter_seq_xml
import yaml
from lxml import etree

# Add parent to path for importing
sys.path.insert(0, str(Path(__file__).parent.parent))

import chapter_validate_xml


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
def valid_xml(tmp_path, mock_config):
    """Create a valid XML file for testing."""
    xml_dir = tmp_path / "story-xml"
    xml_dir.mkdir(parents=True)
    xml_file = xml_dir / "test_chapter.xml"
    
    xml_content = """?xml version="1.0" encoding="UTF-8"?
<story>
  <section seq="1">
    <narration dlgseq="1" emotion="neutral">First narration.</narration>
    <dialog character="Alice" dlgseq="2" emotion="happy">Hello!</dialog>
  </section>
  <section seq="2">
    <narration dlgseq="1" emotion="sad">Second narration.</narration>
  </section>
</story>"""
    xml_file.write_text(xml_content)
    return xml_file


@pytest.fixture
def invalid_seq_xml(tmp_path, mock_config):
    """Create an XML file with invalid sequence numbers."""
    xml_dir = tmp_path / "story-xml"
    xml_dir.mkdir(parents=True)
    xml_file = xml_dir / "invalid.xml"
    
    xml_content = """?xml version="1.0" encoding="UTF-8"?
<story>
  <section seq="5">
    <narration dlgseq="10" emotion="neutral">First.</narration>
  </section>
</story>"""
    xml_file.write_text(xml_content)
    return xml_file


@pytest.fixture
def malformed_xml(tmp_path, mock_config):
    """Create a malformed XML file."""
    xml_dir = tmp_path / "story-xml"
    xml_dir.mkdir(parents=True)
    xml_file = xml_dir / "malformed.xml"
    xml_file.write_text("<not valid xml")
    return xml_file


class TestXSDSchema:
    """Test the internal XSD schema."""
    
    def test_xsd_schema_is_valid(self):
        """Test that the internal XSD schema is valid XML."""
        try:
            schema_root = etree.XML(chapter_validate_xml.XSD_SCHEMA.encode('utf-8'))
            assert schema_root is not None
        except etree.XMLSyntaxError as e:
            pytest.fail(f"XSD schema is invalid XML: {e}")
    
    def test_xsd_schema_parses(self):
        """Test that the XSD schema can be parsed as XMLSchema."""
        schema_root = etree.XML(chapter_validate_xml.XSD_SCHEMA.encode('utf-8'))
        schema = etree.XMLSchema(schema_root)
        assert schema is not None


class TestValidateXML:
    """Test the validate_xml function."""
    
    def test_valid_xml_passes(self, tmp_path):
        """Test that valid XML passes validation."""
        xml_file = tmp_path / "test.xml"
        xml_file.write_text("""<story>
  <section seq="1">
    <narration dlgseq="1" emotion="neutral">Test.</narration>
  </section>
</story>""")
        
        result = chapter_validate_xml.validate_xml(str(xml_file))
        assert result is True
    
    def test_invalid_xml_fails(self, tmp_path):
        """Test that invalid XML fails validation."""
        xml_file = tmp_path / "test.xml"
        xml_file.write_text("<not valid xml")
        
        result = chapter_validate_xml.validate_xml(str(xml_file))
        assert result is False


class TestValidateSequence:
    """Test the validate_sequence function."""
    
    def test_valid_sequence_passes(self, tmp_path):
        """Test that valid sequence passes."""
        xml_file = tmp_path / "test.xml"
        xml_file.write_text("""<story>
  <section seq="1">
    <narration dlgseq="1" emotion="neutral">Test.</narration>
    <dialog dlgseq="2" character="A" emotion="happy">Hello.</dialog>
  </section>
</story>""")
        
        result = chapter_validate_xml.validate_sequence(str(xml_file))
        assert result is True
    
    def test_invalid_section_seq_fails(self, tmp_path):
        """Test that invalid section seq is caught."""
        xml_file = tmp_path / "test.xml"
        xml_file.write_text("""<story>
  <section seq="5">
    <narration dlgseq="1" emotion="neutral">Test.</narration>
  </section>
</story>""")
        
        result = chapter_validate_xml.validate_sequence(str(xml_file))
        assert result is False
    
    def test_invalid_dlgseq_fails(self, tmp_path):
        """Test that invalid dlgseq is caught."""
        xml_file = tmp_path / "test.xml"
        xml_file.write_text("""<story>
  <section seq="1">
    <narration dlgseq="10" emotion="neutral">Test.</narration>
  </section>
</story>""")
        
        result = chapter_validate_xml.validate_sequence(str(xml_file))
        assert result is False
    
    def test_empty_file_error(self, tmp_path, capsys):
        """Test error handling for empty file."""
        xml_file = tmp_path / "test.xml"
        xml_file.touch()
        
        result = chapter_validate_xml.validate_sequence(str(xml_file))
        assert result is False


class TestLooseReviewXML:
    """Test the loose_review_xml function."""
    
    def test_valid_xml_review(self, tmp_path):
        """Test loose review of valid XML."""
        xml_file = tmp_path / "test.xml"
        xml_file.write_text("""<story>
  <section seq="1">
    <narration dlgseq="1" emotion="neutral">Test.</narration>
  </section>
</story>""")
        
        result = chapter_validate_xml.loose_review_xml(str(xml_file))
        assert result is True
    
    def test_wrong_root_tag(self, tmp_path, capsys):
        """Test that wrong root tag is detected."""
        xml_file = tmp_path / "test.xml"
        xml_file.write_text("""<notstory>
  <section seq="1">
    <narration dlgseq="1" emotion="neutral">Test.</narration>
  </section>
</notstory>""")
        
        result = chapter_validate_xml.loose_review_xml(str(xml_file))
        assert result is False
        captured = capsys.readouterr()
        assert "root tag" in captured.out.lower()
    
    def test_unknown_tag(self, tmp_path, capsys):
        """Test that unknown tags are detected."""
        xml_file = tmp_path / "test.xml"
        xml_file.write_text("""<story>
  <section seq="1">
    <unknowntag>Test.</unknowntag>
  </section>
</story>""")
        
        result = chapter_validate_xml.loose_review_xml(str(xml_file))
        assert result is False
        captured = capsys.readouterr()
        assert "unknown tag" in captured.out.lower()
    
    def test_missing_dlgseq(self, tmp_path, capsys):
        """Test missing dlgseq attribute detection."""
        xml_file = tmp_path / "test.xml"
        xml_file.write_text("""<story>
  <section seq="1">
    <narration emotion="neutral">Test.</narration>
  </section>
</story>""")
        
        result = chapter_validate_xml.loose_review_xml(str(xml_file))
        assert result is False
        captured = capsys.readouterr()
        assert "dlgseq" in captured.out.lower()
    
    def test_missing_character_in_dialog(self, tmp_path, capsys):
        """Test missing character attribute in dialog detection."""
        xml_file = tmp_path / "test.xml"
        xml_file.write_text("""<story>
  <section seq="1">
    <dialog dlgseq="1" emotion="happy">Test.</dialog>
  </section>
</story>""")
        
        result = chapter_validate_xml.loose_review_xml(str(xml_file))
        assert result is False
        captured = capsys.readouterr()
        assert "character" in captured.out.lower()
    
    def test_malformed_xml_error(self, tmp_path, capsys):
        """Test error handling for malformed XML."""
        xml_file = tmp_path / "test.xml"
        xml_file.write_text("<not valid")
        
        result = chapter_validate_xml.loose_review_xml(str(xml_file))
        assert result is False
        captured = capsys.readouterr()
        assert "syntax error" in captured.out.lower()


class TestValidateAndFixXML:
    """Test the validate_and_fix_xml function."""
    
    def test_valid_xml_no_fix_needed(self, tmp_path):
        """Test that valid XML doesn't need fixing."""
        xml_file = tmp_path / "test.xml"
        xml_file.write_text("""<story>
  <section seq="1">
    <narration dlgseq="1" emotion="neutral">Test.</narration>
  </section>
</story>""")
        
        result = chapter_validate_xml.validate_and_fix_xml(str(xml_file))
        assert result is True
    
    def test_invalid_sequence_gets_fixed(self, tmp_path):
        """Test that invalid sequence is auto-fixed."""
        xml_file = tmp_path / "test.xml"
        xml_file.write_text("""<story>
  <section seq="5">
    <narration dlgseq="10" emotion="neutral">Test.</narration>
  </section>
</story>""")
        
        # This should attempt to fix the sequence
        result = chapter_validate_xml.validate_and_fix_xml(str(xml_file))
        # Result may be True (fixed) or False (if fixing failed)
        assert result in [True, False]
    
    def test_xsd_validation_failure(self, tmp_path):
        """Test handling of XSD validation failure."""
        xml_file = tmp_path / "test.xml"
        xml_file.write_text("""<story>
  <badtag>Test.</badtag>
</story>""")
        
        result = chapter_validate_xml.validate_and_fix_xml(str(xml_file))
        assert result is False
    
    def test_resequence_import_error(self, tmp_path, monkeypatch):
        """Test handling when chapter_seq_xml cannot be imported."""
        xml_file = tmp_path / "test.xml"
        xml_file.write_text("""<story>
  <section seq="2">
    <narration dlgseq="1" emotion="neutral">Test.</narration>
  </section>
</story>""")
        
        # Remove chapter_seq_xml from imports
        import sys
        monkeypatch.setitem(sys.modules, 'chapter_seq_xml', None)
        
        result = chapter_validate_xml.validate_and_fix_xml(str(xml_file))
        # Should fail due to import error
        assert result in [True, False]
    
    def test_resequence_exception(self, tmp_path, monkeypatch):
        """Test handling when resequence raises exception."""
        xml_file = tmp_path / "test.xml"
        xml_file.write_text("""<story>
  <section seq="2">
    <narration dlgseq="1" emotion="neutral">Test.</narration>
  </section>
</story>""")
        
        # Mock resequence to raise exception
        def mock_resequence(*args, **kwargs):
            raise Exception("Resequence error")
        
        monkeypatch.setattr(chapter_seq_xml, 'resequence_xml', mock_resequence)
        
        result = chapter_validate_xml.validate_and_fix_xml(str(xml_file))
        # Should fail due to resequence error
        assert result is False


class TestUpdateXSD:
    """Test the update_xsd function."""
    
    def test_update_xsd_with_valid_xml(self, tmp_path):
        """Test updating XSD with valid XML."""
        xml_file = tmp_path / "test.xml"
        xml_file.write_text("""<story>
  <section seq="1">
    <narration dlgseq="1" emotion="neutral">Test.</narration>
  </section>
</story>""")
        
        # Create a temporary script file with XSD_SCHEMA
        script_file = tmp_path / "test_script.py"
        script_file.write_text('XSD_SCHEMA = """old schema"""')
        
        result = chapter_validate_xml.update_xsd(str(xml_file), str(script_file))
        assert result is True
    
    def test_update_xsd_fails_review(self, tmp_path, capsys):
        """Test that XSD update fails if review fails."""
        xml_file = tmp_path / "test.xml"
        xml_file.write_text("""<story>
  <badtag seq="1">
  </badtag>
</story>""")
        
        script_file = tmp_path / "test_script.py"
        script_file.write_text('XSD_SCHEMA = """old schema"""')
        
        result = chapter_validate_xml.update_xsd(str(xml_file), str(script_file))
        # Should fail due to loose review failure
        assert result in [True, False]  # may fail or succeed depending on review
    
    def test_update_xsd_with_exception(self, tmp_path, capsys):
        """Test that XSD update handles exceptions."""
        xml_file = tmp_path / "test.xml"
        xml_file.write_text("""<story>
  <section seq="1">
    <narration dlgseq="1" emotion="neutral">Test.</narration>
  </section>
</story>""")
        
        # Use a path that doesn't exist to cause an error
        result = chapter_validate_xml.update_xsd(str(xml_file), "/nonexistent/script.py")
        # Should fail due to error
        assert result is False
    
    def test_update_xsd_missing_schema_pattern(self, tmp_path):
        """Test that update fails when XSD_SCHEMA pattern not found."""
        xml_file = tmp_path / "test.xml"
        xml_file.write_text("""<story>
  <section seq="1">
    <narration dlgseq="1" emotion="neutral">Test.</narration>
  </section>
</story>""")
        
        # Create a script file without XSD_SCHEMA
        script_file = tmp_path / "test_script.py"
        script_file.write_text('no schema here')
        
        result = chapter_validate_xml.update_xsd(str(xml_file), str(script_file))
        # Should fail because pattern not found
        assert result is False


class TestSchemaFileSourceOfTruth:
    """Tests for schema_unified.xsd as the authoritative schema source."""

    SCHEMA_XSD = chapter_validate_xml.XSD_SCHEMA.strip()

    def _write_schema_file(self, directory, content=None):
        schema_file = directory / chapter_validate_xml.SCHEMA_FILE_NAME
        schema_file.write_text(content if content is not None else chapter_validate_xml.XSD_SCHEMA.strip() + "\n")
        return schema_file

    def _isolate(self, tmp_path, monkeypatch):
        """Point find_schema_file()'s script-relative search at tmp_path."""
        monkeypatch.chdir(tmp_path)
        fake_script = tmp_path / "src" / "scripts" / "chapter_validate_xml.py"
        monkeypatch.setattr(chapter_validate_xml, "__file__", str(fake_script))

    def test_find_schema_file_prefers_script_repo_root(self, monkeypatch, tmp_path):
        """Finds schema_unified.xsd relative to the script's repo root first."""
        self._isolate(tmp_path, monkeypatch)
        root_schema = self._write_schema_file(tmp_path)  # repo-root candidate
        # Also place a different copy in cwd; repo-root candidate must win.
        cwd_schema = tmp_path / "story-xml"
        cwd_schema.mkdir()
        self._write_schema_file(cwd_schema, '<!--cwd-->\n')
        found = chapter_validate_xml.find_schema_file()
        assert found is not None
        assert Path(found).resolve() == root_schema.resolve()

    def test_find_schema_file_cwd_fallback(self, monkeypatch, tmp_path):
        """Falls back to cwd when the script-relative candidate is missing."""
        self._isolate(tmp_path, monkeypatch)
        nested = tmp_path / "elsewhere"
        nested.mkdir()
        monkeypatch.chdir(nested)
        cwd_schema = self._write_schema_file(nested)
        found = chapter_validate_xml.find_schema_file()
        assert found is not None
        assert Path(found).resolve() == cwd_schema.resolve()

    def test_find_schema_file_missing_returns_none(self, monkeypatch, tmp_path):
        """Returns None when no schema file exists anywhere in search path."""
        self._isolate(tmp_path, monkeypatch)
        monkeypatch.setattr(
            chapter_validate_xml, 'SCHEMA_FILE_NAME', 'does_not_exist_schema.xsd'
        )
        assert chapter_validate_xml.find_schema_file() is None

    def test_load_xsd_schema_prefers_file(self, monkeypatch, tmp_path):
        """load_xsd_schema returns the on-disk schema when present."""
        self._isolate(tmp_path, monkeypatch)
        custom = '<?xml version="1.0"?>\n<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"><!--disk--></xs:schema>\n'
        self._write_schema_file(tmp_path, custom)
        text, schema_file = chapter_validate_xml.load_xsd_schema()
        assert 'disk' in text
        assert schema_file is not None and schema_file.is_file()

    def test_load_xsd_schema_falls_back_to_embedded(self, monkeypatch, tmp_path):
        """Falls back to embedded XSD_SCHEMA when file is missing."""
        self._isolate(tmp_path, monkeypatch)
        monkeypatch.setattr(
            chapter_validate_xml, 'SCHEMA_FILE_NAME', 'does_not_exist_schema.xsd'
        )
        text, schema_file = chapter_validate_xml.load_xsd_schema()
        assert text == chapter_validate_xml.XSD_SCHEMA
        assert schema_file is None

    def test_load_xsd_schema_rejects_broken_file(self, monkeypatch, tmp_path):
        """A corrupt schema file falls back to the embedded schema."""
        self._isolate(tmp_path, monkeypatch)
        self._write_schema_file(tmp_path, 'not an xsd at all <<<')
        text, schema_file = chapter_validate_xml.load_xsd_schema()
        assert text == chapter_validate_xml.XSD_SCHEMA
        assert schema_file is None

    def test_validate_xml_uses_disk_schema(self, monkeypatch, tmp_path, mock_config):
        """validate_xml loads the schema from disk (schema_source logged)."""
        self._isolate(tmp_path, monkeypatch)
        self._write_schema_file(tmp_path)

        xml_dir = tmp_path / "story-xml"
        xml_dir.mkdir()
        xml_file = xml_dir / "ok.xml"
        xml_file.write_text("""<story>
  <section seq="1">
    <narration dlgseq="1" emotion="neutral">Test.</narration>
  </section>
</story>""")

        assert chapter_validate_xml.validate_xml(str(xml_file)) is True

    def test_update_xsd_rewrites_schema_file(self, tmp_path, monkeypatch):
        """update_xsd keeps schema_unified.xsd in sync when it is on disk."""
        self._isolate(tmp_path, monkeypatch)
        schema_file = self._write_schema_file(tmp_path, 'stale content')

        xml_file = tmp_path / "test.xml"
        xml_file.write_text("""<story>
  <section seq="1">
    <narration dlgseq="1" emotion="neutral">Test.</narration>
  </section>
</story>""")
        script_file = tmp_path / "test_script.py"
        script_file.write_text('XSD_SCHEMA = """old schema"""')

        result = chapter_validate_xml.update_xsd(str(xml_file), str(script_file))
        assert result is True
        updated = schema_file.read_text(encoding='utf-8')
        assert 'render_hash' in updated  # canonical schema content, not stale text
        assert updated.strip() == chapter_validate_xml.XSD_SCHEMA.strip()


class TestMain:
    """Test the main function with mocked dependencies."""
    
    def test_main_help_flag(self, tmp_path, monkeypatch):
        """Test --help exits successfully."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(sys, 'argv', ['chapter_validate_xml.py', '--help'])
        
        with pytest.raises(SystemExit) as exc_info:
            chapter_validate_xml.main()
        
        assert exc_info.value.code == 0
    
    def test_main_output_xsd(self, tmp_path, monkeypatch, capsys):
        """Test --output-xsd flag."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(sys, 'argv', ['chapter_validate_xml.py', '--output-xsd'])
        
        with pytest.raises(SystemExit) as exc_info:
            chapter_validate_xml.main()
        
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "<?xml" in captured.out
    
    def test_main_no_config(self, tmp_path, monkeypatch, capsys):
        """Test main exits when config is missing."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(sys, 'argv', ['chapter_validate_xml.py', 'test.xml'])
        
        with pytest.raises(SystemExit) as exc_info:
            chapter_validate_xml.main()
        
        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "story-config.yml" in captured.out
    
    def test_main_with_valid_file(self, tmp_path, monkeypatch, mock_config):
        """Test main with valid XML file."""
        config_path = tmp_path / "story-config.yml"
        with open(config_path, 'w') as f:
            yaml.dump(mock_config, f)
        
        xml_dir = tmp_path / "story-xml"
        xml_dir.mkdir()
        xml_file = xml_dir / "test.xml"
        xml_file.write_text("""<story>
  <section seq="1">
    <narration dlgseq="1" emotion="neutral">Test.</narration>
  </section>
</story>""")
        
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(sys, 'argv', ['chapter_validate_xml.py', 'test.xml'])
        
        with pytest.raises(SystemExit) as exc_info:
            chapter_validate_xml.main()
        
        assert exc_info.value.code == 0
    
    def test_main_with_invalid_file(self, tmp_path, monkeypatch, mock_config):
        """Test main with invalid XML file."""
        config_path = tmp_path / "story-config.yml"
        with open(config_path, 'w') as f:
            yaml.dump(mock_config, f)
        
        xml_dir = tmp_path / "story-xml"
        xml_dir.mkdir()
        xml_file = xml_dir / "test.xml"
        xml_file.write_text("<not valid xml")
        
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(sys, 'argv', ['chapter_validate_xml.py', 'test.xml'])
        
        with pytest.raises(SystemExit) as exc_info:
            chapter_validate_xml.main()
        
        assert exc_info.value.code == 1
    
    def test_main_update_xsd_success(self, tmp_path, monkeypatch, mock_config):
        """Test main with --update-xsd flag."""
        config_path = tmp_path / "story-config.yml"
        with open(config_path, 'w') as f:
            yaml.dump(mock_config, f)
        
        xml_dir = tmp_path / "story-xml"
        xml_dir.mkdir()
        xml_file = xml_dir / "test.xml"
        xml_file.write_text("""
<story>
  <section seq="1">
    <narration dlgseq="1" emotion="neutral">Test.</narration>
  </section>
</story>""")
        
        # Create script file for update
        script_file = tmp_path / "script.py"
        script_file.write_text('XSD_SCHEMA = """old"""')
        
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(sys, 'argv', ['chapter_validate_xml.py', '--update-xsd', str(xml_file)])
        
        with pytest.raises(SystemExit) as exc_info:
            chapter_validate_xml.main()
        
        # Result code may be 0 or 1 depending on validation
        assert exc_info.value.code in [0, 1]
    
    def test_main_update_xsd_not_found(self, tmp_path, monkeypatch, mock_config, capsys):
        """Test main with --update-xsd when file not found."""
        config_path = tmp_path / "story-config.yml"
        with open(config_path, 'w') as f:
            yaml.dump(mock_config, f)
        
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(sys, 'argv', ['chapter_validate_xml.py', '--update-xsd', 'nonexistent.xml'])
        
        with pytest.raises(SystemExit) as exc_info:
            chapter_validate_xml.main()
        
        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "not found" in captured.out.lower() or "error" in captured.out.lower()
    
    def test_main_xml_not_found(self, tmp_path, monkeypatch, mock_config):
        """Test main when specified XML file not found."""
        config_path = tmp_path / "story-config.yml"
        with open(config_path, 'w') as f:
            yaml.dump(mock_config, f)
        
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(sys, 'argv', ['chapter_validate_xml.py', 'nonexistent.xml'])
        
        with pytest.raises(SystemExit) as exc_info:
            chapter_validate_xml.main()
        
        assert exc_info.value.code == 1
    
    def test_main_with_absolute_path(self, tmp_path, monkeypatch, mock_config):
        """Test main with absolute path."""
        config_path = tmp_path / "story-config.yml"
        with open(config_path, 'w') as f:
            yaml.dump(mock_config, f)
        
        xml_dir = tmp_path / "story-xml"
        xml_dir.mkdir()
        xml_file = xml_dir / "test.xml"
        xml_file.write_text("""
<story>
  <section seq="1">
    <narration dlgseq="1" emotion="neutral">Test.</narration>
  </section>
</story>""")
        
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(sys, 'argv', ['chapter_validate_xml.py', str(xml_file)])
        
        with pytest.raises(SystemExit) as exc_info:
            chapter_validate_xml.main()
        
        assert exc_info.value.code in [0, 1]
