import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import { useChapter } from '../hooks/useChapter';
import type { DialogElement, StoryConfig } from '../models/types';

// Mock must be defined before imports
vi.mock('../services/pythonBridge', () => ({
  PythonBridgeService: {
    validateChapterXML: vi.fn(),
    readChapterFile: vi.fn(),
    listChapterClips: vi.fn(),
    checkChapterAudio: vi.fn(),
    writeChapterFile: vi.fn(),
    checkXmlExists: vi.fn(),
    checkXmlExistsForStory: vi.fn(),
    showConfirmDialog: vi.fn(),
    showErrorDialog: vi.fn(),
    validateConfig: vi.fn(),
    loadStoryConfig: vi.fn(),
    listChapterFiles: vi.fn(),
    readFile: vi.fn(),
    playSoundFile: vi.fn(),
    killProcess: vi.fn(),
    checkStoryFileExists: vi.fn(),
  },
}));

// Import after mock
import { PythonBridgeService } from '../services/pythonBridge';

// Mock window.api
Object.defineProperty(window, 'api', {
  value: {
    runPythonScript: vi.fn(),
    readFile: vi.fn(),
    readAudioFile: vi.fn(),
    writeFile: vi.fn(),
    showErrorDialog: vi.fn(),
    showConfirmDialog: vi.fn(),
    listChapterClips: vi.fn(),
    checkChapterAudio: vi.fn(),
    checkXmlExists: vi.fn(),
    listChapterFiles: vi.fn(),
    playSoundFile: vi.fn(),
    killProcess: vi.fn(),
    checkStoryFileExists: vi.fn(),
  },
  writable: true,
});

const createMockChapterXML = (name: string, dialogs: { dlgseq: string; character: string; text: string }[]) => {
  const dialogNodes = dialogs.map(d => 
    `  <dialog dlgseq="${d.dlgseq}" character="${d.character}">${d.text}</dialog>\n`
  ).join('');
  return `<?xml version="1.0" encoding="UTF-8"?>
<chapter name="${name}">
${dialogNodes}</chapter>`;
};

