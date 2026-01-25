# FlexiTTS Development Notes

The idea with FlexiTTS (Flexi-tus) is to create a flexible taggable story to audio-track system.
Automated book to augmented-audible 

## Features:
  * Character parameters
	* Characters and their voices
  * Flexible use of various open source local TTS models
    * Use best model for the given problem
  * Voice cloning were needed
  * Leverage LLM to find tag dialog associated to a given character.
  * Leverage LLM to identify atmospheric backgrounds and effects for a given story.
   * Leverage LLM to find and possibly automate Character dialog that requires custom voice clone for added effect
     * Find dialog that requires duress, pleasure, sarcasms, specific timing (jokes)
       * Special effects, echo, chambers, street noise, crowds etc...
  * Generate stems
  * Apply effects to stems based on tags
  * Append stems in the appropriate order (final edit)
  * Generate captions

## Voice Generation Pipelines

Additionally, a pipeline could be created that allows for the generation of consistent graphic images that match a given situation.

Given a set of images indicating the various characters of the story and backdrops where scenes are envisioned to occur.
Visuals are synthesized that fit a given scene in the story.

### Design Outline

  1. LLM scans text and adds tags for character dialog
     1. <char-narrator>Text.</char-narrator>
     2. <char-Hendricks>Text.</char-Hendricks>
     3. Use Python and a local LLM to augment text
	    1. Process 1 paragraph at a time.
		2. Include 1 paragraph before and after as context or possibly more to include context.
		3. If the story is short enough to fit into the LLM context window, load the full story.
		4. Determine if the dialog requires attention to dramatization, pain, anger, elation, grief and add the area.
			a. <flag:drama-grief></flag:drama-grief>
	 5. Additional context my be required including...
        1. a list of characters
		2. a summary of the story
		3. instructions on how to surround dialog with tags (tagging rules)
           1. open/close tag may contain other open/close tags, and must not overlap.
           2. output text as a nested XML file.
  2. LLM scans text and adds tags for music and sound effects
		1. Process 1 paragraph at a time.
		2. Include 1 paragraph before and after as context or possibly more to include context.
		3. If the story is short enough to fit into the LLM context window, load the full story.
		4. Additional context my be required including...
			1. a music and sound effects
			2. a summary of the story
			3. instructions on how to surround story sections with tags 
  3. Python program scans augmented text and generates sound stems given character dialog.
	 1. Dialog Stems are replayed through Speech to Text STT (whisper) to validate dialog.
		1. TTS Optimization...
           1. atch TTS for a single characters voice so that cloning does not require reloads of the target voice for voice cloning.
	 2. Stem lengths are noted so as to target appropriate locations for music and sound effect stems.
	 3. Sound effect stems are auto selected or generated.
	 4. Music stems are auto selected or generated.
  4. Python program uses reapy-boost to...
	 1. Place dialog sound-bytes on a track
	 2. Potentially re-align sound-bytes end to end
	 2. generate timing for video closed-captions

#### Additional Ideas
  1. Using Chatterbox-TTS, we can use prompting and sliders to control voice output's emotion.
  	 1. Create a set of parameters that can be used to model emotion over the tone scale.
	 2. Map AI's emotion attributes to points on the Tone Scale.
	 3. Create an algorithm that applies the emotional attribute as an emotional shift to a given character, base on the character's Chronic Tone Level.
	 4. Additionally, allow a character's story arc, to shift the characters Chronic Tone Level.

## Story to XML Generation (AI Prompt)

