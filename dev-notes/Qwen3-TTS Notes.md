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



