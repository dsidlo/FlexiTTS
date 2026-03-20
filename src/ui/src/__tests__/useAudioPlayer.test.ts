import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useAudioPlayer } from '../hooks/useAudioPlayer';

// Store reference to original Audio mock
const createMockAudio = () => ({
  src: '',
  paused: true,
  currentTime: 0,
  duration: 100,
  play: vi.fn().mockResolvedValue(undefined),
  pause: vi.fn(),
  addEventListener: vi.fn(),
  removeEventListener: vi.fn(),
});

// Mock HTML5 Audio
global.Audio = vi.fn().mockImplementation(createMockAudio) as unknown as typeof Audio;

describe('useAudioPlayer', () => {
  let mockAudio: any;
  let eventListeners: Map<string, Function[]>;

  beforeEach(() => {
    eventListeners = new Map();
    mockAudio = {
      src: '',
      paused: true,
      currentTime: 0,
      duration: 100,
      play: vi.fn().mockResolvedValue(undefined),
      pause: vi.fn(),
      addEventListener: vi.fn((event: string, handler: Function) => {
        if (!eventListeners.has(event)) {
          eventListeners.set(event, []);
        }
        eventListeners.get(event)!.push(handler);
      }),
      removeEventListener: vi.fn(),
    };
    vi.mocked(global.Audio).mockReturnValue(mockAudio);
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  describe('initial state', () => {
    it('should initialize with correct default state', () => {
      const { result } = renderHook(() => useAudioPlayer());

      expect(result.current.isPlaying).toBe(false);
      expect(result.current.isPaused).toBe(false);
      expect(result.current.currentTime).toBe(0);
      expect(result.current.duration).toBe(0);
      expect(result.current.error).toBe(null);
    });
  });

  describe('play', () => {
    it('should play audio successfully', async () => {
      const { result } = renderHook(() => useAudioPlayer());

      await act(async () => {
        await result.current.play('/test/audio.mp3');
      });

      expect(result.current.isPlaying).toBe(true);
      expect(result.current.error).toBe(null);
      expect(mockAudio.play).toHaveBeenCalled();
    });

    it('should stop previous audio before playing new audio', async () => {
      const { result } = renderHook(() => useAudioPlayer());

      await act(async () => {
        await result.current.play('/test/audio1.mp3');
      });

      const firstAudio = mockAudio;
      const secondAudio = {
        ...mockAudio,
        play: vi.fn().mockResolvedValue(undefined),
      };
      vi.mocked(global.Audio).mockReturnValue(secondAudio);

      await act(async () => {
        await result.current.play('/test/audio2.mp3');
      });

      expect(firstAudio.pause).toHaveBeenCalled();
    });

    it('should set up event listeners on play', async () => {
      const { result } = renderHook(() => useAudioPlayer());

      await act(async () => {
        await result.current.play('/test/audio.mp3');
      });

      expect(mockAudio.addEventListener).toHaveBeenCalledWith('loadedmetadata', expect.any(Function));
      expect(mockAudio.addEventListener).toHaveBeenCalledWith('timeupdate', expect.any(Function));
      expect(mockAudio.addEventListener).toHaveBeenCalledWith('ended', expect.any(Function));
      expect(mockAudio.addEventListener).toHaveBeenCalledWith('error', expect.any(Function));
    });

    it('should update duration on loadedmetadata event', async () => {
      const { result } = renderHook(() => useAudioPlayer());

      await act(async () => {
        await result.current.play('/test/audio.mp3');
      });

      const loadedMetadataHandler = eventListeners.get('loadedmetadata')?.[0];
      if (loadedMetadataHandler) {
        mockAudio.duration = 150;
        act(() => {
          loadedMetadataHandler();
        });
        expect(result.current.duration).toBe(150);
      }
    });

    it('should update currentTime on timeupdate event', async () => {
      const { result } = renderHook(() => useAudioPlayer());

      await act(async () => {
        await result.current.play('/test/audio.mp3');
      });

      const timeUpdateHandler = eventListeners.get('timeupdate')?.[0];
      if (timeUpdateHandler) {
        mockAudio.currentTime = 45;
        act(() => {
          timeUpdateHandler();
        });
        expect(result.current.currentTime).toBe(45);
      }
    });

    it('should reset state on ended event', async () => {
      const { result } = renderHook(() => useAudioPlayer());

      await act(async () => {
        await result.current.play('/test/audio.mp3');
      });

      act(() => {
        result.current.seek(50);
      });

      const endedHandler = eventListeners.get('ended')?.[0];
      if (endedHandler) {
        act(() => {
          endedHandler();
        });
        expect(result.current.isPlaying).toBe(false);
        expect(result.current.isPaused).toBe(false);
        expect(result.current.currentTime).toBe(0);
      }
    });

    it('should handle error event', async () => {
      const { result } = renderHook(() => useAudioPlayer());

      await act(async () => {
        await result.current.play('/test/audio.mp3');
      });

      const errorHandler = eventListeners.get('error')?.[0];
      if (errorHandler) {
        act(() => {
          errorHandler(new Event('error'));
        });
        expect(result.current.error).toBe('Failed to play audio');
        expect(result.current.isPlaying).toBe(false);
      }
    });

    it('should handle play error', async () => {
      const { result } = renderHook(() => useAudioPlayer());

      // Create a new audio mock that rejects for this specific test
      Object.defineProperty(globalThis, 'Audio', {
        value: vi.fn().mockImplementation(() => ({
          src: '',
          paused: true,
          currentTime: 0,
          duration: 100,
          play: vi.fn().mockRejectedValue(new Error('Playback failed')),
          pause: vi.fn(),
          addEventListener: vi.fn(),
          removeEventListener: vi.fn(),
        })),
        writable: true,
      });

      try {
        await act(async () => {
          await result.current.play('/test/audio.mp3');
        });
      } catch {
        // Expected to throw
      }

      // The error state update happens asynchronously after the play() fails
      // We wait for the state update by checking after a tick
      await act(async () => {});

      expect(result.current.error).toBe('Failed to play audio');
      expect(result.current.isPlaying).toBe(false);

      // Restore original mock
      Object.defineProperty(globalThis, 'Audio', {
        value: vi.fn().mockImplementation(createMockAudio),
        writable: true,
      });
    });
  });

  describe('pause', () => {
    it('should pause playing audio', async () => {
      const { result } = renderHook(() => useAudioPlayer());

      // Create mock with paused: false to simulate playing audio
      const playingMockAudio = {
        ...mockAudio,
        paused: false,
      };
      vi.mocked(global.Audio).mockReturnValue(playingMockAudio);

      await act(async () => {
        await result.current.play('/test/audio.mp3');
      });

      act(() => {
        result.current.pause();
      });

      expect(playingMockAudio.pause).toHaveBeenCalled();
      expect(result.current.isPaused).toBe(true);
    });

    it('should not pause if already paused', async () => {
      const { result } = renderHook(() => useAudioPlayer());

      await act(async () => {
        await result.current.play('/test/audio.mp3');
      });

      act(() => {
        result.current.pause();
      });

      mockAudio.pause.mockClear();
      mockAudio.paused = true;

      act(() => {
        result.current.pause();
      });

      // Second pause should not call pause again since it's already paused
      expect(mockAudio.pause).not.toHaveBeenCalled();
    });
  });

  describe('resume', () => {
    it('should resume paused audio', async () => {
      const { result } = renderHook(() => useAudioPlayer());

      await act(async () => {
        await result.current.play('/test/audio.mp3');
      });

      act(() => {
        result.current.pause();
      });

      mockAudio.paused = true;
      await act(async () => {
        result.current.resume();
      });

      expect(mockAudio.play).toHaveBeenCalled();
      expect(result.current.isPaused).toBe(false);
    });

    it('should handle resume error', async () => {
      const { result } = renderHook(() => useAudioPlayer());

      await act(async () => {
        await result.current.play('/test/audio.mp3');
      });

      act(() => {
        result.current.pause();
      });

      mockAudio.paused = true;
      mockAudio.play = vi.fn().mockRejectedValue(new Error('Resume failed'));

      await act(async () => {
        result.current.resume();
      });

      // Wait for promise rejection to be handled
      await new Promise(resolve => setTimeout(resolve, 0));

      expect(result.current.error).toBe('Failed to resume audio');
    });

    it('should not resume if audio not paused', async () => {
      const { result } = renderHook(() => useAudioPlayer());

      await act(async () => {
        await result.current.play('/test/audio.mp3');
      });

      mockAudio.play.mockClear();
      mockAudio.paused = false;

      act(() => {
        result.current.resume();
      });

      expect(mockAudio.play).not.toHaveBeenCalled();
    });
  });

  describe('stop', () => {
    it('should stop audio and reset state', async () => {
      const { result } = renderHook(() => useAudioPlayer());

      await act(async () => {
        await result.current.play('/test/audio.mp3');
      });

      act(() => {
        result.current.stop();
      });

      expect(mockAudio.pause).toHaveBeenCalled();
      expect(mockAudio.currentTime).toBe(0);
      expect(result.current.isPlaying).toBe(false);
      expect(result.current.isPaused).toBe(false);
      expect(result.current.currentTime).toBe(0);
      expect(result.current.duration).toBe(0);
    });

    it('should handle stop when no audio is playing', () => {
      const { result } = renderHook(() => useAudioPlayer());

      act(() => {
        result.current.stop();
      });

      // Should not throw
      expect(result.current.isPlaying).toBe(false);
      expect(result.current.currentTime).toBe(0);
    });
  });

  describe('seek', () => {
    it('should seek to specified time', async () => {
      const { result } = renderHook(() => useAudioPlayer());

      await act(async () => {
        await result.current.play('/test/audio.mp3');
      });

      mockAudio.duration = 100;

      act(() => {
        result.current.seek(50);
      });

      expect(mockAudio.currentTime).toBe(50);
    });

    it('should clamp seek time to valid range', async () => {
      const { result } = renderHook(() => useAudioPlayer());

      await act(async () => {
        await result.current.play('/test/audio.mp3');
      });

      mockAudio.duration = 100;

      // Test negative time
      act(() => {
        result.current.seek(-10);
      });
      expect(mockAudio.currentTime).toBe(0);

      // Test time beyond duration
      act(() => {
        result.current.seek(200);
      });
      expect(mockAudio.currentTime).toBe(100);
    });

    it('should handle seek when no audio loaded', () => {
      const { result } = renderHook(() => useAudioPlayer());

      act(() => {
        result.current.seek(50);
      });

      // Should not throw
      expect(result.current.currentTime).toBe(0);
    });
  });

  describe('cleanup', () => {
    it('should cleanup on unmount', async () => {
      const { result, unmount } = renderHook(() => useAudioPlayer());

      await act(async () => {
        await result.current.play('/test/audio.mp3');
      });

      unmount();

      expect(mockAudio.pause).toHaveBeenCalled();
      expect(mockAudio.src).toBe('');
    });
  });
});
