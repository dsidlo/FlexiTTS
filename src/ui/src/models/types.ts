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
  id: string; // Internal id for React mapping
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
