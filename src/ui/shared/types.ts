// Re-export types from src/models/types for shared usage
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
  id: string;
  sectionId?: string;
  character: string;
  text: string;
  attributes: Record<string, any>;
}

export interface Chapter {
  fileName: string;
  name: string;
  dialogs: DialogElement[];
}

// Chapter data for UI state
export interface ChapterData {
  fileName: string;
  chapterName: string;
  dialogs: DialogElement[];
}

// FlexiTTS Story Management Types
export interface StoryInfo {
  name: string;
  path: string;
  directory_name: string;
}

export interface FlexiTTSConfig {
  FlexiTTS: {
    'stories-dir': string;
    'story-dir-prefix': string;
  };
}

// Extended types for story configuration
export interface ExtendedStoryConfig extends StoryConfig {
  max_voice_cache_size?: number;
  tts_device?: string;
}

// Chapter context with story information
export interface ChapterContext {
  storyInfo: StoryInfo;
  chapterPath: string;
  storyConfig: ExtendedStoryConfig;
}
