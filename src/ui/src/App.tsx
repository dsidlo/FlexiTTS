import { useEffect, useCallback, useState, useRef } from 'react';
import './App.css';
import { PythonBridgeService } from './services/pythonBridge';
import type { AlertHistoryItem, StoryConfig, StoryInfo } from './models/types';
import { TopBar } from './components/TopBar';
import { DialogBar } from './components/DialogBar';
import { CharacterVoiceDialog } from './components/CharacterVoiceDialog';
import { CharacterAssignPicker } from './components/CharacterAssignPicker';
import { HelpDialog } from './components/HelpDialog';
import { AlertContainer } from './components/AlertContainer';
import { useChapter, useMarkdown, useAlerts, useTtsAlerts, useTtsConnectivity, type AlertType } from './hooks';
import { alertService, alerts } from './services/alertService';
import { generateXMLFromChapter } from './services/chapterService';
import { debugLog } from './utils/debugLogger';
import { saveRecoveryCheckpoint, loadRecoveryCheckpoint, clearRecoveryCheckpoint, hasRecoveryData, type RecoveryCheckpoint } from './utils/sessionRecovery';

const isTestEnvironment = (): boolean => {
  try {
    return Boolean(import.meta.env?.MODE === 'test' || import.meta.env?.VITEST || process.env.VITEST);
  } catch {
    return false;
  }
};

const testSafeConsole = {
  log: (...args: unknown[]) => {
    if (!isTestEnvironment()) {
      console.log(...args);
    }
  },
  warn: (...args: unknown[]) => {
    if (!isTestEnvironment()) {
      console.warn(...args);
    }
  },
  error: (...args: unknown[]) => {
    if (!isTestEnvironment()) {
      console.error(...args);
    }
  },
};

