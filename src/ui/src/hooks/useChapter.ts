import { useState, useCallback, useRef } from 'react';
import type { Chapter, StoryConfig, DialogElement } from '../models/types';
import { PythonBridgeService } from '../services/pythonBridge';
import { generateXMLFromChapter } from '../services/chapterService';

export interface UseChapterReturn {
  // State
  config: StoryConfig | null;
  chapter: Chapter | null;
  chapterList: string[];
  currentChapterFile: string;
  selectedCharacterFilter: string;
  availableClips: string[];
  hasChapterAudio: boolean;
  isGeneratingStructure: boolean;
  generateAttempt: number;
  xmlContent: string;
  lastSavedXml: string;
  hasUnsavedChanges: boolean;
  
  // Setters
  setConfig: React.Dispatch<React.SetStateAction<StoryConfig | null>>;
  setChapter: React.Dispatch<React.SetStateAction<Chapter | null>>;
  setChapterList: React.Dispatch<React.SetStateAction<string[]>>;
  setAvailableClips: React.Dispatch<React.SetStateAction<string[]>>;
  setHasChapterAudio: React.Dispatch<React.SetStateAction<boolean>>;
  setSelectedCharacterFilter: React.Dispatch<React.SetStateAction<string>>;
  
  // Actions
  loadChapter: (filePath: string, loadedConfig?: StoryConfig) => Promise<void>;
  handleChapterSelect: (filePath: string, loadedConfig?: StoryConfig) => Promise<void>;
  handleUpdateDialog: (id: string, sectionId: string, updatedDialog: DialogElement) => void;
  setCurrentChapterFile: React.Dispatch<React.SetStateAction<string>>;
  runXmlGenerationPipeline: (stem: string, attempt: number) => Promise<void>;
  setIsGeneratingStructure: React.Dispatch<React.SetStateAction<boolean>>;
  setGenerateAttempt: React.Dispatch<React.SetStateAction<number>>;
  
  // Ref value setters
  setLastSavedXmlValue: (value: string) => void;
  setHasUnsavedChangesValue: (value: boolean) => void;
  
  // XML/markdown save state references
  xmlContentRef: React.MutableRefObject<string>;
  lastSavedXmlRef: React.MutableRefObject<string>;
  hasUnsavedChangesRef: React.MutableRefObject<boolean>;
  setXmlContent: React.Dispatch<React.SetStateAction<string>>;
  setLastSavedXml: React.Dispatch<React.SetStateAction<string>>;
  setHasUnsavedChanges: React.Dispatch<React.SetStateAction<boolean>>;
}

/**
 * Hook for managing chapter state and operations.
 * Handles loading, parsing, and updating chapters.
 */
