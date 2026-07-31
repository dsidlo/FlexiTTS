# TTS Research

## Character UI

Given the following yaml configuration for character voices... 

```yaml
characters:
  # Supported Qwen3-TTS Custom-Voice Speakers:
  # ['aiden', 'dylan', 'eric', 'ono_anna', 'ryan', 'serena', 'sohee', 'uncle_fu', 'vivian']
  #   Vivian: Bright, slightly edgy young female voice.                    | Chinese
  #   Serena: Warm, gentle young female voice.                             | Chinese
  # Uncle_Fu: Seasoned male voice with a low, mellow timbre.               | Chinese
  #    Dylan: Youthful Beijing male voice with a clear, natural timbre.    | Chinese (Beijing Dialect)
  #     Eric: Lively Chengdu male voice with a slightly husky brightness.  | Chinese (Sichuan Dialect)
  #     Ryan: Dynamic male voice with strong rhythmic drive.               | English
  #    Aiden: Sunny American male voice with a clear midrange.             | English
  # Ono_Anna: Playful Japanese female voice with a light, nimble timbre.   | Japanese
  #    Sohee: Warm Korean female voice with rich emotion.                  | Korean
  - name: Narrator
    # The narrator voice uses voice cloning and a post-effect to make it a bit louder.
    voice-sample: dgs-voice.wav
    sox-effects:
      - gain +4
  - name: Narrator-cv
    # This version of the narrator voice uses Qwen3-TTS voice customization.
    # It customizes one of Qwen3-TTS's 9 internal voices using sox post-processing
    # to make it deeper and rougher.
    custom-voice:
      language: English
      speaker: ryan
      instruct: "Deep manly voice. Speech is moderately fast, slightly hushed."
    sox-effects:
      - treble -5 5000 0.7 compand 0.3,1 6:-70,-60,-20 -4 -90 0.1 gain -3
  - name: Hendrix
    custom-voice:
      language: English
      speaker: ryan
      instruct: "Deep manly voice with a rough texture. Speech is calm and calculating, moderately fast."
    sox-effects:
      - overdrive 15 30 gain -8
  - name: Yamato
    custom-voice:
      language: English
      speaker: ryan
      instruct: "An mature man. Speech is gruff and abrupt with a hit of frustration."
    sox-effects:
      - pitch -250 equalizer 1800 +4 1.8 equalizer 3200 +3 2.2 bass +2 120 gain -n -1.5
  - name: Ayana
    voice-sample: Ayana-voice.wav
  - name: Juko
    voice-sample: Juko-voice.wav
  - name: Hayden
    custom-voice:
      language: English
      speaker: Aiden
      instruct: "Deep manly voice with a rough texture"
  - name: Yakuza-1
    custom-voice:
      language: English
      speaker: Uncle_Fu
      instruct: "Wicked, Sneering"
    sox-effects:
      - pitch -400   echo 0.8 0.88 60 0.4 120 0.3 reverb gain +3
  # Examples Voice Configurations
  - name: Hendrix-vc
    voice-sample: Hendricks-voice.wav
  - name: Yamato-vc
    voice-sample: Yamato-voice.wav
  - name: Hendrix-echo
    voice-sample: Hendricks-voice.wav
    dialog-effects:
      # named dialog-effects can be layered
      - cave
  - name: Ayana-echo
    voice-sample: Ayana-voice.wav
    sox-effects:
      - pitch -400   echo 0.8 0.88 60 0.4 120 0.3 reverb
  - name: Hayden-echo
    custom-voice:
      language: English
      speaker: Aiden
      instruct: "Deep manly voice with a rough texture"
    dialog-effects:
      - cave
  - name: Yakuza-2
    custom-voice:
      language: English
      speaker: Uncle_Fu
      instruct: "Wicked, Sneering"
    dialog-effects:
      - cave
```

Create design concepts for a UI that allows CRUD operations for Characters, the character's voices, which can be sorted by character-state, character-emotion, character-location, 
 and voice-effect

Give me some ideas regarding UI panel design, with mockup images if possible.

