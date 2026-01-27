# Qwen3-TTS Notes

## Voice Generation and Cloning

The **Qwen3-TTS** Python package (`qwen-tts`) provides a clean, high-level API through the `Qwen3TTSModel` class. The main generation functions are specialized based on the model variant you're loading:

- `generate_custom_voice` → for **CustomVoice** models (e.g., `Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice`)
- `generate_voice_design` → for **VoiceDesign** models (e.g., `Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign`)
- `generate_voice_clone` → for **Base** models (e.g., `Qwen/Qwen3-TTS-12Hz-1.7B-Base`)

All of them return a tuple: `(List[np.ndarray], int)` — a list of audio waveforms (one per input text) and the sample rate (usually 22050 or 24000 Hz).

They share many common parameters and support **batch inference** (pass lists for most args, with matching lengths). You can also pass any Hugging Face Transformers-style `generate` kwargs (e.g., `max_new_tokens=512`, `top_p=0.9`, `temperature=0.7`, `do_sample=True`) for fine-tuning output quality/length.

### Common Parameters (shared across functions)
- **`text`** (`str | List[str]`) — Required. The text to synthesize. Single string or list for batch.
- **`language`** (`str | List[str] = "Auto"`) — Language of the text. Supported: "Chinese", "English", "Japanese", "Korean", "German", "French", "Russian", "Portuguese", "Spanish", "Italian". Use `"Auto"` (or omit) for automatic detection.
- `**generate_kwargs` — Any extra kwargs passed to the underlying generation (e.g., `max_new_tokens`, `repetition_penalty`, etc.).

### 1. `generate_custom_voice` (CustomVoice models)
Best for using one of the 9 built-in premium speakers with optional style control.

**Signature**:
```python
generate_custom_voice(
    text: str | List[str],
    language: str | List[str] = "Auto",
    speaker: str | List[str],                # Required
    instruct: str | List[str] | None = None,
    **generate_kwargs
) -> Tuple[List[np.ndarray], int]
```

**Key Parameters**:
- **`speaker`** (`str | List[str]`) — Required. Built-in speaker name (e.g., "Vivian", "Ryan", "Serena", "Uncle_Fu", "Dylan", "Eric", "Aiden", "Ono_Anna", "Sohee"). Call `model.get_supported_speakers()` to list them.
- **`instruct`** (`str | List[str] | None`) — Optional natural language prompt for tone/emotion/style (e.g., "speak very angrily" or "用特别愤怒的语气说").

**Example**:
```python
wavs, sr = model.generate_custom_voice(
    text=["Hello world!", "How are you?"],
    language="English",
    speaker="Ryan",
    instruct="confident and enthusiastic tone"
)
```

### 2. `generate_voice_design` (VoiceDesign models)
For creating entirely new/custom voices purely from description — no reference audio needed.

**Signature**:
```python
generate_voice_design(
    text: str | List[str],
    language: str | List[str] = "Auto",
    instruct: str | List[str],               # Required for meaningful results
    **generate_kwargs
) -> Tuple[List[np.ndarray], int]
```

**Key Parameters**:
- **`instruct`** (`str | List[str]`) — Required. Free-form natural language description of the desired voice (e.g., "a childish spoiled loli female voice, very coquettish and high-pitched", or "deep gravelly male narrator with a dramatic British accent, slow and menacing").

**Example**:
```python
wavs, sr = model.generate_voice_design(
    text="哥哥，你回来啦！人家好想你哦～",
    language="Chinese",
    instruct="体现撒娇稚嫩的萝莉女声，音调偏高且起伏明显，黏人又刻意卖萌"
)
```

### 3. `generate_voice_clone` (Base models)
For cloning from a short reference audio clip (as low as 3 seconds).

**Signature**:
```python
generate_voice_clone(
    text: str | List[str],
    language: str | List[str] = "Auto",
    ref_audio: str | np.ndarray | tuple | None = None,   # or use voice_clone_prompt
    ref_text: str | None = None,
    voice_clone_prompt: dict | None = None,
    x_vector_only_mode: bool = False,
    **generate_kwargs
) -> Tuple[List[np.ndarray], int]
```

