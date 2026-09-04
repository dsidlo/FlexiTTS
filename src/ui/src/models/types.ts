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

export interface EmotionConfig {
  emotion?: string;
  name?: string;
  instruct?: string;
  'sox-effects'?: string[];
}

export interface ClonedEmotionConfig {
  emotion: string;
  'voice-sample': string;
  'sox-effects'?: string[];
}

export interface CharacterConfig {
  name: string;
  'voice-sample'?: string;
  'sox-effects'?: string[];
  'custom-voice'?: {
    language: string;
    speaker: string;
    instruct: string;
    emotions?: EmotionConfig[];
  };
  'dialog-effects'?: string[];
  emotions?: EmotionConfig[];
  'cloned-emotion'?: ClonedEmotionConfig[];
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