Designing a UI for a complex TTS (Text-to-Speech) configuration requires balancing technical precision (SoX effects and YAML parameters) with creative expression (character traits and emotions).

Since your YAML structure supports **Base Voices** (samples or custom) and **Modifiers** (SoX or Dialog effects), the UI should treat these as modular blocks.

---

## 1. The "Modular Persona" Dashboard
Instead of a flat list, this concept uses a **Card-based Grid** where each character is a "Persona."

* **Visual Design:** Each card features a waveform thumbnail of their `voice-sample` or a generated preview of their `custom-voice`. 
* **State-Based Badges:** Use color-coded chips for `Location` (e.g., Blue for "Cave," Green for "Exterior") and `Emotion` (e.g., Red for "Frustrated").
* **Quick CRUD:** Hovering over a card reveals "Duplicate" (perfect for creating `Hendrix-echo` from `Hendrix`) and "Delete" icons.



---

## 2. Three-Pane Configuration Layout
To handle the depth of the YAML (especially the SoX effects strings), a three-pane layout provides the best workflow for technical users.

| Pane | Purpose | Details |
| :--- | :--- | :--- |
| **Left: Library** | Navigation & Sorting | Filter by **Character State** or **Language**. Search bar at the top. |
| **Middle: Canvas** | Character Definition | Edit `name`, choose `speaker` (Aiden, Ryan, etc.), and text-input for `instruct`. |
| **Right: FX Rack** | Effects Stack | A vertical stack of **SoX Effects**. Users can drag-and-drop to reorder (e.g., putting `gain` before or after `reverb`). |



---

## 3. The "Voice Weaver" Filter System
Because you need to sort by **State, Emotion, Location, and Effect**, a standard dropdown isn't enough. Use a **Matrix Filter** or a **Tag Cloud**.

* **Dynamic Attributes:** When you create a character, you can tag them with attributes like "Rough Texture" or "Young Female."
* **The "Variant" Toggle:** Group related voices. For example, `Yamato` and `Yamato-vc` are collapsed under a single "Yamato" header, expandable to see variations based on location (`-echo`).

---

## 4. Audio Processing Visualizer (Mockup Idea)
For the `sox-effects` strings (like your `pitch -400 echo...`), the UI should translate that code into visual sliders and nodes.

* **Effect Modules:** Instead of typing `pitch -250`, the user moves a slider. 
* **Live Preview:** A "Test Voice" button that runs the current YAML config against a snippet of text and displays the output waveform in real-time.
* **The "Instruct" Helper:** For Qwen3-TTS `instruct` strings, provide a list of "Vibe Keywords" (e.g., *Gruff, Mellow, Edgy*) that auto-populate the YAML field.

---

### Implementation Suggestion
Since your data is already in YAML, you might consider a **Schema-Driven UI**. Using a framework like *React-JSON-Schema-Form* would allow you to automatically generate input fields for every key in your configuration while maintaining strict data types for the SoX effects.

Would you like me to help you draft the **JSON Schema** that would define these character objects for a frontend developer?


## Best TTS Systems for Emotional Delivery

What are the strengths and weaknesses of each of these TTS systems? Create a matrix of capabilities.

* Qwen3-TTS
* Orpheus-TTS
* OpenVoice
* Turtle-TTS
* Nari-Dia
* Chatterbox-TTS
* EmotiVoice-TTS

### Commercial TTS

* Hume.ai
* Grok-TTS
* ElevenLabs
* Cartesia
* Play.ht
* Deepgram
* Lovo.ai
* Fish.audio

-----

The modern TTS landscape has shifted from simple "text-to-audio" to sophisticated "multimodal" and "instruction-following" models. Below is a breakdown of the strengths and weaknesses for each system as of early 2026.

### TTS Capability Matrix

