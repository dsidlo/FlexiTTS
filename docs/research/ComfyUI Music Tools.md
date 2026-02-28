# ComfyUI Music Tools

**HeartMuLa** (the open-source music foundation model from early 2026) generates studio-quality songs or instrumentals from **two main inputs**: structured lyrics + style tags/descriptions. It works on the official web demo (heartmula.net – free unlimited beta), Hugging Face Spaces, Google Play app, ComfyUI nodes, or locally via the heartlib GitHub repo.

### Prompting Basics (works everywhere)
- **Lyrics field** (or `lyrics.txt` locally): Plain text. Use **[Section]** markers for structure and coherence.  
  Recommended sections: `[Intro]`, `[Verse 1]`, `[Pre-Chorus]`, `[Chorus]`, `[Bridge]`, `[Solo]`, `[Instrumental]`, `[Outro]`, `[Drop]`.
- **Style/Tags field** (or `tags.txt` locally): Comma-separated list (no spaces after commas) **or** natural-language description.  
  Best format (from the training data):  
  `genre,mood,instruments,vocal style,tempo/scene,...`  
  **Genre is the strongest anchor** — always include one first.

### 1. How to Prompt a Full Song (with vocals)
**Structure**  
Lyrics example (copy-paste ready):
```
[Intro]
[Verse 1]
Waking up to morning light, coffee in my hand
[Pre-Chorus]
Heart is racing, can't deny
[Chorus]
This is our summer, dancing through the night
Feel the rhythm, everything feels right
[Bridge]
[Outro]
```

**Style tags** (comma-separated):
```
indie pop, dreamy, female vocals, acoustic guitar, piano, uplifting, summer, 110bpm
```
**Natural-language version** (some interfaces accept this):
```
Dreamy indie-pop summer anthem, soft female vocals, warm acoustic guitar and piano, uplifting mood, reverb, studio quality, 110 bpm
```

**Result**: The model will sing the lyrics with the exact structure you gave and follow the style closely.

### 2. How to Prompt an Instrumental
Two easy methods:

**Method A – [Instrumental] tag (recommended)**  
Lyrics (keep it short or empty):
```
[Intro]
[Instrumental]
[Verse 1]  ← leave blank or put nothing
[Instrumental]
[Chorus]   ← leave blank
[Instrumental]
[Outro]
```

Style tags:
```
cinematic orchestral, epic, strings and brass, no vocals, building tension, film score, 90bpm, emotional, instrumental
```

**Method B – Empty lyrics + strong instrumental description**  
Leave the lyrics field completely blank or put only one line: `[Instrumental]`.

Style tags (or description):
```
instrumental, lo-fi chillhop, warm vinyl crackle, deep bass, jazzy piano, relaxing, study beats, 85bpm, no vocals, no singing
```

**Pro tip for solos/breaks**: In any song, add a line like  
`[Bridge] [Instrumental] Electric guitar solo, high energy`  
or just leave that section blank and describe the solo in the style tags.

### Tag Categories (use in this priority order for best control)
From the model’s training (8 pillars):
1. **Genre** (95% influence – always add): pop, rock, electronic, hiphop, jazz, classical, ambient, techno, cinematic…
2. **Timbre** (sound texture): warm, bright, dark, distorted, soft, gritty
3. **Vocal gender** (omit for instrumentals): male, female, choir
4. **Mood**: happy, sad, energetic, melancholic, uplifting, dreamy
5. **Instruments** (dominant sounds): piano, synthesizer, acoustic guitar, electric guitar, orchestral, strings, drums
6. **Scene**: dance, cinematic, workout, chill, party, film score
7. **Region**: k-pop, latin, western (optional)
8. **Topic**: love, summer, heartbreak (weakest – use sparingly)

**Rule**: One tag per category. Avoid conflicts (don’t mix “rock” + “jazz”).

### Quick Examples
**Upbeat pop song**  
Lyrics: [Verse 1] … [Chorus] …  
Tags: `pop, energetic, female, synthesizer, catchy, summer, 128bpm`

**Dark cinematic instrumental**  
Lyrics: `[Instrumental]` (or empty)  
Tags: `cinematic, dark ambient, orchestral, strings, brass, no vocals, epic, 70bpm, film trailer`

**Lo-fi chill instrumental**  
Tags: `lofi, chillhop, warm, vinyl crackle, jazzy piano, deep bass, relaxing, study, no vocals`

### Extra Tips for Better Results
- Start short → generate 30–60 seconds, then extend (most interfaces have an “extend” or continuation button). This gives much higher quality than one long generation.
- Reroll 3–4 times — the model has some randomness; pick the best seed.
- Local/ComfyUI users: higher `cfg_scale` (1.5–3.0) makes tags stick better; temperature 0.8–1.0 is sweet spot.
- Reference audio: upload a 10-second clip on supported interfaces to guide the vibe.
- Multilingual: works great in English, Chinese, Japanese, Korean, Spanish (and more).

Just paste structured lyrics + clear style tags and hit generate — that’s literally it.  

If you tell me which platform you’re using (web demo, ComfyUI, local install, app, etc.) I can give exact screenshots-style steps or ready-to-copy prompt templates!  

What kind of song or instrumental are you trying to make first? 😊

