import { useState, useCallback, useRef } from 'react';
import { PythonBridgeService } from '../services/pythonBridge';

export interface UseMarkdownReturn {
  // State
  editorMode: boolean;
  markdownContent: string;
  lastSavedMarkdown: string;
  hasUnsavedMarkdownChanges: boolean;
  windowWidth: number;
  
  // Setters
  setEditorMode: React.Dispatch<React.SetStateAction<boolean>>;
  setHasUnsavedMarkdownChanges: React.Dispatch<React.SetStateAction<boolean>>;
  setWindowWidth: React.Dispatch<React.SetStateAction<number>>;
  
  // Actions
  toggleEditor: (options?: ToggleOptions) => Promise<boolean>;
  setMarkdownContent: (content: string) => void;
  formatMarkdown: () => void;
  saveMarkdown: () => Promise<void>;
  loadMarkdown: (stem: string) => Promise<void>;
  resetMarkdown: () => void;
  getMarkdownPath: (stem: string) => string;
  
  // Ref value setters
  setLastSavedMarkdownValue: (value: string) => void;
  setHasUnsavedMarkdownChangesValue: (value: boolean) => void;
  
  // Refs for synchronous access
  markdownRef: React.MutableRefObject<string>;
  lastSavedMarkdownRef: React.MutableRefObject<string>;
  hasUnsavedMarkdownChangesRef: React.MutableRefObject<boolean>;
}

export interface ToggleOptions {
  /** If true, will not show confirmation dialog even if there are unsaved changes */
  force?: boolean;
  /** Callback to call before toggling */
  onBeforeToggle?: () => Promise<void>;
  /** Callback to call after toggling */
  onAfterToggle?: (newMode: boolean) => void;
}

/**
 * Formats markdown text to wrap lines at specified character limit
 * without breaking words.
 * @param content - The markdown content to format
 * @param limit - The character limit per line (default: 80)
 * @returns The formatted content
 */
export const formatMarkdownContent = (content: string, limit: number = 80): string => {
  const formatLine = (line: string, lineLimit: number): string => {
    if (line.length <= lineLimit) return line;
    const words = line.split(' ');
    let currentLine = '';
    let formatted = '';
    
    for (const word of words) {
      if ((currentLine + word).length > lineLimit) {
        formatted += currentLine.trim() + '\n';
        currentLine = word + ' ';
      } else {
        currentLine += word + ' ';
      }
    }
    formatted += currentLine.trim();
    return formatted;
  };

  return content
    .split('\n')
    .map(line => formatLine(line, limit))
    .join('\n');
};

/**
 * Hook for managing markdown editor state and operations.
 * Handles loading, editing, formatting, and saving markdown content.
 */