| System | Primary Strength | Key Weakness | Best Use Case | Latency |
| :--- | :--- | :--- | :--- | :--- |
| **Qwen3-TTS** | Natural language instruction (tone/style control) | High VRAM usage for 1.7B model | Narratives & precise voice design | Ultra-low (~97ms) |
| **Orpheus-TTS** | Massive scale & high-concurrency (Llama-based) | High computational cost per stream | Call centers & voice agents | Low (~130ms) |
| **OpenVoice** | Perfect separation of tone color vs. style | Inconsistent accent preservation | Cross-lingual cloning | Very Low (12x RT) |
| **Tortoise-TTS** | Elite prosody & multi-voice realism | Extremely slow (non-real-time) | Audiobooks & high-end media | Very High (Minutes) |
| **Nari-Dia** | Realistic multi-speaker dialogue & non-verbals | Random speaker assignment | Podcast & script prototyping | Moderate |
| **Chatterbox** | "Emotion Exaggeration" slider & MIT license | Newer ecosystem (fewer community tools) | Games & expressive characters | Low (<200ms) |
| **EmotiVoice** | Massive preset library (2,000+ voices) | Limited control beyond prompt basics | Batch generation & simple apps | Moderate |

---

### Deep Dive: Strengths & Weaknesses

#### ## Qwen3-TTS (Alibaba)
* **Strengths:** One of the most "intelligent" systems. It understands prompts like *"Warm, slightly edgy, moderately fast"* without needing manual parameter tweaks. It is highly robust in long-form content.
* **Weaknesses:** The 0.6B "light" version can struggle with stability, occasionally producing long silences in voice cloning tasks.

#### ## Orpheus-TTS (Sesame/Simplismart)
* **Strengths:** Designed for production. It uses a 3B Llama backbone, making it smarter at understanding context. It handles "non-word" sounds (like `<laugh>`) natively via special tokens.
* **Weaknesses:** Requires high-end hardware (H100s) to hit its advertised real-time benchmarks.

#### ## OpenVoice (MyShell)
* **Strengths:** Its "Normalizing Flow" architecture allows you to take a base voice and "wrap" another person's tone color around it perfectly while keeping the original's emotion and rhythm.
* **Weaknesses:** Often loses the subtle "native" accent of the source speaker during the conversion process.

#### ## Tortoise-TTS
* **Strengths:** The "gold standard" for open-source quality for years. It excels at "few-shot" cloning—give it 3 seconds of audio, and it captures the soul of the voice.
* **Weaknesses:** Practically unusable for interactive apps; it is strictly an "offline" renderer due to its heavy autoregressive/diffusion pipeline.

#### ## Nari-Dia (Nari Labs)
* **Strengths:** Specializes in **Dialogue**. It uses `[S1]` and `[S2]` tags to handle turn-taking and includes non-verbal cues like coughing or sneezing automatically.
* **Weaknesses:** Voice cloning is its weakest link; the cloned output often sounds "sped up" or unlike the original sample.

#### ## Chatterbox-TTS (Resemble AI)
* **Strengths:** Introduced the **Emotion Scale**. You can dial an emotion from 0.0 (monotone) to 1.5 (theatrical/over-acted). It is also fully MIT-licensed, making it the most "business-friendly" open model.
* **Weaknesses:** Installation can be finicky due to specific dependency requirements across different hardware (CUDA vs. Apple Silicon).

#### ## EmotiVoice-TTS (NetEase)
* **Strengths:** It is a "workhorse" for bilingual (English/Chinese) projects. If you don't want to clone a voice and just need a "happy female" or "angry male," it has 2,000+ options ready to go.
* **Weaknesses:** Focuses on pitch/speed/energy prompts rather than the deep semantic understanding found in Qwen3 or Orpheus.

**Would you like me to generate a sample YAML configuration for one of these specific systems, like Chatterbox's emotion parameters?**

## Commercial TTS API based offerings

The commercial landscape for "Smart TTS" has evolved into **Speech-Language Models (SLMs)**. Unlike traditional TTS, these systems are "LLM-native," meaning they understand the semantic context of your text to automatically apply appropriate prosody, emotion, and emphasis.

Here are the top commercial providers that offer extensive character libraries, granular emotion control, and robust API access.

