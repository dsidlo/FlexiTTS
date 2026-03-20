import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useMarkdown, formatMarkdownContent } from '../hooks/useMarkdown';
import { PythonBridgeService } from '../services/pythonBridge';

// Mock the PythonBridgeService
vi.mock('../services/pythonBridge', () => ({
  PythonBridgeService: {
    readFile: vi.fn(),
    writeFile: vi.fn().mockResolvedValue(undefined),
    writeChapterFile: vi.fn().mockResolvedValue(undefined),
    checkStoryFileExists: vi.fn().mockResolvedValue(false),
    showConfirmDialog: vi.fn(),
  },
}));

// Mock debugLogger
vi.mock('../utils/debugLogger', () => ({
  debugLog: {
    info: vi.fn(),
    warn: vi.fn(),
    error: vi.fn(),
    exception: vi.fn(),
  },
}));

// Mock window.alert
Object.defineProperty(window, 'alert', {
  value: vi.fn(),
  writable: true,
});

describe('formatMarkdownContent', () => {
  it('should return short lines unchanged', () => {
    const content = 'Short line';
    const result = formatMarkdownContent(content, 80);
    expect(result).toBe(content);
  });

  it('should wrap long lines at word boundaries', () => {
    const content = 'This is a very long line that should be wrapped at the specified character limit without breaking words';
    const result = formatMarkdownContent(content, 30);
    expect(result).toContain('\n');
    // Just check it doesn't contain broken words
    expect(result.split('\n').every(line => !line.match(/^\w*$/))).toBe(true);
  });

  it('should preserve existing line breaks', () => {
    const content = 'Line one\nLine two\nLine three';
    const result = formatMarkdownContent(content, 80);
    expect(result).toBe(content);
  });

  it('should format multiple lines independently', () => {
    const content = 'First long line that needs wrapping\nSecond long line that also needs wrapping';
    const result = formatMarkdownContent(content, 20);
    const lines = result.split('\n');
    expect(lines.length).toBeGreaterThan(2);
  });

  it('should handle custom limit', () => {
    const content = 'This is content that will be wrapped at a custom limit';
    const result = formatMarkdownContent(content, 15);
    expect(result).toContain('\n');
  });

  it('should handle empty content', () => {
    const result = formatMarkdownContent('', 80);
    expect(result).toBe('');
  });
});

