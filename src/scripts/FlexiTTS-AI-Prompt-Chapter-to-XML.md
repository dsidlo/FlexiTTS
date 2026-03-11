# FlexiTTS AI Prompt: Chapter to XML

## Story to XML Generation (AI Prompt)

```xml
<instructions>
<example_output>
<story>
  <section seq="1">
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
  <prompt>
** Follow these instuctions percisely **

Given the following story text, first, identify the characters involved by name. Also taking note of the appropriate emotional derived from the content of the text. The emotional_tone may describe timbre, prosody and speaking rate.
1. Then update the text with embedded matching opening and closing tags for the dialog that is said by a given character.
2. The format of the character dialog tags looks like: 
     <dialog character="character_name" emotion="emotional_tone" dlgseq="1"> 
		dialog_from_text
	 </dialog>.
   The dialog tag is only be used when the character is speaking.
   The dlgseq attribute is required within the dialog tag
3. The "narrators" dialog should be tagged with...   
     <narration emotion="emotional_tone" dlgseq="[1..n]">
		narration_from_text
	 </narration>
   The narration tag is only used when characters in the story are not speeking.
   The dlgseq attribute is required within the narration tag
4. If the input text is not separated clearly by paragraphs. Deduce paragraph breaks and assign them to sequential sections.
5. The dlgseq=[1..n] attribute is incremented for each new dialog-tag and narration-tag as we move forward through the document.
	a. Use global variable for a given tag's seq attribute so that tag nesting does not restart a dlgseq attribute at 1.
	b. dlgseq will be used to track the order of all spoken narration and dialog in the story.
6. Make sure not to repeat dialog or narration such that it does not match the input-text.
7. Please output the XML document with standard visually nested indentation as specified in between the example_output tags, where each tag ends with a CR.
	a. Produce visually clean nested output disregarding a given tag's seq attribute with regard to tag nesting.
	b. Ensure that start and end tags and tag-attributes and values meet standard XML requirements.
	c. wrapping content-text at 80 characters.
  </prompt>
</instructions>

<text_input>
...Paste Story Text Here...
</text_input>
```

#### Example Story Text

This example text is inserted into the <text_put> tag.

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
## Additional tags in markdown

You may see additional tag in the markdown document such as...
- <character: {character-name}>: This tag means that the following text is dialog for the given {character-name}