### 1. Hume.ai (The "Empathic" Leader)
Hume's **Empathic Voice Interface (EVI)** is built specifically to detect and generate emotional nuance. It is a "multimodal" model that doesn't just read text; it understands the "vibe."
* **Characters:** A curated library of highly expressive voices (e.g., "Campfire Narrator," "Mysterious Woman") plus custom voice design via natural language descriptions.
* **Emotion Control:** Advanced. It responds to the user's tone and can be prompted to speak with specific emotional "measures" (e.g., calmness, interest, or sympathy).
* **API:** Real-time WebSocket streaming for ultra-low latency (~300ms) interactions.

### 2. ElevenLabs (The Gold Standard for Realism)
ElevenLabs remains the dominant player for high-fidelity content and character-driven narration.
* **Characters:** Thousands of community-generated and professional voices.
* **Emotion Control:** Their **v3 Conversational** model supports "Audio Tags" like `[laughs]`, `[whispers]`, or `[sighs]`. You can also guide delivery through the system prompt (e.g., "Respond in a calm, reassuring tone").
* **API:** Highly mature REST and WebSocket APIs with specific models for "Turbo" (low latency) or "HD" (high quality).

### 3. Fish.audio (The "Open-Weights" Powerhouse)
Fish Audio has quickly become a favorite for developers due to its **S2 (Speech-to-Speech)** and **S2-Pro** models which allow for unprecedented inline control.
* **Characters:** Massive multilingual support (80+ languages) with a heavy focus on custom voice cloning.
* **Emotion Control:** Uses **Inline Natural Language Tags**. You can insert tags directly into the text, such as `[whisper in small voice]` or `[professional broadcast tone]`, with support for over 15,000 expressive variations.
* **API:** Optimized for modern GPU serving (SGLang) with a time-to-first-audio of ~100ms.

### 4. Cartesia (The Speed King)
Cartesia’s **Sonic** model is built for speed and expressive "character" delivery, often used in high-end AI gaming and virtual avatars.
* **Characters:** Flexible voices across many accents; known for "Sonic-3" which produces studio-grade audio.
* **Emotion Control:** Offers a "Voice Changer" (Speech-to-Speech) that preserves the original speaker's emotion, as well as text-based controls for pacing and intonation.
* **API:** Features a blazing fast **40ms to 90ms** time-to-first-audio, making it the fastest on this list for real-time agents.

### 5. Grok-TTS (xAI)
Recently integrated into the X/xAI ecosystem, Grok's voice API is an end-to-end model that reasons directly in the audio domain.
* **Characters:** Integrated into the Grok Voice Agent; focuses on natural, conversational speech rather than a massive library of "fantasy" characters.
* **Emotion Control:** Since it "thinks" in audio, it naturally handles interruptions and shifts in tone based on the conversation's context.
* **API:** Now available via `console.x.ai`, offering sub-second response times and full-duplex communication support.

### 6. Deepgram (Aura-2)
Deepgram's **Aura-2** is designed for the enterprise, balancing human-like prosody with the scale needed for call centers.
* **Characters:** 40+ high-quality English voices across various demographics and professional styles.
* **Emotion Control:** Optimized for "conversational flow." It handles technical terminology and numbers with high precision while maintaining a natural, non-robotic rhythm.
* **API:** Unified STT + TTS API that significantly reduces integration complexity for voice agents.

### Summary Comparison Table

| Provider | Key Feature | Emotion Control Method | Best For |
| :--- | :--- | :--- | :--- |
| **Hume.ai** | Empathic Intelligence | Measures vocal "vibe" | Therapeutic or High-EQ Agents |
| **ElevenLabs** | High-Fidelity Realism | Bracketed Tags (e.g., `[sighs]`) | Audiobooks & Content Creation |
| **Fish.audio** | Word-level Control | 15k+ Natural Language Tags | Developers & Creative Teams |
| **Cartesia** | Ultra-Low Latency | Sliders/Speech-to-Speech | Real-time Gaming & Avatars |
| **Grok-TTS** | Audio-native Reasoning | Implicit Contextual Flow | Fast-paced Conversational AI |
| **Deepgram** | Enterprise Scale | Prosody-optimized Models | Customer Support & IVR |

## 