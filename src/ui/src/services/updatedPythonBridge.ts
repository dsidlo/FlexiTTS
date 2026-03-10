import type { StoryConfig } from '../models/types';
import type { StoryInfo, FlexiTTSConfig, ExtendedStoryConfig } from './extended-types';
import jsyaml from 'js-yaml';
import { debugLog } from '../utils/debugLogger';

const LOG_ID = '[updatedPythonBridge]';

// Module-level WebSocket connection status (set by useTtsAlerts hook)
let wsConnectionStatus: { isConnected: boolean; isReady: boolean; lastConnectedAt: number | null } = {
  isConnected: false,
  isReady: false,
  lastConnectedAt: null
};

/**
 * Set WebSocket connection status from useTtsAlerts hook
 */
export function setTtsWsStatus(connected: boolean, ready: boolean = false) {
  debugLog.info(`${LOG_ID}:setTtsWsStatus`, 'Updating WebSocket status', { connected, ready, previous: { ...wsConnectionStatus } });
  wsConnectionStatus.isConnected = connected;
  wsConnectionStatus.isReady = ready;
  if (connected) {
    wsConnectionStatus.lastConnectedAt = Date.now();
    debugLog.info(`${LOG_ID}:setTtsWsStatus`, 'WebSocket connected, timestamp set');
  } else {
    debugLog.info(`${LOG_ID}:setTtsWsStatus`, 'WebSocket disconnected, ready cleared');
  }
}