function App() {
  const logId = 'App';

  // Standalone help view: the floating help window loads the same Vite app
  // with ?view=help (prod) or ?standalone=help (dev) and renders only the
  // help pane, full-window, no app chrome.
  const isStandaloneHelp = (() => {
    try {
      const params = new URLSearchParams(window.location.search);
      return params.get('view') === 'help' || params.get('standalone') === 'help';
    } catch {
      return false;
    }
  })();

  if (isStandaloneHelp) {
    return <StandaloneHelp />;
  }

  // Story management state - MUST be declared before hooks that use it
  const [currentStory, setCurrentStory] = useState<StoryInfo | null>(null);

  // Chapter state from hook
  const {
    config, setConfig, chapter, chapterList, setChapterList,
    currentChapterFile, setCurrentChapterFile, selectedCharacterFilter, setSelectedCharacterFilter,
    availableClips, setAvailableClips, hasChapterAudio, setHasChapterAudio,
    isGeneratingStructure, setIsGeneratingStructure, generateAttempt, setGenerateAttempt,
    xmlContentRef, hasUnsavedChangesRef, setXmlContent, setLastSavedXmlValue,
    setHasUnsavedChangesValue,
    loadChapter, handleUpdateDialog, getIsStaleClip, checkRenderState, renderState, applyRenderResults,
    bulkAssignCharacter,
  } = useChapter(currentStory?.directory_name);

  // Track the latest renderState so the post-render clip refresh can merge the
  // freshly computed dialog hashes/timestamps into the in-memory chapter and
  // flip render buttons to green without a separate disk read.
  const renderStateRef = useRef<any>(null);
  renderStateRef.current = renderState;

  // Latest handleSave for Phase 11 Ctrl+S (avoids effect dependency churn)
  const handleSaveRef = useRef<(() => void | Promise<void>) | null>(null);
  renderStateRef.current = renderState;

  // Markdown state from hook
  const {
    editorMode, setEditorMode, markdownContent, setMarkdownContent,
    lastSavedMarkdownRef, hasUnsavedMarkdownChangesRef,
    setLastSavedMarkdownValue, setHasUnsavedMarkdownChangesValue,
    windowWidth, setWindowWidth, formatMarkdown, loadMarkdown, resetMarkdown,
  } = useMarkdown(currentStory?.directory_name);

  // Local UI state
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showChapterMenu, setShowChapterMenu] = useState(false);
  const [menuPos, setMenuPos] = useState({ x: 0, y: 0 });
  const [showCharacterVoices, setShowCharacterVoices] = useState(false);

  // Phase 10: dialog multi-selection and character assignment picker.
  // Selected lines are identified by their stable composite key; picker is
  // opened by Ctrl+Shift+A, context menu, or the CharacterBar quick-assign.
  const [selectedDialogKeys, setSelectedDialogKeys] = useState<Set<string>>(new Set());
  const [assignPickerOpen, setAssignPickerOpen] = useState(false);
  // Help dialog (Ctrl+?): independent, always available.
  const [showHelp, setShowHelp] = useState(false);
  // Phase 12.2: unsaved-session recovery dialog on startup
  const [recoveryData, setRecoveryData] = useState<RecoveryCheckpoint | null>(null);
  const [showRecoveryDialog, setShowRecoveryDialog] = useState(false);
  const [helpShortcuts, setHelpShortcuts] = useState<Record<string, string> | undefined>(undefined);

  // Load shortcut overrides for the help docs from the global config.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const globalConfig = await PythonBridgeService.loadGlobalConfig();
        const shortcuts = (globalConfig as { FlexiTTS?: { shortcuts?: Record<string, string> } })?.FlexiTTS?.shortcuts;
        if (!cancelled && shortcuts && Object.keys(shortcuts).length > 0) setHelpShortcuts(shortcuts);
      } catch {
        // Help works without overrides; defaults are shown.
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const dialogKeyOf = useCallback((dlgseq: string, sectionId: string, _index?: number) =>
    _index !== undefined ? `i:${_index}` : `s:${sectionId || '0'}:${dlgseq}`, []);

  const handleToggleDialogSelect = useCallback((dlgseq: string, sectionId: string, _index: number | undefined, _additive: boolean) => {
    const key = dialogKeyOf(dlgseq, sectionId, _index);
    setSelectedDialogKeys((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key); else next.add(key);
      return next;
    });
  }, [dialogKeyOf]);

  // Phase 10.1: Ctrl+Shift+A opens the assign picker for the current
  // selection; with no selection it targets the most recently interacted
  // line via the picker's "no selection" prompt path (picker opens with
  // count 0 and the user can still pick a character, which shows a hint).
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.ctrlKey && e.shiftKey && (e.key === 'A' || e.key === 'a')) {
        e.preventDefault();
        setAssignPickerOpen((open) => !open);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  // Ctrl+? (Ctrl+Shift+/) toggles help. On US layouts '?' needs Shift, so
  // accept both 'Ctrl+?' and 'Ctrl+/'. When the desktop shell exposes the
  // floating help window, toggle that instead of the in-app overlay.
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.ctrlKey && !e.altKey && !e.metaKey && (e.key === '?' || (e.shiftKey && e.key === '/'))) {
        e.preventDefault();
        if (typeof window !== 'undefined' && window.api?.toggleHelpWindow) {
          void window.api.toggleHelpWindow();
        } else {
          setShowHelp((v) => !v);
        }
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  // Phase 11: Ctrl+S saves (editor text or chapter XML); Escape deselects
  // dialog lines first, then closes the topmost open dialog.
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.ctrlKey && !e.shiftKey && !e.altKey && !e.metaKey && (e.key === 's' || e.key === 'S')) {
        const el = document.activeElement as HTMLElement | null;
        if (el && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.isContentEditable)) {
          // Let inputs handle their own Ctrl+S (e.g. markdown editor) only if
          // the app does not. We save globally either way.
          e.preventDefault();
          void handleSaveRef.current?.();
          return;
        }
        e.preventDefault();
        void handleSaveRef.current?.();
      } else if (e.key === 'Escape' && !e.ctrlKey && !e.altKey) {
        // Only intercept Escape when nothing else has already consumed it.
        // Dialogs close themselves; here we just clear the dialog selection.
        setSelectedDialogKeys((prev) => (prev.size > 0 ? new Set() : prev));
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  // Clear stale selection keys when the chapter changes
  useEffect(() => {
    setSelectedDialogKeys(new Set());
  }, [chapter?.fileName]);

  const handleAssignFromPicker = useCallback(async (characterName: string) => {
    setAssignPickerOpen(false);
    if (selectedDialogKeys.size === 0) {
      alerts.warning('No dialog lines selected. Ctrl+Click dialog headers to select lines for assignment.');
      return;
    }
    const targets = chapter?.dialogs
      .filter((d) => selectedDialogKeys.has(dialogKeyOf(d.dlgseq, d.sectionId || '0', d._index)))
      .map((d) => ({ dlgseq: d.dlgseq, sectionId: d.sectionId || '0', _index: d._index })) ?? [];
    const result = await bulkAssignCharacter(targets, characterName);
    if (result.assigned > 0) {
      alerts.success(`Assigned ${result.assigned} line${result.assigned === 1 ? '' : 's'} to ${characterName}.`);
    }
    if (result.failed > 0) {
      alerts.error(`Failed to assign ${result.failed} line${result.failed === 1 ? '' : 's'}.`);
    }
    setSelectedDialogKeys(new Set());
  }, [selectedDialogKeys, chapter, dialogKeyOf, bulkAssignCharacter]);

  const handleAssignCharacterRequest = useCallback((dlgseq: string, sectionId: string, _index?: number) => {
    // Context menu on a line: if the line is not in the selection, make it
    // the sole target; otherwise assign the whole selection.
    const key = dialogKeyOf(dlgseq, sectionId, _index);
    if (!selectedDialogKeys.has(key)) {
      setSelectedDialogKeys(new Set([key]));
    }
    setAssignPickerOpen(true);
  }, [selectedDialogKeys, dialogKeyOf]);

  // Alert system state
  const { alerts: alertList, addAlert, removeAlert, clearAlerts } = useAlerts();
  const [alertHistory, setAlertHistory] = useState<AlertHistoryItem[]>([]);
  const [, setTtsServiceReady] = useState(false);  // State tracked but value unused (WebSocket always enabled)

  // Ref to prevent double initialization in React StrictMode
  const initStarted = useRef(false);

  // Ref to track if we've already shown TTS ready alert
  const ttsReadyShownRef = useRef(false);
  const latestTtsAlertRef = useRef<Record<string, string> | null>(null);
  const latestTtsAlertTypeRef = useRef<AlertType | null>(null);

  const pushAlertHistory = useCallback((message: string, type: AlertType, source: 'internal' | 'tts-service') => {
    debugLog.info(`${logId}:alerts`, 'pushAlertHistory called', { message, type, source });
    setAlertHistory((prev) => ([
      ...prev,
      {
        id: `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`,
        message,
        type,
        source,
        timestamp: new Date(),
      }
    ]));
  }, []);

  const removeAlertHistoryItem = useCallback((id: string) => {
    setAlertHistory((prev) => prev.filter((item) => item.id !== id));
  }, []);

  const clearAlertHistory = useCallback(() => {
    setAlertHistory([]);
  }, []);

  // TTS alert handlers (defined before useEffects)
  const handleTtsAlert = useCallback((alert: { alertType: AlertType; message: string; metadata?: Record<string, string> }) => {
    debugLog.info(`${logId}:tts-alert`, 'handleTtsAlert received alert', { alert });
    // Build rich context message from metadata
    const parts: string[] = [];
    if (alert.metadata) {
      if (alert.metadata.story) parts.push(alert.metadata.story);
      if (alert.metadata.chapter) parts.push(`Ch${alert.metadata.chapter}`);
      if (alert.metadata.section) parts.push(`Sec${alert.metadata.section}`);
      if (alert.metadata.dialog) parts.push(`Dlg${alert.metadata.dialog}`);
      if (alert.metadata.character && alert.metadata.character !== 'narrator') {
        parts.push(alert.metadata.character);
      }
    }

    let fullMsg = alert.message;
    if (parts.length > 0) {
      fullMsg = `${alert.message} - ${parts.join(", ")}`;
    }
    debugLog.info(`${logId}:tts-alert`, 'handleTtsAlert normalized alert', {
      fullMsg,
      alertType: alert.alertType,
      metadata: alert.metadata,
      parts,
    });
    latestTtsAlertRef.current = alert.metadata || null;
    latestTtsAlertTypeRef.current = alert.alertType;
    addAlert(fullMsg, alert.alertType, 'tts-service');
    pushAlertHistory(fullMsg, alert.alertType, 'tts-service');
  }, [addAlert, pushAlertHistory]);

  const handleTtsStatus = useCallback((status: { status: string; ready: boolean }) => {
    // Only update internal state, don't show alerts for status messages
    // (status alerts come via HTTP channel to avoid duplicates)
    if (status.ready) {
      setTtsServiceReady(true);
      ttsReadyShownRef.current = true;
    } else if (status.status === 'warming_up' || status.status === 'starting') {
      setTtsServiceReady(false);
    }
  }, []);

  const handleTtsConnect = useCallback(() => {
    testSafeConsole.log('[App] Connected to TTS alerts');
    alerts.success('TTS Service: Connected');
  }, []);

  const handleTtsDisconnect = useCallback(() => {
    testSafeConsole.log('[App] Disconnected from TTS alerts');
  }, []);

  // Subscribe to internal alerts
  useEffect(() => {
    const unsubscribe = alertService.subscribe((message, type, duration) => {
      addAlert(message, type, 'internal', duration);
      pushAlertHistory(message, type, 'internal');
    });
    return unsubscribe;
  }, [addAlert, pushAlertHistory]);

  useTtsAlerts({
    enabled: true,  // Always enabled to receive startup alerts via WebSocket
    onAlert: handleTtsAlert,
    onStatus: handleTtsStatus,
    onConnect: handleTtsConnect,
    onDisconnect: handleTtsDisconnect,
  });

  // Phase 12.1: TTS connectivity state drives the offline banner + retry.
  const ttsConnectivity = useTtsConnectivity({ enabled: true });

  // Window resize handler
  useEffect(() => {
    const handleResize = () => setWindowWidth(window.innerWidth);
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [setWindowWidth]);

  // Initialize app
  useEffect(() => {
    // Prevent double initialization in React StrictMode
    if (initStarted.current) return;
    initStarted.current = true;

    const init = async () => {
      try {
        setLoading(true);
        debugLog.info(`${logId}:init`, 'Initializing app bootstrap');
        await PythonBridgeService.validateConfig();

        // Load available stories and set current story
        let stories: { name: string; path: string; directory_name: string }[] = [];
        try {
          stories = await PythonBridgeService.listStories();
        } catch (storyErr) {
          testSafeConsole.warn('Failed to list stories, falling back to default:', storyErr);
          stories = [];
        }

        let current = '';
        try {
          current = await PythonBridgeService.getCurrentStory();
          testSafeConsole.log('[App.tsx] getCurrentStory returned:', current);
        } catch (err) {
          testSafeConsole.warn('Failed to get current story:', err);
        }

        testSafeConsole.log('[App.tsx] Available stories:', stories);
        testSafeConsole.log('[App.tsx] Current story from state:', current);

        // Default to first story or use Story-Default for backward compatibility
        let selectedStory = stories[0] || null;
        if (current) {
          const found = stories.find(s => s.directory_name === current);
          testSafeConsole.log('[App.tsx] Found story match:', found);
          if (found) selectedStory = found;
        } else if (!current && stories.length > 0) {
          // Fallback: try to get current-story from global config
          try {
            const globalConfig = await PythonBridgeService.loadGlobalConfig();
            const configCurrentStory = globalConfig?.FlexiTTS?.['current-story'];
            const storyPrefix = globalConfig?.FlexiTTS?.['story-dir-prefix'] || 'Story-';
            testSafeConsole.log('[App.tsx] Global config current-story:', configCurrentStory);
            if (configCurrentStory) {
              const fullDirName = `${storyPrefix}${configCurrentStory}`;
              const found = stories.find(s => s.directory_name === fullDirName);
              testSafeConsole.log('[App.tsx] Found story from global config:', found);
              if (found) {
                selectedStory = found;
                current = fullDirName;
              }
            }
          } catch (err) {
            testSafeConsole.warn('[App.tsx] Failed to load global config for fallback:', err);
          }
        }

        setCurrentStory(selectedStory);
        testSafeConsole.log('[App.tsx] Selected story:', selectedStory);
        debugLog.info(`${logId}:init`, 'Selected story resolved', { selectedStory });

        // Set current story in main process
        if (selectedStory) {
          try {
            await PythonBridgeService.setCurrentStory(selectedStory.directory_name);
          } catch (err) {
            testSafeConsole.warn('Failed to set current story:', err);
          }
        }

        // Load story config for selected story
        let cfg;
        try {
          const storyDir = selectedStory?.directory_name;
          testSafeConsole.log(`[App.tsx] Loading story config for: ${storyDir || 'NULL (legacy fallback)'}`);
          testSafeConsole.log(`[App.tsx] Selected story object:`, selectedStory);
          cfg = selectedStory
            ? await PythonBridgeService.loadStoryConfigForStory(selectedStory.directory_name)
            : await PythonBridgeService.loadStoryConfig();
          debugLog.info(`${logId}:init`, 'Story config loaded', {
            storyDir: storyDir || 'legacy',
            chaptersDir: cfg?.global?.chapters,
            storyXmlDir: cfg?.global?.['story-xml'],
            storyAudioDir: cfg?.global?.['story-audio'],
            clipsDir: cfg?.global?.clips,
            voicesDir: cfg?.global?.voices,
          });
          testSafeConsole.log(`[App.tsx] Successfully loaded config for: ${storyDir || 'legacy'}`);
        } catch (err) {
          testSafeConsole.error('[App.tsx] Failed to load story config:', err);
          testSafeConsole.error('[App.tsx] Error details:', {
            selectedStory: selectedStory?.directory_name,
            error: err instanceof Error ? err.message : String(err)
          });
          throw err;
        }
        setConfig(cfg);

        // Load chapter files for selected story
        let list: string[] = [];
        try {
          list = selectedStory
            ? await PythonBridgeService.listChapterFilesForStory(selectedStory.directory_name)
            : await PythonBridgeService.listChapterFiles();
        } catch (err) {
          testSafeConsole.warn('Failed to list chapter files:', err);
          list = [];
        }
        setChapterList(list);

        if (list.length > 0) await handleChapterSelect(list[0], cfg, selectedStory?.directory_name);

        // Phase 12.2: offer to restore an unsaved session checkpoint
        if (selectedStory) {
          const checkpoint = loadRecoveryCheckpoint(selectedStory.directory_name);
          if (hasRecoveryData(checkpoint)) {
            setRecoveryData(checkpoint);
            setShowRecoveryDialog(true);
          }
        }

        // Start TTS service - service will broadcast warmup alerts via WebSocket
        alerts.info('Starting TTS Service...', 5000);

        // enableWebSocket connects when service is running (not waiting for full warmup)
        const success = await PythonBridgeService.startAndConnectTtsService(setTtsServiceReady);
        if (!success) {
          alerts.warning('TTS Service: Failed to start', 5000);
        }
      } catch (err: unknown) {
        setError((err as Error).message || 'Unknown error');
      } finally {
        setLoading(false);
      }
    };
    init();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // XML generation pipeline
  const runXmlGenerationPipeline = useCallback(async (stem: string, attempt: number, storyDirOverride?: string): Promise<void> => {
    if (attempt > 3) throw new Error('Exceeded max retries');
    setGenerateAttempt(attempt);
    try {
      if (window.api?.runPythonScript) {
        const storyDir = storyDirOverride || currentStory?.directory_name || 'Story-Default';
        const mdPath = `${storyDir}/story-chapters/${stem}.md`;
        const xmlPath = `${storyDir}/story-xml/${stem}.xml`;
        debugLog.info(`${logId}:runXmlGenerationPipeline`, 'Starting XML generation pipeline', { storyDir, stem, attempt, mdPath, xmlPath, currentStory: currentStory?.directory_name, storyDirOverride });
        await window.api.runPythonScript('src/scripts/chapter_to_xml.py', [mdPath]);
        debugLog.info(`${logId}:runXmlGenerationPipeline`, 'chapter_to_xml.py completed', { mdPath, xmlPath, storyDir });
        await window.api.runPythonScript('src/scripts/chapter_seq_xml.py', [xmlPath]);
        debugLog.info(`${logId}:runXmlGenerationPipeline`, 'chapter_seq_xml.py completed', { xmlPath, storyDir });
        await window.api.runPythonScript('src/scripts/chapter_validate_xml.py', [xmlPath]);
        debugLog.info(`${logId}:runXmlGenerationPipeline`, 'chapter_validate_xml.py completed', { xmlPath, storyDir });
      } else {
        debugLog.warn(`${logId}:runXmlGenerationPipeline`, 'Mock pipeline execution', { stem, attempt, storyDirOverride });
        await new Promise(r => setTimeout(r, 2000));
      }
    } catch (err) {
      debugLog.exception(`${logId}:runXmlGenerationPipeline`, 'XML generation pipeline', err, { stem, attempt, storyDirOverride, currentStory: currentStory?.directory_name });
      if (attempt >= 3) throw err;
      await runXmlGenerationPipeline(stem, attempt + 1, storyDirOverride);
    }
  }, [currentStory?.directory_name, setGenerateAttempt]);

  // Chapter selection handler
  const handleChapterSelect = useCallback(async (filePath: string, loadedConfig?: StoryConfig, forcedStoryDir?: string) => {
    // Check for unsaved changes
    if ((hasUnsavedChangesRef.current || hasUnsavedMarkdownChangesRef.current) && currentChapterFile) {
      const res = await PythonBridgeService.showConfirmDialog(
        'Unsaved Changes',
        'You have unsaved changes.',
        'Save before switching?'
      );
      if (res === 2) return;
      if (res === 0) {
        try {
          const stem = currentChapterFile.split('/').pop()?.replace('.md', '') || 'unknown';
          const storyDir = forcedStoryDir || currentStory?.directory_name || 'Story-Default';
          if (hasUnsavedChangesRef.current) {
            await PythonBridgeService.writeChapterFile(
              `${storyDir}/story-xml/${stem}.xml`,
              xmlContentRef.current
            );
            setLastSavedXmlValue(xmlContentRef.current);
          }
          if (hasUnsavedMarkdownChangesRef.current) {
            const storyDir = forcedStoryDir || currentStory?.directory_name || 'Story-Default';
            await PythonBridgeService.writeChapterFile(
              `${storyDir}/story-chapters/${stem}.md`,
              markdownContent
            );
            setLastSavedMarkdownValue(markdownContent);
            setHasUnsavedMarkdownChangesValue(false);
          }
        } catch (e) {
          console.error('Save failed during switch:', e);
          return;
        }
      }
    }

    setShowChapterMenu(false);
    setLoading(true);
    setCurrentChapterFile(filePath);
    const stem = filePath.split('/').pop()?.replace('.md', '')?.replace('.xml', '') || 'unknown';

    const storyDir = forcedStoryDir || currentStory?.directory_name || 'Story-Default';
    debugLog.info(`${logId}:handleChapterSelect`, 'Selecting chapter', { filePath, stem, storyDir, forcedStoryDir });
    await loadMarkdown(stem, storyDir);

    const xmlPath = `${storyDir}/story-xml/${stem}.xml`;
    const xmlExists = await PythonBridgeService.checkXmlExistsForStory(stem, storyDir);
    debugLog.info(`${logId}:handleChapterSelect`, 'XML existence decision', { stem, storyDir, xmlPath, xmlExists });
    if (xmlExists) {
      await loadChapter(xmlPath, loadedConfig, storyDir);
    } else {
      setIsGeneratingStructure(true);
      try {
        await runXmlGenerationPipeline(stem, 1, storyDir);
        await loadChapter(xmlPath, loadedConfig, storyDir);
      } catch {
        await PythonBridgeService.showErrorDialog('Generation Failed', `Failed to generate XML for ${stem}`);
        resetMarkdown();
      } finally {
        setIsGeneratingStructure(false);
        setGenerateAttempt(0);
      }
    }
    setLoading(false);
  }, [currentChapterFile, currentStory, hasUnsavedChangesRef, hasUnsavedMarkdownChangesRef, xmlContentRef,
      markdownContent, setLastSavedXmlValue, setLastSavedMarkdownValue, setHasUnsavedMarkdownChangesValue,
      setCurrentChapterFile, loadMarkdown, loadChapter, setIsGeneratingStructure, setGenerateAttempt,
      setLoading, resetMarkdown, runXmlGenerationPipeline]);

  // Save handler
  const handleSave = useCallback(async () => {
    try {
      const stem = currentChapterFile.split('/').pop()?.replace('.md', '')?.replace('.xml', '') || 'unknown';
      const storyDir = currentStory?.directory_name || 'Story-Default';
      const xmlPath = `${storyDir}/story-xml/${stem}.xml`;
      const mdPath = `${storyDir}/story-chapters/${stem}.md`;
      const hadMarkdownChanges = hasUnsavedMarkdownChangesRef.current;
      const hadXmlChanges = hasUnsavedChangesRef.current;

      debugLog.info(`${logId}:handleSave`, 'Starting save', { stem, storyDir, mdPath, xmlPath, hadMarkdownChanges, hadXmlChanges });

      if (hadXmlChanges && chapter) {
        const xml = generateXMLFromChapter(chapter);
        debugLog.info(`${logId}:handleSave`, 'Saving edited chapter XML from dialog UI', { xmlPath, stem, storyDir, dialogCount: chapter.dialogs.length });
        await PythonBridgeService.writeChapterFile(xmlPath, xml);

        try {
          await PythonBridgeService.validateChapterXML(xmlPath);
        } catch (validationError) {
          alerts.error(`XML validation failed for ${stem}. Reloading chapter from disk to discard invalid dialog edits.`, 7000);
          debugLog.exception(`${logId}:handleSave`, 'Dialog XML validation failed after save', validationError, { xmlPath, stem, storyDir });
          await loadChapter(xmlPath, config || undefined, storyDir);
          setHasUnsavedChangesValue(false);
          return;
        }

        setLastSavedXmlValue(xml);
        setHasUnsavedChangesValue(false);
        alerts.success(`Saved chapter XML to ${xmlPath}`, 5000);
        debugLog.info(`${logId}:handleSave`, 'Saved edited chapter XML', { xmlPath, stem, storyDir });
      }
      if (hadMarkdownChanges) {
        await PythonBridgeService.writeChapterFile(mdPath, markdownContent);
        setLastSavedMarkdownValue(markdownContent);
        setHasUnsavedMarkdownChangesValue(false);
        alerts.success(`Saved chapter markdown to ${mdPath}`, 5000);
        if (currentStory?.directory_name) clearRecoveryCheckpoint(currentStory.directory_name);
        alerts.info(`Regenerating XML for ${stem}...`, 5000);
        debugLog.info(`${logId}:handleSave`, 'Saved markdown, regenerating XML from chapter editor content', { mdPath, xmlPath, stem, storyDir });

        setIsGeneratingStructure(true);
        try {
          await runXmlGenerationPipeline(stem, 1, storyDir);
          alerts.info(`Refreshing Chapter Dialog UI from regenerated XML for ${stem}...`, 4000);
          await loadChapter(xmlPath, config || undefined, storyDir);
          alerts.success(`Chapter Dialog refreshed from regenerated XML for ${stem}`, 4000);
          debugLog.info(`${logId}:handleSave`, 'Reloaded chapter after XML regeneration', { xmlPath, stem, storyDir });
        } finally {
          setIsGeneratingStructure(false);
          setGenerateAttempt(0);
        }
      }
    } catch (e) {
      debugLog.exception(`${logId}:handleSave`, 'Save failed', e, { currentChapterFile, currentStory: currentStory?.directory_name });
      console.error('Save failed:', e);
    }
  }, [currentChapterFile, currentStory, chapter, hasUnsavedChangesRef, hasUnsavedMarkdownChangesRef,
      markdownContent, setLastSavedXmlValue, setHasUnsavedChangesValue,
      setLastSavedMarkdownValue, setHasUnsavedMarkdownChangesValue, runXmlGenerationPipeline,
      loadChapter, config, setIsGeneratingStructure, setGenerateAttempt]);

  // Story selection handler
  const handleStorySelect = useCallback(async (story: StoryInfo | null) => {
    if (!story) return;

    // Check for unsaved changes
    if ((hasUnsavedChangesRef.current || hasUnsavedMarkdownChangesRef.current) && currentChapterFile) {
      const res = await PythonBridgeService.showConfirmDialog(
        'Unsaved Changes',
        'You have unsaved changes.',
        'Save before switching stories?'
      );
      if (res === 2) return; // Cancel
      if (res === 0) {
        // Save current chapter before switching
        await handleSave();
      }
    }

    setLoading(true);
    setCurrentStory(story);
    debugLog.info(`${logId}:handleStorySelect`, 'Switching story', { story });
    await PythonBridgeService.setCurrentStory(story.directory_name);

    // Load config for new story
    const cfg = await PythonBridgeService.loadStoryConfigForStory(story.directory_name);
    debugLog.info(`${logId}:handleStorySelect`, 'Loaded story config after switch', {
      storyDir: story.directory_name,
      chaptersDir: cfg?.global?.chapters,
      storyXmlDir: cfg?.global?.['story-xml'],
      storyAudioDir: cfg?.global?.['story-audio'],
      clipsDir: cfg?.global?.clips,
      voicesDir: cfg?.global?.voices,
    });
    setConfig(cfg);

    // Load chapters for new story
    const files = await PythonBridgeService.listChapterFilesForStory(story.directory_name);
    setChapterList(files);

    // Select first chapter of new story
    if (files.length > 0) {
      await handleChapterSelect(files[0], cfg, story.directory_name);
    }

    setLoading(false);
  }, [hasUnsavedChangesRef, hasUnsavedMarkdownChangesRef, currentChapterFile,
      setLoading, setCurrentStory, setConfig, setChapterList, handleChapterSelect, handleSave]);
  // Keep the Phase 11 Ctrl+S ref pointing at the latest handleSave
  handleSaveRef.current = handleSave;

  // Phase 12.2: debounced recovery checkpoint of unsaved content
  useEffect(() => {
    const storyDir = currentStory?.directory_name;
    if (!storyDir || !currentChapterFile) return;
    const unsavedMd = hasUnsavedMarkdownChangesRef.current;
    const unsavedXml = hasUnsavedChangesRef.current;
    if (!unsavedMd && !unsavedXml) return;
    const timer = window.setTimeout(() => {
      saveRecoveryCheckpoint({
        storyDir,
        chapterFile: currentChapterFile,
        stem: currentChapterFile.split('/').pop()?.replace(/\.(md|xml)$/, '') || 'unknown',
        markdown: unsavedMd ? markdownContent : null,
        xml: unsavedXml ? xmlContentRef.current : null,
        savedAt: new Date().toISOString(),
      });
    }, 1500);
    return () => window.clearTimeout(timer);
  }, [currentStory?.directory_name, currentChapterFile, markdownContent]);

  // Phase 12.2: recovery dialog actions
  const handleRecoveryRestore = useCallback(() => {
    if (!recoveryData) { setShowRecoveryDialog(false); return; }
    try {
      if (recoveryData.markdown !== null) {
        setMarkdownContent(recoveryData.markdown);
        setLastSavedMarkdownValue(recoveryData.markdown);
        setHasUnsavedMarkdownChangesValue(true);
      }
      if (recoveryData.xml !== null) {
        // XML restore: write into state so the save flow picks it up
        xmlContentRef.current = recoveryData.xml;
        setXmlContent(recoveryData.xml);
        setLastSavedXmlValue(recoveryData.xml);
        setHasUnsavedChangesValue(true);
      }
      setEditorMode(recoveryData.markdown !== null);
      clearRecoveryCheckpoint(recoveryData.storyDir);
      alerts.success('Unsaved session restored.', 5000);
    } catch (e) {
      alerts.error(`Recovery failed: ${(e as Error).message}`);
    } finally {
      setShowRecoveryDialog(false);
      setRecoveryData(null);
    }
  }, [recoveryData, xmlContentRef, setXmlContent, setLastSavedXmlValue, setHasUnsavedChangesValue]);

  const handleRecoveryDiscard = useCallback(() => {
    if (recoveryData) clearRecoveryCheckpoint(recoveryData.storyDir);
    setShowRecoveryDialog(false);
    setRecoveryData(null);
    alerts.info('Recovered changes discarded.');
  }, [recoveryData]);

  // Toggle editor handler
  const handleToggleEditor = useCallback(async () => {
    if (editorMode && hasUnsavedMarkdownChangesRef.current) {
      const res = await PythonBridgeService.showConfirmDialog(
        'Unsaved Changes',
        'You have unsaved changes.',
        'Save before closing?'
      );
      if (res === 2) return;
      if (res === 0) await handleSave();
      else {
        setMarkdownContent(lastSavedMarkdownRef.current);
        setHasUnsavedMarkdownChangesValue(false);
      }
    }
    setEditorMode(!editorMode);
  }, [editorMode, hasUnsavedMarkdownChangesRef, lastSavedMarkdownRef, handleSave,
      setEditorMode, setMarkdownContent, setHasUnsavedMarkdownChangesValue]);

  // Refresh clips and render state
  const refreshClips = useCallback(async (fullRefresh: boolean = false) => {
    if (!currentChapterFile) return;
    const name = currentChapterFile.split('/').pop()?.replace('.md', '.xml') || '';
    setAvailableClips(await PythonBridgeService.listChapterClips(name));
    setHasChapterAudio(await PythonBridgeService.checkChapterAudio(name));
    // Also refresh render state so stale indicators update after selective dialog re-renders
    if (checkRenderState) {
      await checkRenderState(null, fullRefresh); // Pass null for chapterOverride to use current chapter
    }

    // Merge the freshly computed dialog hashes/timestamps into the in-memory
    // chapter so edited dialogs flip back to green immediately after a render,
    // without needing another XML disk read.
    const state = renderStateRef.current;
    const hashes = state?.dialog_hashes as Record<string, string> | undefined;
    if (hashes && applyRenderResults) {
      const renderedAt = (state?.rendered_at as Record<string, number> | undefined) || {};
      const merged: Record<string, { hash: string; renderedAt?: number }> = {};
      for (const [dialogId, hash] of Object.entries(hashes)) {
        merged[dialogId] = { hash, renderedAt: renderedAt[dialogId] };
      }
      applyRenderResults(merged);
    }
  }, [currentChapterFile, setAvailableClips, setHasChapterAudio, checkRenderState, applyRenderResults]);

  useEffect(() => {
    const metadata = latestTtsAlertRef.current;
    if (!metadata || !chapter) return;

    const currentChapterName = chapter.fileName?.split('/').pop()?.replace('.md', '.xml') || '';
    const alertChapterNum = metadata.chapter;
    const currentChapterNum = chapter.fileName?.match(/(\d+)/)?.[1]?.padStart(3, '0') || '';
    const isDialogRenderAlert = metadata.kind === 'dialog' && !!metadata.dialog;
    const isCurrentChapterAlert = !!currentChapterName && !!alertChapterNum && currentChapterNum === alertChapterNum;

    if (isDialogRenderAlert && isCurrentChapterAlert && (latestTtsAlertTypeRef.current === 'success' || latestTtsAlertTypeRef.current === 'info')) {
      debugLog.info(`${logId}:tts-alert`, 'Refreshing clips after dialog render alert for current chapter', {
        currentChapterName,
        currentChapterNum,
        alertChapterNum,
        dialog: metadata.dialog,
        section: metadata.section,
        alertType: latestTtsAlertTypeRef.current,
      });
      void refreshClips();
    }
  }, [chapter, refreshClips, alertHistory.length]);

  // Context menu handlers
  const handleContextMenu = (e: React.MouseEvent) => {
    e.preventDefault();
    setShowChapterMenu(true);
    setMenuPos({ x: e.pageX, y: e.pageY });
  };
  const closeMenu = () => setShowChapterMenu(false);

  if (loading) return <div className="loading-screen">Loading FlexiTTS...</div>;
  if (error) return <div className="error-screen">Error: {error}</div>;

  const hasAnyUnsaved = hasUnsavedChangesRef.current || hasUnsavedMarkdownChangesRef.current;

  return (
    <div className="app-container" onContextMenu={handleContextMenu} onClick={closeMenu}>
      {isGeneratingStructure && (
        <div className="loading-overlay">
          <div className="spinner" />
          <h2>Processing Markdown...</h2>
          <p>Attempt {generateAttempt}/3</p>
        </div>
      )}

      {chapter && (
        <CharacterVoiceDialog
          storyDir={currentStory?.directory_name || ''}
          open={showCharacterVoices}
          onClose={() => setShowCharacterVoices(false)}
          onQuickAssign={(characterName) => {
            // Phase 10.1: quick assign from the Characters tab. Requires an
            // existing dialog selection; hints otherwise.
            if (selectedDialogKeys.size === 0) {
              alerts.warning('No dialog lines selected. Ctrl+Click dialog headers, then use Assign.');
              return;
            }
            setAssignPickerOpen(false);
            void handleAssignFromPicker(characterName);
          }}
        />
      )}

      {chapter && (
        <TopBar
          config={config}
          chapter={chapter}
          filePath={currentChapterFile}
          chapterList={chapterList}
          hasChapterAudio={hasChapterAudio}
          selectedCharacter={selectedCharacterFilter}
          onChapterSelect={handleChapterSelect}
          onCharacterSelect={setSelectedCharacterFilter}
          onSave={handleSave}
          onRenderComplete={refreshClips}
          hasUnsavedChanges={hasAnyUnsaved}
          editorMode={editorMode}
          onToggleEditor={handleToggleEditor}
          onToggleCharacterVoices={() => setShowCharacterVoices((v) => !v)}
          onOpenHelp={() => {
            if (window.api?.toggleHelpWindow) void window.api.toggleHelpWindow();
            else setShowHelp(true);
          }}
          alertHistory={alertHistory}
          onRemoveAlertHistoryItem={removeAlertHistoryItem}
          onClearAlertHistory={() => {
            clearAlertHistory();
            clearAlerts();
          }}
          currentStory={currentStory}
          onStorySelect={handleStorySelect}
          // Pass centralized renderState from useChapter hook
          // This ensures TopBar reflects the authoritative computed state
          renderState={renderState}
        />
      )}

      {/* Phase 12.1: offline indicator with retry + backoff status */}
      {!ttsConnectivity.online && (
        <div
          role="status"
          aria-live="polite"
          data-testid="tts-offline-banner"
          style={{
            display: 'flex', alignItems: 'center', gap: 10, padding: '6px 14px',
            background: '#4a1d1d', color: '#ffd7d7', borderBottom: '1px solid #a33',
            fontSize: 13,
          }}
        >
          <span aria-hidden="true">⚠️</span>
          <span>
            TTS service offline
            {ttsConnectivity.retrying ? ' — reconnecting…' : ttsConnectivity.nextRetryInMs !== null ? ` — next retry in ${Math.round(ttsConnectivity.nextRetryInMs / 1000)}s (attempt ${ttsConnectivity.attempt})` : ''}
          </span>
          <button
            type="button"
            data-testid="tts-retry"
            onClick={ttsConnectivity.retryNow}
            disabled={ttsConnectivity.retrying}
            style={{
              marginLeft: 'auto', padding: '3px 12px', borderRadius: 4, cursor: 'pointer',
              border: '1px solid #d88', background: '#5a2a2a', color: '#ffe', fontWeight: 600,
              opacity: ttsConnectivity.retrying ? 0.6 : 1,
            }}
          >
            {ttsConnectivity.retrying ? 'Retrying…' : 'Retry'}
          </button>
        </div>
      )}

      <div style={{ display: 'flex', height: 'calc(100vh - 60px)', overflow: 'hidden' }}>
        {editorMode && (
          <aside style={{ flex: 1, display: 'flex', flexDirection: 'column', background: '#1e1e1e', color: '#d4d4d4', borderRight: windowWidth >= 1200 ? '1px solid #ccc' : 'none' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '10px 20px', background: '#2d2d2d', borderBottom: '1px solid #444', alignItems: 'center' }}>
              <h2 style={{ margin: 0, fontSize: '1rem', color: '#fff' }}>Chapter Editor (Markdown)</h2>
              <div style={{ display: 'flex', gap: '10px' }}>
                <button onClick={formatMarkdown} style={{ padding: '6px 12px', background: '#4CAF50', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer' }}>Clean Up (80 chars)</button>
                <button onClick={handleSave} style={{ padding: '6px 12px', background: hasUnsavedMarkdownChangesRef.current ? '#ff9800' : '#2196F3', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer', fontWeight: hasUnsavedMarkdownChangesRef.current ? 'bold' : 'normal' }}>{hasUnsavedMarkdownChangesRef.current ? 'Save *' : 'Save'}</button>
                <button onClick={handleToggleEditor} style={{ padding: '6px 12px', background: '#2196F3', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer' }}>Close</button>
              </div>
            </div>
            <textarea
              value={markdownContent}
              onChange={e => {
                setMarkdownContent(e.target.value);
                setHasUnsavedMarkdownChangesValue(e.target.value !== lastSavedMarkdownRef.current);
              }}
              style={{ flex: 1, width: '100%', padding: '20px', background: '#1e1e1e', color: '#d4d4d4', border: 'none', resize: 'none', fontFamily: 'monospace', fontSize: '14px', lineHeight: '1.6', outline: 'none', whiteSpace: 'pre-wrap' }}
              spellCheck={false}
            />
          </aside>
        )}

        {(!editorMode || windowWidth >= 1200) && (
          <main className="window-body" style={{ flex: 1, padding: '20px', overflowY: 'auto' }}>
            <h2 style={{ marginTop: 0 }}>Dialogs</h2>
            {chapter?.dialogs.map(dialog => {
              const isFiltered = !!selectedCharacterFilter && dialog.character !== selectedCharacterFilter;
              const dialogSeq = String(dialog.dlgseq || dialog.attributes?.dlgseq || dialog.attributes?.id || '0');
              const displayId = dialog.sectionId ? `${dialog.sectionId}.${dialogSeq}` : dialogSeq;
              const chapNum = chapter.fileName.match(/(\d+)/)?.[1]?.padStart(3, '0') || '000';
              const secStr = String(dialog.sectionId || '0').padStart(3, '0');
              const dlgStr = dialogSeq.padStart(3, '0');
              const speakerFileName = dialog.character;
              const clipPrefix = `chapter_${chapNum}_${secStr}_${dlgStr}_${speakerFileName}`;
              const hasClip = availableClips.some(c => c === `${clipPrefix}.wav` || c.startsWith(`${clipPrefix}_s`));
              const isStaleClip = getIsStaleClip(secStr, dlgStr);

              // Check for timestamp-specific staleness (for blue button color)
              // Support both camelCase and snake_case from Python JSON response
              const timestampStaleDialogs = renderState?.timestamp_stale_dialogs ||
                                          renderState?.timestampStaleDialogs ||
                                          renderState?.timestamp_stale || [];
              const dialogId = `${secStr}_${dlgStr}`;
              const isTimestampStale = timestampStaleDialogs.includes(dialogId);

              // After full chapter render, dialogs should be considered in sync
              // Only show blue if explicitly marked as timestamp stale by the backend
              const finalIsTimestampStale = isTimestampStale;

              if (dialogId === '002_003') {
                debugLog.info('App:getIsStaleClip', `Dialog ${dialogId} - isTimestampStale=${finalIsTimestampStale}`, {
                  dialogId,
                  finalIsTimestampStale,
                  hasRenderState: !!renderState,
                  renderStateKeys: renderState ? Object.keys(renderState) : [],
                  timestampStaleDialogsCount: timestampStaleDialogs.length
                });
              }

              // Get available emotions for current dialog's character
              const getAvailableEmotions = (characterName: string): string[] => {
                const charConfig = config?.characters?.find(c => c.name === characterName);
                if (!charConfig) return [];
                
                const emotions: string[] = [];
                
                // Check custom-voice emotions
                if (charConfig['custom-voice']?.emotions) {
                  charConfig['custom-voice'].emotions.forEach((em: { emotion?: string; name?: string }) => {
                    const emotionName = em.emotion || em.name;
                    if (emotionName) emotions.push(emotionName);
                  });
                }
                
                // Check cloned-emotion configurations
                if (charConfig['cloned-emotion']) {
                  charConfig['cloned-emotion'].forEach((em: { emotion?: string }) => {
                    if (em.emotion) emotions.push(em.emotion);
                  });
                }
                
                // Check top-level emotions array
                if (charConfig.emotions) {
                  charConfig.emotions.forEach((em: { emotion?: string; name?: string }) => {
                    const emotionName = em.emotion || em.name;
                    if (emotionName) emotions.push(emotionName);
                  });
                }
                
                return emotions;
              };

              return (
                <DialogBar
                  key={`${dialog.sectionId || '1'}-${dialog.dlgseq}-${dialog._index}`}
                  dialog={dialog}
                  displayId={displayId}
                  chapterFileName={chapter.fileName.split('/').pop()}
                  storyDirectory={currentStory?.directory_name}
                  isFilteredOut={isFiltered}
                  hasAudioClip={hasClip}
                  isStaleClip={isStaleClip}
                  isTimestampStale={finalIsTimestampStale}
                  onSaveRequest={handleSave}
                  onUpdateDialog={handleUpdateDialog}
                  onRefreshClips={refreshClips}
                  availableCharacters={config?.characters?.map(c => c.name) || []}
                  availableEmotions={getAvailableEmotions(dialog.character)}
                  isSelected={selectedDialogKeys.has(dialogKeyOf(dialog.dlgseq, dialog.sectionId || '0', dialog._index))}
                  onToggleSelect={handleToggleDialogSelect}
                  onAssignCharacter={handleAssignCharacterRequest}
                />
              );
            })}
          </main>
        )}
      </div>

      {showChapterMenu && (
        <div
          style={{ position: 'fixed', top: menuPos.y, left: menuPos.x, background: 'white', border: '1px solid #ccc', boxShadow: '0 2px 5px rgba(0,0,0,0.2)', zIndex: 1000, padding: '5px 0', minWidth: '200px' }}
          onClick={e => e.stopPropagation()}
        >
          <div style={{ padding: '5px 10px', fontWeight: 'bold', borderBottom: '1px solid #eee', color: '#333' }}>Select Chapter</div>
          {chapterList.map((chFile, idx) => {
            const name = chFile.split('/').pop()?.replace('.md', '')?.replace('.xml', '') || chFile;
            const isActive = chFile === currentChapterFile;
            return (
              <div
                key={idx}
                style={{ padding: '5px 15px', cursor: 'pointer', color: '#333', background: isActive ? '#e6f7ff' : 'transparent', fontWeight: isActive ? 'bold' : 'normal' }}
                onClick={() => {
                  setShowChapterMenu(false);
                  handleChapterSelect(chFile);
                }}
                onMouseEnter={e => { if (!isActive) e.currentTarget.style.background = '#f0f0f0'; }}
                onMouseLeave={e => { if (!isActive) e.currentTarget.style.background = 'transparent'; }}
              >
                {name}
              </div>
            );
          })}
        </div>
      )}

      {/* Alert notifications container */}
      {/* Phase 10: character assignment picker (quick/bulk assign, A/B compare) */}
      <CharacterAssignPicker
        open={assignPickerOpen}
        characters={config?.characters ?? []}
        targetCount={selectedDialogKeys.size}
        allowCompare
        onCancel={() => setAssignPickerOpen(false)}
        onAssign={handleAssignFromPicker}
      />
      {/* Phase 12.2: unsaved-session recovery dialog */}
      {showRecoveryDialog && recoveryData && (
        <div
          role="presentation"
          data-testid="recovery-overlay"
          style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', zIndex: 5000, display: 'flex', alignItems: 'center', justifyContent: 'center' }}
        >
          <div
            role="dialog"
            aria-modal="true"
            aria-label="Recover unsaved session"
            data-testid="recovery-dialog"
            onClick={(e) => e.stopPropagation()}
            style={{ background: '#fff', color: '#222', borderRadius: 8, padding: 20, minWidth: 420, maxWidth: 560, boxShadow: '0 8px 30px rgba(0,0,0,0.35)' }}
          >
            <h3 style={{ margin: '0 0 8px', fontSize: 16 }}>Recover unsaved changes?</h3>
            <p style={{ margin: '0 0 6px', fontSize: 13.5 }}>
              A previous FlexiTTS session ended with unsaved edits to
              {' '}<strong>{recoveryData.stem}</strong> in <strong>{recoveryData.storyDir}</strong>
              {' '}(saved {new Date(recoveryData.savedAt).toLocaleString()}).
            </p>
            <p style={{ margin: '0 0 14px', fontSize: 13, color: '#666' }}>
              Restore loads the checkpoint into the editor and flags it as unsaved so you can review and save. Discard removes the checkpoint permanently.
            </p>
            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
              <button
                type="button"
                data-testid="recovery-discard"
                onClick={handleRecoveryDiscard}
                style={{ padding: '6px 14px', borderRadius: 4, cursor: 'pointer', border: '1px solid #c66', background: '#fdd' }}
              >
                Discard
              </button>
              <button
                type="button"
                data-testid="recovery-restore"
                onClick={handleRecoveryRestore}
                style={{ padding: '6px 14px', borderRadius: 4, cursor: 'pointer', border: '1px solid #4a90d9', background: '#e3ecff', fontWeight: 600 }}
              >
                Restore
              </button>
            </div>
          </div>
        </div>
      )}
      {/* Help dialog: Ctrl+? — subjects left, details right, search on top */}
      <HelpDialog
        open={showHelp}
        onClose={() => setShowHelp(false)}
        shortcutOverrides={helpShortcuts}
      />
      <AlertContainer alerts={alertList} onDismiss={removeAlert} />
    </div>
  );
}

/** Full-window help pane for the floating help window (?view=help). */
const StandaloneHelp: React.FC = () => {
  const [shortcuts, setShortcuts] = useState<Record<string, string> | undefined>(undefined);
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const globalConfig = await PythonBridgeService.loadGlobalConfig();
        const s = (globalConfig as { FlexiTTS?: { shortcuts?: Record<string, string> } })?.FlexiTTS?.shortcuts;
        if (!cancelled && s && Object.keys(s).length > 0) setShortcuts(s);
      } catch {
        // defaults are fine
      }
    })();
    return () => { cancelled = true; };
  }, []);
  // In the floating window 'close' asks main to toggle (hide) the window.
  const handleClose = useCallback(() => {
    void window.api?.toggleHelpWindow?.();
  }, []);
  return (
    <div style={{ height: '100vh' }}>
      <HelpDialog open onClose={handleClose} shortcutOverrides={shortcuts} mode="panel" />
    </div>
  );
};

export default App;