describe('useChapter', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(PythonBridgeService.validateChapterXML).mockResolvedValue(undefined);
    vi.mocked(PythonBridgeService.readChapterFile).mockResolvedValue(
      createMockChapterXML('Test Chapter', [
        { dlgseq: '1', character: 'Alice', text: 'Hello' },
        { dlgseq: '2', character: 'Bob', text: 'World' }
      ])
    );
    vi.mocked(PythonBridgeService.listChapterClips).mockResolvedValue([]);
    vi.mocked(PythonBridgeService.checkChapterAudio).mockResolvedValue(false);
    vi.mocked(PythonBridgeService.checkStoryFileExists).mockResolvedValue(true);
  });

  describe('initial state', () => {
    it('should initialize with null values', () => {
      const { result } = renderHook(() => useChapter());
      
      expect(result.current.config).toBeNull();
      expect(result.current.chapter).toBeNull();
      expect(result.current.chapterList).toEqual([]);
      expect(result.current.currentChapterFile).toBe('');
      expect(result.current.hasUnsavedChanges).toBe(false);
    });
  });

  describe('state setters', () => {
    it('should set config', () => {
      const { result } = renderHook(() => useChapter());
      const mockConfig = { 
        global: { 
          'story-dir': '',
          voices: '',
          chapters: '',
          'story-xml': '',
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
      
      act(() => {
        result.current.setConfig(mockConfig);
      });
      
      expect(result.current.config).toEqual(mockConfig);
    });

    it('should set chapter list', () => {
      const { result } = renderHook(() => useChapter());
      
      act(() => {
        result.current.setChapterList(['ch1.xml', 'ch2.xml']);
      });
      
      expect(result.current.chapterList).toEqual(['ch1.xml', 'ch2.xml']);
    });

    it('should update selected character filter', () => {
      const { result } = renderHook(() => useChapter());
      
      act(() => {
        result.current.setSelectedCharacterFilter('Alice');
      });
      
      expect(result.current.selectedCharacterFilter).toBe('Alice');
    });

    it('should track available clips', () => {
      const { result } = renderHook(() => useChapter());
      
      act(() => {
        result.current.setAvailableClips(['clip1.wav', 'clip2.wav']);
      });
      
      expect(result.current.availableClips).toEqual(['clip1.wav', 'clip2.wav']);
    });

    it('should track chapter audio status', () => {
      const { result } = renderHook(() => useChapter());
      
      act(() => {
        result.current.setHasChapterAudio(true);
      });
      
      expect(result.current.hasChapterAudio).toBe(true);
    });
  });

  describe('loadChapter', () => {
    it('should load and parse chapter XML', async () => {
      const { result } = renderHook(() => useChapter());
      
      await act(async () => {
        await result.current.loadChapter('test.xml');
      });
      
      expect(result.current.chapter).not.toBeNull();
      expect(result.current.chapter?.name).toBe('Test Chapter');
      expect(result.current.chapter?.dialogs).toHaveLength(2);
      expect(PythonBridgeService.readChapterFile).toHaveBeenCalledWith('test.xml');
    });

    it('should set available clips', async () => {
      const { result } = renderHook(() => useChapter());
      vi.mocked(PythonBridgeService.listChapterClips).mockResolvedValue(['clip1.wav']);
      
      await act(async () => {
        await result.current.loadChapter('chapter_001.xml');
      });
      
      expect(result.current.availableClips).toEqual(['clip1.wav']);
    });

    it('should check chapter audio status', async () => {
      const { result } = renderHook(() => useChapter());
      vi.mocked(PythonBridgeService.checkChapterAudio).mockResolvedValue(true);
      
      await act(async () => {
        await result.current.loadChapter('chapter_001.xml');
      });
      
      expect(result.current.hasChapterAudio).toBe(true);
    });

    it('should reset character filter on load', async () => {
      const { result } = renderHook(() => useChapter());
      
      act(() => {
        result.current.setSelectedCharacterFilter('Alice');
      });
      
      await act(async () => {
        await result.current.loadChapter('test.xml');
      });
      
      expect(result.current.selectedCharacterFilter).toBe('');
    });

    it('should set XML content after load', async () => {
      const { result } = renderHook(() => useChapter());
      
      await act(async () => {
        await result.current.loadChapter('test.xml');
      });
      
      expect(result.current.xmlContent).toContain('<?xml version="1.0"');
      expect(result.current.hasUnsavedChanges).toBe(false);
    });
  });

  describe('handleUpdateDialog', () => {
    it('should update dialog and mark changes', async () => {
      const { result } = renderHook(() => useChapter());
      
      await act(async () => {
        await result.current.loadChapter('test.xml');
      });

      const updatedDialog = {
        _index: 0,
        dlgseq: '1',
        sectionId: '1',
        character: 'Alice',
        text: 'Updated text',
        attributes: { dlgseq: '1', character: 'Alice' }
      };

      await act(async () => {
        await result.current.handleUpdateDialog('1', '1', updatedDialog as DialogElement);
      });

      expect(result.current.chapter?.dialogs[0].text).toBe('Updated text');
      expect(result.current.hasUnsavedChanges).toBe(true);
    });

    it('should match dialog by _index when available', async () => {
      const { result } = renderHook(() => useChapter());
      
      await act(async () => {
        await result.current.loadChapter('test.xml');
      });

      const updatedDialog = {
        _index: 1,
        dlgseq: '99',
        sectionId: '99',
        character: 'Updated',
        text: 'By index',
        attributes: {}
      };

      await act(async () => {
        await result.current.handleUpdateDialog('1', '1', updatedDialog as DialogElement);
      });

      expect(result.current.chapter?.dialogs[1].text).toBe('By index');
    });

    it('should immediately revalidate after changing a dialog character', async () => {
      const { result } = renderHook(() => useChapter('Story-Fractured_Assistance'));
      const mockConfig = {
        global: {
          'story-dir': '',
          voices: 'story-voice-refs/',
          chapters: '',
          'story-xml': '',
          logs: '',
          'story-audio': '',
          clips: '',
          'clip-separation': 0,
        },
        'llm-xml-generator': [],
        'dialog-effects': [{ name: 'cave' }],
        'story-audio-post-process': {},
        characters: [
          { name: 'Alice', 'voice-sample': 'alice.wav' },
          { name: 'Hendrixx-echo', 'voice-sample': 'missing.wav', 'dialog-effects': ['bad-1', 'bad-2'] },
        ],
      } as StoryConfig;

      act(() => {
        result.current.setConfig(mockConfig);
      });

      vi.mocked(PythonBridgeService.checkStoryFileExists).mockResolvedValue(false);

      await act(async () => {
        await result.current.loadChapter('test.xml', mockConfig, 'Story-Fractured_Assistance');
      });

      await act(async () => {
        await result.current.handleUpdateDialog('1', '0', {
          ...result.current.chapter!.dialogs[0],
          character: 'Hendrixx-echo',
          attributes: {
            ...result.current.chapter!.dialogs[0].attributes,
            character: 'Alice',
          },
        });
      });

      const issues = result.current.chapter?.dialogs[0].validationIssues || [];
      expect(issues.map((issue) => issue.code)).toEqual(['invalid-dialog-effects', 'invalid-voice-sample']);
    });
  });

  describe('handleChapterSelect - basic flow', () => {
    it('should load chapter when XML exists', async () => {
      const { result } = renderHook(() => useChapter());
      
      vi.mocked(PythonBridgeService.checkXmlExistsForStory).mockResolvedValue(true);
      vi.mocked(PythonBridgeService.showConfirmDialog).mockResolvedValue(1); // Discard
      
      await act(async () => {
        await result.current.handleChapterSelect('Story-Entanglement/story-chapters/test.md');
      });
      
      await waitFor(() => {
        expect(result.current.currentChapterFile).toBe('Story-Entanglement/story-chapters/test.md');
      });
    });
  });

  describe('unsaved changes ref', () => {
    it('should sync ref with state', async () => {
      const { result } = renderHook(() => useChapter());
      
      await act(async () => {
        await result.current.loadChapter('test.xml');
      });

      // Update dialog to create unsaved changes
      await act(async () => {
        await result.current.handleUpdateDialog('1', '1', {
          _index: 0,
          dlgseq: '1',
          sectionId: '1',
          character: 'Alice',
          text: 'Changed',
          attributes: { dlgseq: '1', character: 'Alice' }
        });
      });

      expect(result.current.hasUnsavedChangesRef.current).toBe(true);
    });

    it('should allow direct ref value updates', () => {
      const { result } = renderHook(() => useChapter());
      
      act(() => {
        result.current.setLastSavedXmlValue('updated xml');
      });
      
      expect(result.current.lastSavedXmlRef.current).toBe('updated xml');
    });
  });

  describe('edge cases', () => {
    it('should handle XML validation warnings gracefully', async () => {
      vi.mocked(PythonBridgeService.validateChapterXML).mockRejectedValue(new Error('Invalid XML'));
      
      const { result } = renderHook(() => useChapter());
      
      await act(async () => {
        await result.current.loadChapter('test.xml');
      });
      
      // Should still load despite validation error
      expect(result.current.chapter).not.toBeNull();
    });

    it('should not update dialog if chapter is null', async () => {
      const { result } = renderHook(() => useChapter());
      
      const testDialog = {
        _index: 0,
        dlgseq: '1',
        sectionId: '1',
        character: 'Test',
        text: 'Test',
        attributes: {}
      };
      
      await expect(result.current.handleUpdateDialog('1', '1', testDialog as DialogElement)).resolves.toBeUndefined();
    });

    it('should flag missing voice-sample file on load', async () => {
      const { result } = renderHook(() => useChapter('Story-Entanglement'));
      const mockConfig = {
        global: {
          'story-dir': '', voices: '', chapters: '', 'story-xml': '', logs: '', 'story-audio': '', clips: '', 'clip-separation': 0,
        },
        'llm-xml-generator': [],
        'dialog-effects': [],
        'story-audio-post-process': {},
        characters: [{ name: 'Alice', 'voice-sample': 'refs/alice.wav' }],
      } as StoryConfig;

      act(() => {
        result.current.setConfig(mockConfig);
      });
      vi.mocked(PythonBridgeService.checkStoryFileExists).mockResolvedValue(false);

      await act(async () => {
        await result.current.loadChapter('test.xml', mockConfig, 'Story-Entanglement');
      });

      expect(PythonBridgeService.checkStoryFileExists).toHaveBeenCalledWith('Story-Entanglement', 'refs/alice.wav');
      expect(result.current.chapter?.dialogs[0].validationIssues?.[0]?.code).toBe('invalid-voice-sample');
    });
  });
});
