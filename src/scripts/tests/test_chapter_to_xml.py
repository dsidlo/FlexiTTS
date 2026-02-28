"""Direct import tests for chapter_to_xml.py - achieves coverage via imports."""

import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, patch, mock_open
import yaml

# Add parent to path for importing
sys.path.insert(0, str(Path(__file__).parent.parent))

import chapter_to_xml


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
        },
        "llm-xml-generator": [
            {
                "default-llm": "test-llm",
                "model": "test-model",
                "api_base": "http://localhost:8000",
                "api_key": "test-key"
            }
        ]
    }
    return config


@pytest.fixture
def sample_markdown(tmp_path, mock_config):
    """Create a sample markdown file for testing."""
    chapters_dir = tmp_path / "chapters"
    chapters_dir.mkdir(parents=True)
    md_file = chapters_dir / "test_chapter.md"
    md_file.write_text("# Chapter 1\n\nAlice said: Hello there!\n\nNarrator: It was a sunny day.")
    
    # Also create the XML output dir
    xml_dir = tmp_path / "story-xml"
    xml_dir.mkdir(parents=True)
    
    return md_file


class TestLoadConfig:
    """Test the load_config function."""
    
    def test_load_config_success(self, tmp_path):
        """Test loading a valid config file."""
        config_path = tmp_path / "story-config.yml"
        config_data = {"global": {"story-dir": "/test"}}
        with open(config_path, 'w') as f:
            yaml.dump(config_data, f)
        
        original_cwd = Path.cwd()
        try:
            import os
            os.chdir(tmp_path)
            config = chapter_to_xml.load_config()
            assert config["global"]["story-dir"] == "/test"
        finally:
            os.chdir(original_cwd)
    
    def test_load_config_file_not_found(self, tmp_path):
        """Test loading a nonexistent config file."""
        original_cwd = Path.cwd()
        try:
            import os
            os.chdir(tmp_path)
            with pytest.raises(FileNotFoundError):
                chapter_to_xml.load_config()
        finally:
            os.chdir(original_cwd)


class TestGetPromptTemplate:
    """Test the get_prompt_template function."""
    
    def test_get_prompt_template_success(self, tmp_path):
        """Test extracting prompt template from markdown."""
        prompt_file = tmp_path / "prompt.md"
        prompt_content = """
## Story to XML Generation (AI Prompt)

```xml
<template>
  <text>{{STORY}}</text>
</template>
```

Some other content.
"""
        prompt_file.write_text(prompt_content)
        
        template = chapter_to_xml.get_prompt_template(str(prompt_file))
        assert "<template>" in template
        assert "<text>" in template
    
    def test_get_prompt_template_missing_marker(self, tmp_path):
        """Test error when marker is not found."""
        prompt_file = tmp_path / "prompt.md"
        prompt_file.write_text("Some content without markers")
        
        with pytest.raises(ValueError) as exc_info:
            chapter_to_xml.get_prompt_template(str(prompt_file))
        assert "prompt template" in str(exc_info.value).lower()


class TestCreateParser:
    """Test the create_parser function."""
    
    def test_parser_creation(self):
        """Test that parser is created with expected arguments."""
        parser = chapter_to_xml.create_parser()
        
        # Test parsing --help doesn't raise
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(['--help'])
        assert exc_info.value.code == 0
    
    def test_parser_arguments(self):
        """Test parser accepts expected arguments."""
        parser = chapter_to_xml.create_parser()
        args = parser.parse_args(['test.md'])
        assert args.file_path == 'test.md'
        
        args = parser.parse_args(['--all-chapters'])
        assert args.all_chapters is True
        
        args = parser.parse_args(['--llm', 'test-model'])
        assert args.llm == 'test-model'


