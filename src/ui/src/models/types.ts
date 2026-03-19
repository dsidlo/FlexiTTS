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
  'llm-xml-generator': any[];
  'dialog-effects': any[];
  'story-audio-post-process': any;
  characters: CharacterConfig[];
}

export interface CharacterConfig {
  name: string;
  'voice-sample'?: string;
  'sox-effects'?: string[];
  'custom-voice'?: {
    language: string;
    speaker: string;
    instruct: string;
  };
  'dialog-effects'?: string[];
}

export interface DialogValidationIssue {
  code: 'missing-character' | 'invalid-custom-voice' | 'invalid-voice-sample' | 'invalid-dialog-effects';
  message: string;
}

export interface DialogElement {
  _index?: number;
  dlgseq: string;
  sectionId?: string; // Optional section sequence
  character: string;
  text: string;
  validationIssues?: DialogValidationIssue[];
  // Other XML attributes (e.g. emotion, tone, pace)
  attributes: Record<string, any>;
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
    [key: string]: any;
  };
  summary?: any;
  metadata?: any;
  // Explicit properties from get_comprehensive_render_state()
  stale_dialogs?: string[];
  timestamp_stale?: string[];
  [key: string]: any;  // Allow any additional properties from Python comprehensive function
}
