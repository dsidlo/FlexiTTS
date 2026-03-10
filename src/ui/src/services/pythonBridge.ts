import type { StoryConfig } from '../models/types';
import { debugLog } from '../utils/debugLogger';

const LOG_ID = '[pythonBridge]';

// Module-level WebSocket connection status (set by useTtsAlerts hook)
let wsConnectionStatus: { isConnected: boolean; isReady: boolean; lastConnectedAt: number | null } = {
  isConnected: false,
  isReady: false,
  lastConnectedAt: null
};

/**
 * Set WebSocket connection status from useTtsAlerts hook
 * This allows the bridge to check service status via WebSocket when Python check fails
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

export const PythonBridgeService = {
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
    // Mock fallback
    const result = window.confirm(`${title}\n\n${message}\n${detail}\n\nOK to Save, Cancel to cancel.`);
    return result ? 0 : 2; // 0=Save, 2=Cancel (no easy way to mock 3-way in browser)
  },

  validateConfig: async (storyDir?: string): Promise<void> => {
    try {
      if (typeof window !== 'undefined' && window.api && window.api.runPythonScript) {
        // If story directory is provided, validate that story's config
        const args = storyDir ? [`Stories/${storyDir}/story-config.yml`] : [];
        await window.api.runPythonScript('src/scripts/validate_config.py', args);
      } else {
        console.log('Mock: Config validated');
      }
    } catch (err: unknown) {
      console.warn("Config validation failed silently:", err);
      // Suppress hard crash dialogs on initial validation failure 
      // if (typeof window !== 'undefined' && window.api) await window.api.showErrorDialog('Configuration Error', (err as Error).message || 'Unknown error');
    }
  },

  validateChapterXML: async (chapterFilePath: string): Promise<void> => {
    try {
      if (typeof window !== 'undefined' && window.api && window.api.runPythonScript) {
        await window.api.runPythonScript('src/scripts/chapter_validate_xml.py', [chapterFilePath]);
      } else {
        console.log(`Mock: XML Validated for ${chapterFilePath}`);
      }
    } catch (err: unknown) {
      console.warn(`XML Validation failed for ${chapterFilePath}:`, err);
      if (typeof window !== 'undefined' && window.api && window.api.showErrorDialog) {
        await window.api.showErrorDialog('XML Validation Error', (err as Error).message || 'Invalid XML generated.');
      }
      throw err;
    }
  },

  loadStoryConfig: async (): Promise<StoryConfig> => {
    // Legacy method - fetches current story config. 
    // First gets current story from global config, then loads that story's config
    const id = `${LOG_ID}:loadStoryConfig`;
    debugLog.info(id, 'ENTER legacy loadStoryConfig - delegating to loadStoryConfigForStory');
    
    try {
      // Get current story from global config
      const globalConfig = await PythonBridgeService.loadGlobalConfig();
      const currentStory = globalConfig.FlexiTTS?.['current-story'];
      const storiesDir = globalConfig.FlexiTTS?.['stories-dir']?.split('/').pop() || 'Stories';
      const storyPrefix = globalConfig.FlexiTTS?.['story-dir-prefix'] || 'Story-';
      
      if (!currentStory) {
        debugLog.error(id, 'No current-story in global config');
        throw new Error('No current story selected in global config');
      }
      
      // Build story directory name: prefix + story name
      const storyDir = `${storyPrefix}${currentStory}`;
      debugLog.info(id, 'Resolved story directory', { currentStory, storyDir, storiesDir });
      
      // Delegate to loadStoryConfigForStory
      return await PythonBridgeService.loadStoryConfigForStory(storyDir);
    } catch (e) {
      debugLog.exception(id, 'loadStoryConfig failed', e);
      throw e;
    }
  },

  loadStoryConfigForStory: async (storyDir: string): Promise<StoryConfig> => {
    const id = `${LOG_ID}:loadStoryConfigForStory`;
    const configPath = `Stories/${storyDir}/story-config.yml`;
    debugLog.info(id, '[RESOURCE-ACCESS] Loading story config', { storyDir, configPath, resourceType: 'yaml' });
    
    if (typeof window !== 'undefined' && window.api && window.api.loadStoryConfig) {
      try {
        const config = await window.api.loadStoryConfig(storyDir);
        debugLog.info(id, '[RESOURCE-ACCESS] Successfully loaded story config', { storyDir, configPath, resourceType: 'yaml', hasCharacters: !!config?.characters, hasGlobal: !!config?.global });
        return config as StoryConfig;
      } catch (e) {
        debugLog.exception(id, '[RESOURCE-ACCESS] loadStoryConfig IPC call failed', e, { storyDir, configPath, resourceType: 'yaml' });
        throw e;
      }
    }
    
    // Fallback to mock config
    debugLog.warn(id, '[RESOURCE-ACCESS] window.api.loadStoryConfig not available, returning mock config', { storyDir });
    return {
      global: {
        'story-dir': `${storyDir}/`,
        voices: 'refs/',
        chapters: 'story-chapters/',
        'story-xml': 'story-xml/',
        logs: 'logs/',
        'story-audio': 'story-audio/',
        clips: 'story-audio/clips/',
        'clip-separation': 0
      },
      'llm-xml-generator': [],
      'dialog-effects': [],
      'story-audio-post-process': {},
      characters: []
    } as StoryConfig;
  },

  loadGlobalConfig: async (): Promise<any> => {
    const id = `${LOG_ID}:loadGlobalConfig`;
    debugLog.info(id, 'ENTER loadGlobalConfig');
    
    if (typeof window !== 'undefined' && window.api && window.api.loadGlobalConfig) {
      try {
        const config = await window.api.loadGlobalConfig();
        debugLog.info(id, 'Successfully loaded global config', { config });
        return config;
      } catch (e) {
        debugLog.exception(id, 'loadGlobalConfig IPC call', e);
        throw e;
      }
    }
    
    debugLog.error(id, 'window.api.loadGlobalConfig not available');
    // Return default config
    return {
      FlexiTTS: {
        'stories-dir': '~/workspace/FlexiTTS/Stories',
        'story-dir-prefix': 'Story-'
      }
    };
  },

  saveGlobalConfig: async (configData: any): Promise<boolean> => {
    const id = `${LOG_ID}:saveGlobalConfig`;
    debugLog.info(id, 'ENTER saveGlobalConfig', { configData });
    
    if (typeof window !== 'undefined' && window.api && window.api.saveGlobalConfig) {
      try {
        const result = await window.api.saveGlobalConfig(configData);
        debugLog.info(id, 'Successfully saved global config', { result });
        return result;
      } catch (e) {
        debugLog.exception(id, 'saveGlobalConfig IPC call', e);
        throw e;
      }
    }
    
    debugLog.error(id, 'window.api.saveGlobalConfig not available');
    throw new Error('saveGlobalConfig requires Electron IPC');
  },

  listStories: async (): Promise<{ name: string; path: string; directory_name: string }[]> => {
    const id = `${LOG_ID}:listStories`;
    debugLog.info(id, 'ENTER listStories');
    
    if (typeof window !== 'undefined' && window.api && window.api.listStories) {
      try {
        const stories = await window.api.listStories();
        debugLog.info(id, 'Successfully listed stories', { count: stories?.length });
        return stories;
      } catch (e) {
        debugLog.exception(id, 'listStories IPC call', e);
        throw e;
      }
    }
    
    debugLog.error(id, 'window.api.listStories not available');
    throw new Error('listStories requires Electron IPC');
  },

  setCurrentStory: async (storyDirectory: string): Promise<boolean> => {
    const id = `${LOG_ID}:setCurrentStory`;
    debugLog.info(id, 'ENTER setCurrentStory', { storyDirectory });
    
    if (typeof window !== 'undefined' && window.api && window.api.setCurrentStory) {
      try {
        const result = await window.api.setCurrentStory(storyDirectory);
        debugLog.info(id, 'Successfully set current story', { result });
        return result;
      } catch (e) {
        debugLog.exception(id, 'setCurrentStory IPC call', e);
        throw e;
      }
    }
    
    debugLog.error(id, 'window.api.setCurrentStory not available');
    return false;
  },

  getCurrentStory: async (): Promise<string> => {
    const id = `${LOG_ID}:getCurrentStory`;
    debugLog.info(id, 'ENTER getCurrentStory');
    
    if (typeof window !== 'undefined' && window.api && window.api.getCurrentStory) {
      try {
        const story = await window.api.getCurrentStory();
        debugLog.info(id, 'Successfully got current story', { story });
        return story;
      } catch (e) {
        debugLog.exception(id, 'getCurrentStory IPC call', e);
        throw e;
      }
    }
    
    debugLog.error(id, 'window.api.getCurrentStory not available');
    return '';
  },

  listChapterFilesForStory: async (storyDir: string): Promise<string[]> => {
    const id = `${LOG_ID}:listChapterFilesForStory`;
    debugLog.info(id, 'ENTER listChapterFilesForStory', { storyDir });
    
    if (typeof window !== 'undefined' && window.api && window.api.listChapterFilesForStory) {
      try {
        const files = await window.api.listChapterFilesForStory(storyDir);
        debugLog.info(id, 'Successfully listed chapter files', { count: files?.length });
        return files;
      } catch (e) {
        debugLog.exception(id, 'listChapterFilesForStory IPC call', e);
        throw e;
      }
    }
    
    debugLog.error(id, 'window.api.listChapterFilesForStory not available');
    throw new Error('listChapterFilesForStory requires Electron IPC');
  },

  checkXmlExistsForStory: async (chapterStem: string, storyDir: string): Promise<boolean> => {
    const id = `${LOG_ID}:checkXmlExistsForStory`;
    debugLog.info(id, 'ENTER checkXmlExistsForStory', { chapterStem, storyDir });
    
    if (typeof window !== 'undefined' && window.api && window.api.checkXmlExistsForStory) {
      try {
        const exists = await window.api.checkXmlExistsForStory(chapterStem, storyDir);
        debugLog.info(id, 'Successfully checked XML existence', { exists });
        return exists;
      } catch (e) {
        debugLog.exception(id, 'checkXmlExistsForStory IPC call', e);
        throw e;
      }
    }
    
    debugLog.error(id, 'window.api.checkXmlExistsForStory not available');
    return false;
  },

  readChapterFile: async (filePath: string): Promise<string> => {
    const id = `${LOG_ID}:readChapterFile`;
    debugLog.info(id, '[RESOURCE-ACCESS] Reading markdown file', { filePath, resourceType: 'markdown' });
    
    // If the python bridge exists (i.e. running inside electron), use it
    if (typeof window !== 'undefined' && window.api && window.api.readFile) {
      try {
        const fileContent = await window.api.readFile(filePath);
        if (fileContent) {
          debugLog.info(id, '[RESOURCE-ACCESS] Successfully read markdown', { filePath, resourceType: 'markdown', length: fileContent.length });
          return fileContent;
        }
      } catch (e) {
        debugLog.exception(id, '[RESOURCE-ACCESS] Electron IPC readFile failed', e, { filePath, resourceType: 'markdown' });
        // Don't fall through - in production, we need the real file
        throw new Error(`Failed to read file ${filePath}: ${e}`);
      }
    }
    
    // Fallback for browser/dev mode - try Vite import.meta.glob
    debugLog.warn(id, '[RESOURCE-ACCESS] Electron IPC not available, falling back to Vite glob', { filePath, resourceType: 'markdown' });
    
    try {
      const xmlFiles = import.meta.glob('/../../**/story-xml/*.xml', { query: '?raw', import: 'default' });
      for (const path in xmlFiles) {
        if (path.includes(filePath.split('/').pop() || '')) {
          const content = await xmlFiles[path]();
          debugLog.info(id, 'Successfully read file via Vite glob', { filePath, matchedPath: path });
          return content as string;
        }
      }
      debugLog.error(id, 'File not found in Vite glob patterns', { filePath });
      throw new Error(`File not found: ${filePath}`);
    } catch(e) {
      debugLog.exception(id, 'Vite glob fallback', e, { filePath });
      throw e;
    }
  },

  listChapterFiles: async (): Promise<string[]> => {
    const id = `${LOG_ID}:listChapterFiles`;
    debugLog.info(id, 'ENTER listChapterFiles');
    
    if (typeof window !== 'undefined' && window.api && window.api.listChapterFiles) {
      try {
        const files = await window.api.listChapterFiles();
        debugLog.info(id, 'Successfully retrieved chapter files', { count: files?.length });
        return files;
      } catch (e) {
        debugLog.exception(id, 'listChapterFiles IPC call', e);
        throw e; // Rethrow so caller can handle appropriately
      }
    }
    
    debugLog.error(id, 'window.api.listChapterFiles not available - must run in Electron');
    throw new Error('listChapterFiles requires Electron IPC - window.api.listChapterFiles not available');
  },

  checkXmlExists: async (chapterStem: string): Promise<boolean> => {
    const id = `${LOG_ID}:checkXmlExists`;
    debugLog.info(id, 'ENTER checkXmlExists', { chapterStem });
    
    if (typeof window !== 'undefined' && window.api && window.api.checkXmlExists) {
      try {
        const exists = await window.api.checkXmlExists(chapterStem);
        debugLog.info(id, 'Successfully checked XML existence', { chapterStem, exists });
        return exists;
      } catch (e) {
        debugLog.exception(id, 'checkXmlExists IPC call', e, { chapterStem });
        throw e;
      }
    }
    
    debugLog.error(id, 'window.api.checkXmlExists not available', { chapterStem });
    throw new Error('checkXmlExists requires Electron IPC');
  },

  readFile: async (filePath: string): Promise<string> => {
    const id = `${LOG_ID}:readFile`;
    const resourceType = filePath.endsWith('.md') ? 'markdown' : filePath.endsWith('.xml') ? 'xml' : filePath.endsWith('.wav') ? 'audio' : 'unknown';
    debugLog.info(id, '[RESOURCE-ACCESS] Reading file', { filePath, resourceType });
    
    if (typeof window !== 'undefined' && window.api && window.api.readFile) {
      try {
        const content = await window.api.readFile(filePath);
        debugLog.info(id, '[RESOURCE-ACCESS] Successfully read file', { filePath, resourceType, length: content?.length });
        return content;
      } catch (e) {
        debugLog.exception(id, '[RESOURCE-ACCESS] readFile IPC call failed', e, { filePath, resourceType });
        throw e;
      }
    }
    
    debugLog.error(id, '[RESOURCE-ACCESS] window.api.readFile not available', { filePath, resourceType });
    throw new Error('readFile requires Electron IPC');
  },

  writeChapterFile: async (filePath: string, xmlContent: string): Promise<boolean> => {
    const id = `${LOG_ID}:writeChapterFile`;
    debugLog.info(id, '[RESOURCE-ACCESS] Writing XML file', { filePath, resourceType: 'xml', contentLength: xmlContent?.length });
    
    if (typeof window !== 'undefined' && window.api && window.api.writeFile) {
      try {
        await window.api.writeFile(filePath, xmlContent);
        debugLog.info(id, '[RESOURCE-ACCESS] Successfully wrote XML file', { filePath, resourceType: 'xml' });
        return true;
      } catch (err: unknown) {
        debugLog.exception(id, '[RESOURCE-ACCESS] writeFile IPC call failed', err, { filePath, resourceType: 'xml' });
        if (window.api.showErrorDialog) {
           await window.api.showErrorDialog('Save Error', (err as Error).message || 'Failed to write chapter file.');
        }
        throw err;
      }
    }
    
    debugLog.error(id, '[RESOURCE-ACCESS] window.api.writeFile not available', { filePath, resourceType: 'xml' });
    throw new Error('writeChapterFile requires Electron IPC');
  },

  playAudio: async (chapterName: string, sectionNum: string, dlgseqNum: string, onGenerationComplete?: () => void, skipPlay: boolean = false, onPlay?: (dataUrl: string) => void): Promise<string | void> => {
    const id = `${LOG_ID}:playAudio`;
    const storyDir = await PythonBridgeService.getCurrentStory();
    const xmlPath = `${storyDir || 'Story-Default'}/story-xml/${chapterName}`;
    debugLog.info(id, '[RESOURCE-ACCESS] Starting audio generation', { chapterName, sectionNum, dlgseqNum, xmlPath, resourceType: 'xml', operation: 'read' });
    
    if (typeof window !== 'undefined' && window.api && window.api.runPythonScript) {
      try {
        // Start TTS WebSocket service for fast GPU-accelerated rendering (required)
        debugLog.info(id, 'Calling ensureTtsService for TTS WebSocket service');
        const ttsServiceUrl = await PythonBridgeService.ensureTtsService();
        debugLog.info(id, 'ensureTtsService completed', { ttsServiceUrl });
        
        // Get current story from main process
        let storyDir = 'Story-Default';
        try {
          const currentStoryDir = await window.api.getCurrentStory();
          if (currentStoryDir) {
            storyDir = currentStoryDir;
          }
        } catch (err) {
          debugLog.warn(id, 'Failed to get current story, using default', err);
        }
        
        const xmlInputPath = `${storyDir}/story-xml/${chapterName}`;
        debugLog.info(id, '[RESOURCE-ACCESS] Running chapter_xml_to_audio.py', { 
          script: 'src/scripts/chapter_xml_to_audio.py',
          xmlInputPath,
          resourceType: 'xml',
          chapter: chapterName,
          section: sectionNum,
          dlgseq: dlgseqNum,
          ttsService: ttsServiceUrl,
          storyDir
        });
        
        const out = await window.api.runPythonScript('src/scripts/chapter_xml_to_audio.py', [
            xmlInputPath,
            `--section`, sectionNum,
            `--dlgseq`, dlgseqNum,
            `--tts-service`, ttsServiceUrl
        ]);
        debugLog.info(id, '[RESOURCE-ACCESS] Audio generation completed', { outputLength: out?.length, xmlInputPath });

        // Parse stdout to find the generated WAV file path
        let wavName = '';
        
        // Let's explicitly log the parsing process to help debug if it fails
        console.log(`[playAudio] Parsing stdout to find filename...`);
        
        // Match actual output format: "  Generating chapter_004_004_001_alice..."
        // This is the primary matching pattern based on chapter_xml_to_audio.py line 188
        const genMatch = out.match(/Generating\s+(chapter_\d+_\d+_\d+_\w+)/i);
        if (genMatch?.[1]) {
           wavName = genMatch[1] + ".wav";
           console.log(`[playAudio] Found filename via Generating match: ${wavName}`);
        } else {
           // Fallback to "Applying character effects to /path/to/file.wav"
           // (only prints if character has effects configured in story-config.yml)
           const effectMatch = out.match(/Applying character effects to (.*?\.wav)/i);
           if (effectMatch?.[1]) {
               wavName = effectMatch[1];
               console.log(`[playAudio] Found filename via character effects match: ${wavName}`);
           } else {
               // Fallback to "Would save clip to /path/to/file.wav" or "saved to /path/to/file.wav"
               const saveMatch = out.match(/save clip to .*?(chapter_.*?\.wav)/i) || out.match(/saved to .*?(chapter_.*?\.wav)/i);
               if (saveMatch?.[1]) {
                   wavName = saveMatch[1];
                   console.log(`[playAudio] Found filename via saved match: ${wavName}`);
               } else {
                   // Additional fallback for normal save pattern without full path logging
                   const altMatch = out.match(/(chapter_.*?\.wav)/i);
                   if (altMatch?.[1]) {
                       wavName = altMatch[1];
                       console.log(`[playAudio] Found filename via alternative match: ${wavName}`);
                   }
               }
           }
        }

        if (wavName) {
            debugLog.info(id, 'Found WAV filename', { wavName, chapterStem: chapterName.replace('.xml', '') });
            
            // Generation is done
            if (onGenerationComplete) {
                debugLog.info(id, 'Calling onGenerationComplete callback');
                onGenerationComplete();
            }
            
            // Reconstruct the full path
            const chapterStem = chapterName.replace('.xml', '');
            // Get current story directory (already loaded above)
            const audioPath = `${storyDir}/story-audio/clips/${chapterStem}/${wavName}`;
            debugLog.info(id, '[RESOURCE-ACCESS] Reading audio file for playback', { audioPath, resourceType: 'audio', wavName, chapterStem });
            
            // Client-side playback via data URL with onPlay callback
            if (!skipPlay) {
                debugLog.info(id, 'Starting audio playback', { skipPlay, hasOnPlay: !!onPlay });
                if (window.api && window.api.readAudioFile) {
                    try {
                        const dataUrl = await window.api.readAudioFile(audioPath);
                        debugLog.info(id, '[RESOURCE-ACCESS] Audio file loaded successfully', { audioPath, resourceType: 'audio', dataUrlLength: dataUrl?.length });
                        if (onPlay) {
                            // Use caller's play function (e.g., useAudioPlayer)
                            debugLog.info(id, 'Using onPlay callback for audio playback');
                            await onPlay(dataUrl);
                        } else {
                            // Fallback: create Audio element directly
                            debugLog.warn(id, 'No onPlay callback, using direct Audio element');
                            const audio = new Audio(dataUrl);
                            await audio.play();
                        }
                        debugLog.info(id, 'Audio playback completed successfully');
                    } catch (playErr) {
                        debugLog.exception(id, 'readAudioFile/playback', playErr, { audioPath });
                    }
                } else if (window.api) {
                    debugLog.warn(id, 'readAudioFile not available', { audioPath });
                }
            } else {
                debugLog.info(id, 'SkipPlay flag true, skipping playback');
            }
        } else {
            debugLog.error(id, 'Failed to parse WAV filename from output', { output: out });
            throw new Error("Could not parse output filename from Python stdout");
        }
        
      } catch (err) {
        debugLog.exception(id, 'playAudio main try-block', err, { chapterName, sectionNum, dlgseqNum });
        throw err;
      }
      debugLog.info(id, 'EXIT playAudio - SUCCESS');
    } else {
        debugLog.warn(id, 'Running in mock mode (window.api not available)');
        await new Promise(resolve => setTimeout(resolve, 2000));
        if (onGenerationComplete) onGenerationComplete();
        await new Promise(resolve => setTimeout(resolve, 2000));
        debugLog.info(id, 'Mock playback completed');
    }
  },

  listChapterClips: async (chapterName: string): Promise<string[]> => {
    const id = `${LOG_ID}:listChapterClips`;
    debugLog.info(id, 'ENTER listChapterClips', { chapterName });
    
    if (typeof window !== 'undefined' && window.api && window.api.listChapterClips) {
      try {
        const clips = await window.api.listChapterClips(chapterName);
        debugLog.info(id, 'Successfully listed chapter clips', { chapterName, count: clips?.length });
        return clips;
      } catch (e) {
        debugLog.exception(id, 'listChapterClips IPC call', e, { chapterName });
        throw e;
      }
    }
    
    debugLog.error(id, 'window.api.listChapterClips not available', { chapterName });
    throw new Error('listChapterClips requires Electron IPC');
  },

  checkChapterAudio: async (chapterName: string): Promise<boolean> => {
    const id = `${LOG_ID}:checkChapterAudio`;
    debugLog.info(id, 'ENTER checkChapterAudio', { chapterName });
    
    if (typeof window !== 'undefined' && window.api && window.api.checkChapterAudio) {
      try {
        const hasAudio = await window.api.checkChapterAudio(chapterName);
        debugLog.info(id, 'Successfully checked chapter audio', { chapterName, hasAudio });
        return hasAudio;
      } catch (e) {
        debugLog.exception(id, 'checkChapterAudio IPC call', e, { chapterName });
        throw e;
      }
    }
    
    debugLog.error(id, 'window.api.checkChapterAudio not available', { chapterName });
    throw new Error('checkChapterAudio requires Electron IPC');
  },

  cancelAudio: async (matchString: string): Promise<void> => {
    const id = `${LOG_ID}:cancelAudio`;
    debugLog.info(id, 'ENTER cancelAudio', { matchString });
    
    if (typeof window !== 'undefined' && window.api && window.api.killProcess) {
      try {
        await window.api.killProcess(matchString);
        debugLog.info(id, 'Successfully cancelled audio process', { matchString });
      } catch (e) {
        debugLog.exception(id, 'killProcess IPC call', e, { matchString });
        throw e;
      }
    } else {
      debugLog.error(id, 'window.api.killProcess not available', { matchString });
      throw new Error('cancelAudio requires Electron IPC');
    }
  },

  /**
   * Check if the TTS service process exists (running or warming up)
   * @returns Promise<boolean> - true if service process exists
   */
  isTtsServiceRunning: async (): Promise<boolean> => {
    const id = `${LOG_ID}:isTtsServiceRunning`;
    debugLog.info(id, 'ENTER isTtsServiceRunning');
    
    // Check WebSocket connection status first (most reliable)
    if (wsConnectionStatus.isConnected || 
        (wsConnectionStatus.lastConnectedAt && Date.now() - wsConnectionStatus.lastConnectedAt < 10000)) {
      debugLog.info(id, 'Service detected via WebSocket connection', { 
        isConnected: wsConnectionStatus.isConnected, 
        lastConnectedAt: wsConnectionStatus.lastConnectedAt,
        timeSinceLastConnection: wsConnectionStatus.lastConnectedAt ? Date.now() - wsConnectionStatus.lastConnectedAt : null
      });
      return true;
    }
    
    try {
      if (typeof window !== 'undefined' && window.api && window.api.runPythonScript) {
        debugLog.info(id, 'Running Python check script');
        const out = await window.api.runPythonScript('src/scripts/check_tts_service.py', []);
        // Service exists if output is 'ready' or 'starting' (warming up)
        const isRunning = out.includes('ready') || out.includes('starting');
        debugLog.info(id, 'Python check completed', { output: out.trim(), isRunning });
        return isRunning;
      }
    } catch (e) {
      debugLog.exception(id, 'Python service check', e);
      // If Python check fails but WebSocket shows recent connection, trust WebSocket
      if (wsConnectionStatus.lastConnectedAt && Date.now() - wsConnectionStatus.lastConnectedAt < 30000) {
        debugLog.info(id, 'Falling back to WebSocket status after Python check failure');
        return true;
      }
    }
    debugLog.info(id, 'Service not running (all checks failed)');
    return false;
  },

  /**
   * Check if the TTS service is fully ready (warmed up)
   * @returns Promise<boolean> - true if service is ready
   */
  isTtsServiceReady: async (): Promise<boolean> => {
    const id = `${LOG_ID}:isTtsServiceReady`;
    debugLog.info(id, 'ENTER isTtsServiceReady');
    
    // Check WebSocket status first
    if (wsConnectionStatus.isReady) {
      debugLog.info(id, 'Service ready via WebSocket status');
      return true;
    }
    
    try {
      if (typeof window !== 'undefined' && window.api && window.api.runPythonScript) {
        debugLog.info(id, 'Running Python ready check');
        const out = await window.api.runPythonScript('src/scripts/check_tts_service.py', []);
        const isReady = out.includes('ready');
        debugLog.info(id, 'Python ready check completed', { output: out.trim(), isReady });
        return isReady;
      }
    } catch (e) {
      debugLog.exception(id, 'Python ready check', e);
    }
    debugLog.info(id, 'Service not ready');
    return false;
  },

  /**
   * Start the TTS service
   * @returns Promise<boolean> - true if service started successfully
   */
  startTtsService: async (): Promise<boolean> => {
    const id = `${LOG_ID}:startTtsService`;
    debugLog.info(id, 'ENTER startTtsService');
    
    try {
      if (typeof window !== 'undefined' && window.api && window.api.runPythonScript) {
        debugLog.info(id, 'Calling start_tts_service.py via IPC');
        const out = await window.api.runPythonScript('src/scripts/start_tts_service.py', []);
        // Service started successfully or was already running
        const success = out.includes('started') || out.includes('success') || out.includes('already running');
        debugLog.info(id, 'start_tts_service.py completed', { success, output: out?.trim() });
        return success;
      }
    } catch (e) {
      debugLog.exception(id, 'startTtsService IPC call', e);
      throw e;
    }
    
    debugLog.error(id, 'window.api.runPythonScript not available');
    throw new Error('startTtsService requires Electron IPC');
  },

  /**
   * Ensure TTS service is running with health check and retry logic
   * Uses exponential backoff: 1s, 2s, 4s, 8s delays, max 4 attempts
   * @returns Promise<string> - service URL ws://localhost:8765 if running
   */
  ensureTtsService: async (): Promise<string> => {
    const id = `${LOG_ID}:ensureTtsService`;
    const maxRetries = 4;
    const delays = [1000, 2000, 4000, 8000]; // 1s, 2s, 4s, 8s
    const pollInterval = 2000; // Poll every 2 seconds for readiness
    const maxWaitTime = 300000; // Max 5 minutes wait for warmup (models take time to load)

    const serviceUrl = 'ws://localhost:8765';
    
    debugLog.info(id, 'ENTER ensureTtsService', { maxRetries, maxWaitTime, pollInterval });

    try {
      // First check if already ready
      debugLog.info(id, 'Checking if service is already ready');
      if (await PythonBridgeService.isTtsServiceReady()) {
        debugLog.info(id, 'Service already running and ready');
        return serviceUrl;
      }

      // Check if service is running but warming up
      debugLog.info(id, 'Checking if service is running but warming up');
      if (await PythonBridgeService.isTtsServiceRunning()) {
        debugLog.info(id, 'Service is running, waiting for warmup...');
        const startTime = Date.now();
        while (Date.now() - startTime < maxWaitTime) {
          if (await PythonBridgeService.isTtsServiceReady()) {
            debugLog.info(id, 'Service is now ready after waiting', { waitedMs: Date.now() - startTime });
            return serviceUrl;
          }
          debugLog.debug(id, 'Still waiting for warmup...', { waitedMs: Date.now() - startTime });
          await new Promise(resolve => setTimeout(resolve, pollInterval));
        }
        debugLog.error(id, 'TTS service warmup timed out after 5 minutes');
        throw new Error('TTS service warmup timed out after 5 minutes');
      }
    } catch (e) {
      debugLog.exception(id, 'ensureTtsService initial checks', e);
      throw e;
    }

    debugLog.info(id, 'Service not running, attempting to start...');

    for (let attempt = 0; attempt < maxRetries; attempt++) {
      debugLog.info(id, `Attempting to start service (attempt ${attempt + 1}/${maxRetries})`);
      try {
        const started = await PythonBridgeService.startTtsService();
        
        if (started) {
          debugLog.info(id, `Service start command completed on attempt ${attempt + 1}`);
          
          // Poll for service to be ready (it may still be warming up)
          const startTime = Date.now();
          while (Date.now() - startTime < maxWaitTime) {
            if (await PythonBridgeService.isTtsServiceReady()) {
              debugLog.info(id, `Service is now ready (attempt ${attempt + 1})`);
              return serviceUrl;
            }
            if (!(await PythonBridgeService.isTtsServiceRunning())) {
              debugLog.error(id, `Service process disappeared during warmup`);
              break; // Service died, retry
            }
            debugLog.debug(id, `Waiting for service ready...`, { waitedMs: Date.now() - startTime });
            await new Promise(resolve => setTimeout(resolve, pollInterval));
          }
        }

        if (attempt < maxRetries - 1) {
          debugLog.info(id, `Start attempt ${attempt + 1} incomplete, waiting before retry`, { waitMs: delays[attempt] });
          await new Promise(resolve => setTimeout(resolve, delays[attempt]));
        }
      } catch (e) {
        debugLog.exception(id, `startTtsService attempt ${attempt + 1}`, e);
        if (attempt === maxRetries - 1) throw e;
        await new Promise(resolve => setTimeout(resolve, delays[attempt]));
      }
    }

    // All attempts failed
    debugLog.warn(id, 'All start attempts failed, checking final state');
    const isRunning = await PythonBridgeService.isTtsServiceRunning();
    if (isRunning) {
      debugLog.warn(id, 'Service is running but not ready after all attempts');
      return serviceUrl; // Return URL anyway so UI can connect and receive alerts
    }

    debugLog.error(id, 'Failed to start TTS service after all attempts');
    const userMessage = 'Unable to start the TTS service after multiple attempts. ' +
      'Please check that:\n' +
      '1. Python dependencies are installed (pip install -r requirements.txt)\n' +
      '2. The TTS model files are available\n' +
      '3. Port 8765 is not in use by another process\n\n' +
      'See the application logs for more details.';
    
    await PythonBridgeService.showErrorDialog(
      'TTS Service Failed to Start',
      userMessage
    );
    
    throw new Error('TTS service failed to start after ' + maxRetries + ' attempts');
  },

  /**
   * Start TTS service and enable WebSocket connection as soon as service is running.
   * Returns true if service is running (WebSocket will connect), false otherwise.
   * @param onRunningCallback - Called when service is running (enables WebSocket)
   * @returns Promise<boolean> - true if service was started
   */
  startAndConnectTtsService: async (onRunningCallback?: (ready: boolean) => void): Promise<boolean> => {
    const id = `${LOG_ID}:startAndConnectTtsService`;
    const pollInterval = 2000;
    const maxStartTime = 60000; // 60 seconds to start process
    const maxWaitTime = 300000; // 5 minutes for warmup
    
    debugLog.info(id, 'ENTER startAndConnectTtsService', { maxStartTime, maxWaitTime, pollInterval });
    
    try {
      // Check if already running
      debugLog.info(id, 'Checking if service is already running');
      if (await PythonBridgeService.isTtsServiceRunning()) {
        debugLog.info(id, 'Service already running, invoking onRunningCallback');
        onRunningCallback?.(true);
        return true;
      }

      // Start the service
      debugLog.info(id, 'Starting TTS service...');
      const started = await PythonBridgeService.startTtsService();
      
      if (!started) {
        debugLog.error(id, 'Failed to start service');
        return false;
      }
      debugLog.info(id, 'Service start command succeeded, waiting for it to be running');

      // Poll for service to be running (process exists, WebSocket accepting)
      const startTime = Date.now();
      while (Date.now() - startTime < maxStartTime) {
        if (await PythonBridgeService.isTtsServiceRunning()) {
          debugLog.info(id, 'Service is running, enabling WebSocket connection');
          // Enable WebSocket NOW - this allows receiving warmup alerts
          onRunningCallback?.(true);
          
          // Continue polling for full readiness (warmup complete)
          const warmupStart = Date.now();
          while (Date.now() - warmupStart < maxWaitTime) {
            if (await PythonBridgeService.isTtsServiceReady()) {
              debugLog.info(id, 'Service is fully ready (warmup complete)', { waitedMs: Date.now() - warmupStart });
              return true;
            }
            debugLog.debug(id, 'Waiting for warmup complete...', { waitedMs: Date.now() - warmupStart });
            await new Promise(resolve => setTimeout(resolve, pollInterval));
          }
          debugLog.warn(id, 'Warmup timed out, but service is running', { waitedMs: Date.now() - warmupStart });
          return true; // Still return true since service is running
        }
        debugLog.debug(id, 'Waiting for service to start...', { waitedMs: Date.now() - startTime });
        await new Promise(resolve => setTimeout(resolve, pollInterval));
      }

      debugLog.error(id, 'Service failed to start within timeout', { waitedMs: Date.now() - startTime });
      return false;
    } catch (e) {
      debugLog.exception(id, 'startAndConnectTtsService', e);
      return false;
    }
  }
};
