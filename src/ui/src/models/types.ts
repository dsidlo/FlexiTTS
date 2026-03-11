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

export interface DialogElement {
  _index?: number;
  dlgseq: string;
  sectionId?: string; // Optional section sequence
  character: string;
  text: string;
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