describe('useMarkdown', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('initial state', () => {
    it('should initialize with correct default state', () => {
      const { result } = renderHook(() => useMarkdown());

      expect(result.current.editorMode).toBe(false);
      expect(result.current.markdownContent).toBe('');
      expect(result.current.lastSavedMarkdown).toBe('');
      expect(result.current.hasUnsavedMarkdownChanges).toBe(false);
    });

    it('should initialize with provided storyDirectory', () => {
      const { result } = renderHook(() => useMarkdown('Story-Test'));
      // The hook uses storyDirectory internally
      expect(result.current.getMarkdownPath('test')).toContain('Story-Test');
    });
  });

  describe('setMarkdownContent', () => {
    it('should update content and track unsaved changes', () => {
      const { result } = renderHook(() => useMarkdown());

      act(() => {
        result.current.setMarkdownContent('New content');
      });

      expect(result.current.markdownContent).toBe('New content');
      expect(result.current.hasUnsavedMarkdownChanges).toBe(true);
    });

    it('should not mark as changed if content matches saved', () => {
      const { result } = renderHook(() => useMarkdown());

      act(() => {
        result.current.setMarkdownContent('Content');
        result.current.setLastSavedMarkdownValue('Content');
      });

      // Reset and set same content
      act(() => {
        result.current.setMarkdownContent('Content');
      });

      expect(result.current.hasUnsavedMarkdownChanges).toBe(false);
    });
  });

  describe('formatMarkdown', () => {
    it('should format content to 80 characters', () => {
      const { result } = renderHook(() => useMarkdown());

      const longContent = 'This is a very long line that should be wrapped at eighty characters without breaking words';

      act(() => {
        result.current.setMarkdownContent(longContent);
      });

      act(() => {
        result.current.formatMarkdown();
      });

      expect(result.current.markdownContent).toContain('\n');
    });

    it('should track unsaved changes after formatting', () => {
      const { result } = renderHook(() => useMarkdown());

      act(() => {
        result.current.setMarkdownContent('Content');
        result.current.setLastSavedMarkdownValue('Different content');
      });

      act(() => {
        result.current.formatMarkdown();
      });

      expect(result.current.hasUnsavedMarkdownChanges).toBe(true);
    });
  });

  describe('loadMarkdown', () => {
    it('should load markdown content from file', async () => {
      const mockContent = '# Chapter Title\n\nContent here';
      vi.mocked(PythonBridgeService.readFile).mockResolvedValue(mockContent);

      const { result } = renderHook(() => useMarkdown('Story-Test'));

      await act(async () => {
        await result.current.loadMarkdown('01-Test');
      });

      expect(result.current.markdownContent).toBe(mockContent);
      expect(result.current.lastSavedMarkdown).toBe(mockContent);
      expect(result.current.hasUnsavedMarkdownChanges).toBe(false);
      expect(PythonBridgeService.readFile).toHaveBeenCalledWith(
        'Story-Test/story-chapters/01-Test.md'
      );
    });

    it('should use forceStoryDir if provided', async () => {
      vi.mocked(PythonBridgeService.readFile).mockResolvedValue('# Content');

      const { result } = renderHook(() => useMarkdown('Story-Default'));

      await act(async () => {
        await result.current.loadMarkdown('01-Test', 'Story-Custom');
      });

      expect(PythonBridgeService.readFile).toHaveBeenCalledWith(
        'Story-Custom/story-chapters/01-Test.md'
      );
    });

    it('should handle load error gracefully', async () => {
      vi.mocked(PythonBridgeService.readFile).mockRejectedValue(new Error('File not found'));

      const { result } = renderHook(() => useMarkdown());

      await act(async () => {
        await result.current.loadMarkdown('nonexistent');
      });

      expect(result.current.markdownContent).toBe('');
      expect(result.current.lastSavedMarkdown).toBe('');
      expect(result.current.hasUnsavedMarkdownChanges).toBe(false);
    });

    it('should use default story directory when none provided', async () => {
      vi.mocked(PythonBridgeService.readFile).mockResolvedValue('# Content');

      const { result } = renderHook(() => useMarkdown());

      await act(async () => {
        await result.current.loadMarkdown('01-Test');
      });

      expect(PythonBridgeService.readFile).toHaveBeenCalledWith(
        expect.stringContaining('story-chapters/01-Test.md')
      );
    });
  });

  describe('saveMarkdown', () => {
    it('should save markdown content with stem', async () => {
      vi.mocked(PythonBridgeService.writeChapterFile).mockResolvedValue(undefined);

      const { result } = renderHook(() => useMarkdown('Story-Test'));

      act(() => {
        result.current.setMarkdownContent('# Title');
      });

      await act(async () => {
        await result.current.saveMarkdown('01-Chapter');
      });

      expect(PythonBridgeService.writeChapterFile).toHaveBeenCalledWith(
        'Story-Test/story-chapters/01-Chapter.md',
        '# Title'
      );
      expect(result.current.lastSavedMarkdown).toBe('# Title');
      expect(result.current.hasUnsavedMarkdownChanges).toBe(false);
    });

    it('should handle save error gracefully', async () => {
      vi.mocked(PythonBridgeService.writeChapterFile).mockRejectedValue(new Error('Write failed'));

      const { result } = renderHook(() => useMarkdown('Story-Test'));

      act(() => {
        result.current.setMarkdownContent('# Title');
      });

      // Should throw since saveMarkdown re-throws errors
      await expect(act(async () => {
        await result.current.saveMarkdown('01-Chapter');
      })).rejects.toThrow('Write failed');
    });

    it('should not save if no changes', async () => {
      const { result } = renderHook(() => useMarkdown('Story-Test'));

      // No changes made, will not save
      await act(async () => {
        await result.current.saveMarkdown('01-Chapter');
      });

      expect(PythonBridgeService.writeChapterFile).not.toHaveBeenCalled();
    });

    it('should not save if no stem provided', async () => {
      const { result } = renderHook(() => useMarkdown());

      act(() => {
        result.current.setMarkdownContent('# Title');
      });

      await act(async () => {
        await result.current.saveMarkdown();
      });

      expect(PythonBridgeService.writeChapterFile).not.toHaveBeenCalled();
    });
  });

  describe('resetMarkdown', () => {
    it('should reset all markdown state', () => {
      const { result } = renderHook(() => useMarkdown());

      act(() => {
        result.current.setMarkdownContent('Some content');
        result.current.setLastSavedMarkdownValue('Saved content');
      });

      act(() => {
        result.current.resetMarkdown();
      });

      expect(result.current.markdownContent).toBe('');
      expect(result.current.lastSavedMarkdown).toBe('');
      expect(result.current.hasUnsavedMarkdownChanges).toBe(false);
    });
  });

  describe('getMarkdownPath', () => {
    it('should return correct markdown path', () => {
      const { result } = renderHook(() => useMarkdown('Story-Test'));

      const path = result.current.getMarkdownPath('01-Chapter');

      expect(path).toBe('Story-Test/story-chapters/01-Chapter.md');
    });

    it('should use default story directory if not provided', () => {
      const { result } = renderHook(() => useMarkdown());

      const path = result.current.getMarkdownPath('01-Chapter');

      expect(path).toBe('Story-Default/story-chapters/01-Chapter.md');
    });
  });

  describe('toggleEditor', () => {
    it('should toggle editor mode', async () => {
      const { result } = renderHook(() => useMarkdown());

      expect(result.current.editorMode).toBe(false);

      await act(async () => {
        await result.current.toggleEditor();
      });

      expect(result.current.editorMode).toBe(true);

      await act(async () => {
        await result.current.toggleEditor();
      });

      expect(result.current.editorMode).toBe(false);
    });

    it('should show confirmation when unsaved changes exist', async () => {
      // 0 = Save, 1 = Discard, 2 = Cancel
      vi.mocked(PythonBridgeService.showConfirmDialog).mockResolvedValue(0);

      const { result } = renderHook(() => useMarkdown());

      // First enter editor mode
      await act(async () => {
        await result.current.toggleEditor();
      });

      act(() => {
        result.current.setMarkdownContent('Unsaved content');
      });

      await act(async () => {
        await result.current.toggleEditor();
      });

      expect(PythonBridgeService.showConfirmDialog).toHaveBeenCalledWith(
        "Unsaved Text Changes",
        "You have unsaved changes in the text editor.",
        "Do you want to save them before closing?"
      );
    });

    it('should respect force option', async () => {
      const { result } = renderHook(() => useMarkdown());

      // First enter editor mode
      await act(async () => {
        await result.current.toggleEditor();
      });

      act(() => {
        result.current.setMarkdownContent('Unsaved content');
      });

      await act(async () => {
        await result.current.toggleEditor({ force: true });
      });

      // Should not show confirmation even with unsaved changes
      expect(PythonBridgeService.showConfirmDialog).not.toHaveBeenCalled();
    });

    it('should call onBeforeToggle callback when saving with unsaved changes', async () => {
      const onBeforeToggle = vi.fn().mockResolvedValue(undefined);
      // 0 = Save
      vi.mocked(PythonBridgeService.showConfirmDialog).mockResolvedValue(0);

      const { result } = renderHook(() => useMarkdown());

      // First enter editor mode
      await act(async () => {
        await result.current.toggleEditor();
      });

      // Modify content to have unsaved changes
      act(() => {
        result.current.setMarkdownContent('New content');
      });

      // Now toggle to exit - should trigger confirmation with save option
      await act(async () => {
        await result.current.toggleEditor({ onBeforeToggle });
      });

      expect(onBeforeToggle).toHaveBeenCalled();
    });

    it('should call onAfterToggle callback', async () => {
      const onAfterToggle = vi.fn();

      const { result } = renderHook(() => useMarkdown());

      await act(async () => {
        await result.current.toggleEditor({ onAfterToggle });
      });

      expect(onAfterToggle).toHaveBeenCalledWith(true);
    });

    it('should cancel toggle if user declines confirmation', async () => {
      // 2 = Cancel
      vi.mocked(PythonBridgeService.showConfirmDialog).mockResolvedValue(2);

      const { result } = renderHook(() => useMarkdown());

      // First enter editor mode
      await act(async () => {
        await result.current.toggleEditor();
      });

      act(() => {
        result.current.setMarkdownContent('Unsaved');
      });

      await act(async () => {
        await result.current.toggleEditor();
      });

      // Mode should not have changed (still in editor mode because cancel)
      expect(result.current.editorMode).toBe(true);
    });
  });

  describe('ref value setters', () => {
    it('should update lastSavedMarkdown via setLastSavedMarkdownValue', () => {
      const { result } = renderHook(() => useMarkdown());

      act(() => {
        result.current.setLastSavedMarkdownValue('Saved value');
      });

      expect(result.current.lastSavedMarkdown).toBe('Saved value');
    });

    it('should update hasUnsavedMarkdownChanges via setHasUnsavedMarkdownChangesValue', () => {
      const { result } = renderHook(() => useMarkdown());

      act(() => {
        result.current.setHasUnsavedMarkdownChangesValue(true);
      });

      expect(result.current.hasUnsavedMarkdownChanges).toBe(true);
    });
  });

  describe('refs synchronization', () => {
    it('should sync refs with state', () => {
      const { result } = renderHook(() => useMarkdown());

      act(() => {
        result.current.setMarkdownContent('Test content');
      });

      // Refs should be synced
      expect(result.current.markdownRef.current).toBe('Test content');

      act(() => {
        result.current.setLastSavedMarkdownValue('Saved');
      });

      expect(result.current.lastSavedMarkdownRef.current).toBe('Saved');

      act(() => {
        result.current.setHasUnsavedMarkdownChangesValue(true);
      });

      expect(result.current.hasUnsavedMarkdownChangesRef.current).toBe(true);
    });
  });

  describe('window width', () => {
    it('should update window width', () => {
      const { result } = renderHook(() => useMarkdown());

      act(() => {
        result.current.setWindowWidth(800);
      });

      expect(result.current.windowWidth).toBe(800);
    });

    it('should initialize with window.innerWidth', () => {
      Object.defineProperty(window, 'innerWidth', {
        value: 1200,
        writable: true,
      });

      const { result } = renderHook(() => useMarkdown());

      expect(result.current.windowWidth).toBe(1200);
    });
  });
});
