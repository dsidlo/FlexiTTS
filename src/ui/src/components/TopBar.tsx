import React, { useState } from 'react';
import { PythonBridgeService } from '../services/pythonBridge';
import type { Chapter, StoryConfig } from '../models/types';

interface TopBarProps {
  config: StoryConfig | null;
  chapter: Chapter | null;
  filePath: string;
  chapterList: string[];
  hasChapterAudio?: boolean;
  selectedCharacter: string;
  onChapterSelect: (filePath: string) => void;
  onCharacterSelect: (character: string) => void;
  onSave?: () => Promise<void> | void;
  onRenderComplete?: () => void;
  hasUnsavedChanges?: boolean;
  editorMode?: boolean;
  onToggleEditor?: () => void;
}

export const TopBar: React.FC<TopBarProps> = ({ 
  config, chapter, filePath, chapterList, hasChapterAudio,
  selectedCharacter, onChapterSelect, onCharacterSelect, onSave, onRenderComplete,
  hasUnsavedChanges, editorMode, onToggleEditor
}) => {
  const [isSaving, setIsSaving] = useState(false);
  const [isRendering, setIsRendering] = useState(false);
  const [isPlayingAudio, setIsPlayingAudio] = useState(false);

  if (!chapter) {
    return (
      <div className="top-bar">
        <span>No chapter loaded.</span>
      </div>
    );
  }

  const uniqueCharacters = Array.from(new Set(chapter.dialogs.map((d) => d.character)));
  const characterCount = uniqueCharacters.length;
  const dialogCount = chapter.dialogs.length;

  const handleSave = async () => {
    setIsSaving(true);
    try {
      if (onSave) {
        await onSave();
      }
    } catch (error) {
      console.error("[TopBar] Save or validation failed:", error);
    } finally {
      setIsSaving(false);
    }
  };

  const handleRenderChapter = async () => {
    const chapterName = filePath.split('/').pop()?.replace('.md', '.xml') || 'Unknown.xml';
    
    if (isRendering) {
      // Cancel operation
      await PythonBridgeService.cancelAudio(chapterName);
      setIsRendering(false);
      return;
    }

    setIsRendering(true);
    try {
      if (hasUnsavedChanges && onSave) {
        console.log(`[TopBar] Auto-saving unsaved changes before rendering...`);
        await handleSave();
      }

      console.log(`[TopBar] Rendering full chapter: ${chapterName}`);
      
      // We can use runPythonScript explicitly to process the whole chapter
      if (typeof window !== 'undefined' && window.api && window.api.runPythonScript) {
         await window.api.runPythonScript('src/scripts/chapter_xml_to_audio.py', [
            `Story-Entanglement/story-xml/${chapterName}`,
            `--create-missing-clips`
         ]);
         
         if (onRenderComplete) onRenderComplete();
      } else {
        console.warn("API not available for rendering");
      }
    } catch (error) {
      console.error("[TopBar] Render chapter failed or was cancelled:", error);
    } finally {
      setIsRendering(false);
    }
  };

  const handlePlayChapter = async () => {
    const chapterName = filePath.split('/').pop()?.replace('.md', '.xml') || 'Unknown.xml';
    
    if (isPlayingAudio) {
      // Cancel operation
      await PythonBridgeService.cancelAudio(chapterName);
      setIsPlayingAudio(false);
      return;
    }

    setIsPlayingAudio(true);
    try {
      if (typeof window !== 'undefined' && window.api && window.api.playSoundFile) {
         const stem = chapterName.replace('.xml', '');
         const fullPath = `Story-Entanglement/story-audio/${stem}.wav`;
         await window.api.playSoundFile(fullPath);
      }
    } catch (error) {
      console.error("[TopBar] Play chapter failed or was cancelled:", error);
    } finally {
      setIsPlayingAudio(false);
    }
  };

  return (
    <div className="top-bar" style={{ display: 'flex', alignItems: 'center', gap: '16px', padding: '8px', borderBottom: '1px solid #ccc' }}>
      <div className="chapter-name" style={{ display: 'flex', alignItems: 'center' }}>
        <strong>Chapter Name:</strong>{' '}
        <select 
          value={filePath} 
          onChange={(e) => onChapterSelect(e.target.value)}
          style={{ marginLeft: '8px', maxWidth: '200px' }}
        >
          {chapterList.map((file) => {
            const fileName = file.split('/').pop()?.replace('.md', '')?.replace('.xml', '') || file;
            return (
              <option key={file} value={file}>
                {fileName}
              </option>
            );
          })}
        </select>
        {!editorMode && (
          <button 
            onClick={onToggleEditor}
            style={{
              marginLeft: '12px',
              padding: '4px 12px',
              backgroundColor: '#e0e0e0',
              color: '#333',
              border: '1px solid #888',
              borderRadius: '4px',
              cursor: 'pointer',
              fontSize: '0.9em',
              fontWeight: 'bold'
            }}
            title="Open Markdown Editor"
          >
            Edit Text
          </button>
        )}
      </div>
      
      <div className="characters">
        <strong>Characters:</strong> [{characterCount}]
        <select 
          style={{ marginLeft: '8px' }}
          value={selectedCharacter}
          onChange={(e) => onCharacterSelect(e.target.value)}
        >
          <option value="">All Characters</option>
          {uniqueCharacters.map((char) => {
             const isUnknown = config ? !config.characters.some(c => c.name === char) : false;
             return (
              <option 
                key={char} 
                value={char} 
                style={isUnknown ? { color: '#ffb74d', fontWeight: 'bold' } : {}}
              >
                {char} {isUnknown ? '(New)' : ''}
              </option>
            );
          })}
        </select>
      </div>

      <div className="dialogs">
        <strong>Dialogs:</strong> [{dialogCount}]
      </div>
      
      <div style={{ marginLeft: 'auto', display: 'flex', gap: '8px', alignItems: 'center' }}>
        <button 
          onClick={handleRenderChapter} 
          style={{ 
            padding: '4px 16px',
            backgroundColor: isRendering ? '#f44336' : (hasChapterAudio ? '#4CAF50' : '#888'),
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            opacity: 1
          }}
          title={isRendering ? "Stop rendering" : (hasChapterAudio ? "Re-render chapter" : "Render full chapter")}
        >
          {isRendering ? (
            <>
              <span className="spinner-icon" style={{ 
                display: 'inline-block',
                width: '0.8em',
                height: '0.8em',
                border: '2px solid rgba(255,255,255,0.3)',
                borderRadius: '50%',
                borderTopColor: '#fff',
                animation: 'spin 1s ease-in-out infinite',
                marginRight: '4px'
              }}></span>
              <span style={{
                display: 'inline-block',
                width: '10px',
                height: '10px',
                backgroundColor: 'white'
              }} /> Stop Chapter Render
            </>
          ) : (
            'Render Chapter'
          )}
        </button>

        {hasChapterAudio && !isRendering && (
          <button 
            onClick={handlePlayChapter} 
            style={{ 
              padding: '4px 16px',
              backgroundColor: isPlayingAudio ? '#f44336' : '#2196F3',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '8px'
            }}
            title={isPlayingAudio ? "Stop playback" : "Play full chapter"}
          >
            {isPlayingAudio ? (
              <>
                <span style={{
                  display: 'inline-block',
                  width: '10px',
                  height: '10px',
                  backgroundColor: 'white'
                }} /> Stop
              </>
            ) : (
              '▶ Play Chapter'
            )}
          </button>
        )}

        <button 
          onClick={handleSave} 
          disabled={isSaving || !hasUnsavedChanges}
          style={{ 
            padding: '4px 16px',
            backgroundColor: hasUnsavedChanges ? '#ff9800' : 'transparent',
            color: hasUnsavedChanges ? 'white' : '#888',
            border: hasUnsavedChanges ? 'none' : '1px solid #888',
            borderRadius: '4px',
            cursor: hasUnsavedChanges ? 'pointer' : 'default',
            transition: 'all 0.2s ease-in-out'
          }}
          title={hasUnsavedChanges ? "You have unsaved changes!" : "No changes to save"}
        >
          {isSaving ? 'Saving...' : (hasUnsavedChanges ? 'Save *' : 'Saved')}
        </button>
      </div>

      <style>{`
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
};
