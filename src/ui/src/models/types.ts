export interface StoryConfig {
  global: {
    'story-dir': string;
    voices: string;
    chapters: string;
    'story-xml': string;
    logs: string;
    'story-audio': string;
    clips: string;
    'clip-separation': number;
  };
  'llm-xml-generator': Record<string, unknown>[];
  'dialog-effects': Record<string, unknown>[];
  'story-audio-post-process': unknown;
  characters: CharacterConfig[];
}

/**
 * Per-emotion entry for custom-voice (instruct-driven) characters.
 *
 * Emotion name is accepted as either `emotion` (canonical) or `name`
 * (legacy/alias form). `sox-effects` on an emotion overrides the
 * character-level `sox-effects` chain for that emotion.
 */
export interface EmotionConfig {
  emotion?: string;
  name?: string;
  instruct?: string;
  'sox-effects'?: string[];
}

/**
 * Per-emotion entry for sample-based (voice-design) characters.
 *
 * Each emotion clones a distinct reference recording; `sox-effects` and
 * `dialog-effects` override the character-level chains for that emotion.
 */
export interface ClonedEmotionConfig {
  emotion: string;
  'voice-sample': string;
  'sox-effects'?: string[];
  'dialog-effects'?: string[];
}

export interface CharacterConfig {
  name: string;
  /** Optional character description used by LLM annotation and UI tooltips. */
  description?: string;
  'voice-sample'?: string;
  'sox-effects'?: string[];
  /**
   * Custom-voice (built-in Qwen3-TTS speaker) configuration.
   *
   * Canonical YAML key remains `custom-voice`; `qwen3-tts-custom-voice` is
   * accepted as an alias (per docs/FlexiTTS Create Character UI.md) so the new
   * naming from the spec can be loaded without breaking
   * existing configs. Runtime code treats the two names as equivalent via
   * `customVoiceOf`.
   */
  'custom-voice'?: {
    language: string;
    speaker: string;
    instruct: string;
    /** Per-emotion instruct presets; each may override character SoX chain. */
    emotions?: EmotionConfig[];
  };
  /**
   * Voice-design (sample-based) character: one emotion per reference sample.
   * New spec naming for what `cloned-emotion` carries today; consumers that
   * read emotions should treat this list and `cloned-emotion` as the same
   * collection (`clonedEmotionsOf`).
   */
  'qwen3-tts-voice-design'?: ClonedEmotionConfig[];
  'dialog-effects'?: string[];
  /** Top-level emotion list shared by both voice kinds. */
  emotions?: EmotionConfig[];
  'cloned-emotion'?: ClonedEmotionConfig[];
}

/**
 * Resolve the custom-voice object regardless of whether the config uses the
 * legacy `custom-voice` key or the spec's `qwen3-tts-custom-voice` alias.
 */
export function customVoiceOf(
  character: CharacterConfig
): CharacterConfig['custom-voice'] | undefined {
  const rec = character as unknown as Record<string, unknown>;
  return (rec['custom-voice'] ?? rec['qwen3-tts-custom-voice']) as
    | CharacterConfig['custom-voice']
    | undefined;
}

/**
 * All sample-based emotion entries for a character, from either the legacy
 * `cloned-emotion` key or the spec's `qwen3-tts-voice-design` key.
 */
export function clonedEmotionsOf(character: CharacterConfig): ClonedEmotionConfig[] {
  const rec = character as unknown as Record<string, unknown>;
  return ((rec['cloned-emotion'] ?? rec['qwen3-tts-voice-design']) as ClonedEmotionConfig[]) || [];
}

export interface DialogValidationIssue {
  code: 'missing-character' | 'invalid-custom-voice' | 'invalid-voice-sample' | 'invalid-dialog-effects' | 'invalid-emotion';
  message: string;
}

export interface DialogElement {
  _index?: number;
  dlgseq: string;
  sectionId?: string; // Optional section sequence
  character: string;
  text: string;
  validationIssues?: DialogValidationIssue[];
  /**
   * MD5 signature of this dialog's content captured at the last successful
   * render. Lives in the XML as the `render_hash` attribute and is mirrored
   * into the in-memory model for instant client-side staleness checks.
   */
  renderHash?: string;
  /** Unix timestamp (ms) when this dialog's clip was last rendered. */
  renderedAt?: number;
  // Other XML attributes (e.g. emotion, tone, pace)
  attributes: Record<string, string | number | boolean>;
}

export interface Chapter {
  fileName: string;
  name: string;
  dialogs: DialogElement[];
}

// FlexiTTS Story Management Types (added by integration)
export interface StoryInfo {
  name: string;           // Display name (without prefix)
  path: string;           // Full path to story directory
  directory_name: string; // Full directory name (with prefix)
}

export interface FlexiTTSConfig {
  FlexiTTS: {
    'stories-dir': string;
    'story-dir-prefix': string;
  };
}

export interface AlertHistoryItem {
  id: string;
  message: string;
  type: 'info' | 'success' | 'warning' | 'error';
  source: 'internal' | 'tts-service';
  timestamp: Date;
}

export interface DialogRenderStatus {
  dialogId: string;
  hash: string;
  clipFile: string;
  renderedAt: number;
  clipExists: boolean;
  needsRender: boolean;
}

export interface ChapterRenderState {
  version?: number;
  story?: string;
  chapter?: string;
  xmlHash?: string;
  needsRender: boolean;
  isFullyRendered?: boolean;
  staleDialogs?: string[];
  staleCount?: number;
  chapterRenderedAt?: number;
  dialogCount?: number;
  // Timestamp-based staleness fields (added 2026-03-17)
  hasTimestampStale?: boolean;
  has_timestamp_stale?: boolean;  // Python uses snake_case
  timestampStaleDialogs?: string[];
  timestamp_stale_dialogs?: string[];  // Python uses snake_case
  dialogs?: Record<string, DialogRenderStatus>;
  error?: string;
  // Additional fields from comprehensive render state function
  status?: string;
  chapterState?: {
    reason?: string;
    [key: string]: unknown;
  };
  summary?: unknown;
  metadata?: unknown;
  // Explicit properties from get_comprehensive_render_state()
  stale_dialogs?: string[];
  timestamp_stale?: string[];
  [key: string]: unknown;  // Allow additional properties from Python comprehensive function
}
