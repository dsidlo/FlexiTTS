import { useState, useCallback, useRef } from 'react';
import { PythonBridgeService } from '../services/pythonBridge';
import { debugLog } from '../utils/debugLogger';

const isTestEnvironment = (): boolean => {
  try {
    return Boolean(import.meta.env?.MODE === 'test' || import.meta.env?.VITEST || process.env.VITEST);
  } catch {
    return false;
  }
};

const testSafeConsole = {
  warn: (...args: unknown[]) => {
    if (!isTestEnvironment()) {
      console.warn(...args);
    }
  },
};

export interface UseAudioReturn {
  // State
  availableClips: string[];
  hasChapterAudio: boolean;
  
  // Setters
  setAvailableClips: React.Dispatch<React.SetStateAction<string[]>>;
  setHasChapterAudio: React.Dispatch<React.SetStateAction<boolean>>;
  
  // Actions
  refreshClips: (currentChapterFile: string) => Promise<void>;
  checkAudioStatus: (chapterName: string) => Promise<void>;
  generateAudio: (params: AudioGenerationParams) => Promise<void>;
  cancelAudio: (chapterName: string) => Promise<void>;
}

export interface AudioGenerationParams {
  chapterName: string;
  sectionNum: string;
  dlgseqNum: string;
  onComplete?: () => void;
  skipPlay?: boolean;
}

/**
 * Hook for managing audio-related operations.
 * Handles audio generation, clip listing, and audio status checking.
 */
