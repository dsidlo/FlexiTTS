# FlexiTTS (flexi-tus)
## Story to Audio Conversion
  - Human like voice and emotion
  - Voice Cloning and Voice Effects via Qwen3-TTS
  - Voice and Dialog Effects via Sox
  - AI Augmented workflow

## Setup
- Run `git clone https://github.com/QwenLM/Qwen3-TTS.git`
- Run `uv init`
- Run `uv sync`

## Basic Workflow
- **Input**: Provide a story as a Markdown text (.md) file
  - Place Markdown file into the story-chapters directory as .md file
    - Ideally, use a consistent naming convention for chapters starting with the chapter number (left padded with zeros).
    - Clean up the Markdown file's paragraphs with a blank line between each paragraph.
  - If you have voice samples, place them into the voice-samples: directory (refs/)
  - Configure story-config.yaml with your desired settings.
    - ** Run the validate_config.py to ensure that there are no issues with the story_config.yml file. 
  - Working through one chapter at time...
    - Run `python chapter_to_xml.py <>.md`
- **Processing**: 
  1. Text to Speech conversion using Qwen3-TTS
  2. Voice and dialog effects using Sox
  3. AI augmentation for emotion and context
- **Output**: Audio file with human-like voice and effects


