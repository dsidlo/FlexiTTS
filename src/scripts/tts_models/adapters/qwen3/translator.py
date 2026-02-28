"""Qwen3-TTS specific parameter translations."""
from typing import Dict, Any


class Qwen3Translator:
    """Translate generic params to Qwen3-TTS format."""
    
    # Qwen3 uses full language names
    LANGUAGE_MAP = {
        'en': 'English',
        'zh': 'Chinese',
        'es': 'Spanish',
        'fr': 'French',
        'de': 'German',
        'ja': 'Japanese',
        'ko': 'Korean',
    }
    
    # Emotion instructions (Qwen3 uses natural language)
    EMOTION_INSTRUCTIONS = {
        'neutral': 'Speak in a neutral tone.',
        'happy': 'Speak in a happy, cheerful tone.',
        'sad': 'Speak in a sad, somber tone.',
        'angry': 'Speak in an angry, forceful tone.',
        'excited': 'Speak in an excited, enthusiastic tone.',
        'whisper': 'Speak in a soft whisper.',
    }
    
    def translate_parameters(
        self,
        emotion: str,
        language: str,
        instruct: str
    ) -> Dict[str, Any]:
        """Convert to Qwen3 format."""
        lang = self.LANGUAGE_MAP.get(language.lower(), language)
        
        # Build emotion instruction
        emotion_part = self.EMOTION_INSTRUCTIONS.get(
            emotion.lower(),
            f'Speak in a {emotion} tone.'
        )
        
        # Combine with user instruction (max 2K chars)
        final_instruct = f"{instruct} {emotion_part}".strip() if instruct else emotion_part
        if len(final_instruct) > 2000:
            final_instruct = final_instruct[:1997] + "..."
        
        return {
            'language': lang,
            'instruct': final_instruct,
            'emotion': emotion
        }