export const useChapter = (): UseChapterReturn => {
  const [config, setConfig] = useState<StoryConfig | null>(null);
  const [chapter, setChapter] = useState<Chapter | null>(null);
  const [chapterList, setChapterList] = useState<string[]>([]);
  const [currentChapterFile, setCurrentChapterFile] = useState<string>('');
  const [selectedCharacterFilter, setSelectedCharacterFilter] = useState<string>('');
  const [availableClips, setAvailableClips] = useState<string[]>([]);
  const [hasChapterAudio, setHasChapterAudio] = useState(false);
  const [isGeneratingStructure, setIsGeneratingStructure] = useState(false);
  const [generateAttempt, setGenerateAttempt] = useState(0);
  
  // XML state
  const [xmlContent, setXmlContent] = useState<string>('');
  const [lastSavedXml, setLastSavedXml] = useState<string>('');
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState<boolean>(false);
  
  // Use refs for synchronous access within handlers
  const xmlContentRef = useRef(xmlContent);
  const lastSavedXmlRef = useRef(lastSavedXml);
  const hasUnsavedChangesRef = useRef(hasUnsavedChanges);
  
  // Keep refs in sync
  xmlContentRef.current = xmlContent;
  lastSavedXmlRef.current = lastSavedXml;
  hasUnsavedChangesRef.current = hasUnsavedChanges;

  /**
   * Parse XML string into Chapter object
   */
  const parseChapterXML = useCallback((xmlString: string, filePath: string): Chapter => {
    const parser = new DOMParser();
    const xmlDoc = parser.parseFromString(xmlString, 'text/xml');
    
    const parseError = xmlDoc.querySelector('parsererror');
    if (parseError) {
      console.error('Error parsing XML', parseError);
    }

    const chapterNode = xmlDoc.querySelector('chapter') || xmlDoc.querySelector('story');
    const chapterName = chapterNode?.getAttribute('name') || 
                       filePath.split('/').pop()?.replace('.xml', '') || 
                       'Unknown Chapter';
    
    const dialogNodes = Array.from(xmlDoc.querySelectorAll('dialog, narration'));
    
    if (dialogNodes.length === 0) {
      console.warn("No <dialog> or <narration> nodes found in XML string");
    }

    const dialogs: DialogElement[] = dialogNodes.map((node, index) => {
      const attributes: Record<string, string> = {};
      
      for (let i = 0; i < node.attributes.length; i++) {
        const attr = node.attributes[i];
        attributes[attr.name] = attr.value;
      }
      
      const parentSection = node.closest('section');
      if (parentSection && parentSection.hasAttribute('seq')) {
        attributes['section_seq'] = parentSection.getAttribute('seq') || '';
      }
      
      const rawText = node.textContent || '';
      const text = rawText.replace(/\s+/g, ' ').trim();
      
      return {
        _index: index,
        id: attributes.id || attributes.dlgseq || `dialog-${index}`,
        sectionId: attributes.section_seq || '1',
        character: attributes.character || (node.tagName.toLowerCase() === 'narration' ? 'Narrator' : 'Unknown'),
        text: text,
        attributes: attributes
      };
    });
    
    return {
      fileName: filePath,
      name: chapterName,
      dialogs: dialogs
    };
  }, []);

  /**
   * Load a chapter from file
   */
  const loadChapter = useCallback(async (filePath: string, _loadedConfig?: StoryConfig) => {
    try {
      console.log(`Loading chapter: ${filePath}`);
      
      try {
        await PythonBridgeService.validateChapterXML(filePath);
      } catch (validationErr: unknown) {
        console.warn('XML validation failed:', validationErr);
      }

      const loadedXml = await PythonBridgeService.readChapterFile(filePath);
      console.log(`Loaded XML for ${filePath}:`, loadedXml.substring(0, 50) + '...');
      
      const parsedChapter = parseChapterXML(loadedXml, filePath);
      console.log(`Parsed chapter:`, parsedChapter);
      
      setChapter(parsedChapter);
      setSelectedCharacterFilter('');
      
      const chapterName = filePath.split('/').pop() || '';
      if (chapterName) {
        const clips = await PythonBridgeService.listChapterClips(chapterName);
        setAvailableClips(clips);
        const hasAudio = await PythonBridgeService.checkChapterAudio(chapterName);
        setHasChapterAudio(hasAudio);
      }
      
      const newXml = generateXMLFromChapter(parsedChapter);
      setXmlContent(newXml);
      setLastSavedXml(newXml);
      setHasUnsavedChanges(false);
    } catch (err) {
      console.error('Failed to load chapter:', err);
      throw err;
    }
  }, [parseChapterXML]);

  /**
   * Run XML generation pipeline with retries
   */
  const runXmlGenerationPipeline = useCallback(async (stem: string, attempt: number): Promise<void> => {
    if (attempt > 3) {
      throw new Error("Exceeded maximum retry attempts (3).");
    }
    setGenerateAttempt(attempt);

    try {
      if (typeof window !== 'undefined' && window.api && window.api.runPythonScript) {
        console.log(`[Pipeline] Attempt ${attempt}: Running chapter_to_xml.py on ${stem}`);
        await window.api.runPythonScript('src/scripts/chapter_to_xml.py', 
          [`Story-Entanglement/story-chapters/${stem}.md`]);
        
        console.log(`[Pipeline] Attempt ${attempt}: Running chapter_seq_xml.py on ${stem}`);
        await window.api.runPythonScript('src/scripts/chapter_seq_xml.py', 
          [`Story-Entanglement/story-xml/${stem}.xml`]);
        
        console.log(`[Pipeline] Attempt ${attempt}: Running chapter_validate_xml.py on ${stem}`);
        await window.api.runPythonScript('src/scripts/chapter_validate_xml.py', 
          [`Story-Entanglement/story-xml/${stem}.xml`]);
      } else {
        console.log(`[Mock Pipeline] Attempt ${attempt} for ${stem}`);
        await new Promise(r => setTimeout(r, 2000));
      }
    } catch (err: unknown) {
      console.warn(`[Pipeline] Attempt ${attempt} failed:`, err);
      if (attempt >= 3) {
        throw err;
      }
      await runXmlGenerationPipeline(stem, attempt + 1);
    }
  }, []);

  /**
   * Handle chapter selection with unsaved changes check
   */
  const handleChapterSelect = useCallback(async (filePath: string, loadedConfig?: StoryConfig) => {
    // Check for unsaved changes
    if ((hasUnsavedChangesRef.current) && currentChapterFile) {
      const title = "Unsaved Changes";
      const message = "You have unsaved changes in the current chapter.";
      const detail = "Do you want to save them before switching chapters?";
      
      const res = await PythonBridgeService.showConfirmDialog(title, message, detail);
      if (res === 2) {
        return; // Cancel
      } else if (res === 0) {
        // Save - handled by parent
        // This will trigger save via the ref and then proceed
      }
      // res === 1 (Discard) just proceeds
    }

    setCurrentChapterFile(filePath);
    
    const stem = filePath.split('/').pop()?.replace('.md', '')?.replace('.xml', '') || 'unknown';
    const xmlPath = `Story-Entanglement/story-xml/${stem}.xml`;
    
    // Check if XML exists
    const xmlExists = await PythonBridgeService.checkXmlExists(stem);
    
    if (xmlExists) {
      await loadChapter(xmlPath, loadedConfig);
    } else {
      // Missing XML -> Generation Pipeline
      setIsGeneratingStructure(true);
      setGenerateAttempt(1);
      
      try {
        await runXmlGenerationPipeline(stem, 1);
        await loadChapter(xmlPath, loadedConfig);
      } catch (err: unknown) {
        console.error("XML Generation Pipeline failed entirely:", err);
        await PythonBridgeService.showErrorDialog(
          "Generation Failed",
          `Could not generate valid XML for ${stem} after 3 attempts.`
        );
      } finally {
        setIsGeneratingStructure(false);
      }
    }
  }, [currentChapterFile, loadChapter, runXmlGenerationPipeline]);

  /**
   * Update a dialog element within the chapter
   */
  const handleUpdateDialog = useCallback((id: string, sectionId: string, updatedDialog: DialogElement) => {
    if (!chapter) return;
    
    const updatedDialogs = chapter.dialogs.map(d => {
      const isMatch = updatedDialog._index !== undefined && d._index !== undefined 
        ? d._index === updatedDialog._index 
        : d.id === id && (d.sectionId || '1') === sectionId;
      
      return isMatch ? updatedDialog : d;
    });
    
    const updatedChapter = { ...chapter, dialogs: updatedDialogs };
    setChapter(updatedChapter);
    
    const newXml = generateXMLFromChapter(updatedChapter);
    setXmlContent(newXml);
    const hasChanges = newXml !== lastSavedXmlRef.current;
    setHasUnsavedChanges(hasChanges);
  }, [chapter, lastSavedXml]);

  /**
   * Set lastSavedXml ref value directly
   */
  const setLastSavedXmlValue = useCallback((value: string) => {
    lastSavedXmlRef.current = value;
    setLastSavedXml(value);
  }, []);

  /**
   * Set hasUnsavedChanges ref value directly
   */
  const setHasUnsavedChangesValue = useCallback((value: boolean) => {
    hasUnsavedChangesRef.current = value;
    setHasUnsavedChanges(value);
  }, []);

  return {
    config,
    chapter,
    chapterList,
    currentChapterFile,
    selectedCharacterFilter,
    availableClips,
    hasChapterAudio,
    isGeneratingStructure,
    generateAttempt,
    xmlContent,
    lastSavedXml,
    hasUnsavedChanges,
    
    setConfig,
    setChapter,
    setChapterList,
    setAvailableClips,
    setHasChapterAudio,
    setSelectedCharacterFilter,
    
    loadChapter,
    handleChapterSelect,
    handleUpdateDialog,
    setCurrentChapterFile,
    runXmlGenerationPipeline,
    setIsGeneratingStructure,
    setGenerateAttempt,
    
    setLastSavedXmlValue,
    setHasUnsavedChangesValue,
    
    xmlContentRef,
    lastSavedXmlRef,
    hasUnsavedChangesRef,
    setXmlContent,
    setLastSavedXml,
    setHasUnsavedChanges,
  };
};
