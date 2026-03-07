import { describe, it, expect, vi, beforeEach, type Mock } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useAudio } from '../hooks/useAudio';
import { PythonBridgeService } from '../services/pythonBridge';

// Safe mock helper function
const safeMock = <T extends (...args: any[]) => any>(fn: T | undefined): Mock<T> => (fn ?? vi.fn()) as Mock<T>;

// Mock the PythonBridgeService
vi.mock('../services/pythonBridge', () => ({
  PythonBridgeService: {
    listChapterClips: vi.fn(),
    checkChapterAudio: vi.fn(),
    cancelAudio: vi.fn(),
    showErrorDialog: vi.fn(),
    isTtsServiceRunning: vi.fn(),
    startTtsService: vi.fn(),
    ensureTtsService: vi.fn(),
  },
}));

// Mock window.api
Object.defineProperty(window, 'api', {
  value: {
    runPythonScript: vi.fn(),
    playSoundFile: vi.fn(),
    killProcess: vi.fn(),
  },
  writable: true,
});

describe('useAudio', () => {
  const mockRunPython = safeMock(window.api?.runPythonScript);
  const mockPlaySound = safeMock(window.api?.playSoundFile);

  beforeEach(() => {
    vi.clearAllMocks();
    // Default mock implementations for TTS service methods
    vi.mocked(PythonBridgeService.isTtsServiceRunning).mockResolvedValue(true);
    vi.mocked(PythonBridgeService.startTtsService).mockResolvedValue(true);
    vi.mocked(PythonBridgeService.ensureTtsService).mockResolvedValue('ws://localhost:8765');
    vi.mocked(PythonBridgeService.showErrorDialog).mockResolvedValue(undefined);
  });

  describe('initial state', () => {
    it('should initialize with empty clips and no audio', () => {
      const { result } = renderHook(() => useAudio());
      
      expect(result.current.availableClips).toEqual([]);
      expect(result.current.hasChapterAudio).toBe(false);
    });
  });

  describe('state setters', () => {
    it('should set available clips', () => {
      const { result } = renderHook(() => useAudio());
      
      act(() => {
        result.current.setAvailableClips(['clip1.wav', 'clip2.wav']);
      });
      
      expect(result.current.availableClips).toEqual(['clip1.wav', 'clip2.wav']);
    });

    it('should set chapter audio status', () => {
      const { result } = renderHook(() => useAudio());
      
      act(() => {
        result.current.setHasChapterAudio(true);
      });
      
      expect(result.current.hasChapterAudio).toBe(true);
    });
  });

  describe('refreshClips', () => {
    it('should fetch and set clips for chapter', async () => {
      const { result } = renderHook(() => useAudio());
      
      vi.mocked(PythonBridgeService.listChapterClips).mockResolvedValue(['clip1.wav', 'clip2.wav']);
      vi.mocked(PythonBridgeService.checkChapterAudio).mockResolvedValue(true);
      
      await act(async () => {
        await result.current.refreshClips('Story-Entanglement/story-chapters/chapter_001.md');
      });
      
      expect(PythonBridgeService.listChapterClips).toHaveBeenCalledWith('chapter_001.xml');
      expect(result.current.availableClips).toEqual(['clip1.wav', 'clip2.wav']);
      expect(result.current.hasChapterAudio).toBe(true);
    });

    it('should handle empty chapter file gracefully', async () => {
      const { result } = renderHook(() => useAudio());
      
      await act(async () => {
        await result.current.refreshClips('');
      });
      
      expect(PythonBridgeService.listChapterClips).not.toHaveBeenCalled();
    });

    it('should handle errors gracefully', async () => {
      const { result } = renderHook(() => useAudio());
      const consoleSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
      
      vi.mocked(PythonBridgeService.listChapterClips).mockRejectedValue(new Error('Failed'));
      
      await act(async () => {
        await result.current.refreshClips('chapter_001.md');
      });
      
      expect(consoleSpy).toHaveBeenCalledWith('Failed to refresh clips:', expect.any(Error));
      consoleSpy.mockRestore();
    });
  });

  describe('checkAudioStatus', () => {
    it('should check and set audio status', async () => {
      const { result } = renderHook(() => useAudio());
      
      vi.mocked(PythonBridgeService.checkChapterAudio).mockResolvedValue(true);
      
      await act(async () => {
        await result.current.checkAudioStatus('chapter_001');
      });
      
      expect(PythonBridgeService.checkChapterAudio).toHaveBeenCalledWith('chapter_001');
      expect(result.current.hasChapterAudio).toBe(true);
    });

    it('should handle check errors', async () => {
      const { result } = renderHook(() => useAudio());
      const consoleSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
      
      vi.mocked(PythonBridgeService.checkChapterAudio).mockRejectedValue(new Error('Failed'));
      
      await act(async () => {
        await result.current.checkAudioStatus('chapter_001');
      });
      
      expect(result.current.hasChapterAudio).toBe(false);
      consoleSpy.mockRestore();
    });
  });

  describe('cancelAudio', () => {
    it('should cancel audio generation', async () => {
      const { result } = renderHook(() => useAudio());
      
      vi.mocked(PythonBridgeService.cancelAudio).mockResolvedValue(undefined);
      
      await act(async () => {
        await result.current.cancelAudio('chapter_001');
      });
      
      expect(PythonBridgeService.cancelAudio).toHaveBeenCalledWith('chapter_001');
    });

    it('should handle cancel errors', async () => {
      const { result } = renderHook(() => useAudio());
      const consoleSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
      
      vi.mocked(PythonBridgeService.cancelAudio).mockRejectedValue(new Error('Failed'));
      
      await act(async () => {
        await result.current.cancelAudio('chapter_001');
      });
      
      expect(consoleSpy).toHaveBeenCalled();
      consoleSpy.mockRestore();
    });
  });

  describe('generateAudio', () => {
    beforeEach(() => {
      mockRunPython.mockResolvedValue(
        'Generating Alice chapter_001_001_001_alice...\nApplying character effects to chapter_001_001_001_alice.wav...'
      );
    });

    it('should generate audio for a dialog', async () => {
      const { result } = renderHook(() => useAudio());
      
      const onComplete = vi.fn();
      
      await act(async () => {
        await result.current.generateAudio({
          chapterName: 'chapter_001.xml',
          sectionNum: '001',
          dlgseqNum: '001',
          onComplete,
          skipPlay: true
        });
      });
      
      expect(mockRunPython).toHaveBeenCalledWith(
        'src/scripts/chapter_xml_to_audio.py',
        expect.arrayContaining(['Story-Entanglement/story-xml/chapter_001.xml', '--section', '001', '--dlgseq', '001'])
      );
      expect(onComplete).toHaveBeenCalled();
    });

    it('should parse filename from different output formats', async () => {
      const { result } = renderHook(() => useAudio());
      
      // Test with "saved to" format - matches pattern /saved to .*?(chapter_.*?\.wav)/i
      // The non-greedy .*? should match the path and capture the filename
      mockRunPython.mockResolvedValueOnce('saved to output/clips/chapter_001_002_003_bob.wav');
      
      await act(async () => {
        await result.current.generateAudio({
          chapterName: 'chapter_001.xml',
          sectionNum: '002',
          dlgseqNum: '003',
          skipPlay: false
        });
      });
      
      // Should parse and play the file - note: depends on regex behavior in useAudio.ts
      // The regex saved to .*?(chapter_.*?\.wav) with non-greedy matching
      // captures minimal chars, so it may capture 'chapter_001_002_003_bob.wav'
      expect(mockPlaySound).toHaveBeenCalled();
    });

    it('should throw error if filename cannot be parsed', async () => {
      const { result } = renderHook(() => useAudio());
      
      mockRunPython.mockResolvedValueOnce('Some unparseable output');
      
      await expect(result.current.generateAudio({
        chapterName: 'chapter_001.xml',
        sectionNum: '001',
        dlgseqNum: '001'
      })).rejects.toThrow('Could not parse output filename');
    });

    it('should handle generation errors', async () => {
      const { result } = renderHook(() => useAudio());
      
      mockRunPython.mockRejectedValueOnce(new Error('Generation failed'));
      
      await expect(result.current.generateAudio({
        chapterName: 'chapter_001.xml',
        sectionNum: '001',
        dlgseqNum: '001'
      })).rejects.toThrow('Generation failed');
    });

    it('should skip playback when skipPlay is true', async () => {
      const { result } = renderHook(() => useAudio());
      
      await act(async () => {
        await result.current.generateAudio({
          chapterName: 'chapter_001.xml',
          sectionNum: '001',
          dlgseqNum: '001',
          skipPlay: true
        });
      });
      
      expect(mockPlaySound).not.toHaveBeenCalled();
    });

    it('should use mock fallback when window.api is unavailable', async () => {
      const originalApi = window.api;
      Object.defineProperty(window, 'api', { value: undefined, writable: true });
      
      const { result } = renderHook(() => useAudio());
      
      const onComplete = vi.fn();
      
      await act(async () => {
        await result.current.generateAudio({
          chapterName: 'chapter_001.xml',
          sectionNum: '001',
          dlgseqNum: '001',
          onComplete,
          skipPlay: true
        });
      });
      
      expect(onComplete).toHaveBeenCalled();
      
      Object.defineProperty(window, 'api', { value: originalApi, writable: true });
    });

    it('should handle cancellation during generation', async () => {
      const { result } = renderHook(() => useAudio());
      
      // Create a delayed promise
      mockRunPython.mockImplementation(() => 
        new Promise(resolve => setTimeout(() => resolve('output'), 100))
      );
      
      // Start generation in background
      const generatePromise = result.current.generateAudio({
        chapterName: 'chapter_001.xml',
        sectionNum: '001',
        dlgseqNum: '001'
      });
      
      // Cancel immediately
      await act(async () => {
        await result.current.cancelAudio('chapter_001');
      });
      
      await generatePromise;
      
      // Should not throw
      expect(PythonBridgeService.cancelAudio).toHaveBeenCalled();
    });
  });

  describe('edge cases', () => {
    it('should handle null currentChapterFile in refreshClips', async () => {
      const { result } = renderHook(() => useAudio());
      
      await act(async () => {
        await result.current.refreshClips('');
      });
      
      expect(result.current.availableClips).toEqual([]);
    });

    it('should handle file paths without extension', async () => {
      const { result } = renderHook(() => useAudio());
      
      vi.mocked(PythonBridgeService.listChapterClips).mockResolvedValue([]);
      
      await act(async () => {
        await result.current.refreshClips('some/file/without/extension');
      });
      
      expect(PythonBridgeService.listChapterClips).toHaveBeenCalled();
    });
  });
});
