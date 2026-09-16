# FlexiTTS — Features Worth Borrowing

Research notes on comparable open-source LLM-annotated / multi-voice audiobook projects, and the
specific features from them that are worth adopting in FlexiTTS. Each item is written as a
candidate for a future PR: what it is, why it helps, where it would land in this codebase, and
how we would know it works.

## Reference projects

| Project | Stack / approach | Why it is relevant |
|---------|------------------|--------------------|
| [Finrandojin/alexandria-audiobook](https://github.com/Finrandojin/alexandria-audiobook) | Qwen3-TTS, LLM annotates book to structured JSON, per-character voice cards, voice-design + LoRA, second LLM "review script" pass, MP3 / M4B / Audacity export | Closest twin to FlexiTTS |
| [dudarenok-maker/Castwright](https://github.com/dudarenok-maker/Castwright) | Kokoro + Qwen3-TTS, LLM casts characters, voice consistency across a whole series, M4B / Audiobookshelf export | Multi-book voice identity |
| [Xerophayze/TTS-Story](https://github.com/Xerophayze/TTS-Story) | Web studio for tagged scripts: speaker management, chunk review/regeneration, job queue, multi-backend | Job queue + review UX |
| [DrewThomasson/VoxNovel](https://github.com/DrewThomasson/VoxNovel) | BookNLP quote attribution + GUI to correct speaker assignment | Speaker-correction UI |
| [DrewThomasson/ebook2audiobook](https://github.com/DrewThomasson/ebook2audiobook) | Broad format/language coverage, inline SML tags | Input format breadth |
| [Stiven-Gjekaj/OpenBook](https://github.com/Stiven-Gjekaj/OpenBook), [hneal98/NarraVoice](https://github.com/hneal98/NarraVoice), [denizsafak/abogen](https://github.com/denizsafak/abogen) | Qwen3-TTS instruct presets, captions, curated "similar projects" list | Preset libraries |

## Where FlexiTTS is already ahead

Keep these as the differentiators; borrowed features should not erode them.

- **XSD-validated XML intermediate format** (`schema_unified.xsd`, `chapter_validate_xml.py`) — most
  competitors use ad-hoc JSON or inline tags. A real schema gives validation and stable diffs.
- **SoX effect chains per character *and* per emotion**, plus dialog-level effects (e.g. `cave`).
  No comparable project does audio post-processing pipelines.
- **Electron desktop app with per-dialog clip regeneration** (`--create-missing-clips`) —
  competitors are Gradio/web/CLI and regenerate at chunk granularity at best.

---

## 1. Second LLM review pass for speaker misattribution

*Source: alexandria-audiobook*

**What** — After `chapter_to_xml.py` produces annotated XML, run a second, cheaper LLM pass whose
only job is to re-read the chapter alongside the annotation and flag/repair lines attributed to the
wrong speaker (the classic failure mode: unattributed dialogue absorbed into `Narrator`, or
speaker carry-over across a scene break).

**Why** — Highest-value, lowest-cost accuracy win available. Misattribution is the error users
notice immediately in the rendered audio, and it currently has to be fixed by hand in the XML.

**Where**
- New script `src/scripts/chapter_review_xml.py` (or a `--review` flag on `chapter_to_xml.py`).
- New prompt file alongside `FlexiTTS-AI-Prompt-Chapter-to-XML.md`, e.g.
  `FlexiTTS-AI-Prompt-Review-XML.md`, returning either corrected XML or a list of
  `{dialog-id, current-speaker, suggested-speaker, confidence, rationale}`.
- Output must still pass `chapter_validate_xml.py` against `schema_unified.xsd`.
- UI: surface suggestions in `DialogBar` as an accept/reject affordance rather than silently
  rewriting, wired through `pythonBridge.ts`.

**Notes / risks** — Make the pass opt-in and idempotent; never let it silently drop dialog. Prefer
the suggestion-list form so the review is auditable and reversible.

**Done when** — Running the review pass on a chapter with known seeded misattributions recovers
them, the reviewed XML validates, and rejecting all suggestions leaves the file byte-identical.

## 2. Speaker aliases

*Source: alexandria-audiobook*

**What** — Allow a character to declare alternate names that the LLM may emit: `YOUNG ELENA`,
`ELENA'S MOTHER`, `THE STRANGER` all resolving to one configured character (optionally with a
different default emotion).

**Why** — Removes a whole class of "unknown character" failures during audio generation, and makes
flashbacks / disguises / epithets work without duplicating voice configuration.

**Where**
- `story-config.yml`: `aliases:` list on each character entry; extend the schema check in
  `validate_config.py`.
- Resolution in `chapter_xml_to_audio.py` when mapping a dialog's speaker to a voice.
- Optionally allow the alias list to be injected into the annotation prompt so the LLM prefers
  canonical names.
- UI: an aliases field in the Characters dialog (see `docs/FlexiTTS Create Character UI.md`).

**Done when** — A chapter referring to a character only by an alias renders with the correct voice,
and a duplicate/conflicting alias is rejected by config validation with a clear message.

## 3. Cross-chapter / cross-book voice consistency

*Source: Castwright*

**What** — Promote voice identity above the single story: a shared voice library that multiple
stories reference, so a recurring character keeps the same speaker, instruct text, sample and SoX
chain across chapters and across books in a series.

**Why** — Today voice configuration lives per story config, so a series means copy-paste and drift.
This is also the natural home for the character import/export already specced for the Characters UI.

**Where**
- A user-level library (e.g. `~/.flexitts/voices/*.yml`) that `story-config.yml` can reference by
  id, with local per-story overrides winning.
- `validate_config.py` resolves references and reports unresolved ids.
- UI: library browser plus "copy from library" / "publish to library" in the Characters dialog;
  reuse the planned import/export merge-vs-replace dialog.

**Notes / risks** — Keep the story config self-describing enough to stay reproducible: either vendor
the resolved voice into the story on render, or record the library version used.

**Done when** — Two stories referencing one library character produce identical voice settings, and
editing the library entry propagates to both while a local override still takes precedence.

## 4. M4B / chaptered export and Audiobookshelf-friendly output

*Source: Castwright, alexandria-audiobook*

**What** — Extend output beyond per-chapter WAV: MP3 and chaptered M4B for the whole book, with
chapter markers, embedded cover art and metadata (title, author, narrator, series).

**Why** — This is the last mile of an audiobook tool. Right now the artifact is
`story-audio/<NN-Chapter>.wav`, which no audiobook player consumes comfortably.

**Where**
- New script `src/scripts/story_to_audiobook.py` that consumes the existing per-chapter WAVs.
- Requires `ffmpeg` (and optionally `mp4v2`); add to documented prerequisites next to SoX.
- Metadata source: a `book:` block in `story-config.yml` (title, author, series, cover image).
- UI: an "Export audiobook" action with format choice and progress reporting.

**Done when** — Exported M4B opens in a standard player with correct chapter list, duration and
metadata, and re-export is deterministic given unchanged chapter WAVs.

## 5. Multi-track / Audacity project export

*Source: alexandria-audiobook*

**What** — Optionally emit a multi-track project (one track per character, clips placed at their
timeline offsets) rather than only a flattened mix.

**Why** — Lets power users do final mastering, ducking and music beds in a real DAW while keeping
FlexiTTS as the generation engine. Cheap to build because per-dialog clips already exist.

**Where** — `chapter_xml_to_audio.py` already knows clip order and durations; add an exporter that
writes an Audacity `.lof`/project or a simple timeline manifest (JSON/EDL) next to
`story-audio/clips/<NN-Chapter>/`.

**Done when** — Importing the exported project reproduces the same chapter audio as the merged WAV
within a small tolerance.

## 6. Generation job queue with per-clip status

*Source: TTS-Story*

**What** — A real queue in front of TTS generation: queued / running / done / failed per dialog,
cancel, retry-failed, and re-queue a selection — instead of a single long blocking run.

**Why** — Chapter generation is long and failure-prone (GPU OOM, service restart). A queue makes
progress visible, makes partial failure recoverable, and pairs naturally with the existing
`--create-missing-clips` behaviour.

**Where**
- Python: a queue/worker layer around clip generation in `chapter_xml_to_audio.py`, emitting
  structured per-clip progress events.
- Bridge: extend the WebSocket TTS-state channel in `pythonBridge.ts` to carry per-clip events.
- UI: per-dialog status indicator in `DialogBar`, a queue panel, and cancel/retry controls; reuse
  `useTtsAlerts` / `useAlerts` for failure surfacing.

**Done when** — Killing the TTS service mid-run leaves the queue in a `failed` state for the
affected clips only, and "retry failed" completes the chapter without regenerating good clips.

## 7. Colour-coded speaker review view

*Source: VoxNovel*

**What** — A chapter-wide review mode where each speaker has a stable colour, making attribution
errors visible at a glance, with bulk reassignment of selected lines.

**Why** — Complements feature 1: the LLM proposes, the human verifies fast. Reading a whole chapter
one `DialogBar` row at a time is the current bottleneck.

**Where** — `DialogBar` / chapter view in `src/ui/src`, with colour assignment derived
deterministically from the character list; bulk assign already sketched in
`docs/FlexiTTS Create Character UI.md` ("Bulk Assign", `Ctrl+Shift+A`).

**Notes / risks** — Colours must respect the high-contrast/accessibility goals already stated in the
Characters UI doc; never encode speaker identity by colour alone.

**Done when** — A chapter renders with per-speaker colouring, multi-select reassignment writes valid
XML, and the view is fully keyboard navigable.

## 8. Instruct / voice-design preset library

*Source: NarraVoice, OpenBook*

**What** — A curated, shipped set of `instruct` presets ("gruff older man, slow and deliberate",
"bright young woman, fast and clipped") and matching SoX chains, selectable as a starting point when
creating a character or emotion.

**Why** — Writing good instruct prompts is the hardest part of onboarding. Presets make the
Characters dialog immediately useful and document by example what Qwen3-TTS responds to.

**Where** — A data file (e.g. `src/scripts/presets/voice_presets.yml`) consumed by both the config
validator and the UI; in the Characters dialog, "start from preset" on character and emotion
creation, with the preset copied (not referenced) so it stays editable.

**Done when** — Creating a character from a preset yields a working voice with no further editing,
and the preset list is extensible without code changes.

## 9. Broader input formats

*Source: ebook2audiobook*

**What** — Accept EPUB (and optionally plain text / HTML) in addition to Markdown chapters, with
automatic chapter splitting into the existing per-chapter Markdown files.

**Why** — Removes the manual "convert the book to Markdown chapters" prep step that currently gates
the whole pipeline.

**Where** — A new front-end script `src/scripts/book_to_chapters.py` producing the Markdown chapter
files the pipeline already expects, so nothing downstream changes.

**Notes / risks** — Keep it strictly a pre-processing step; do not let new formats leak into the
XML/XSD contract.

**Done when** — Importing an EPUB produces correctly ordered, correctly named chapter Markdown files
that run through the existing pipeline unmodified.

## 10. Voice-design with generated reference audio + style text

*Source: alexandria-audiobook*

**What** — Alexandria pairs Qwen3-TTS voice *design* with generated reference audio plus style text,
which suggests the limitation noted in the root `README.md` — that cloned/reference voices cannot be
given emotion instructions — may be avoidable.

**Why** — If confirmed, it unifies the two character models in
`docs/FlexiTTS Create Character UI.md`: reference-voice characters would gain per-emotion instruct
support instead of needing one recorded sample per emotion.

**Where** — Investigation first, against `Qwen3-TTS/` and `Qwen3-TTS_server/`; then, if viable, a
per-emotion `instruct` field for `qwen3-tts-voice-design` characters and a corresponding schema
update in `validate_config.py`.

**Notes / risks** — Unverified; treat as a spike, not a committed feature. Confirm against the
Qwen3-TTS API actually vendored here rather than upstream docs.

**Done when** — A spike note documents whether reference-voice + instruct works on our pinned
Qwen3-TTS, with A/B audio samples, and the root `README.md` limitation is either removed or
restated precisely.

## 11. Render whole story / whole chapter from the UI, with re-render confirmation

*Source: FlexiTTS UI requirement*

**What** — Two new top-level actions in the UI: **Render Chapter** and **Render Story**. Both drive
`chapter_xml_to_audio.py`, but the mode depends on what already exists on disk:

- If **no** dialog clips exist for the target scope, render straight away in batch/full mode —
  effectively `--create-missing-clips` over every chapter in scope, with no prompt.
- If dialog clips **do** exist for any chapter in scope, block on a confirmation dialog:

  > *Recorded Dialogs currently exist for this **Chapter**. Are you sure that you want to re-render
  > all dialogs for this **chapter**?*

  (with `Story` / `story` substituted for the story-scoped action). Confirming forces a full
  re-render of every dialog in scope, ignoring existing clips; cancelling aborts without touching
  any audio.

**Why** — Today the UI is a per-dialog tool: renders go through `--section` / `--dlgseq`, one clip at
a time, and a first-pass render of a new chapter (or a whole story after a global config or voice
change) has to be done from the CLI. Full-scope rendering is exactly the case where batching pays
off (see the deferred-batching note below), and it is the one operation where an accidental click is
expensive — hence the explicit confirmation whenever recorded dialog already exists.

**Where**
- **Scope discovery** — enumerate chapters for the story from the XML directory (`global.story-xml`)
  and existing clips from `story-audio/clips/<NN-Chapter>/`; reuse the persisted render state
  (`.chapter_rendered.json`, `ChapterRenderState` in `src/ui/src/models/types.ts`) rather than
  re-globbing where possible.
- **Existing-audio probe** — a cheap "does any clip exist in scope" check in `chapterService.ts`
  (chapter scope) plus a story-level aggregate; must also count the merged
  `story-audio/<NN-Chapter>.wav`.
- **Bridge** — new `renderChapter(story, chapter, { force })` and
  `renderStory(story, { force })` entry points in `pythonBridge.ts`, calling
  `chapter_xml_to_audio.py` with neither `--section` nor `--dlgseq`; `force` selects full re-render
  vs. `--create-missing-clips`.
- **Script** — story scope means iterating chapters; either loop in the bridge (one process per
  chapter, simplest and keeps per-chapter progress) or add a `--all-chapters` flag. A `--force`
  (or `--overwrite`) flag is needed so the UI can request a genuine re-render rather than the
  skip-existing behaviour at `chapter_xml_to_audio.py:607`.
- **UI** — actions in `TopBar` (chapter-scoped) and next to `StoryDropdown` (story-scoped); a
  confirmation modal whose noun is parameterised (`Story` / `Chapter`); progress and per-clip
  alerts through `useTtsAlerts` / `useAlerts`; disable both actions while a render is in flight.

**Notes / risks**
- The confirmation text is user-facing copy and must interpolate the scope noun with correct
  capitalisation in both the sentence-initial and mid-sentence positions.
- Story-scope runs are long: they need cancel support, and a failure part-way must leave already
  rendered chapters intact. This is the strongest argument for landing **feature 6** (job queue)
  first, or at least alongside.
- A forced re-render discards hand-tuned clips. Consider stating the clip count in the confirmation
  ("42 recorded dialogs across 3 chapters") so the cost is explicit.
- Full-scope render is the *only* place chapter-level batching would help; keep it CLI/script-side
  behind a `--batch-size` flag so the per-dialog UI path and its per-clip progress reporting stay
  untouched.

**Done when** — Rendering a chapter with no existing clips starts immediately and produces all
clips plus the merged chapter WAV; rendering a chapter or story that has any existing clips shows
the confirmation with the correct scope noun; cancelling leaves every clip and its mtime unchanged;
confirming regenerates every dialog in scope even where clips already existed; and a mid-run failure
leaves previously completed chapters valid.

---

## Considered and deferred: batching in the UI

Chapter-level batched generation (one `generate_*` call per character with a list of texts) was
evaluated and **deliberately deferred for the UI path**. Qwen3-TTS supports it natively and the
`by_character` grouping in `chapter_xml_to_audio.py` is already the right partition, but the UI's
dominant workload is tweak-one-dialog / re-render-one-clip, where `--section` / `--dlgseq` renders
are N=1 and a batch of one is identical to today's call. Batching there would also require
batch-aware progress reporting (the per-clip alerts and the `Generating chapter_…` match in
`pythonBridge.ts`), turn per-clip failure isolation into whole-batch loss, and add VRAM chunking and
OOM-retry work — all to accelerate the operation users rarely run.

If wanted, scope it as a **CLI-only `--batch-size` flag**, active only when neither `--section` nor
`--dlgseq` is given, i.e. exactly the full-scope renders introduced in feature 11. The felt speedup
in the UI comes instead from eliminating the per-render Python process spawn (`pythonBridge.ts:463`)
via a persistent worker.

---

## Prerequisites for features 12 and 13

Cheap, low-risk, and they de-risk both pipelines. Land them first.

1. **Supply `ref_text` and stop defaulting to `x_vector_only_mode=True`** (`tts_local.py:145`,
   `tts_models/adapters/qwen3/adapter.py:194`). Per `Qwen3-TTS/README.md`, x-vector-only mode skips
   ICL and "cloning quality may be reduced"; ICL mode is where prosody transfer lives. Add a
   `ref-text:` sibling field next to every `voice-sample` in `story-config.yml`.
2. **Delete the dead `instruct=` on `generate_voice_clone`** (`tts_local.py:245`, `adapter.py:287`).
   The Base/clone checkpoint has no `instruct` parameter and never builds `instruct_ids`; the value
   falls through `**kwargs` into HuggingFace `generate()` and is discarded. Right now the code reads
   as though the feature works.
3. **Implement `cloned-emotion[].voice-sample`** — already declared in
   `src/ui/src/models/types.ts:25-29` and read at `chapter_xml_to_audio.py:641-651`, but the sample
   is ignored and only the top-level `voice-sample` is ever loaded. Emotion via *which recording is
   cloned* is the zero-new-model baseline that features 12 and 13 must beat to justify their cost.

## 12. Reference voice + instruct, via driver → voice conversion

*Source: FlexiTTS requirement; alexandria-audiobook (design→clone); vendored `chatterbox-tts/`*

**What** — Per-emotion `instruct` for reference-voice (cloned) characters. Qwen3-TTS cannot do this
in one pass — clone and instruct are separate checkpoints (`-Base` vs `-1.7B-CustomVoice` /
`-VoiceDesign`, enforced by a `tts_model_type` guard) and Qwen's own released-models table leaves
"Instruction Control" blank for both Base models. So chain two passes:

```
instruct → generate_custom_voice(speaker=<driver>, instruct=…)      # the performance
         → ChatterboxVC(audio=driver_wav, target_voice_path=<character voice-sample>)
         → clip.wav                                                  # the identity
```

**Why** — It is the only route that keeps the character's *own recorded identity* while taking
emotion from text. It makes `cloned-emotion[].instruct` — currently read at
`chapter_xml_to_audio.py:649` then silently discarded — finally mean something, and it removes the
"one recording per emotion" burden that `docs/FlexiTTS Create Character UI.md` currently assumes.

**Where**
- New `src/scripts/tts_models/adapters/chatterbox/` — the provider seam already exists in
  `tts_factory.py` / `tts_interface.py`, and `adapters/` holds only `qwen3/` today.
- A `vc_stage` applied *after* generation and *before* SoX, so existing per-character / per-emotion /
  dialog effect chains layer on top unchanged.
- `story-config.yml`: opt-in `emotion-engine: custom-voice+vc` per character plus a pinned driver
  `speaker:` (otherwise prosody drifts between emotions and VC output gets inconsistent).
- VC model is already vendored — `chatterbox-tts/example_vc.py` provides
  `ChatterboxVC.generate(audio=…, target_voice_path=…)`. No FreeVC/OpenVoice dependency needed.

**Notes / risks**
- Two model passes per clip: slower and more VRAM. Keep opt-in per character; acceptable for the
  tweak-one-dialog loop, painful for full-scope renders (feature 11).
- VC smears consonants and can flatten extremes. A/B before committing.
- **A/B against the one-pass alternative first**: Chatterbox with cloning + `exaggeration`
  (`chatterbox-tts/gradio_tts_app.py`) gives cloned identity *and* continuous emotion control in a
  single call, but the identity is Chatterbox's clone, so a character cannot mix engines mid-story.
- Reference captioning → voice-design (describe the sample in `instruct`) is a cheap fallback for
  minor characters with no recording, but it does **not** preserve identity. Prompt-token
  concatenation against a "unified multi-codebook checkpoint" is not viable here — no such
  checkpoint is vendored and the clone path has nothing to condition an instruct block on.
- Overlaps **feature 10** (Qwen's documented design→clone workflow): 10 covers *designed* identities,
  12 covers *recorded* ones. Cross-reference rather than duplicate.

**Done when** — One character with three emotions renders via `custom-voice+vc`, A/B'd against
per-emotion recorded samples (prerequisite 3) and against Chatterbox-with-`exaggeration`, with a
documented preference; effects chains and per-dialog regeneration still work unchanged.

## 13. Voice-actor take → character voice (no instruct)

*Source: FlexiTTS requirement*

**What** — Bind a **recorded human performance** to a specific dialog line, then voice-convert it
onto the character's `voice-sample` so the delivery is the actor's and the identity is the
character's:

```
takes/<chapter>_<section>_<dlgseq>.wav → ChatterboxVC(target_voice_path=<character voice-sample>) → clip.wav
```

**Why** — Covers everything `instruct` cannot articulate: screams, sobbing, laughter mid-line,
whispered menace, specific comic timing. Instruct prompts are lossy paraphrases of a performance;
this is the performance itself. No comparable project supports actor-driven takes per line, so it is
a genuine differentiator, and it pairs naturally with the existing per-dialog regeneration and SoX
chains.

**Where**
- Same Chatterbox VC adapter and `vc_stage` as feature 12 — this is that pipeline run with recorded
  driver audio instead of synthesized.
- Granularity is **per dialog, not per emotion**: a `voice-take` attribute on the XML `<dialog>`
  element (with a `schema_unified.xsd` update) or a `takes/<chapter>_<section>_<dlgseq>.wav`
  convention discovered by `chapter_xml_to_audio.py`.
- Loudness + sample-rate normalisation of the driver audio before VC; actor takes arrive at wildly
  varying levels and that alone causes most VC artefacts.
- UI: drop a take onto the `DialogBar` row, re-render that one clip, listen — exactly the loop the
  UI already optimises for. Needs a visible "has take" indicator so a take is never invisible.

**Notes / risks**
- **Text-independent** — there is no `text=` in this path, so it bypasses the TTS front-end
  entirely, along with the 2000-character limit and language handling at
  `chapter_xml_to_audio.py:686`. The XML text becomes documentation only; the take is the source of
  truth, so drift between them must be surfaced (hash the take, warn if text changed).
- The take must survive `--create-missing-clips` and forced re-render (feature 11) — a re-render
  should re-run VC from the take, never fall back to TTS and silently discard the performance.
- Ironically the artefact risk is highest exactly where this feature shines: a scream may not
  survive conversion intact. A/B required.

**Done when** — Dropping a take on one dialog produces a clip with the actor's delivery and the
character's timbre; re-rendering the chapter preserves it; removing the take falls back to normal
TTS generation; and a take whose dialog text has since changed raises a visible warning.

---

## Suggested ordering

1. **Feature 1** (LLM review pass) and **feature 2** (aliases) — best accuracy-per-effort, no UI
   dependency.
2. **Feature 11** (render whole chapter / story from the UI) — closes the biggest functional gap in
   the UI; the confirmation guard makes it safe to ship on its own.
3. **The three prerequisites for features 12 and 13** — small, independent, and they improve clone
   quality (`ref_text` / ICL) and remove misleading dead code straight away.
4. **Feature 13** (voice-actor takes) before **feature 12** (reference voice + instruct) — they
   share one Chatterbox VC adapter, so build the VC stage once and both fall out of it; 13 is the
   stronger differentiator, has no driver-speaker tuning problem, and validates the VC stage against
   real audio. If VC smears a scream, better to know that before paying feature 12's two-pass cost.
5. **Feature 6** (job queue) and **feature 7** (speaker review view) — the two biggest UX wins;
   feature 7 depends on feature 1 being useful, and feature 6 makes feature 11's story-scope runs
   cancellable and recoverable.
6. **Feature 4** (M4B export) — completes the product story.
7. **Features 3, 5, 8, 9** — valuable but self-contained; schedule opportunistically.
8. **Feature 10** — spike alongside 12; it covers *designed* identities where 12 covers *recorded*
   ones.

Features 10, 12 and 13 all gate the same UI decision: whether the Characters dialog in
`docs/FlexiTTS Create Character UI.md` exposes **instruct text**, **emotion sliders**, or
**per-emotion recorded samples** for reference-voice characters. Spike them before that UI is
finalised.

---

## Appendix: story-config.yml key consistency rules

Authoring reference for the keys in `story-config.yml` whose values reference other keys or
external identifiers. Enforcement is split across two points: named-effect references are checked
at config-validation time; voice wiring is checked at render preflight
(`chapter_xml_to_audio.py::validate_character_voice_setup`) just before generation starts.

| # | Key | Must resolve to | Checked at | Enforced by |
|---|-----|-----------------|------------|-------------|
| 1 | `characters[].dialog-effects` entries | A `name` in the top-level `dialog-effects:` list | Config validation (hard fail) | `validate_config.py` cross-reference check |
| 2 | `characters[].voice-sample` | An existing audio file; relative paths resolve against the `global.voices` directory (absolute paths allowed) | Render preflight | `validate_character_voice_setup` |
| 3 | `characters[].custom-voice.speaker` | One of the nine documented Qwen3-TTS CustomVoice speakers: `aiden`, `dylan`, `eric`, `ono_anna`, `ryan`, `serena`, `sohee`, `uncle_fu`, `vivian` (case-insensitive match) | Render preflight | `QWEN3_DOC_SUPPORTED_SPEAKERS` in `chapter_xml_to_audio.py` |
| 4 | `<speaker>` in chapter XML | A `characters[].name` in `story-config.yml` (case-insensitive match) | Render preflight | `validate_character_voice_setup` |
| 5 | `voice-sample` vs `custom-voice` | Exactly one voice source per character | Render preflight | `validate_character_voice_setup` |

### Authoring rules

1. **Define named dialog-effects before characters reference them.** A character's
   `dialog-effects` entry is a *name reference*, not an inline effect chain. The effect must exist
   once at the top level with `name:` plus at least one `sox-effects:` list (the schema requires
   both). Multiple names on one character layer their chains.
2. **Do not double the `global.voices` prefix in `voice-sample`.** With `global.voices: refs/`,
   write `voice-sample: Ayana-voice.wav`, not `refs/Ayana-voice.wav` — the latter resolves to
   `refs/refs/…` and fails preflight with "voice-sample not found".
3. **Write `custom-voice.speaker` in canonical lowercase.** Render-time matching is
   case-insensitive, so `Uncle_Fu` works, but the canonical keys are lowercase (`uncle_fu`);
   keeping configs and comments in canonical form avoids drift against
   `QWEN3_DOC_SUPPORTED_SPEAKERS`.
4. **Exactly one voice source per character.** If both `voice-sample` and `custom-voice` are
   present, `custom-voice` wins and the sample is *silently ignored* — delete the unused one so
   the config states what actually renders. A character with neither fails render preflight with
   "has neither voice-sample nor custom-voice configured".
5. **Treat `characters[].name` as a primary key.** Chapter XML `<speaker>` values must match a
   configured name or rendering aborts with "referenced in XML but missing from
   story-config.yml". Renaming a character is a fan-out edit across every `story-xml` file;
   prefer stable canonical names and let per-character SoX chains carry variation. (Feature 2,
   speaker aliases, is the planned formalisation of nickname mapping.)
6. **Renaming a shared dialog-effect is also a fan-out edit.** The name in
   `dialog-effects[].name` is the single definition point; every `characters[].dialog-effects`
   entry referencing it must change in the same edit. `validate_config.py` catches any missed
   reference with "Named dialog-effect '…' used by character '…' is not defined."

### Verification after any config edit

```
python src/scripts/validate_config.py Stories/<Story-Name>/story-config.yml
```

This covers YAML syntax, the JSON schema, and rule 1 above. Rules 2-5 run automatically as part
of the render preflight before any clip is generated; a failure there aborts generation before
audio work begins.