```xml
<instructions>
<example_output>
<story>
  <section seq=1>
	<narration emotion="[derived-emotion]" dlgseq="1">
	  His personal sanctuary, Yamo's-Lab, was a cathedral of technology, a place
	  where past and future coexisted in a delicate balance. Vintage machines
	  that had once revolutionized society stood next to cutting-edge devices
	  that promised to do the same for future generations. It was here that Yamo
	  had penned contributions to some of the most groundbreaking scientific
	  papers of the age, his name a footnote in the annals of human progress.
	</narration>
	<dialog character="Hendricks" emotion="urgent"  dlgseq="2">
	  Hey Yamo, I need to talk with you... Let me in.
	</dialog>
  </section>
  <section seq="2">
	<dialog character="Hendricks" emotion="urgent"  dlgseq="3">
	  Hey Yamo, I need to talk with you... Let me in.
	</dialog>
	<narration emotion="[derived-emotion]" dlgseq="4">
	  The sound of bunker locks disengaging filled the room, a mechanical
	  symphony that ended with the hiss of the air-lock seal. Hendricks stepped
	  into the lab, his eyes scanning the room with a predator's intensity.
	  Without a word, he tossed a dark chip across the table to Yamo.
	</narration>
	<dialog character="Yamo" emotion="curious"  dlgseq="5">
	  What is it?
	</dialog>
	<narration emotion="[derived-emotion]" dlgseq="6">
	  The game was far from over, and the stakes had never been higher. But for
	  now, for this brief moment in time, they were together. And in a world of
	  shifting alliances and shadowy adversaries, of rogue AIs and military-grade
	  snuffers, that was something. It was a start.
	</narration>
  </section>
</story>
</example_output>
** Follow these instuctions percisely **
Given the following story text, first, identify the characters involved by name. Also taking note of the appropriate emotional derived from the content of the text.
1. Then update the text with embedded matching opening and closing tags for the dialog that is said by a given character.
2. The format of the character dialog tags looks like: 
     <dialog character="character_name" emotion="emotional_tone" dlgseq=1> 
		dialog_from_text
	 </dialog>.
   The dialog tag is only be used when the character is speaking.
   The dlgseq attribute is required within the dialog tag
3. The "narrators" dialog should be tagged with...   
     <narration emotion="emotional_tone" dlgseq=[1..n]>
		narration_from_text
	 </narration>
   The narration tag is only used when characters in the story are not speeking.
   The dlgseq attribute is required within the narration tag
4. For the emotion attribute, add the word flag in the value to indicate emotional content that might be difficult for TTS such as Chatterbox-TTS to duplicate.
	a. example <[dialog|narrative] emotion="sarcasm;flag">
	b. only add "flag" to the attribute if the emotion required must be particularly strong.
	c. If the emotion for the dialog or narration can not be determined, don't include the attribute.
5. The dlgseq=[1..n] attribute is incremented for each new dialog-tag and narration-tag as we move forward through the document.
	a. Use global variable for a given tag's seq attribute so that tag nesting does not restart a dlgseq attribute at 1.
	b. dlgseq will be used to track the order of all spoken narration & dialog in the story.
6. Make sure not to repeat dialog or narration such that it does not match the inuput-text.
7. Please output the XML document with standard visually nested indentation as specified in between the example_output tags, were each tag ends with a CR.
	a. Produce visually clean nested output disregarding a given tag's seq attribute with regard to tag nesting.
	b. Ensure that start and end tags and tag-attributes and values meet standard XML requirements.
	c. wrapping content-text at 80 characters.
</instructions>

<text_input>
...Paste Story Text Here...
</text_input>
```

#### Example Story Text