**Key Parameters**:
- **`ref_audio`** (`str | np.ndarray | tuple`) — Path/URL to audio file, base64 string, or `(audio_array, sample_rate)` tuple. Required if not using `voice_clone_prompt`.
- **`ref_text`** (`str | None`) — Exact transcript of the reference audio. Highly recommended for best alignment/quality (required unless `x_vector_only_mode=True`).
- **`voice_clone_prompt`** (`dict | None`) — Precomputed prompt from `model.create_voice_clone_prompt(...)`. Use this for efficiency when cloning the same voice multiple times (avoids re-extracting features).
- **`x_vector_only_mode`** (`bool = False`) — If `True`, uses only speaker embedding (faster, but lower quality cloning — skips prosody/timbre alignment).

**Helper: `create_voice_clone_prompt`** (to cache voices)
```python
create_voice_clone_prompt(
    ref_audio: str | np.ndarray | tuple,
    ref_text: str | None = None,
    x_vector_only_mode: bool = False
) -> dict
```

**Example (with caching)**:
```python
# Cache once
clone_prompt = model.create_voice_clone_prompt(
    ref_audio="path/to/ref.wav",
    ref_text="This is my reference speech."
)

# Then generate many times efficiently
wavs, sr = model.generate_voice_clone(
    text=["Line one.", "Line two."],
    language="English",
    voice_clone_prompt=clone_prompt
)
```

These are the primary generation entry points — no other `generate_*` methods exist in the current release. All support multilingual input, batching, and low-latency streaming under the hood. For the absolute latest details or any undocumented kwargs, check the source in the GitHub repo (especially `qwen_tts/model.py` or examples folder) or run `help(model.generate_voice_clone)` after loading a model.

If you're coding this up in Alameda tonight and hit any parameter-related errors, paste the traceback and I'll help debug!

# Custom Voice Generation

Qwen3-TTS (from the Qwen team at Alibaba Cloud) provides advanced capabilities for creating and using **custom voices** through open-source models, primarily via the `qwen-tts` Python package.

There are a few related but distinct ways to achieve "custom voices":

1. **CustomVoice models** (e.g., Qwen3-TTS-12Hz-1.7B-CustomVoice or 0.6B variant): These build on pre-fine-tuned premium speaker timbres with added style control. You don't create a brand-new voice from scratch but customize predefined ones.

2. **Voice Design models** (e.g., Qwen3-TTS-12Hz-1.7B-VoiceDesign): This is the primary way to create entirely novel/custom voices using free-form natural language descriptions.

3. **Voice Cloning** (via Base models): Creates a custom voice by cloning from reference audio (often combined with Voice Design for fully synthetic references).

The parameters depend on the approach and model.

### For CustomVoice Models (Style Control on Predefined Speakers)
Use the `generate_custom_voice` method.

**Key parameters**:
- `text`: The input text to synthesize (string or list for batch).
- `language`: Language of the text (string or list; e.g., "Chinese", "English", "Auto" for auto-detection).
- `speaker`: Predefined speaker ID (required; string or list). Supported speakers include:
  - Vivian (bright, edgy young Chinese female)
  - Serena (warm, gentle young Chinese female)
  - Uncle_Fu (seasoned, low/mellow Chinese male)
  - Dylan (youthful Beijing dialect Chinese male)
  - Eric (lively Sichuan dialect Chinese male)
  - Ryan (dynamic English male)
  - Aiden (sunny American English male)
  - Ono_Anna (playful Japanese female)
  - Sohee (warm, emotional Korean female)
- `instruct` (optional but key for customization): Natural language instruction to control style, emotion, prosody, etc. (string or list; e.g., "用特别愤怒的语气说" / "Very happy.", "Speak very softly and secretly", "Low-pitched and sad").

Additional generation kwargs (from Transformers) like `max_new_tokens`, `top_p`, etc., can be passed.

Outputs: List of waveforms (numpy arrays) and sample rate.

### For True Custom Voice Creation (Voice Design / Free-Form)
Use the `generate_voice_design` method on VoiceDesign models.