export const UpdatedPythonBridgeService = {
  /**
   * Validate FlexiTTS configuration (main config)
   */
  validateFlexiTTSConfig: async (): Promise<void> => {
    try {
      if (typeof window !== 'undefined' && window.api && window.api.runPythonScript) {
        await window.api.runPythonScript('src/scripts/flexitts_bridge.py', ['validate-config']);
      } else {
        console.log('Mock: FlexiTTS Config validated');
      }
    } catch (err: unknown) {
      console.warn("FlexiTTS configuration validation failed:", err);
      throw new Error(`FlexiTTS configuration validation failed: ${(err as Error).message}`);
    }
  },

  /**
   * Load available stories from the configured stories directory
   */
  loadAvailableStories: async (): Promise<StoryInfo[]> => {
    const id = `${LOG_ID}:loadAvailableStories`;
    debugLog.info(id, 'ENTER loadAvailableStories');
    
    if (typeof window !== 'undefined' && window.api && window.api.runPythonScript) {
      try {
        const output = await window.api.runPythonScript('src/scripts/flexitts_bridge.py', ['get-stories']);
        const stories: StoryInfo[] = JSON.parse(output);
        debugLog.info(id, 'Successfully loaded stories', { count: stories.length });
        return stories;
      } catch (e) {
        debugLog.exception(id, 'loadAvailableStories IPC call', e);
        throw e;
      }
    }
    
    // Mock data for development
    debugLog.warn(id, 'Using mock story data');
    return [
      { name: 'Entanglement', path: '/home/user/Stories/Story-Entanglement', directory_name: 'Story-Entanglement' },
      { name: 'Adventure', path: '/home/user/Stories/Story-Adventure', directory_name: 'Story-Adventure' }
    ] as StoryInfo[];
  },

  /**
   * Load story-specific configuration for a chapter
   */
  loadStoryConfigForChapter: async (chapterPath: string): Promise<ExtendedStoryConfig> => {
    const id = `${LOG_ID}:loadStoryConfigForChapter`;
    debugLog.info(id, 'ENTER loadStoryConfigForChapter', { chapterPath });
    
    if (typeof window !== 'undefined' && window.api && window.api.runPythonScript) {
      try {
        const output = await window.api.runPythonScript('src/scripts/flexitts_bridge.py', ['load-story-config', chapterPath]);
        const config: ExtendedStoryConfig = JSON.parse(output);
        debugLog.info(id, 'Successfully loaded story config', { chapterPath, hasCharacters: !!config.characters });
        return config;
      } catch (e) {
        debugLog.exception(id, 'loadStoryConfigForChapter IPC call', e, { chapterPath });
        throw e;
      }
    }
    
    // Mock fallback
    debugLog.warn(id, 'Using mock story config');
    return {
      global: {
        'story-dir': 'Story-Mock/',
        voices: 'refs/',
        chapters: 'story-chapters/',
        'story-xml': 'story-xml/',
        logs: 'logs/',
        'story-audio': 'story-audio/',
        clips: 'story-audio/clips/',
        'clip-separation': 0.3
      },
      'llm-xml-generator': [{
        'default-llm': 'mock',
        model: 'mock-model',
        api_base: 'http://localhost:1234/v1'
      }],
      'dialog-effects': [],
      'story-audio-post-process': {
        'sox-effects': ['normalize']
      },
      characters: [
        { name: 'Narrator', 'voice-sample': 'mock-narrator.wav' },
        { name: 'Alice', 'voice-sample': 'mock-alice.wav' }
      ]
    } as ExtendedStoryConfig;
  },

  /**
   * List chapter files from all discovered stories
   */
  listAllChapterFiles: async (): Promise<string[]> => {
    const id = `${LOG_ID}:listAllChapterFiles`;
    debugLog.info(id, 'ENTER listAllChapterFiles');
    
    if (typeof window !== 'undefined' && window.api && window.api.runPythonScript) {
      try {
        const output = await window.api.runPythonScript('src/scripts/flexitts_bridge.py', ['list-chapters']);
        const chapters: string[] = JSON.parse(output);
        debugLog.info(id, 'Successfully listed all chapter files', { count: chapters.length });
        return chapters;
      } catch (e) {
        debugLog.exception(id, 'listAllChapterFiles IPC call', e);
        throw e;
      }
    }
    
    // Mock fallback
    debugLog.warn(id, 'Using mock chapter list');
    return [
      'Story-Entanglement/story-chapters/chapter-001.md',
      'Story-Entanglement/story-chapters/chapter-002.md',
      'Story-Adventure/story-chapters/chapter-001.md'
    ];
  },

  /**
   * List chapter files for a specific story
   */
  listStoryChapterFiles: async (storyInfo: StoryInfo): Promise<string[]> => {
    const id = `${LOG_ID}:listStoryChapterFiles`;
    debugLog.info(id, 'ENTER listStoryChapterFiles', { story: storyInfo.name });
    
    try {
      const allChapters = await UpdatedPythonBridgeService.listAllChapterFiles();
      const storyChapters = allChapters.filter(chapter => 
        chapter.startsWith(storyInfo.directory_name + '/')
      );
      
      debugLog.info(id, 'Successfully filtered story chapters', { 
        story: storyInfo.name, 
        totalChapters: allChapters.length,
        storyChapters: storyChapters.length 
      });
      
      return storyChapters;
    } catch (e) {
      debugLog.exception(id, 'listStoryChapterFiles', e, { story: storyInfo.name });
      throw e;
    }
  },

  // Re-export necessary functions from original bridge with minimal changes
  showErrorDialog: async (title: string, message: string): Promise<void> => {
    if (typeof window !== 'undefined' && window.api && window.api.showErrorDialog) {
      return await window.api.showErrorDialog(title, message);
    } else {
      console.error(`Mock Error Dialog: [${title}] ${message}`);
      alert(`Error: ${title}\n${message}`);
    }
  },

  showConfirmDialog: async (title: string, message: string, detail: string): Promise<number> => {
    if (typeof window !== 'undefined' && window.api && window.api.showConfirmDialog) {
      return await window.api.showConfirmDialog(title, message, detail);
    }
    const result = window.confirm(`${title}\n\n${message}\n${detail}\n\nOK to Save, Cancel to cancel.`);
    return result ? 0 : 2;
  },

  // Forward other methods to original bridge
  readChapterFile: async (filePath: string): Promise<string> => {
    // Import and use original bridge method
    const { PythonBridgeService } = await import('../services/pythonBridge');
    return PythonBridgeService.readChapterFile(filePath);
  },

  writeChapterFile: async (filePath: string, xmlContent: string): Promise<boolean> => {
    const { PythonBridgeService } = await import('../services/pythonBridge');
    return PythonBridgeService.writeChapterFile(filePath, xmlContent);
  },

  validateChapterXML: async (chapterFilePath: string): Promise<void> => {
    const { PythonBridgeService } = await import('../services/pythonBridge');
    return PythonBridgeService.validateChapterXML(chapterFilePath);
  },

  checkXmlExists: async (chapterStem: string): Promise<boolean> => {
    const { PythonBridgeService } = await import('../services/pythonBridge');
    return PythonBridgeService.checkXmlExists(chapterStem);
  },

  playAudio: async (chapterName: string, sectionNum: string, dlgseqNum: string, onGenerationComplete?: () => void, skipPlay: boolean = false, onPlay?: (dataUrl: string) => void): Promise<string | void> => {
    const { PythonBridgeService } = await import('../services/pythonBridge');
    return PythonBridgeService.playAudio(chapterName, sectionNum, dlgseqNum, onGenerationComplete, skipPlay, onPlay);
  },

  listChapterClips: async (chapterName: string): Promise<string[]> => {
    const { PythonBridgeService } = await import('../services/pythonBridge');
    return PythonBridgeService.listChapterClips(chapterName);
  },

  checkChapterAudio: async (chapterName: string): Promise<boolean> => {
    const { PythonBridgeService } = await import('../services/pythonBridge');
    return PythonBridgeService.checkChapterAudio(chapterName);
  },

  cancelAudio: async (matchString: string): Promise<void> => {
    const { PythonBridgeService } = await import('../services/pythonBridge');
    return PythonBridgeService.cancelAudio(matchString);
  },

  // TTS Service methods
  isTtsServiceRunning: async (): Promise<boolean> => {
    const { PythonBridgeService } = await import('../services/pythonBridge');
    return PythonBridgeService.isTtsServiceRunning();
  },

  isTtsServiceReady: async (): Promise<boolean> => {
    const { PythonBridgeService } = await import('../services/pythonBridge');
    return PythonBridgeService.isTtsServiceReady();
  },

  startTtsService: async (): Promise<boolean> => {
    const { PythonBridgeService } = await import('../services/pythonBridge');
    return PythonBridgeService.startTtsService();
  },

  ensureTtsService: async (): Promise<string> => {
    const { PythonBridgeService } = await import('../services/pythonBridge');
    return PythonBridgeService.ensureTtsService();
  },

  startAndConnectTtsService: async (onRunningCallback?: (ready: boolean) => void): Promise<boolean> => {
    const { PythonBridgeService } = await import('../services/pythonBridge');
    return PythonBridgeService.startAndConnectTtsService(onRunningCallback);
  }
};