```md
# 3. - Yamamoto -
Created Thursday 25 December 2025

# - Yamamoto -

His personal sanctuary, Yamo's-Lab, was a cathedral of technology, a place where past and future coexisted in a delicate balance. Vintage machines that had once revolutionized society stood next to cutting-edge devices that promised to do the same for future generations. It was here that Yamo had penned contributions to some of the most groundbreaking scientific papers of the age, his name a footnote in the annals of human progress.

Rushing to Anyana's apartment, he found her sprawled on the floor, her phone lying next to her like a dead man's switch. Her eyes were closed, her face a mask of anguish. Time was running out.

Back in Yamo's-Lab, he booted up Sony, an AI of his own creation, a Frankenstein's monster cobbled together from three D-Wave quantum processors and a cluster of Cerebras wafer-scale CPUs. It was a makeshift solution, a patchwork quilt of code and silicon, but it was the best he could do on short notice.

Activating the old DSIC interface, he initiated the connection. Data packets began to flow, a digital lifeline thrown across the abyss. It was a gamble, a roll of the dice with human lives hanging in the balance. But as he watched the interface protocols sync, as he saw the first flickers of activity on Anyana's EEG, he felt a glimmer of hope.

Perhaps Sony could provide a temporary anchor, a digital touchstone to help Anyana navigate the disorienting landscape of her disconnected mind. Perhaps, in this makeshift fusion of old and new, he could find a way to bring her back from the edge of the abyss.

And as the data streams converged, as the algorithms began their intricate dance of ones and zeros, Yamo knew that he had crossed a line, had ventured into uncharted territory where the boundaries between human and machine, between ethics and necessity, were as fluid as the data that flowed through his servers.

The atmosphere in Yamo's lab was a cocktail of relief and residual tension, the afterglow of a crisis narrowly averted. Anyana was propped up on a lab stool, her eyes still tinged with the disorientation of her recent ordeal. Harbrough, the makeshift AI, hummed quietly in the background, a poor substitute for Ryan but a lifeline nonetheless.

"Hey Yamo, I need to talk with you... Let me in."

The sound of bunker locks disengaging filled the room, a mechanical symphony that ended with the hiss of the air-lock seal. Hendricks stepped into the lab, his eyes scanning the room with a predator's intensity. Without a word, he tossed a dark chip across the table to Yamo.

Yamo picked it up, his fingers tracing the contours of the device. "What is it?"

"An AI snuffer. Military grade. I don't know the specifics, but if anyone can figure it out, it's you."

Yamo's eyes flicked to Anyana, then back to Hendricks. "Who's the chick?"

Hendricks' augments, barely perceptible but undeniably present, gave off a subtle aura of otherworldly precision. It was as if he moved through the world on a different frequency, one that most people couldn't tune into.

"Dude, this is Mil-Tech. How did you even get your hands on it?"

...

The game was far from over, and the stakes had never been higher. But for now, for this brief moment in time, they were together. And in a world of shifting alliances and shadowy adversaries, of rogue AIs and military-grade snuffers, that was something. It was a start.

```

#### Exmple results

