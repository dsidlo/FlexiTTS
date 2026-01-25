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
    - For ideal security, place you API key into your ~/.env file and use the notaion `api_key: os.environ/<api-key-variable-name>`. Don't place your actual API key string in story_config.yml where possible.
    - ** Run the validate_config.py to ensure that there are no issues with the story_config.yml file. 
  - Working through one chapter at time...
    - Run `python chapter_to_xml.py <NN-Chapter-Name>.md`
    - Review the XML to make sure that it makes sense.
    - Run `python chapter_xml_to_audio.py <NN-Chapter-Name>.xml` to generate audio clips to the story-audio/clips/<NN-Chapter-Name> directory.
      - The clips are also appended together into one audio file in as story-audio/<NN-Chapter-Name>.wav
    - Review the generated audio.
    - To correct a clip, just delete the clip file in the story-audio/clips/<NN-Chapter-Name> directory...
      - Modify the dialog to improve clarity or emotion.
      - Then run `python chapter_xml_to_audio.py <NN-Chapter-Name>.xml --create-missing-clips` to regenerate the clip. This will also re-append the clips into the final audio file story-audio/<NN-Chapter-Name>.wav
    - You can also place the audio into a DAW for additional audio enhancement.
- **Processing**: 
  1. Text to Speech conversion using Qwen3-TTS
  2. Voice and dialog effects using Sox
  3. AI augmentation for emotion and context
- **Output**: Audio file with human-like voice and effects


