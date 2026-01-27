# FlexiTTS (flexi-tus)

The idea with FlexiTTS (Flexi-tus) is to create a simple flexible text to audio-book workflow.

## Story to Audio Conversion
  - Human like voice and emotion
  - Voice Cloning and Voice Effects via Qwen3-TTS
  - Voice and Dialog Effects via Sox
  - AI Augmented workflow

## Features:
   * Clone or Synthesize Voices + post-processing audio effects to voices.
  * Character parameters
	* Clone or Synthesize
    * Post-Processing effects
  * Flexible use of various open source local TTS models
    * Use best model for the given problem
    * Currently, only uses Qwen3-TTS is supported.
  * Uses LLM to generate XML, determines dialog associated to a given character. Added tags base on what should be the emotional tone of the character's dialog.
     * Find dialog that requires duress, pleasure, sarcasm.
  * Generates a sequence of audio-clips
    * Appls effects to audio-clips based on tags
    * Append audio-clips into your favorite DAW.
    * Final audio-clips are also appended together by chapter.

## Examples of generated audio

- Listen to "story-audio/04-Manus Labs.wav"

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
- **Output**:
    - Audio clips for all dialog
      - You can also place the audio into a DAW for additional audio enhancement.
    - An Audio track for each chapter.

## Hardware Requirements

  * CPU with at least 4 cores and 8GB of RAM
  * GPU with at least 8GB of VRAM
    * Use for local audio dialog generation. 
  * SSD with at least 500GB of storage
  * Access to a commercial grade LLM
    * Used to generate the required XML representation of the original Chapter document augmented with tags indicating dialogs for the Narrator and other Characters.

## Setup
- Run `git clone https://github.com/QwenLM/Qwen3-TTS.git`
- Run `uv init --python 3.12`
- Run `uv sync`

## Scripts

  - validate_config.py
    - Validates the configuration file story_config.yml
    - The internal schema used by story_config.yml text file can be updated given an properly formatted YAML document.
  - chapter_to_xml.py
    - Converts a Markdown Chapter text file to XML using the LLM service configured.
  - chapter_validate.xml
    - Validates the XML output of chapter_to_xml.py to ensure a properly formatted file, and that sections and indicated audio sequences are properly numbered.
    - Contains an internal XSD (XML Schema Definition) which can be updated given an properly formatted XML document.
  - chapter_xml_to_audio.py
    - Generates audio given the augmented XML representation of the original Markdown text chapter.


## A note on using voice-clone and instructing emotions.
- Currently when using voice-clone (referencing a sampled voice), does not have a parameter for instructing emotions. This is a limitation of the current implementation in Qwen3-TTS and may require further development to address.
  - To overcome this, you either use custom-voice mode, or use voice-samples with various emotional states. But more work needs to be done to extend the character configuration to support more nuanced emotion control.
    - A change to the character configuration to support more nuanced emotion control.
    - A change to the Story to XML LLM prompt to support more nuanced emotion control, based on voice samples available for a given character.

## Possible Future Enhancements

- **Web Interface**: Develop a web-based interface for managing chapters, editing XML, and generating audio.
- **Advanced Audio Effects**: Integrate more advanced audio effects and filters for better audio quality.
- **Multi-Language Support**: Extend the system to support multiple languages for diverse content.
- **AI Video Generation**: Generate video clips with synchronized audio for immersive storytelling.
- **Support for other TTS Tools**: Expand compatibility with other text-to-speech tools for diverse voices and languages.
  - Leverage capabilities of other TTS tools for enhanced voice quality and language support based on their strengths and capabilities.

## Help...

If you are good with UI work, consider helping out by creating a web interface to manage chapters, edit XML, and generate audio. This could include features like:
  - Chapter management: Add, edit, and delete chapters.
  - XML editing: A WYSIWYG editor for XML with syntax highlighting and validation.
  - Audio preview: Play audio clips and the final output.
  - Batch processing: Process multiple chapters at once.
  - User feedback: Allow users to report issues or suggest improvements.

