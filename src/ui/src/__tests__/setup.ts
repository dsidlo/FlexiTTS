import '@testing-library/jest-dom';
import { expect, vi } from 'vitest';

// Extend matchers
expect.extend({});

// Mock window.api
Object.defineProperty(window, 'api', {
  value: {
    runPythonScript: vi.fn(),
    readFile: vi.fn(),
    writeFile: vi.fn(),
    showErrorDialog: vi.fn(),
    showConfirmDialog: vi.fn(),
    listChapterClips: vi.fn(),
    checkChapterAudio: vi.fn(),
    checkXmlExists: vi.fn(),
    listChapterFiles: vi.fn(),
    playSoundFile: vi.fn(),
    killProcess: vi.fn(),
  },
  writable: true,
});

// Mock window.DOMParser if needed
if (!window.DOMParser) {
  class MockDOMParser {
    parseFromString(_str: string, _type: string) {
      return {
        querySelector: (sel: string) => {
          if (sel === 'parsererror') return null;
          if (sel === 'chapter' || sel === 'story') return { getAttribute: () => 'Test Chapter' };
          return null;
        },
        querySelectorAll: () => [],
      };
    }
  }
  Object.defineProperty(window, 'DOMParser', { value: MockDOMParser });
}

// ResizeObserver mock
global.ResizeObserver = vi.fn().mockImplementation(() => ({
  observe: vi.fn(),
  unobserve: vi.fn(),
  disconnect: vi.fn(),
}));
