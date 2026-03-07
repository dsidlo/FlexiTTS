import type { StoryConfig } from '../models/types';
import jsyaml from 'js-yaml';

// Declaration to satisfy TypeScript for window.api
declare global {
  interface Window {
    api?: {
      runPythonScript: (scriptPath: string, args: string[]) => Promise<string>;
      readFile: (filePath: string) => Promise<string>;
      writeFile: (filePath: string, content: string) => Promise<boolean>;
      showErrorDialog: (title: string, content: string) => Promise<void>;
      showConfirmDialog?: (title: string, message: string, detail: string) => Promise<number>;
      listChapterClips?: (chapterName: string) => Promise<string[]>;
      checkChapterAudio?: (chapterName: string) => Promise<boolean>;
      checkXmlExists?: (chapterStem: string) => Promise<boolean>;
      listChapterFiles?: () => Promise<string[]>;
      playSoundFile?: (filePath: string) => Promise<void>;
      killProcess?: (matchString: string) => Promise<boolean>;
    };
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

  validateConfig: async (): Promise<void> => {
    try {
      if (typeof window !== 'undefined' && window.api && window.api.runPythonScript) {
        await window.api.runPythonScript('src/scripts/validate_config.py', []);
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
    if (typeof window !== 'undefined' && window.api) {
      const yamlContent = await window.api.readFile('story-config.yml');
      return jsyaml.load(yamlContent) as StoryConfig;
    }
    // Mock Config for browser viewing
    return {
      global: {
        'story-dir': 'Story-Entanglement/',
        voices: '',
        chapters: '',
        'story-xml': 'Story-Entanglement/story-xml/',
        logs: '',
        'story-audio': '',
        clips: '',
        'clip-separation': 0
      },
      'llm-xml-generator': [],
      'dialog-effects': [],
      'story-audio-post-process': {},
      characters: []
    } as StoryConfig;
  },

  readChapterFile: async (filePath: string): Promise<string> => {
    // If the python bridge exists (i.e. running inside electron), use it
    if (typeof window !== 'undefined' && window.api && window.api.readFile) {
      try {
        const fileContent = await window.api.readFile(filePath);
        if (fileContent) return fileContent;
      } catch (e) {
        console.warn(`Could not read file natively: ${filePath}`, e);
      }
    }
    
    // Otherwise fallback to Vite import.meta.glob to read the raw file
    console.log(`Mocking read for ${filePath}`);
    
    try {
      const xmlFiles = import.meta.glob('/../../Story-Entanglement/story-xml/*.xml', { query: '?raw', import: 'default' });
      for (const path in xmlFiles) {
        if (path.includes(filePath.split('/').pop() || '')) {
          const content = await xmlFiles[path]();
          return content as string;
        }
      }
    } catch(e) {
      console.warn("Failed to fetch real file via glob:", e);
    }
    
    return `<story><section><narration emotion="neutral" dlgseq="1">Fallback mock data for ${filePath}.</narration></section></story>`;
  },

  listChapterFiles: async (): Promise<string[]> => {
    if (typeof window !== 'undefined' && window.api && window.api.listChapterFiles) {
      return await window.api.listChapterFiles();
    }
    
    console.log(`Mocking list for chapters`);
    // Simulate real delay
    await new Promise(resolve => setTimeout(resolve, 300));
    
    // Hardcode fallback paths if glob isn't working right
    return [
      'Story-Entanglement/story-chapters/01-Hendrix.md',
      'Story-Entanglement/story-chapters/02-Tech.md',
      'Story-Entanglement/story-chapters/03-Yamato.md',
      'Story-Entanglement/story-chapters/04-Manus Labs.md'
    ];
  },

  checkXmlExists: async (chapterStem: string): Promise<boolean> => {
    if (typeof window !== 'undefined' && window.api && window.api.checkXmlExists) {
      return await window.api.checkXmlExists(chapterStem);
    }
    return true; // Mock true for browser testing
  },

  readFile: async (filePath: string): Promise<string> => {
    if (typeof window !== 'undefined' && window.api && window.api.readFile) {
      return await window.api.readFile(filePath);
    }
    console.warn(`Mock: Reading file ${filePath}`);
    return `Mock content for ${filePath}`;
  },

  writeChapterFile: async (filePath: string, xmlContent: string): Promise<boolean> => {
    if (typeof window !== 'undefined' && window.api && window.api.writeFile) {
      try {
        await window.api.writeFile(filePath, xmlContent);
        return true;
      } catch (err: unknown) {
        if (window.api.showErrorDialog) {
           await window.api.showErrorDialog('Save Error', (err as Error).message || 'Failed to write chapter file.');
        }
        throw err;
      }
    }
    console.log(`Mock: Wrote file ${filePath}`, xmlContent);
    return true;
  },

  playAudio: async (chapterName: string, sectionNum: string, dlgseqNum: string, onGenerationComplete?: () => void, skipPlay: boolean = false): Promise<void> => {
    console.log(`[playAudio] Starting generation/play for chapter=${chapterName} section=${sectionNum} dlgseq=${dlgseqNum}`);
    if (typeof window !== 'undefined' && window.api && window.api.runPythonScript) {
      try {
        // Start TTS WebSocket service for fast GPU-accelerated rendering (required)
        const ttsServiceUrl = await PythonBridgeService.ensureTtsService();
        
        console.log(`[playAudio] Calling runPythonScript with chapter_xml_to_audio.py, tts-service=${ttsServiceUrl}`);
        const out = await window.api.runPythonScript('src/scripts/chapter_xml_to_audio.py', [
            `Story-Entanglement/story-xml/${chapterName}`,
            `--section`, sectionNum,
            `--dlgseq`, dlgseqNum,
            `--tts-service`, ttsServiceUrl
        ]);
        console.log("[playAudio] Audio generation output:", out);

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
            // Generation is done
            if (onGenerationComplete) onGenerationComplete();
            
            // Reconstruct the full path
            // Format is Story-Entanglement/story-audio/clips/<chapter-stem>/<wavName>
            const chapterStem = chapterName.replace('.xml', '');
            const fullPath = `Story-Entanglement/story-audio/clips/${chapterStem}/${wavName}`;
            
            console.log(`[playAudio] Attempting to play parsed path: ${fullPath}`);
            
            // To play this in the browser, we need to read it as a buffer or use a custom protocol
            if (!skipPlay) {
                if (window.api && window.api.playSoundFile) {
                    console.log(`[playAudio] Calling window.api.playSoundFile...`);
                    try {
                        await window.api.playSoundFile(fullPath);
                        console.log(`[playAudio] Finished playback.`);
                    } catch (playErr) {
                        console.error(`[playAudio] Error during audio playback API call:`, playErr);
                    }
                } else if (window.api) {
                    console.warn(`[playAudio] Need an electron API to play ${fullPath}`);
                }
            } else {
                console.log(`[playAudio] SkipPlay flag true. Generation complete.`);
            }
        } else {
            console.error("[playAudio] Could not parse output filename from Python stdout", out);
            throw new Error("Could not parse output filename from Python stdout");
        }
        
      } catch (err) {
        console.error("[playAudio] Failed to generate/play audio", err);
        throw err;
      }
    } else {
        console.log(`Mock: Generating audio for ${chapterName} s:${sectionNum} d:${dlgseqNum}...`);
        await new Promise(resolve => setTimeout(resolve, 2000)); // Simulate generation time
        if (onGenerationComplete) onGenerationComplete();
        await new Promise(resolve => setTimeout(resolve, 2000)); // Simulate play time
        console.log(`Mock: Played audio.`);
    }
  },

  listChapterClips: async (chapterName: string): Promise<string[]> => {
    if (typeof window !== 'undefined' && window.api && window.api.listChapterClips) {
      try {
        return await window.api.listChapterClips(chapterName);
      } catch (e) {
        console.warn('Failed to list chapter clips', e);
      }
    }
    return [];
  },

  checkChapterAudio: async (chapterName: string): Promise<boolean> => {
    if (typeof window !== 'undefined' && window.api && window.api.checkChapterAudio) {
      try {
        return await window.api.checkChapterAudio(chapterName);
      } catch (e) {
        console.warn('Failed to check chapter audio', e);
      }
    }
    return false;
  },

  cancelAudio: async (matchString: string): Promise<void> => {
    if (typeof window !== 'undefined' && window.api && window.api.killProcess) {
       console.log(`[PythonBridge] Attempting to kill process matching: ${matchString}`);
       await window.api.killProcess(matchString);
    }
  },

  /**
   * Check if the TTS service process exists (running or warming up)
   * @returns Promise<boolean> - true if service process exists
   */
  isTtsServiceRunning: async (): Promise<boolean> => {
    try {
      if (typeof window !== 'undefined' && window.api && window.api.runPythonScript) {
        const out = await window.api.runPythonScript('src/scripts/check_tts_service.py', []);
        // Service exists if output is 'ready' or 'starting' (warming up)
        return out.includes('ready') || out.includes('starting');
      }
    } catch (e) {
      console.warn('TTS service check failed:', e);
    }
    return false;
  },

  /**
   * Check if the TTS service is fully ready (warmed up)
   * @returns Promise<boolean> - true if service is ready
   */
  isTtsServiceReady: async (): Promise<boolean> => {
    try {
      if (typeof window !== 'undefined' && window.api && window.api.runPythonScript) {
        const out = await window.api.runPythonScript('src/scripts/check_tts_service.py', []);
        return out.includes('ready');
      }
    } catch (e) {
      console.warn('TTS service ready check failed:', e);
    }
    return false;
  },

  /**
   * Start the TTS service
   * @returns Promise<boolean> - true if service started successfully
   */
  startTtsService: async (): Promise<boolean> => {
    try {
      if (typeof window !== 'undefined' && window.api && window.api.runPythonScript) {
        // Use nohup to start service in background
        const out = await window.api.runPythonScript('src/scripts/start_tts_service.py', []);
        // Service started successfully or was already running
        return out.includes('started') || out.includes('success') || out.includes('already running');
      }
    } catch (e) {
      console.error('Failed to start TTS service:', e);
    }
    return false;
  },

  /**
   * Ensure TTS service is running with health check and retry logic
   * Uses exponential backoff: 1s, 2s, 4s, 8s delays, max 4 attempts
   * @returns Promise<string> - service URL ws://localhost:8765 if running
   */
  ensureTtsService: async (): Promise<string> => {
    const maxRetries = 4;
    const delays = [1000, 2000, 4000, 8000]; // 1s, 2s, 4s, 8s
    const pollInterval = 2000; // Poll every 2 seconds for readiness
    const maxWaitTime = 300000; // Max 5 minutes wait for warmup (models take time to load)

    const serviceUrl = 'ws://localhost:8765';

    // First check if already ready
    if (await PythonBridgeService.isTtsServiceReady()) {
      console.log('[TTS] Service is already running and ready');
      return serviceUrl;
    }

    // Check if service is running but warming up
    if (await PythonBridgeService.isTtsServiceRunning()) {
      console.log('[TTS] Service is running, waiting for warmup...');
      const startTime = Date.now();
      while (Date.now() - startTime < maxWaitTime) {
        if (await PythonBridgeService.isTtsServiceReady()) {
          console.log('[TTS] Service is now ready');
          return serviceUrl;
        }
        await new Promise(resolve => setTimeout(resolve, pollInterval));
      }
      throw new Error('TTS service warmup timed out after 5 minutes');
    }

    console.log('[TTS] Service not running, attempting to start...');

    for (let attempt = 0; attempt < maxRetries; attempt++) {
      try {
        const started = await PythonBridgeService.startTtsService();
        
        if (started) {
          console.log(`[TTS] Service start command completed on attempt ${attempt + 1}`);
          
          // Poll for service to be ready (it may still be warming up)
          const startTime = Date.now();
          while (Date.now() - startTime < maxWaitTime) {
            if (await PythonBridgeService.isTtsServiceReady()) {
              console.log(`[TTS] Service is now ready (attempt ${attempt + 1})`);
              return serviceUrl;
            }
            if (!(await PythonBridgeService.isTtsServiceRunning())) {
              console.log(`[TTS] Service process disappeared`);
              break; // Service died, retry
            }
            await new Promise(resolve => setTimeout(resolve, pollInterval));
          }
        }

        if (attempt < maxRetries - 1) {
          console.log(`[TTS] Start attempt ${attempt + 1} incomplete, waiting ${delays[attempt]}ms before retry...`);
          await new Promise(resolve => setTimeout(resolve, delays[attempt]));
        }
      } catch (e) {
        console.error(`[TTS] Attempt ${attempt + 1} error:`, e);
        if (attempt === maxRetries - 1) throw e;
        await new Promise(resolve => setTimeout(resolve, delays[attempt]));
      }
    }

    // All attempts failed
    const isRunning = await PythonBridgeService.isTtsServiceRunning();
    if (isRunning) {
      // Service is running but not ready - show warning but don't throw
      console.warn('[TTS] Service is running but not ready after all attempts');
      return serviceUrl; // Return URL anyway so UI can connect and receive alerts
    }

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
  }
};