```xml
<story>
  <section seq="1">
    <narration emotion="reverent" dlgseq="1">
      His personal sanctuary, Yamo's-Lab, was a cathedral of technology, a place
      where past and future coexisted in a delicate balance. Vintage machines
      that had once revolutionized society stood next to cutting-edge devices
      that promised to do the same for future generations. It was here that
      Yamo had penned contributions to some of the most groundbreaking
      scientific papers of the age, his name a footnote in the annals of human
      progress.
    </narration>
  </section>

  <section seq="2">
    <narration emotion="urgent;flag" dlgseq="2">
      Rushing to Anyana's apartment, he found her sprawled on the floor, her
      phone lying next to her like a dead man's switch. Her eyes were closed,
      her face a mask of anguish. Time was running out.
    </narration>
  </section>

  <section seq="3">
    <narration emotion="focused" dlgseq="3">
      Back in Yamo's-Lab, he booted up Sony, an AI of his own creation, a
      Frankenstein's monster cobbled together from three D-Wave quantum
      processors and a cluster of Cerebras wafer-scale CPUs. It was a
      makeshift solution, a patchwork quilt of code and silicon, but it was the
      best he could do on short notice.
    </narration>

    <narration emotion="tense" dlgseq="4">
      Activating the old DSIC interface, he initiated the connection. Data
      packets began to flow, a digital lifeline thrown across the abyss. It was
      a gamble, a roll of the dice with human lives hanging in the balance.
      But as he watched the interface protocols sync, as he saw the first
      flickers of activity on Anyana's EEG, he felt a glimmer of hope.
    </narration>

    <narration emotion="reflective" dlgseq="5">
      Perhaps Sony could provide a temporary anchor, a digital touchstone to
      help Anyana navigate the disorienting landscape of her disconnected mind.
      Perhaps, in this makeshift fusion of old and new, he could find a way to
      bring her back from the edge of the abyss.
    </narration>

    <narration emotion="foreboding;flag" dlgseq="6">
      And as the data streams converged, as the algorithms began their
      intricate dance of ones and zeros, Yamo knew that he had crossed a line,
      had ventured into uncharted territory where the boundaries between human
      and machine, between ethics and necessity, were as fluid as the data that
      flowed through his servers.
    </narration>
  </section>

  <section seq="4">
    <narration emotion="relieved" dlgseq="7">
      The atmosphere in Yamo's lab was a cocktail of relief and residual
      tension, the afterglow of a crisis narrowly averted. Anyana was propped
      up on a lab stool, her eyes still tinged with the disorientation of her
      recent ordeal. Harbrough, the makeshift AI, hummed quietly in the
      background, a poor substitute for Ryan but a lifeline nonetheless.
    </narration>

    <dialog character="Hendricks" emotion="urgent" dlgseq="8">
      Hey Yamo, I need to talk with you... Let me in.
    </dialog>

    <narration emotion="neutral" dlgseq="9">
      The sound of bunker locks disengaging filled the room, a mechanical
      symphony that ended with the hiss of the air-lock seal. Hendricks stepped
      into the lab, his eyes scanning the room with a predator's intensity.
      Without a word, he tossed a dark chip across the table to Yamo.
    </narration>

    <dialog character="Yamo" emotion="curious" dlgseq="10">
      What is it?
    </dialog>

    <dialog character="Hendricks" emotion="matter-of-fact" dlgseq="11">
      An AI snuffer. Military grade. I don't know the specifics, but if anyone
      can figure it out, it's you.
    </dialog>

    <dialog character="Yamo" emotion="suspicious" dlgseq="12">
      Who's the chick?
    </dialog>

    <narration emotion="observant" dlgseq="13">
      Hendricks' augments, barely perceptible but undeniably present, gave off
      a subtle aura of otherworldly precision. It was as if he moved through
      the world on a different frequency, one that most people couldn't tune
      into.
    </narration>

    <dialog character="Yamo" emotion="incredulous" dlgseq="14">
      Dude, this is Mil-Tech. How did you even get your hands on it?
    </dialog>

...
      
    <narration emotion="reflective" dlgseq="36">
      The game was far from over, and the stakes had never been higher. But for
      now, for this brief moment in time, they were together. And in a world of
      shifting alliances and shadowy adversaries, of rogue AIs and
      military-grade snuffers, that was something. It was a start.
    </narration>
  </section>
</story>
```

## AI Prompts for Program Generation

### chapter_to_xml.py

Create a script (chapter_to_xml.py) that...
  1. Reads the story-config.yml file for directory locations.
  2. Takes as an argument the file-path of a markdown file.
     1. If there is no file-path indicated, it looks for the file in the "chapters:" directory.
  3. Uses the xml example in the file "FlexiTTS Dev Notes.md", under "Story to XML Generation (AI Prompt)".
  4. Places the markdown text of the story into the "<text-input>"  section, and submits the request to an LLM using a LiteLLM, where it will by default interface with a local lm-studio LLM service.
  5. The output xml created by the LLM should be placed into the "story-xml:" directory path, and it should use the same name as the original .md file but the suffix of the file name should change to .xml

## chapter_xml_to_audio.py

