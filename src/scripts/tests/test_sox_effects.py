"""Tests for apply_sox_effects function in chapter_xml_to_audio."""

import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call

# Mock all TTS modules before importing chapter_xml_to_audio
sys.modules['tts_factory'] = Mock()
sys.modules['tts_factory'].create_tts_provider = Mock()
sys.modules['tts_factory'].TTSFactory = Mock()
sys.modules['tts_interface'] = Mock()
sys.modules['tts_local'] = Mock()
sys.modules['tts_service'] = Mock()
sys.modules['yaml'] = Mock()
sys.modules['soundfile'] = Mock()
# Note: Do NOT mock sys.modules['numpy'] here - it causes isolation issues
# Instead use @patch('chapter_xml_to_audio.np') in tests that need it

# Import after mocking
from chapter_xml_to_audio import apply_sox_effects, generate_silence


class TestApplySoxEffects:
    """Test apply_sox_effects function."""
    
    @patch('chapter_xml_to_audio.subprocess.run')
    @patch('chapter_xml_to_audio.random.choices')
    def test_apply_single_effect(self, mock_choices, mock_run):
        """Test applying a single SoX effect."""
        mock_choices.return_value = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h']
        mock_run.return_value = Mock(returncode=0)
        
        input_path = Path("/tmp/test.wav")
        
        with patch.object(Path, 'exists', return_value=True):
            with patch.object(Path, 'unlink'):
                with patch.object(Path, 'rename'):
                    apply_sox_effects(input_path, ["reverb 50"], dry_run=False)
        
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert args[0] == "sox"
        assert "reverb" in args
        assert "50" in args
    
    @patch('chapter_xml_to_audio.subprocess.run')
    @patch('chapter_xml_to_audio.random.choices')
    def test_apply_multiple_effects(self, mock_choices, mock_run):
        """Test applying multiple SoX effects."""
        mock_choices.side_effect = [
            ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h'],
            ['i', 'j', 'k', 'l', 'm', 'n', 'o', 'p']
        ]
        mock_run.return_value = Mock(returncode=0)
        
        input_path = Path("/tmp/test.wav")
        
        with patch.object(Path, 'exists', return_value=True):
            with patch.object(Path, 'unlink'):
                with patch.object(Path, 'rename'):
                    apply_sox_effects(
                        input_path, 
                        ["reverb 50", "pitch 100"], 
                        dry_run=False
                    )
        
        assert mock_run.call_count == 2
    
    @patch('chapter_xml_to_audio.subprocess.run')
    def test_dry_run_no_execution(self, mock_run):
        """Test dry_run mode doesn't execute sox."""
        input_path = Path("/tmp/test.wav")
        
        # Mock print to capture output
        with patch('builtins.print') as mock_print:
            apply_sox_effects(input_path, ["reverb 50"], dry_run=True)
        
        mock_run.assert_not_called()
        mock_print.assert_called_once()
        assert "Dry-run" in mock_print.call_args[0][0]
    
    @patch('chapter_xml_to_audio.subprocess.run')
    @patch('chapter_xml_to_audio.random.choices')
    def test_sox_error_handling(self, mock_choices, mock_run):
        """Test error handling when sox fails."""
        mock_choices.return_value = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h']
        from subprocess import CalledProcessError
        mock_run.side_effect = CalledProcessError(1, "sox", stderr=b"Error message")
        
        input_path = Path("/tmp/test.wav")
        temp_path = Path("/tmp/temp-abcdefgh.wav")
        
        with patch.object(Path, 'parent', Path("/tmp")):
            with patch.object(Path, '__truediv__', return_value=temp_path):
                with patch.object(Path, 'exists', side_effect=[True, True]):
                    with patch.object(Path, 'unlink') as mock_unlink:
                        apply_sox_effects(input_path, ["reverb 50"], dry_run=False)
                        # Should clean up temp file on error
                        mock_unlink.assert_called()
    
    def test_empty_effects_list(self):
        """Test empty effects list returns early."""
        input_path = Path("/tmp/test.wav")
        
        with patch('chapter_xml_to_audio.subprocess.run') as mock_run:
            apply_sox_effects(input_path, [])
            mock_run.assert_not_called()
    
    def test_empty_effects_string(self):
        """Test empty effects string is skipped."""
        input_path = Path("/tmp/test.wav")
        
        with patch('chapter_xml_to_audio.subprocess.run') as mock_run:
            apply_sox_effects(input_path, [""])
            mock_run.assert_not_called()


class TestGenerateSilence:
    """Test generate_silence function."""
    
    def test_generate_silence(self):
        """Test silence generation."""
        with patch('chapter_xml_to_audio.np') as mock_np:
            mock_np.zeros.return_value = [0.0] * 24000
            result = generate_silence(1.0, 24000)
            
            mock_np.zeros.assert_called_once_with(24000)
            assert len(result) == 24000
    
    def test_generate_silence_different_duration(self):
        """Test silence generation with different duration."""
        with patch('chapter_xml_to_audio.np') as mock_np:
            mock_np.zeros.return_value = [0.0] * 12000
            result = generate_silence(0.5, 24000)
            
            mock_np.zeros.assert_called_once_with(12000)


class TestApplySoxEffectsEdgeCases:
    """Test edge cases for apply_sox_effects."""
    
    @patch('chapter_xml_to_audio.subprocess.run')
    @patch('chapter_xml_to_audio.random.choices')
    def test_unexpected_error_handling(self, mock_choices, mock_run):
        """Test handling of unexpected exceptions."""
        mock_choices.return_value = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h']
        mock_run.side_effect = Exception("Unexpected error")
        
        input_path = Path("/tmp/test.wav")
        temp_path = Path("/tmp/temp-abcdefgh.wav")
        
        with patch('builtins.print') as mock_print:
            with patch.object(Path, 'parent', Path("/tmp")):
                with patch.object(Path, '__truediv__', return_value=temp_path):
                    with patch.object(Path, 'exists', side_effect=[True, True]):
                        with patch.object(Path, 'unlink'):
                            apply_sox_effects(input_path, ["reverb 50"], dry_run=False)
            
            # Should print error message
            assert any("Unexpected error" in str(call) for call in mock_print.call_args_list)
