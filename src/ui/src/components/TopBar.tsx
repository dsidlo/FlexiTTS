import React, { useMemo, useState } from 'react';
import { PythonBridgeService } from '../services/pythonBridge';
import { debugLog } from '../utils/debugLogger';
import { StoryDropdown } from './StoryDropdown';
import type { AlertHistoryItem, Chapter, StoryConfig, StoryInfo, ChapterRenderState } from '../models/types';

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
  onRenderComplete?: () => Promise<void> | void;
  hasUnsavedChanges?: boolean;
  editorMode?: boolean;
  onToggleEditor?: () => void;
  onToggleCharacterVoices?: () => void;
  alertHistory?: AlertHistoryItem[];
  onRemoveAlertHistoryItem?: (id: string) => void;
  onClearAlertHistory?: () => void;
  // Story selection props
  currentStory?: StoryInfo | null;
  onStorySelect?: (story: StoryInfo | null) => void;
  // Render state from centralized hook (preferred source of truth)
  renderState?: ChapterRenderState;
}

export const TopBar: React.FC<TopBarProps> = ({
  config, chapter, filePath, chapterList, hasChapterAudio,
  selectedCharacter, onChapterSelect, onCharacterSelect, onSave, onRenderComplete,
  hasUnsavedChanges, editorMode, onToggleEditor, onToggleCharacterVoices,
  alertHistory = [], onRemoveAlertHistoryItem, onClearAlertHistory,
  currentStory, onStorySelect, renderState
}) => {
  const [isSaving, setIsSaving] = useState(false);
  const [isRendering, setIsRendering] = useState(false);
  const [isPlayingAudio, setIsPlayingAudio] = useState(false);
  const [showAlertHistory, setShowAlertHistory] = useState(false);

  // Track which chapter is currently being rendered to prevent duplicate renders
  const currentRenderChapterRef = React.useRef<string | null>(null);

  // Derive render status directly from the centralized renderState prop.
  // This removes the duplicate local state that could drift out of sync.
  const needsRender = renderState?.needs_render ?? renderState?.needsRender ?? false;
  const staleCount = renderState?.stale_count ?? renderState?.staleCount ?? 0;
  const xmlChanged = renderState?.xml_changed ?? renderState?.xmlChanged ?? false;
  const hasTimestampStale =
    renderState?.has_timestamp_stale ??
    renderState?.hasTimestampStale ??
    false;

  const chapterReason = renderState?.chapter?.reason ?? renderState?.chapterReason ?? 'good';

  debugLog.info('TopBar:renderState', 'Derived render state from centralized prop', {
    needsRender,
    staleCount,
    hasTimestampStale,
    chapterReason
  });

  const alertBadgeCount = alertHistory.length;
  const recentAlertHistory = useMemo(() => [...alertHistory].reverse(), [alertHistory]);

  const alertBadgeColor = useMemo(() => {
    const hasError = alertHistory.some((alert) => {
      const message = alert.message.toLowerCase();
      return alert.type === 'error' || message.includes('exception');
    });
    if (hasError) return '#f44336';

    const hasWarning = alertHistory.some((alert) => alert.type === 'warning');
    if (hasWarning) return '#ffeb3b';

    return '#2196F3';
  }, [alertHistory]);

  const alertBadgeTextColor = alertBadgeColor === '#ffeb3b' ? '#222' : 'white';

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

  const getAlertColor = (type: AlertHistoryItem['type']) => {
    switch (type) {
      case 'success': return '#4CAF50';
      case 'warning': return '#ff9800';
      case 'error': return '#f44336';
      default: return '#2196F3';
    }
  };

  const formatAlertTime = (timestamp: Date) => {
    try {
      return new Date(timestamp).toLocaleTimeString();
    } catch {
      return '';
    }
  };

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

    // Prevent concurrent renders of the same chapter
    if (isRendering) {
      // Cancel operation
      await PythonBridgeService.cancelAudio(chapterName);
      setIsRendering(false);
      currentRenderChapterRef.current = null;
      return;
    }

    // Check if we're already rendering this specific chapter
    if (currentRenderChapterRef.current === chapterName) {
      debugLog.warn('TopBar:handleRenderChapter', 'Render already in progress for this chapter, skipping', { chapterName });
      return;
    }

    setIsRendering(true);
    currentRenderChapterRef.current = chapterName;

    try {
      if (hasUnsavedChanges && onSave) {
        console.log(`[TopBar] Auto-saving unsaved changes before rendering...`);
        await handleSave();
      }

      console.log(`[TopBar] Rendering chapter: ${chapterName}`);

      if (typeof window !== 'undefined' && window.api && window.api.runPythonScript) {
        const storyDir = currentStory?.directory_name || 'Story-Default';
        const ttsServiceUrl = 'ws://localhost:8765';
        const renderStoryDir = currentStory?.directory_name || 'Story-Default';

        // Get the list of dialogs that need rendering from renderState
        // These are dialogs with content changes (hash mismatch) or missing clips
        const dialogsToRender = renderState?.dialogs?.needs_render ||
                                renderState?.needsRenderDialogs ||
                                renderState?.stale_dialogs ||
                                renderState?.staleDialogs ||
                                [];

        // Filter to only content-stale dialogs (not just timestamp-stale)
        // Timestamp-stale dialogs don't need re-rendering, just timestamp update
        const timestampStaleDialogs = renderState?.dialogs?.timestamp_stale ||
                                     renderState?.timestampStaleDialogs ||
                                     [];

        // Only render dialogs that are content-stale or missing
        const contentStaleDialogs = dialogsToRender.filter((id: string) => !timestampStaleDialogs.includes(id));

        debugLog.info('TopBar:handleRenderChapter', 'Starting selective render', {
          totalStale: dialogsToRender.length,
          contentStale: contentStaleDialogs.length,
          timestampStale: timestampStaleDialogs.length,
          chapterName
        });

        // Step 1: Render each content-stale dialog individually
        for (const dialogId of contentStaleDialogs) {
          // Parse dialogId format: "section_dlgseq" e.g., "002_003"
          const [sectionNum, dlgseqNum] = dialogId.split('_');

          debugLog.info('TopBar:handleRenderChapter', 'Rendering individual dialog', {
            dialogId,
            sectionNum,
            dlgseqNum,
            chapterName
          });

          await window.api.runPythonScript('src/scripts/chapter_xml_to_audio.py', [
            `${storyDir}/story-xml/${chapterName}`,
            `--section`, sectionNum,
            `--dlgseq`, dlgseqNum,
            `--tts-service`, ttsServiceUrl
          ]);
        }

        // Step 2: Call with --create-missing-clips to stitch all clips together
        // This creates the final chapter audio file without re-rendering individual dialogs
        debugLog.info('TopBar:handleRenderChapter', 'Stitching chapter audio with --create-missing-clips', {
          chapterName
        });

        await window.api.runPythonScript('src/scripts/chapter_xml_to_audio.py', [
          `${storyDir}/story-xml/${chapterName}`,
          `--create-missing-clips`,
          `--tts-service`, ttsServiceUrl
        ]);

        // Step 3: Update .chapter_rendered.json with actual file timestamps
        // This updates timestamps based on the actual audio clip files and chapter audio file
        await PythonBridgeService.updateChapterXmlHash(chapterName, renderStoryDir);
        debugLog.info('TopBar:handleRenderChapter', 'Updated render state with file timestamps');

        // Step 4: Notify parent to refresh centralized render state from disk.
        // The parent will re-run checkRenderState and pass the updated renderState
        // prop back down, which TopBar will then render directly.
        if (onRenderComplete) {
          await onRenderComplete();
        }
      } else {
        console.warn("API not available for rendering");
      }
    } catch (error) {
      console.error("[TopBar] Render chapter failed or was cancelled:", error);
    } finally {
      setIsRendering(false);
      currentRenderChapterRef.current = null;
    }
  };

  const handlePlayChapter = async () => {
    const chapterName = filePath.split('/').pop()?.replace('.md', '.xml') || 'Unknown.xml';
    const logId = 'TopBar:handlePlayChapter';

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
         const storyDir = currentStory?.directory_name || 'Story-Default';
         const fullPath = `Stories/${storyDir}/story-audio/${stem}.wav`;
         debugLog.info(logId, 'Attempting chapter playback', { chapterName, stem, storyDir, fullPath });
         await window.api.playSoundFile(fullPath);
         debugLog.info(logId, 'Chapter playback completed', { chapterName, fullPath });
      } else {
         debugLog.warn(logId, 'playSoundFile API unavailable', { chapterName });
      }
    } catch (error) {
      debugLog.exception(logId, 'Play chapter failed', error, { chapterName, filePath, currentStory: currentStory?.directory_name });
      console.error("[TopBar] Play chapter failed or was cancelled:", error);
    } finally {
      setIsPlayingAudio(false);
    }
  };

  return (
    <div className="top-bar" style={{ display: 'flex', alignItems: 'center', gap: '16px', padding: '8px', borderBottom: '1px solid #ccc' }}>
      {/* Story Selection Dropdown */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
        <strong>Current Story:</strong>
        <StoryDropdown
          onStorySelect={onStorySelect || (() => {})}
          selectedStory={currentStory}
        />
      </div>

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
        {onToggleCharacterVoices && (
          <button
            data-testid="toggle-character-voices"
            onClick={onToggleCharacterVoices}
            style={{
              marginLeft: '8px',
              padding: '4px 12px',
              backgroundColor: '#e0e0e0',
              color: '#333',
              border: '1px solid #888',
              borderRadius: '4px',
              cursor: 'pointer',
              fontSize: '0.9em',
              fontWeight: 'bold'
            }}
            title="Open Character Voices"
            aria-label="Toggle character voices dialog"
          >
            🎭 Characters
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

      <div style={{ marginLeft: 'auto', display: 'flex', gap: '8px', alignItems: 'center', position: 'relative' }}>
        <button
          onClick={() => setShowAlertHistory((prev) => !prev)}
          style={{
            position: 'relative',
            padding: '6px 10px',
            backgroundColor: showAlertHistory ? '#333' : '#f5f5f5',
            color: showAlertHistory ? 'white' : '#333',
            border: '1px solid #888',
            borderRadius: '4px',
            cursor: 'pointer',
            fontSize: '1rem',
            lineHeight: 1,
          }}
          title="Show alert history"
          aria-label="Show alert history"
        >
          🔔
          {alertBadgeCount > 0 && (
            <span style={{
              position: 'absolute',
              top: '-6px',
              right: '-6px',
              minWidth: '18px',
              height: '18px',
              padding: '0 4px',
              borderRadius: '999px',
              backgroundColor: alertBadgeColor,
              color: alertBadgeTextColor,
              fontSize: '0.72rem',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontWeight: 'bold',
            }}>
              {alertBadgeCount > 99 ? '99+' : alertBadgeCount}
            </span>
          )}
        </button>

        {showAlertHistory && (
          <div style={{
            position: 'absolute',
            top: 'calc(100% + 8px)',
            right: 0,
            width: '420px',
            maxHeight: '360px',
            backgroundColor: '#1e1e1e',
            color: '#fff',
            border: '1px solid #555',
            borderRadius: '8px',
            boxShadow: '0 10px 30px rgba(0,0,0,0.35)',
            zIndex: 1000,
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden',
          }}>
            <div style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              padding: '10px 12px',
              borderBottom: '1px solid #444',
            }}>
              <strong>Alert History</strong>
              <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                <span style={{ color: '#bbb', fontSize: '0.8rem' }}>{alertBadgeCount} total</span>
                <button
                  onClick={() => onClearAlertHistory?.()}
                  disabled={alertBadgeCount === 0}
                  style={{
                    padding: '4px 8px',
                    backgroundColor: alertBadgeCount === 0 ? '#555' : '#f44336',
                    color: 'white',
                    border: 'none',
                    borderRadius: '4px',
                    cursor: alertBadgeCount === 0 ? 'default' : 'pointer',
                    opacity: alertBadgeCount === 0 ? 0.6 : 1,
                  }}
                >
                  Clear All
                </button>
              </div>
            </div>

            <div style={{ overflowY: 'auto', maxHeight: '300px', padding: '8px' }}>
              {recentAlertHistory.length === 0 ? (
                <div style={{ padding: '16px', color: '#bbb', textAlign: 'center' }}>
                  No alerts yet.
                </div>
              ) : (
                recentAlertHistory.map((alert) => (
                  <div
                    key={alert.id}
                    style={{
                      display: 'flex',
                      gap: '10px',
                      alignItems: 'flex-start',
                      padding: '10px',
                      borderBottom: '1px solid #333',
                    }}
                  >
                    <span style={{
                      width: '10px',
                      height: '10px',
                      marginTop: '5px',
                      borderRadius: '50%',
                      flexShrink: 0,
                      backgroundColor: getAlertColor(alert.type),
                    }} />
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: '0.92rem', wordBreak: 'break-word' }}>{alert.message}</div>
                      <div style={{ marginTop: '4px', fontSize: '0.76rem', color: '#aaa' }}>
                        {formatAlertTime(alert.timestamp)} • {alert.source}
                      </div>
                    </div>
                    <button
                      onClick={() => onRemoveAlertHistoryItem?.(alert.id)}
                      style={{
                        background: 'transparent',
                        color: '#bbb',
                        border: 'none',
                        cursor: 'pointer',
                        fontSize: '1rem',
                        lineHeight: 1,
                      }}
                      title="Remove alert"
                      aria-label="Remove alert"
                    >
                      ×
                    </button>
                  </div>
                ))
              )}
            </div>
          </div>
        )}
        <button
          onClick={handleRenderChapter}
          style={{
            padding: '4px 16px',
            backgroundColor: isRendering
              ? '#f44336'
              : needsRender
                ? '#ff9800'  // Yellow: any staleness (timestamp, content, or missing clips)
                : '#4CAF50', // Green: fully in sync
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            opacity: 1
          }}
          title={
            isRendering
              ? "Stop rendering"
              : needsRender
                ? `Chapter needs render - ${staleCount} dialogs affected (${hasTimestampStale ? 'timestamp issues' : xmlChanged ? 'XML changed' : 'stale content'})`
                : "Chapter is up to date (timestamps and hashes in sync)"
          }
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