Create a script (chapter_to_xml.py) that...
Read the documentation on Qwen3-TTS. in the Qwen3-TTS/ directory (Github repo clone).
  1. Create a program called chapter_xml_to_audio.py to convert XML chapters into audio files using Qwen3-TTS and leveraging its ability to do voice-cloning, and emotions.
  2. Reads the story-config.yml file for directory locations.
  3. Takes as an argument the file-path of a chapter's XML file.
     1. If there is no file-path indicated, it looks for the file in the "story-xml:" directory.
  4. Read and parse the XML file.
  5. Generate wav audio files for each section of the story.
     1. The audio files should be placed into the "story-audio:" directory path, and should use the same name as the original .xml file but the suffix of the file name should change to .wav
     2. Clone the narrator voice-sample for narrator tagged text, as defined in the story-config.yml file.
     3. Clone the appropriate characters voice-sample for the character tagged text, as defined in the story-config.yml file.
     4. use the emotion attributes for the narrator and character tagged text, to drive appropriate parameters to Qwen3-TTS
     5. Generate voice clips to the "clips:" directory within a directory having the same name as the XML document (less its suffix .xml).
     6. wav file segments should be labeled with...
        1. <chapter_number> format nnn (the first digits of the xml file's chapter name), 
        2. <section_nunber> format nnn (from the seq attribute of the section tag).
        3. <dialog_sequence> format nnn (from the dlgseq attribute of the dialog tag)
        4. Example: chapter_001_001_001.wav ...
           1. Is the audio file for the first dialog or narrator section for the first section of the first chapter.
        5. If the TTS process needs to segment the dialog further, use an additional sequence value at the end prefixed with an s, ie. chapter_001_001_001_s001.wav
	 7. As an optimization, first gather all dialog sections for all characters and the narrator, and batch voice generation for all wave files for a given character.
        1. For a given character. Run generate_voice_clone(), and cache it.
        2. Generate all audio segments for the given character.
        3. Repeat for the next character.

## Character Voice and Dialog clip post effects

### configuration: sox-effect in voice-sample: and custom-voice:
- `sox-effect` allows you to apply audio effects to the synthesized speech using the `sox` library. This can be useful for enhancing the naturalness and quality of the generated audio.
- Example: `sox-effect: pitch -400   echo 0.8 0.88 60 0.4 120 0.3   reverb`
- This effect can be applied globally or overridden by speaker-specific settings.
- The sox-effects attribute can be used as attributes to voice-sample: and custom-voice: for additional post-processing of dialog clips.

### configuration: named dialog-effects: for <<dialog|narration ...post-effects=<dialog-effects-name>> tags
- `dialog-effects` defines named audio effects applied to narration and dialog tags via the post-effect attribute, such as pitch shifting, echo, and reverb. These effects are layered on top of a characters dialog which itself may have been post processed. 
- Config Example dialog-effects:
  - ```yaml
    dialog-effects:
      - name: cave
        sox-effects: pitch -400   echo 0.8 0.88 60 0.4 120 0.3   reverb
    ```
- This effect attribute can be applied to any given dialog or narration tag and is not required.
- <<story>> XML Example:
  - ```xml
    	<narration emotion="uncertain" dlgseq="25" post-effects="cave">
    	  And so, as Hendrix exited the lab, the air-lock sealing behind him with a
    	  finality that felt almost ominous, Yamo turned back to his consoles, to
    	  Ayana, and to the uncertain future that lay ahead. They were all pieces on
    	  the board, and the game was far from over.
    	</narration>
    ``` 
- Config Examples for narrator:, voice-sample: and custom-voice: and dialog-effects: character attributes
  - ```xml
      - name: Hendrix-echo
        voice-sample: Hendricks-voice.wav
        dialog-effects: cave
      - name: Ayana-echo
        voice-sample: Ayana-voice.wav
        sox-effects: pitch -400   echo 0.8 0.88 60 0.4 120 0.3   reverb
      - name: Hayden-echo
        custom-voice:
          language: English
          speaker: Aiden
          instruct: "Deep manly voice with a rough texture"
        dialog-effects: cave
      - name: Yakuza-1
        custom-voice:
          language: English
          speaker: Uncle_Fu
          instruct: "Wicked, Sneering"
        sox-effects: pitch -400   echo 0.8 0.88 60 0.4 120 0.3   reverb
      - name: Yakuza-1
        custom-voice:
          language: English
          speaker: Uncle_Fu
          instruct: "Wicked, Sneering"
        dialog-effects: cave
    ```

Modify @chapter_xml_to_audio.py to apply post-effects on character dialog, such that the named dialog-effects are applied to character dialog clips first, then if the <<dialog>> tag contains a named post-effects attribute, then that is also applied to the dialog clip.
The process of applying the effect is to use sox to apply the clip to a temp-<random_test>.wav file, then the original wav file is removed, and the temp wav file is renamed with the original file's full filename.
Thus, a max number of 2 effects operations are possible, one for the character's attributes, and one for the dialog's attributes.