export const useMarkdown = (): UseMarkdownReturn => {
  const [editorMode, setEditorMode] = useState<boolean>(false);
  const [markdownContent, setMarkdownContentState] = useState<string>('');
  const [lastSavedMarkdown, setLastSavedMarkdown] = useState<string>('');
  const [hasUnsavedMarkdownChanges, setHasUnsavedMarkdownChanges] = useState<boolean>(false);
  const [windowWidth, setWindowWidth] = useState(
    typeof window !== 'undefined' ? window.innerWidth : 1024
  );
  
  // Use refs for synchronous access within handlers
  const markdownRef = useRef(markdownContent);
  const lastSavedMarkdownRef = useRef(lastSavedMarkdown);
  const hasUnsavedMarkdownChangesRef = useRef(hasUnsavedMarkdownChanges);
  
  // Keep refs in sync
  markdownRef.current = markdownContent;
  lastSavedMarkdownRef.current = lastSavedMarkdown;
  hasUnsavedMarkdownChangesRef.current = hasUnsavedMarkdownChanges;

  /**
   * Update markdown content and track unsaved changes
   * @param content - The new markdown content
   */
  const setMarkdownContent = useCallback((content: string) => {
    setMarkdownContentState(content);
    const hasChanges = content !== lastSavedMarkdownRef.current;
    setHasUnsavedMarkdownChanges(hasChanges);
  }, [lastSavedMarkdown]);

  /**
   * Format markdown content to wrap at 80 characters without breaking words
   */
  const formatMarkdown = useCallback(() => {
    const formattedContent = formatMarkdownContent(markdownContent);
    setMarkdownContentState(formattedContent);
    const hasChanges = formattedContent !== lastSavedMarkdownRef.current;
    setHasUnsavedMarkdownChanges(hasChanges);
  }, [markdownContent]);

  /**
   * Load markdown content from file
   * @param stem - The chapter file stem (without extension)
   */
  const loadMarkdown = useCallback(async (stem: string) => {
    try {
      const mdPath = `Story-Entanglement/story-chapters/${stem}.md`;
      const mdContent = await PythonBridgeService.readFile(mdPath);
      setMarkdownContentState(mdContent);
      setLastSavedMarkdown(mdContent);
      setHasUnsavedMarkdownChanges(false);
    } catch (e) {
      console.warn("Failed to load markdown for", stem, e);
      setMarkdownContentState("");
      setLastSavedMarkdown("");
      setHasUnsavedMarkdownChanges(false);
    }
  }, []);

  /**
   * Reset markdown state to empty
   */
  const resetMarkdown = useCallback(() => {
    setMarkdownContentState("");
    setLastSavedMarkdown("");
    setHasUnsavedMarkdownChanges(false);
    setEditorMode(false);
  }, []);

  /**
   * Get the markdown file path for a chapter stem
   * @param stem - The chapter file stem
   * @returns The full markdown file path
   */
  const getMarkdownPath = useCallback((stem: string): string => {
    return `Story-Entanglement/story-chapters/${stem}.md`;
  }, []);

  /**
   * Save the current markdown content
   * @param stem - Optional chapter stem (uses current if not provided)
   */
  const saveMarkdown = useCallback(async (stem?: string) => {
    if (!hasUnsavedMarkdownChanges) return;
    
    if (!stem) {
      console.warn("Cannot save markdown: no stem provided");
      return;
    }
    
    try {
      const mdPath = getMarkdownPath(stem);
      await PythonBridgeService.writeChapterFile(mdPath, markdownContent);
      setLastSavedMarkdown(markdownContent);
      setHasUnsavedMarkdownChanges(false);
    } catch (err) {
      console.error("Failed to save markdown:", err);
      throw err;
    }
  }, [markdownContent, hasUnsavedMarkdownChanges, getMarkdownPath]);

  /**
   * Toggle editor mode with unsaved changes handling
   * @param options - Optional toggle behavior configuration
   * @returns Promise<boolean> indicating if toggle was successful
   */
  const toggleEditor = useCallback(async (options?: ToggleOptions) => {
    const { force = false, onBeforeToggle, onAfterToggle } = options || {};
    
    // If turning off editor and there are unsaved changes
    if (editorMode && hasUnsavedMarkdownChangesRef.current && !force) {
      const title = "Unsaved Text Changes";
      const message = "You have unsaved changes in the text editor.";
      const detail = "Do you want to save them before closing?";
      
      const res = await PythonBridgeService.showConfirmDialog(title, message, detail);
      
      if (res === 2) {
        // Cancel
        return false;
      } else if (res === 0) {
        // Save - caller should handle the save
        if (onBeforeToggle) {
          await onBeforeToggle();
        }
      } else if (res === 1) {
        // Discard - revert to last saved
        setMarkdownContentState(lastSavedMarkdownRef.current);
        setHasUnsavedMarkdownChanges(false);
      }
    }
    
    const newMode = !editorMode;
    setEditorMode(newMode);
    
    if (onAfterToggle) {
      onAfterToggle(newMode);
    }
    
    return true;
  }, [editorMode]);

  /**
   * Set lastSavedMarkdown ref value directly
   */
  const setLastSavedMarkdownValue = useCallback((value: string) => {
    lastSavedMarkdownRef.current = value;
    setLastSavedMarkdown(value);
  }, []);

  /**
   * Set hasUnsavedMarkdownChanges ref value directly
   */
  const setHasUnsavedMarkdownChangesValue = useCallback((value: boolean) => {
    hasUnsavedMarkdownChangesRef.current = value;
    setHasUnsavedMarkdownChanges(value);
  }, []);

  return {
    editorMode,
    markdownContent,
    lastSavedMarkdown,
    hasUnsavedMarkdownChanges,
    windowWidth,
    
    setEditorMode,
    setHasUnsavedMarkdownChanges,
    setWindowWidth,
    
    toggleEditor,
    setMarkdownContent,
    formatMarkdown,
    saveMarkdown,
    loadMarkdown,
    resetMarkdown,
    getMarkdownPath,
    
    setLastSavedMarkdownValue,
    setHasUnsavedMarkdownChangesValue,
    
    markdownRef,
    lastSavedMarkdownRef,
    hasUnsavedMarkdownChangesRef,
  };
};
