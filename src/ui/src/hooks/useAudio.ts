import { useState, useCallback, useRef } from 'react';
import { PythonBridgeService } from '../services/pythonBridge';

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
export const useAudio = (): UseAudioReturn => {
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
    } catch (e) {
      console.warn('Failed to refresh clips:', e);
    }
  }, []);

  /**
   * Check if chapter has generated audio
   * @param chapterName - The chapter name to check
   */
  const checkAudioStatus = useCallback(async (chapterName: string) => {
    try {
      const hasAudio = await PythonBridgeService.checkChapterAudio(chapterName);
      setHasChapterAudio(hasAudio);
    } catch (e) {
      console.warn('Failed to check chapter audio:', e);
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
      console.warn('Failed to cancel audio:', e);
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
    isCancelledRef.current = false;
    
    try {
      // Start TTS WebSocket service (--tts-service enables fast GPU-accelerated rendering)
      // Required for audio generation - returns ws://localhost:8765 for remote TTS mode
      const ttsServiceUrl = await PythonBridgeService.ensureTtsService();
      
      if (isCancelledRef.current) return;
      
      if (typeof window !== 'undefined' && window.api && window.api.runPythonScript) {
        const out = await window.api.runPythonScript('src/scripts/chapter_xml_to_audio.py', [
          `Story-Entanglement/story-xml/${chapterName}`,
          `--section`, sectionNum,
          `--dlgseq`, dlgseqNum,
          `--tts-service`, ttsServiceUrl
        ]);
        
        if (isCancelledRef.current) return;
        
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
          if (onComplete && !isCancelledRef.current) {
            onComplete();
          }
          
          if (!skipPlay && !isCancelledRef.current) {
            const chapterStem = chapterName.replace('.xml', '');
            const relativePath = `Story-Entanglement/story-audio/clips/${chapterStem}/${wavName}`;
            
            // Read audio file via Electron IPC and play as data URL (client-side)
            if (window.api?.readAudioFile) {
              const dataUrl = await window.api.readAudioFile(relativePath);
              // Create temporary audio element for playback
              const audio = new Audio(dataUrl);
              await audio.play();
            }
          }
        } else {
          console.error("Could not parse output filename from Python stdout", out);
          throw new Error("Could not parse output filename");
        }
      } else {
        // Mock fallback
        console.log(`Mock: Generating audio for ${chapterName} s:${sectionNum} d:${dlgseqNum}...`);
        await new Promise(resolve => setTimeout(resolve, 2000));
        if (onComplete && !isCancelledRef.current) {
          onComplete();
        }
      }
    } catch (err: unknown) {
      if (!isCancelledRef.current) {
        console.error("Failed to generate audio:", err);
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