**Key parameters**:
- `text`: Input text to synthesize (string or list).
- `language`: Language (string or list; e.g., "Chinese", "English").
- `instruct`: The core parameter for creating the custom voice — a natural language description/prompt defining the voice. This can include:
  - Acoustic attributes: pitch (high/low/mid), speed (fast/slow), volume (loud/soft), clarity, fluency, accent, texture.
  - Identity: gender (male/female), age (young/middle-aged/elderly), personality (confident/extroverted/shy).
  - Emotion/tone: happy/sad/angry/enthusiastic/authoritative/sarcastic.
  - Prosody: rhythm, intonation, pauses, emphasis, gradual changes (e.g., "pitch stable then rising", "volume normal to shouting").
  - Persona/background: e.g., "17-year-old male gaining confidence", "sassy lolita girl voice, high pitch with obvious fluctuations, deliberately cutesy and clingy".
  Examples:
  - "A composed middle-aged male announcer with a deep, rich and magnetic voice."
  - "体现撒娇稚嫩的萝莉女声，音调偏高且起伏明显，营造出黏人、做作又刻意卖萌的听觉效果。"
  - "Male, 17 years old, tenor range, gaining confidence - deeper breath support now, though vowels still tighten when nervous."

This `instruct` effectively defines the custom voice parameters via descriptive text (no fixed structured fields like sliders; it's prompt-based).

Outputs: Waveforms and sample rate. You can then use the generated audio as a reference for cloning to make the voice reusable/persistent.

### Additional Notes
- In API contexts (e.g., DashScope/Qwen API, not purely local), voice design/cloning returns a reusable `voice` parameter (ID or name) after creation, along with preview audio. You then pass this `voice` to TTS synthesis calls.
- Local open-source usage focuses on per-inference `instruct` prompts rather than permanent saved profiles (though you can workflow-save references via cloning).
- Install: `pip install -U qwen-tts` (supports torch, flash-attn for efficiency).

For full examples and setup, see the official GitHub repo: https://github.com/QwenLM/Qwen3-TTS. The 1.7B models offer the best quality for detailed custom control.


## Sox Dialog Clip Post-Processing Tips

Here is a practical list of common voice effects achievable with **SoX**, including typical parameter combinations for speech/voice processing. These are based on real-world examples from SoX documentation, man pages, and community usage.

Most commands follow this pattern:  
`sox input.wav output.wav [effect1 params] [effect2 params] ... gain -n -1`  
(End with `gain -n -1` for safe peak normalization to -1 dB headroom.)

| Effect / Style              | SoX Command Example                                                                 | Key Parameters & Notes                                                                 | Typical Use Case |
|-----------------------------|-------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------|------------------|
| **Deeper voice**            | `pitch -350`                                                                        | -200 to -500 cents (≈ -2 to -5 semitones). Use `-q` for better quality on large shifts. | Male-sounding, authoritative, narration |
| **Higher / chipmunk voice** | `pitch +400`                                                                        | +200 to +800 cents. Often paired with `tempo` if you want speed change too.           | Cartoonish, excited, helium effect |
| **Robot / metallic**        | `overdrive 20 40 echo 0.8 0.88 6 0.4`                                               | Short echo delay + distortion. Add `synth sine fmod 30` for ring-mod robot vibe.      | Sci-fi robot, Dalek-like |
| **Heavy robot / Dalek**     | `overdrive 30 30 echo 0.4 0.8 15 0.8 synth sine fmod 30 echo 0.8 0.8 29 0.8`         | Ring modulation + layered echoes + distortion. Classic BBC Radiophonic style.         | Exterminate! style voices |
| **Echo / slapback**         | `echo 0.8 0.88 60 0.4`                                                              | gain-in 0.8, gain-out 0.88, delay(ms) 60, decay 0.4. Short = slapback, longer = canyon. | Radio, spacious speech |
| **Multiple echoes**         | `echo 0.8 0.9 100 0.35 180 0.3 300 0.25`                                            | Chain multiple delay/decay pairs. Good for mountain/hall feel.                        | Open space, reverb-like |
| **Reverb / hall**           | `reverb 50 50 100 100 0 0`                                                          | reverberance 50, hf-damping 50, room-scale 100, stereo-depth 100, pre-delay 0, wet-gain 0. | Bathroom, concert hall, large room simulation |
| **Small room / intimate**   | `reverb 30 60 40 80 20 -3`                                                          | Lower reverberance + some pre-delay + negative wet gain for subtle space.             | Podcast closeness, voice-over |
| **Phone / tinny**           | `highpass 300 lowpass 3400`                                                         | Cut lows <300 Hz, highs >3400 Hz. Add `gain -3` if needed.                            | Telephone, old radio, bandwidth-limited |
| **Muffled / hushed**        | `treble -5 5000 0.7 lowpass -2 4500`                                                | Gentle high-shelf cut + soft low-pass. Add light `compand` for dynamic control.       | Whispery, intimate, subdued |
| **Sibilance reduction**     | `equalizer 7000 -5 2.5`                                                             | Narrow cut at 6–9 kHz (s/z/sh zone). Q=2–4 for precision.                             | De-ess voice recordings |
| **Plosive / pop taming**    | `highpass 100 lowshelf -6 150 0.8 compand 0.05,0.2:6:-60/-50/-20 -3`                | Low-cut + shelf + fast compressor to squash bursts.                                   | Remove "P/B" thumps |
| **Breathy / airy**          | `treble +4 8000 compand 0.1,0.5:-90,-70,-60,-40 -3`                                 | Boost highs + upward expansion on quiet parts.                                        | Soft, ethereal voice |
| **Chorus / thickening**     | `chorus 0.7 0.9 50 0.4 0.25 2`                                                      | gain-in/out, delay(ms), decay, speed, depth. Multiple stages for thicker voice.       | Doubling, ensemble feel |
| **Flanger / jet-like**      | `flanger 20 10 60 50 25 sin`                                                        | Delay 20 ms, depth 10 ms, regen 60%, width 50%, speed 0.25 Hz.                        | Psychedelic, whooshy modulation |
| **Phaser / sweeping**       | `phaser 0.8 0.74 3 0.4 0.5 -s`                                                      | Similar to flanger but uses reverb-style phasing. `-s` for sin sweep.                 | Classic 70s/80s vocal effect |
| **Compression / leveling**  | `compand 0.3,1 6:-70,-60,-20 -4 -90 0.1`                                            | Fast attack/decay, gentle ratio, makeup -4 dB. Evens out speech dynamics.             | Podcast, consistent volume |
| **Light distortion / grit** | `overdrive 10 40`                                                                   | Drive 8–15 = warmth, 20+ = rough/gritty. Second param % undistorted signal.           | Raspy, aggressive voice |
| **Vibrato / pitch wobble**  | `tremolo 5 40` or `bend .5,200,.5`                                                  | `tremolo` for volume wobble; `bend` for pitch variation (start,cents,duration).       | Expressive, warbly singing/speech |

### Quick Tips
- **Order matters**: Usually process in this sequence: pitch/formant → EQ/filters → dynamics (compand/overdrive) → modulation (echo/reverb/chorus) → final gain.
- **Preview short clip**: Add `trim 0 10` at the end and use `play` instead of saving to file.
- **Avoid extremes**: Pitch shifts > ±600 cents often sound unnatural without formant correction (SoX doesn't preserve formants perfectly — consider Rubber Band for that).
- **Combine for custom voices**: e.g., deeper + robot: `pitch -400 overdrive 15 40 echo 0.8 0.88 8 0.4`
- **Stats check**: Run `sox input.wav -n stat` before/after to see amplitude changes.

These cover ~90% of common voice modifications people do with SoX. If you want a specific style (e.g., monster, alien, elderly, accent approximation), describe it and I can refine a chain!

### Grok Prompt - sox parameter generation

Give me sox parameters for a squiggly alien sounding voice.

#### Grok Response

Here are several **SoX** parameter chains to create a **squiggly alien-sounding voice** — think wobbly, warbly, undulating pitch/tremolo with metallic/ring-mod-like artifacts, sci-fi vibe, and some instability (the "squiggly" part comes mainly from modulated pitch wobble + tremolo + optional ring-mod simulation).

These work best on clear speech input. Apply to mono audio for cleaner results, and end with normalization.

### 1. Classic Squiggly Alien (Wobbly Pitch + Tremolo + Light Distortion)
```bash
sox input.wav output.wav \
  pitch -200 \                     # Slight pitch drop for eerie base (adjust -100 to -400)
  tremolo 8 60 \                   # Fast wobble: 8 Hz speed, 60% depth → squiggly vibrato
  overdrive 8 50 \                 # Mild distortion for metallic edge
  compand 0.1,0.5:6:-70/-50/-20 -4 -90 0.1 \  # Tame dynamics
  gain -n -1.5
```
- **Squiggly factor**: High from the `tremolo` at 6–12 Hz with 50–80% depth.
- Result: Warbling, unstable alien warble.

### 2. Strong Squiggly + Ring-Mod Feel (Most "Alien" Classic)
SoX doesn't have true ring modulation, but this approximates it with fast tremolo + pitch bend + distortion (common hack from audio communities).

```bash
sox input.wav output.wav \
  tremolo 12 70 \                  # Very fast wobble → ring-mod-like metallic squiggle
  pitch -300 \                     # Deeper eerie tone
  overdrive 15 40 \                # Gritty metallic timbre
  flanger 5 5 80 60 0.8 sin \      # Add sweeping whoosh for extra squiggle
  gain -n -2
```
- **Why squiggly**: `tremolo` at high speed + depth creates amplitude modulation that mimics ring mod sidebands when combined with distortion.
- Tweak: Increase tremolo speed to 15–20 Hz for more "buzzing alien" feel.

### 3. Bendy Squiggly Alien (Pitch Warble via Bend)
Uses SoX `bend` for slow-to-fast pitch undulations (great for "probing alien" squiggles).

```bash
sox input.wav output.wav \
  bend .8,300,.8,0,400,.6,-200,1.2 \  # Pitch bends: up 3 semitones, back to 0, down 2 semitones, etc.
  tremolo 5.5 45 \                 # Slower wobble layered on top
  treble +3 6000 \                 # Boost highs for glassy alien sheen
  overdrive 6 60 \
  gain -n -1
```
- `bend` syntax: duration(s),cents change,duration,...
- Creates organic squiggles as pitch sways up/down irregularly.

### 4. High-Pitched Squiggly Gremlin Alien
For smaller, frantic aliens.

```bash
sox input.wav output.wav \
  pitch +450 \                     # Chipmunk-high base
  tremolo 10 75 \                  # Rapid squiggle
  chorus 0.7 0.9 40 0.4 0.25 2 \   # Thickening + more wobble
  overdrive 12 45 \
  gain -n -1.5
```
- Result: Fast, jittery, cartoon-alien squiggles.

### 5. Full Sci-Fi Squiggly Package (Layered for Maximum Weirdness)
```bash
sox input.wav output.wav \
  pitch -250 \
  tremolo 9 65 \                   # Core squiggle
  flanger 10 8 70 50 1.2 tri \     # Sweeping modulation
  overdrive 10 50 \                # Metallic bite
  echo 0.7 0.75 40 0.4 \           # Short metallic reflections
  compand 0.08,0.3:8:-65/-55/-18 -5 -90 0.05 \
  gain -n -2
```
- Best for "transmission from space" alien voices.

### Tuning Tips for More/Max Squiggle
- **Increase squiggle intensity**: Raise `tremolo` depth (60–90) or speed (8–18 Hz). Higher speed = more ring-mod/buzzy alien.
- **Less intelligible**: Add stronger `overdrive` (15–25 drive) or narrow bandpass `equalizer 1500  -12 3` then boost highs.
- **Preview quickly**: Replace `input.wav output.wav` with `input.wav -n trim 0 8` and pipe to `play`:
  ```bash
  sox input.wav -n trim 0 8 tremolo 10 70 overdrive 12 50 gain -n | play -
  ```
- **If too harsh**: Reduce overdrive/distortion and add `reverb 20 40 30 60 10 -6` for spacey distance.

Start with #1 or #2 — they're the quickest path to a solid squiggly alien voice. Adjust the tremolo speed/depth first for the wobble feel you want. If it still doesn't hit the mark, describe the exact alien vibe (e.g., high-pitched gremlin vs. deep droning probe) for a refined chain!

## sox parameter testing

### Orgorobotic

```shell
play chapter_003_001_030_Ayana.wav \
  chorus 0.5 0.95 30 0.3 2.0 4.0 -t \
  flanger 5 5 90 95 3.0 tri \
  bend 0.15,300,0.4 0.4,-300,0.7 0.7,200,1.0 \
  overdrive 15 \
  treble +7 4500 \
  gain -n -3
```