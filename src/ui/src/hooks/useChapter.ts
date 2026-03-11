import { useState, useCallback, useRef } from 'react';
import type { Chapter, StoryConfig, DialogElement } from '../models/types';
import { PythonBridgeService } from '../services/pythonBridge';
import { generateXMLFromChapter } from '../services/chapterService';
import { debugLog } from '../utils/debugLogger';
import { validateChapterDialogs, getDialogValidationKey } from '../utils/dialogValidation';

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
  loadChapter: (filePath: string, loadedConfig?: StoryConfig, forceStoryDir?: string) => Promise<void>;
  handleChapterSelect: (filePath: string, loadedConfig?: StoryConfig) => Promise<void>;
  handleUpdateDialog: (dlgseq: string, sectionId: string, updatedDialog: DialogElement) => Promise<void>;
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
export const useChapter = (storyDirectory?: string): UseChapterReturn => {
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
        dlgseq: attributes.dlgseq || attributes.id || `${index + 1}`,
        sectionId: attributes.section_seq || '0',
        character: attributes.character || (node.tagName.toLowerCase() === 'narration' ? 'Narrator' : 'Unknown'),
        text: text,
        attributes: {
          ...attributes,
          dlgseq: attributes.dlgseq || attributes.id || `${index + 1}`,
          section_seq: attributes.section_seq || '0'
        }
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
  const loadChapter = useCallback(async (filePath: string, _loadedConfig?: StoryConfig, forceStoryDir?: string) => {
    const id = 'useChapter:loadChapter';
    const chapterName = filePath.split('/').pop()?.replace('.xml', '') || 'unknown';
    const storyDir = forceStoryDir || storyDirectory || 'Story-Default';
    const xmlPath = `${storyDir}/story-xml/${chapterName}.xml`;
    debugLog.info(id, '[RESOURCE-ACCESS] Loading chapter XML', { filePath, xmlPath, storyDir, resourceType: 'xml', operation: 'read' });
    
    try {
      try {
        await PythonBridgeService.validateChapterXML(filePath);
        debugLog.info(id, '[RESOURCE-ACCESS] XML validation successful', { filePath });
      } catch (validationErr: unknown) {
        debugLog.warn(id, `[RESOURCE-ACCESS] XML validation failed: ${validationErr}`, { filePath });
      }

      const loadedXml = await PythonBridgeService.readChapterFile(filePath);
      debugLog.info(id, '[RESOURCE-ACCESS] Successfully read chapter XML', { filePath, length: loadedXml?.length });
      
      const parsedChapter = parseChapterXML(loadedXml, filePath);
      const validationMap = await validateChapterDialogs(parsedChapter.dialogs, _loadedConfig || config, storyDir);
      parsedChapter.dialogs = parsedChapter.dialogs.map((dialog) => ({
        ...dialog,
        validationIssues: validationMap[getDialogValidationKey(dialog)] || [],
      }));
      debugLog.info(id, '[RESOURCE-ACCESS] Parsed chapter', { chapter: parsedChapter.name, dialogs: parsedChapter.dialogs.length, validationIssueCount: Object.keys(validationMap).length });
      
      setChapter(parsedChapter);
      setSelectedCharacterFilter('');
      
      const chapterName = filePath.split('/').pop() || '';
      if (chapterName) {
        const clips = await PythonBridgeService.listChapterClips(chapterName);
        setAvailableClips(clips);
        const hasAudio = await PythonBridgeService.checkChapterAudio(chapterName);
        setHasChapterAudio(hasAudio);
        debugLog.info(id, '[RESOURCE-ACCESS] Audio clips checked', { chapterName, clipCount: clips.length, hasAudio });
      }
      
      const newXml = generateXMLFromChapter(parsedChapter);
      setXmlContent(newXml);
      setLastSavedXml(newXml);
      setHasUnsavedChanges(false);
      debugLog.info(id, '[RESOURCE-ACCESS] Chapter loaded successfully', { filePath });
    } catch (err) {
      debugLog.exception(id, '[RESOURCE-ACCESS] Failed to load chapter', err as Error, { filePath });
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
    const id = 'useChapter:runXmlGenerationPipeline';

    const storyDir = storyDirectory || 'Story-Default';
    const mdInputPath = `${storyDir}/story-chapters/${stem}.md`;
    const xmlOutputPath = `${storyDir}/story-xml/${stem}.xml`;
    
    debugLog.info(id, '[RESOURCE-ACCESS] Starting XML generation pipeline', { stem, attempt, mdInputPath, xmlOutputPath });
    
    try {
      if (typeof window !== 'undefined' && window.api && window.api.runPythonScript) {
        debugLog.info(id, '[RESOURCE-ACCESS] Running chapter_to_xml.py', { attempt, input: mdInputPath, resourceType: 'markdown' });
        await window.api.runPythonScript('src/scripts/chapter_to_xml.py', 
          [`${storyDir}/story-chapters/${stem}.md`]);
        debugLog.info(id, '[RESOURCE-ACCESS] chapter_to_xml.py completed', { attempt, output: xmlOutputPath, resourceType: 'xml' });
        
        debugLog.info(id, '[RESOURCE-ACCESS] Running chapter_seq_xml.py', { attempt, xmlPath: xmlOutputPath });
        await window.api.runPythonScript('src/scripts/chapter_seq_xml.py', 
          [`${storyDir}/story-xml/${stem}.xml`]);
        debugLog.info(id, '[RESOURCE-ACCESS] chapter_seq_xml.py completed', { attempt, xmlPath: xmlOutputPath });
        
        debugLog.info(id, '[RESOURCE-ACCESS] Running chapter_validate_xml.py', { attempt, xmlPath: xmlOutputPath });
        await window.api.runPythonScript('src/scripts/chapter_validate_xml.py', 
          [`${storyDir}/story-xml/${stem}.xml`]);
        debugLog.info(id, '[RESOURCE-ACCESS] chapter_validate_xml.py completed', { attempt, xmlPath: xmlOutputPath });
      } else {
        debugLog.warn(id, '[RESOURCE-ACCESS] Mock Pipeline', { attempt, stem });
        await new Promise(r => setTimeout(r, 2000));
      }
      debugLog.info(id, '[RESOURCE-ACCESS] XML generation pipeline completed successfully', { stem, attempt });
    } catch (err: unknown) {
      debugLog.warn(id, `[RESOURCE-ACCESS] Pipeline attempt ${attempt} failed: ${err}`, { stem });
      if (attempt >= 3) {
        debugLog.error(id, '[RESOURCE-ACCESS] Pipeline failed after all retries', { stem });
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

    const storyDir = storyDirectory || 'Story-Default';
    
    setCurrentChapterFile(filePath);
    
    const stem = filePath.split('/').pop()?.replace('.md', '')?.replace('.xml', '') || 'unknown';
    const xmlPath = `${storyDir}/story-xml/${stem}.xml`;
    
    // Check if XML exists for the currently selected story
    const xmlExists = await PythonBridgeService.checkXmlExistsForStory(stem, storyDir);
    
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
  const handleUpdateDialog = useCallback(async (dlgseq: string, sectionId: string, updatedDialog: DialogElement) => {
    if (!chapter) return;

    const effectiveStoryDir = storyDirectory || 'Story-Default';
    
    const updatedDialogs = chapter.dialogs.map(d => {
      const isMatch = updatedDialog._index !== undefined && d._index !== undefined 
        ? d._index === updatedDialog._index 
        : d.dlgseq === dlgseq && (d.sectionId || '1') === sectionId;
      
      return isMatch
        ? {
            ...updatedDialog,
            attributes: {
              ...updatedDialog.attributes,
              character: updatedDialog.character,
              dlgseq: updatedDialog.dlgseq,
              section_seq: updatedDialog.sectionId || '0',
            },
          }
        : d;
    });
    
    const draftChapter = { ...chapter, dialogs: updatedDialogs };

    try {
      const validationMap = await validateChapterDialogs(updatedDialogs, config, effectiveStoryDir);
      const validatedDialogs = draftChapter.dialogs.map((dialog) => ({
        ...dialog,
        validationIssues: validationMap[getDialogValidationKey(dialog)] || [],
      }));
  
      const updatedChapter = { ...chapter, dialogs: validatedDialogs };
      setChapter(updatedChapter);
      
      const newXml = generateXMLFromChapter(updatedChapter);
      setXmlContent(newXml);
      const hasChanges = newXml !== lastSavedXmlRef.current;
      setHasUnsavedChanges(hasChanges);
    } catch (error) {
      debugLog.exception('useChapter:handleUpdateDialog', 'validateChapterDialogs failed', error, {
        dlgseq,
        sectionId,
        character: updatedDialog.character,
        storyDirectory: effectiveStoryDir,
      });
      // Keep optimistic state (empty issues) to avoid UI freeze, but rethrow for upstream handling if needed
    }
  }, [chapter, config, storyDirectory]);

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
