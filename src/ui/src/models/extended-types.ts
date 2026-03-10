// Extended types for FlexiTTS story management

export interface StoryInfo {
  name: string;           // Display name (without prefix)
  path: string;           // Full path to story directory
  directory_name: string; // Full directory name (with prefix)
}

// Extended StoryConfig interface to support both old and new formats
export interface ExtendedStoryConfig extends StoryConfig {
  // Existing fields from original StoryConfig
  global: {
    'story-dir': string;
    voices: string;
    chapters: string;
    'story-xml': string;
    logs: string;
    'story-audio': string;
    clips: string;
    'clip-separation': number;
    'max_voice_cache_size'?: number;
    'tts-device'?: string;
  };
  'llm-xml-generator': Array<{
    'default-llm'?: string;
    llm?: string;
    model: string;
    api_key?: string;
    api_base: string;
    temperature?: number;
    max_tokens?: number;
    rpm?: number;
    timeout?: number;
  }>;
  'dialog-effects': Array<{
    name: string;
    'sox-effects': string[];
  }>;
  'story-audio-post-process': {
    'sox-effects': string[];
  };
  characters: Array<{
    name: string;
    'voice-sample'?: string;
    'custom-voice'?: {
      language: string;
      speaker: string;
      instruct: string;
    };
    'sox-effects'?: string[];
    'dialog-effects'?: string[];
  }>;
}

// Main FlexiTTS configuration
export interface FlexiTTSConfig {
  FlexiTTS: {
    'stories-dir': string;
    'story-dir-prefix': string;
  };
}

// Chapter context with story information
export interface ChapterContext {
  storyInfo: StoryInfo;
  chapterPath: string;
  storyConfig: ExtendedStoryConfig;
}

// Re-export original types
export * from '../models/types';