class TestMain:
    """Test the main function with mocked dependencies."""
    
    def test_main_help_flag(self, tmp_path, monkeypatch):
        """Test --help exits successfully."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(sys, 'argv', ['chapter_to_xml.py', '--help'])
        
        with pytest.raises(SystemExit) as exc_info:
            chapter_to_xml.main()
        
        assert exc_info.value.code == 0
    
    def test_main_missing_config_file(self, tmp_path, monkeypatch, capsys):
        """Test main exits when config is missing."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(sys, 'argv', ['chapter_to_xml.py', 'test.md'])
        
        # Should raise FileNotFoundError when trying to load config
        with pytest.raises(FileNotFoundError):
            chapter_to_xml.main()

    @patch('chapter_to_xml.completion')
    def test_main_with_valid_markdown(self, mock_completion, tmp_path, monkeypatch, mock_config, sample_markdown):
        """Test main with valid markdown file."""
        # Create config
        config_path = tmp_path / "story-config.yml"
        with open(config_path, 'w') as f:
            yaml.dump(mock_config, f)
        
        # Create prompt file
        prompt_file = tmp_path / "prompt.md"
        prompt_content = """
## Story to XML Generation (AI Prompt)

```xml
<story>
  <section seq="1">
    <text_input>{{STORY}}</text_input>
  </section>
</story>
```
"""
        prompt_file.write_text(prompt_content)
        
        # Mock completion response
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="<story><section seq=\"1\"></section></story>"))]
        mock_completion.return_value = mock_response
        
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(sys, 'argv', ['chapter_to_xml.py', str(sample_markdown.name)])
        
        # Mock the prompt template path
        with patch.object(chapter_to_xml, 'get_prompt_template', return_value='<template>{{STORY}}</template>'):
            chapter_to_xml.main()
        
        # Verify output file was created
        output_file = tmp_path / "story-xml" / "test_chapter.xml"
        assert output_file.exists()
    
    def test_main_with_nonexistent_file(self, tmp_path, monkeypatch, mock_config, capsys):
        """Test main exits when input file doesn't exist."""
        # Create config
        config_path = tmp_path / "story-config.yml"
        with open(config_path, 'w') as f:
            yaml.dump(mock_config, f)
        
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(sys, 'argv', ['chapter_to_xml.py', 'nonexistent.md'])
        
        with pytest.raises(SystemExit) as exc_info:
            chapter_to_xml.main()
        
        assert exc_info.value.code == 1
    
    @patch('chapter_to_xml.completion')
    def test_main_with_all_chapters(self, mock_completion, tmp_path, monkeypatch, mock_config):
        """Test main with --all-chapters flag."""
        # Create config
        config_path = tmp_path / "story-config.yml"
        with open(config_path, 'w') as f:
            yaml.dump(mock_config, f)
        
        # Create chapters and output dirs
        chapters_dir = tmp_path / "chapters"
        chapters_dir.mkdir()
        xml_dir = tmp_path / "story-xml"
        xml_dir.mkdir()
        
        # Create markdown files
        (chapters_dir / "01_chapter.md").write_text("# Chapter 1")
        (chapters_dir / "02_chapter.md").write_text("# Chapter 2")
        
        # Mock completion response
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="<story></story>"))]
        mock_completion.return_value = mock_response
        
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(sys, 'argv', ['chapter_to_xml.py', '--all-chapters'])
        
        with patch.object(chapter_to_xml, 'get_prompt_template', return_value='<template>{{STORY}}</template>'):
            chapter_to_xml.main()
    
    @patch('chapter_to_xml.completion')
    def test_main_with_llm_option(self, mock_completion, tmp_path, monkeypatch, mock_config, sample_markdown):
        """Test main with --llm option."""
        # Create config
        config_path = tmp_path / "story-config.yml"
        with open(config_path, 'w') as f:
            yaml.dump(mock_config, f)
        
        # Mock completion response
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="<story></story>"))]
        mock_completion.return_value = mock_response
        
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(sys, 'argv', ['chapter_to_xml.py', str(sample_markdown.name), '--llm', 'test-llm'])
        
        with patch.object(chapter_to_xml, 'get_prompt_template', return_value='<template>{{STORY}}</template>'):
            chapter_to_xml.main()
    
    @patch('chapter_to_xml.completion')
    def test_main_llm_not_found(self, mock_completion, tmp_path, monkeypatch, mock_config, sample_markdown, capsys):
        """Test main exits when specified LLM not found."""
        # Create config without the specified LLM
        config_path = tmp_path / "story-config.yml"
        with open(config_path, 'w') as f:
            yaml.dump(mock_config, f)
        
        # Create prompt file (required by main)
        prompt_file = tmp_path / "prompt.md"
        prompt_file.write_text("""
## Story to XML Generation (AI Prompt)

```xml
<template>{{STORY}}</template>
```
""")
        
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(sys, 'argv', ['chapter_to_xml.py', str(sample_markdown.name), '--llm', 'nonexistent'])
        
        with patch.object(chapter_to_xml, 'get_prompt_template', return_value='<template>{{STORY}}</template>'):
            with pytest.raises(SystemExit) as exc_info:
                chapter_to_xml.main()
        
        assert exc_info.value.code == 1
    
    @patch('chapter_to_xml.completion')
    def test_main_llm_with_env_var_api_key(self, mock_completion, tmp_path, monkeypatch, mock_config, sample_markdown):
        """Test main with LLM using os.environ for api_key."""
        # Create config with env var reference
        config_with_env = mock_config.copy()
        config_with_env["llm-xml-generator"][0]["api_key"] = "os.environ/TEST_API_KEY"
        
        config_path = tmp_path / "story-config.yml"
        with open(config_path, 'w') as f:
            yaml.dump(config_with_env, f)
        
        # Set env var
        monkeypatch.setenv("TEST_API_KEY", "test-api-key-value")
        
        # Mock completion response
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="<story></story>"))]
        mock_completion.return_value = mock_response
        
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(sys, 'argv', ['chapter_to_xml.py', str(sample_markdown.name)])
        
        with patch.object(chapter_to_xml, 'get_prompt_template', return_value='<template>{{STORY}}</template>'):
            chapter_to_xml.main()
    
    @patch('chapter_to_xml.completion')
    def test_main_llm_response_with_code_blocks(self, mock_completion, tmp_path, monkeypatch, mock_config, sample_markdown):
        """Test main handles LLM response with XML in code blocks."""
        # Create config
        config_path = tmp_path / "story-config.yml"
        with open(config_path, 'w') as f:
            yaml.dump(mock_config, f)
        
        # Mock completion response with code blocks
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="```xml\n<story></story>\n```"))]
        mock_completion.return_value = mock_response
        
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(sys, 'argv', ['chapter_to_xml.py', str(sample_markdown.name)])
        
        with patch.object(chapter_to_xml, 'get_prompt_template', return_value='<template>{{STORY}}</template>'):
            chapter_to_xml.main()
        
        # Verify output
        output_file = tmp_path / "story-xml" / "test_chapter.xml"
        assert output_file.exists()
        content = output_file.read_text()
        assert "<story>" in content
        assert "```" not in content
    
    @patch('chapter_to_xml.completion')
    def test_main_llm_error(self, mock_completion, tmp_path, monkeypatch, mock_config, sample_markdown, capsys):
        """Test main handles LLM errors."""
        # Create config
        config_path = tmp_path / "story-config.yml"
        with open(config_path, 'w') as f:
            yaml.dump(mock_config, f)
        
        # Mock completion to raise exception
        mock_completion.side_effect = Exception("API Error")
        
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(sys, 'argv', ['chapter_to_xml.py', str(sample_markdown.name)])
        
        with patch.object(chapter_to_xml, 'get_prompt_template', return_value='<template>{{STORY}}</template>'):
            with pytest.raises(SystemExit) as exc_info:
                chapter_to_xml.main()
        
        assert exc_info.value.code == 1


class TestEdgeCases:
    """Test edge cases."""
    
    def test_main_no_args_no_all_chapters(self, tmp_path, monkeypatch, mock_config, capsys):
        """Test main with no arguments and no --all-chapters."""
        # Create config
        config_path = tmp_path / "story-config.yml"
        with open(config_path, 'w') as f:
            yaml.dump(mock_config, f)
        
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(sys, 'argv', ['chapter_to_xml.py'])
        
        with pytest.raises(SystemExit) as exc_info:
            chapter_to_xml.main()
        
        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "chapter" in captured.out.lower() or "all-chapters" in captured.out.lower()
    
    def test_main_empty_chapters_dir(self, tmp_path, monkeypatch, mock_config, capsys):
        """Test main with --all-chapters on empty chapters directory."""
        # Create config
        config_path = tmp_path / "story-config.yml"
        with open(config_path, 'w') as f:
            yaml.dump(mock_config, f)
        
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(sys, 'argv', ['chapter_to_xml.py', '--all-chapters'])
        
        with pytest.raises(SystemExit) as exc_info:
            chapter_to_xml.main()
        
        assert exc_info.value.code == 1