export const useAudio = (storyDirectory?: string): UseAudioReturn => {
  const [availableClips, setAvailableClips] = useState<string[]>([]);
  const [hasChapterAudio, setHasChapterAudio] = useState(false);
  
  // Use refs to avoid stale closures in async operations
  const isCancelledRef = useRef(false);

  /**
   * Refresh the list of available audio clips for a chapter
   * @param currentChapterFile - The current chapter file path
   */
  const refreshClips = useCallback(async (currentChapterFile: string) => {
    const chapterName = currentChapterFile.split('/').pop()?.replace('.md', '.xml') || '';
    if (!chapterName) return;
    
    try {
      const clips = await PythonBridgeService.listChapterClips(chapterName);
      setAvailableClips(clips);
      
      const hasAudio = await PythonBridgeService.checkChapterAudio(chapterName);
      setHasChapterAudio(hasAudio);
      
      // Check render state to determine if chapter needs re-rendering
      if (storyDirectory) {
        try {
          const renderState = await PythonBridgeService.checkChapterRenderState(chapterName, storyDirectory);
          debugLog.info('useAudio:refreshClips', 'Render state checked', { 
            chapterName, 
            needsRender: renderState?.needs_render, 
            staleCount: renderState?.stale_count 
          });
        } catch (renderErr) {
          debugLog.warn('useAudio:refreshClips', 'Failed to check render state', renderErr);
        }
      }
    } catch (e) {
      testSafeConsole.warn('Failed to refresh clips:', e);
    }
  }, [storyDirectory]);

  /**
   * Check if chapter has generated audio
   * @param chapterName - The chapter name to check
   */
  const checkAudioStatus = useCallback(async (chapterName: string) => {
    try {
      const hasAudio = await PythonBridgeService.checkChapterAudio(chapterName);
      setHasChapterAudio(hasAudio);
    } catch (e) {
      testSafeConsole.warn('Failed to check chapter audio:', e);
      setHasChapterAudio(false);
    }
  }, []);

  /**
   * Cancel ongoing audio generation or playback
   * @param chapterName - The chapter name to cancel
   */
  const cancelAudio = useCallback(async (chapterName: string) => {
    isCancelledRef.current = true;
    try {
      await PythonBridgeService.cancelAudio(chapterName);
    } catch (e) {
      testSafeConsole.warn('Failed to cancel audio:', e);
    }
  }, []);

  /**
   * Generate audio for a specific dialog with TTS service health check
   * @param params - Audio generation parameters
   */
  const generateAudio = useCallback(async ({
    chapterName,
    sectionNum,
    dlgseqNum,
    onComplete,
    skipPlay = false
  }: AudioGenerationParams) => {
    const id = 'useAudio:generateAudio';
    const storyDir = storyDirectory || 'Story-Default';
    const xmlInputPath = `${storyDir}/story-xml/${chapterName}`;
    debugLog.info(id, '[RESOURCE-ACCESS] Starting audio generation', { chapterName, sectionNum, dlgseqNum, xmlInputPath, resourceType: 'xml', operation: 'read' });
    
    isCancelledRef.current = false;
    
    try {
      // Start TTS WebSocket service (--tts-service enables fast GPU-accelerated rendering)
      // Required for audio generation - returns ws://localhost:8765 for remote TTS mode
      const ttsServiceUrl = await PythonBridgeService.ensureTtsService();
      debugLog.info(id, '[RESOURCE-ACCESS] TTS service ready', { ttsServiceUrl });
      
      if (isCancelledRef.current) return;
      
      if (typeof window !== 'undefined' && window.api && window.api.runPythonScript) {
        debugLog.info(id, '[RESOURCE-ACCESS] Running chapter_xml_to_audio.py', { xmlInputPath });
        const out = await window.api.runPythonScript('src/scripts/chapter_xml_to_audio.py', [
          `${storyDir}/story-xml/${chapterName}`,
          `--section`, sectionNum,
          `--dlgseq`, dlgseqNum,
          `--tts-service`, ttsServiceUrl
        ]);
        
        if (isCancelledRef.current) return;
        debugLog.info(id, '[RESOURCE-ACCESS] Python script completed', { outputLength: out?.length });
        
        // Parse output to find generated WAV file
        let wavName = '';
        
        const effectMatch = out.match(/Applying character effects to (.*?\.wav)/i);
        if (effectMatch?.[1]) {
          wavName = effectMatch[1];
        } else {
          const genMatch = out.match(/Generating \w+ (chapter_\d+_\d+_\d+_[^.]+)/i);
          if (genMatch?.[1]) {
            wavName = genMatch[1] + ".wav";
          } else {
            const saveMatch = out.match(/save clip to .*?(chapter_.*?\.wav)/i) || 
                            out.match(/saved to .*?(chapter_.*?\.wav)/i);
            if (saveMatch?.[1]) {
              wavName = saveMatch[1];
            } else {
              const altMatch = out.match(/(chapter_.*?\.wav)/i);
              if (altMatch?.[1]) {
                wavName = altMatch[1];
              }
            }
          }
        }

        if (wavName) {
          debugLog.info(id, '[RESOURCE-ACCESS] Audio clip generated', { wavName });
          if (onComplete && !isCancelledRef.current) {
            onComplete();
          }
          
          if (!skipPlay && !isCancelledRef.current) {
            const chapterStem = chapterName.replace('.xml', '');
            const audioOutputPath = `${storyDir}/story-audio/clips/${chapterStem}/${wavName}`;
            debugLog.info(id, '[RESOURCE-ACCESS] Reading audio file for playback', { audioOutputPath, resourceType: 'audio', operation: 'read' });
            
            // Read audio file via Electron IPC and play as data URL (client-side)
            if (window.api?.readAudioFile) {
              const dataUrl = await window.api.readAudioFile(audioOutputPath);
              debugLog.info(id, '[RESOURCE-ACCESS] Audio file loaded', { audioOutputPath, length: dataUrl?.length });
              // Create temporary audio element for playback
              const audio = new Audio(dataUrl);
              await audio.play();
              debugLog.info(id, '[RESOURCE-ACCESS] Audio playback completed', { audioOutputPath });
            }
          }
        } else {
          debugLog.error(id, '[RESOURCE-ACCESS] Could not parse output filename', { output: out });
          throw new Error("Could not parse output filename");
        }
      } else {
        // Mock fallback
        debugLog.warn(id, '[RESOURCE-ACCESS] Mock audio generation', { chapterName, sectionNum, dlgseqNum });
        await new Promise(resolve => setTimeout(resolve, 2000));
        if (onComplete && !isCancelledRef.current) {
          onComplete();
        }
      }
      debugLog.info(id, '[RESOURCE-ACCESS] Audio generation completed successfully', { chapterName });
    } catch (err: unknown) {
      if (!isCancelledRef.current) {
        debugLog.exception(id, '[RESOURCE-ACCESS] Failed to generate audio', err as Error, { chapterName });
        // Show user-friendly error
        const errorMessage = err instanceof Error 
          ? err.message 
          : "An unknown error occurred during audio generation";
        await PythonBridgeService.showErrorDialog(
          "Audio Generation Failed", 
          `Failed to generate audio: ${errorMessage}\n\nPlease ensure the TTS service is running and try again.`
        );
        throw err;
      }
    }
  }, []);

  return {
    availableClips,
    hasChapterAudio,
    setAvailableClips,
    setHasChapterAudio,
    refreshClips,
    checkAudioStatus,
    generateAudio,
    cancelAudio,
  };
};
