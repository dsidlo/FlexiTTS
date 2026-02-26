import { useEffect, useCallback, useState } from 'react';
import './App.css';
import { PythonBridgeService } from './services/pythonBridge';
import type { StoryConfig } from './models/types';
import { TopBar } from './components/TopBar';
import { DialogBar } from './components/DialogBar';
import { useChapter, useMarkdown } from './hooks';
import { generateXMLFromChapter } from './services/chapterService';

function App() {
  // Chapter state from hook
  const {
    config, setConfig, chapter, chapterList, setChapterList,
    currentChapterFile, setCurrentChapterFile, selectedCharacterFilter, setSelectedCharacterFilter,
    availableClips, setAvailableClips, hasChapterAudio, setHasChapterAudio,
    isGeneratingStructure, setIsGeneratingStructure, generateAttempt, setGenerateAttempt,
    xmlContentRef, hasUnsavedChangesRef,
    setLastSavedXmlValue, setHasUnsavedChangesValue,
    loadChapter, handleUpdateDialog,
  } = useChapter();

  // Markdown state from hook
  const {
    editorMode, setEditorMode, markdownContent, setMarkdownContent,
    lastSavedMarkdownRef, hasUnsavedMarkdownChangesRef,
    setLastSavedMarkdownValue, setHasUnsavedMarkdownChangesValue,
    windowWidth, setWindowWidth, formatMarkdown, loadMarkdown, resetMarkdown,
  } = useMarkdown();

  // Local UI state
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showChapterMenu, setShowChapterMenu] = useState(false);
  const [menuPos, setMenuPos] = useState({ x: 0, y: 0 });

  // Window resize handler
  useEffect(() => {
    const handleResize = () => setWindowWidth(window.innerWidth);
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [setWindowWidth]);

  // Initialize app
  useEffect(() => {
    const init = async () => {
      try {
        setLoading(true);
        await PythonBridgeService.validateConfig();
        const cfg = await PythonBridgeService.loadStoryConfig();
        setConfig(cfg);
        const list = await PythonBridgeService.listChapterFiles();
        setChapterList(list);
        if (list.length > 0) await handleChapterSelect(list[0], cfg);
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
  const runXmlGenerationPipeline = async (stem: string, attempt: number): Promise<void> => {
    if (attempt > 3) throw new Error('Exceeded max retries');
    setGenerateAttempt(attempt);
    try {
      if (window.api?.runPythonScript) {
        await window.api.runPythonScript('src/scripts/chapter_to_xml.py', [`Story-Entanglement/story-chapters/${stem}.md`]);
        await window.api.runPythonScript('src/scripts/chapter_seq_xml.py', [`Story-Entanglement/story-xml/${stem}.xml`]);
        await window.api.runPythonScript('src/scripts/chapter_validate_xml.py', [`Story-Entanglement/story-xml/${stem}.xml`]);
      } else {
        console.log(`[Mock] Attempt ${attempt}`);
        await new Promise(r => setTimeout(r, 2000));
      }
    } catch (err) {
      if (attempt >= 3) throw err;
      await runXmlGenerationPipeline(stem, attempt + 1);
    }
  };

  // Chapter selection handler
  const handleChapterSelect = useCallback(async (filePath: string, loadedConfig?: StoryConfig) => {
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
          if (hasUnsavedChangesRef.current) {
            await PythonBridgeService.writeChapterFile(
              `Story-Entanglement/story-xml/${stem}.xml`, 
              xmlContentRef.current
            );
            setLastSavedXmlValue(xmlContentRef.current);
          }
          if (hasUnsavedMarkdownChangesRef.current) {
            await PythonBridgeService.writeChapterFile(
              `Story-Entanglement/story-chapters/${stem}.md`, 
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
    
    await loadMarkdown(stem);
    
    const xmlPath = `Story-Entanglement/story-xml/${stem}.xml`;
    if (await PythonBridgeService.checkXmlExists(stem)) {
      await loadChapter(xmlPath, loadedConfig);
    } else {
      setIsGeneratingStructure(true);
      try {
        await runXmlGenerationPipeline(stem, 1);
        await loadChapter(xmlPath, loadedConfig);
      } catch (err) {
        await PythonBridgeService.showErrorDialog('Generation Failed', `Failed to generate XML for ${stem}`);
        resetMarkdown();
      } finally {
        setIsGeneratingStructure(false);
        setGenerateAttempt(0);
      }
    }
    setLoading(false);
  }, [currentChapterFile, hasUnsavedChangesRef, hasUnsavedMarkdownChangesRef, xmlContentRef, 
      markdownContent, setLastSavedXmlValue, setLastSavedMarkdownValue, setHasUnsavedMarkdownChangesValue,
      setCurrentChapterFile, loadMarkdown, loadChapter, setIsGeneratingStructure, setGenerateAttempt,
      setLoading, resetMarkdown]);

  // Save handler
  const handleSave = useCallback(async () => {
    try {
      const stem = currentChapterFile.split('/').pop()?.replace('.md', '') || 'unknown';
      if (hasUnsavedChangesRef.current && chapter) {
        const xml = generateXMLFromChapter(chapter);
        await PythonBridgeService.writeChapterFile(`Story-Entanglement/story-xml/${stem}.xml`, xml);
        await PythonBridgeService.validateChapterXML(`Story-Entanglement/story-xml/${stem}.xml`);
        setLastSavedXmlValue(xml);
        setHasUnsavedChangesValue(false);
      }
      if (hasUnsavedMarkdownChangesRef.current) {
        const mdPath = `Story-Entanglement/story-chapters/${stem}.md`;
        await PythonBridgeService.writeChapterFile(mdPath, markdownContent);
        setLastSavedMarkdownValue(markdownContent);
        setHasUnsavedMarkdownChangesValue(false);
      }
    } catch (e) {
      console.error('Save failed:', e);
    }
  }, [currentChapterFile, chapter, hasUnsavedChangesRef, hasUnsavedMarkdownChangesRef, 
      markdownContent, setLastSavedXmlValue, setHasUnsavedChangesValue,
      setLastSavedMarkdownValue, setHasUnsavedMarkdownChangesValue]);

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

  // Refresh clips
  const refreshClips = useCallback(async () => {
    if (!currentChapterFile) return;
    const name = currentChapterFile.split('/').pop()?.replace('.md', '.xml') || '';
    setAvailableClips(await PythonBridgeService.listChapterClips(name));
    setHasChapterAudio(await PythonBridgeService.checkChapterAudio(name));
  }, [currentChapterFile, setAvailableClips, setHasChapterAudio]);

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
        />
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
              const displayId = dialog.sectionId ? `${dialog.sectionId}.${dialog.id}` : dialog.id;
              const chapNum = chapter.fileName.match(/(\d+)/)?.[1]?.padStart(3, '0') || '000';
              const secStr = (dialog.sectionId || '1').padStart(3, '0');
              const dlgStr = dialog.id.replace('dialog-', '').padStart(3, '0');
              const hasClip = availableClips.some(c => c.includes(`chapter_${chapNum}_${secStr}_${dlgStr}`));

              return (
                <DialogBar 
                  key={`${dialog.sectionId || '1'}-${dialog.id}-${dialog._index}`}
                  dialog={dialog}
                  displayId={displayId}
                  chapterFileName={chapter.fileName.split('/').pop()}
                  isFilteredOut={isFiltered}
                  hasAudioClip={hasClip}
                  onSaveRequest={handleSave}
                  onUpdateDialog={handleUpdateDialog}
                  onRefreshClips={refreshClips}
                  availableCharacters={config?.characters?.map(c => c.name) || []}
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
    </div>
  );
}

export default App;
