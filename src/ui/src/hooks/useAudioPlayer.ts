import { useState, useCallback, useRef, useEffect } from 'react';

export interface AudioPlayerState {
  isPlaying: boolean;
  isPaused: boolean;
  currentTime: number;
  duration: number;
  error: string | null;
}

export interface UseAudioPlayerReturn extends AudioPlayerState {
  play: (audioUrl: string) => Promise<void>;
  pause: () => void;
  resume: () => void;
  stop: () => void;
  seek: (time: number) => void;
}

/**
 * Hook for client-side audio playback using HTML5 Audio API.
 * Replaces server-side aplay with browser-based playback.
 */
export const useAudioPlayer = (): UseAudioPlayerReturn => {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [state, setState] = useState<AudioPlayerState>({
    isPlaying: false,
    isPaused: false,
    currentTime: 0,
    duration: 0,
    error: null,
  });

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current.src = '';
        audioRef.current = null;
      }
    };
  }, []);

  const updateState = useCallback((updates: Partial<AudioPlayerState>) => {
    setState(prev => ({ ...prev, ...updates }));
  }, []);

  const play = useCallback(async (audioUrl: string) => {
    // Stop any currently playing audio
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.src = '';
    }

    try {
      const audio = new Audio(audioUrl);
      audioRef.current = audio;

      // Set up event listeners
      audio.addEventListener('loadedmetadata', () => {
        updateState({ duration: audio.duration });
      });

      audio.addEventListener('timeupdate', () => {
        updateState({ currentTime: audio.currentTime });
      });

      audio.addEventListener('ended', () => {
        updateState({ 
          isPlaying: false, 
          isPaused: false, 
          currentTime: 0 
        });
      });

      audio.addEventListener('error', (e) => {
        console.error('Audio playback error:', e);
        updateState({ 
          error: 'Failed to play audio', 
          isPlaying: false 
        });
      });

      await audio.play();
      updateState({ 
        isPlaying: true, 
        isPaused: false, 
        error: null 
      });
    } catch (err) {
      console.error('Failed to play audio:', err);
      updateState({ 
        error: 'Failed to play audio', 
        isPlaying: false 
      });
      throw err;
    }
  }, [updateState]);

  const pause = useCallback(() => {
    if (audioRef.current && !audioRef.current.paused) {
      audioRef.current.pause();
      updateState({ isPaused: true });
    }
  }, [updateState]);

  const resume = useCallback(() => {
    if (audioRef.current && audioRef.current.paused) {
      audioRef.current.play().catch(err => {
        console.error('Failed to resume audio:', err);
        updateState({ error: 'Failed to resume audio' });
      });
      updateState({ isPaused: false });
    }
  }, [updateState]);

  const stop = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
      audioRef.current.src = '';
      audioRef.current = null;
    }
    updateState({ 
      isPlaying: false, 
      isPaused: false, 
      currentTime: 0,
      duration: 0 
    });
  }, [updateState]);

  const seek = useCallback((time: number) => {
    if (audioRef.current) {
      audioRef.current.currentTime = Math.max(0, Math.min(time, audioRef.current.duration || 0));
    }
  }, []);

  return {
    ...state,
    play,
    pause,
    resume,
    stop,
    seek,
  };
};

export default useAudioPlayer;
