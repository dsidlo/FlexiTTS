// Type definitions for Electron API

import type { StoryConfig } from '../models/types';

export interface TtsAlert {
  type: 'alert';
  alertType: 'info' | 'success' | 'warning' | 'error';
  message: string;
  source: 'tts-service';
  timestamp: string;
  metadata?: {
    story?: string;
    chapter?: string;
    section?: string;
    dialog?: string;
    character?: string;
    [key: string]: any;
  };
}

export interface StoryInfo {
  name: string;
  path: string;
  directory_name: string;
}

declare global {
  interface Window {
    api: {
      runPythonScript: (scriptPath: string, args: string[]) => Promise<string>;
      readFile: (filePath: string) => Promise<string>;
      readAudioFile: (filePath: string) => Promise<string>;
      writeFile: (filePath: string, content: string) => Promise<void>;
      showErrorDialog: (title: string, content: string) => Promise<void>;
      checkXmlExists: (chapterStem: string) => Promise<boolean>;
      showConfirmDialog: (title: string, message: string, detail: string) => Promise<number>;
      listChapterClips: (chapterName: string) => Promise<string[]>;
      checkChapterAudio: (chapterName: string) => Promise<boolean>;
      playSoundFile: (filePath: string) => Promise<void>;
      killProcess: (matchString: string) => Promise<boolean>;
      listChapterFiles: () => Promise<string[]>;
      // FlexiTTS Global Config and Story Management
      loadGlobalConfig: () => Promise<any>;
      saveGlobalConfig: (configData: any) => Promise<boolean>;
      listStories: () => Promise<StoryInfo[]>;
      setCurrentStory: (storyDirectory: string) => Promise<boolean>;
      getCurrentStory: () => Promise<string>;
      loadStoryConfig: (storyDir: string) => Promise<StoryConfig>;
      listChapterFilesForStory: (storyDir: string) => Promise<string[]>;
      checkXmlExistsForStory: (chapterStem: string, storyDir: string) => Promise<boolean>;
      checkStoryFileExists: (storyDir: string, relativePath: string) => Promise<boolean>;
    };
  }
}

export {};
