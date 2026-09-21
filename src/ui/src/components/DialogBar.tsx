import React, { useState } from 'react';
import type { DialogElement, DialogValidationIssue } from '../models/types';
import { getColorForCharacter } from '../utils/colors';
import { useAudioPlayer } from '../hooks/useAudioPlayer';
import { debugLog } from '../utils/debugLogger';
import { md5 } from '../utils/md5';
import { normalizeDialogText } from '../utils/dialogHash';

import { PythonBridgeService } from '../services/pythonBridge';

interface DialogBarProps {
  dialog: DialogElement;
  displayId?: string;
  chapterFileName?: string; // Need this for chapter_xml_to_audio.py
  storyDirectory?: string; // Story directory for path construction (e.g., 'Story-Entanglement')
  isFilteredOut?: boolean;
  hasAudioClip?: boolean;
  isStaleClip?: boolean;
  isTimestampStale?: boolean;  // New: specifically for timestamp out of sync
  availableCharacters?: string[];
  availableEmotions?: string[]; // Emotions available for current character
  /** Phase 10: whether this line is part of the current multi-selection. */
  isSelected?: boolean;
  /** Phase 10: toggle this line's membership in the multi-selection (Ctrl+Click). */
  onToggleSelect?: (dlgseq: string, sectionId: string, _index: number | undefined, additive: boolean) => void;
  /** Whether this line is the currently opened (last-interacted) dialog. */
  isCurrentDialog?: boolean;
  /** Notify the app that this line was opened (plain click); the app marks it current. */
  onOpened?: (dlgseq: string, sectionId: string, _index: number | undefined) => void;
  /** Phase 10: open the character picker to assign this line (or the whole selection). */
  onAssignCharacter?: (dlgseq: string, sectionId: string, _index: number | undefined) => void;
  onSaveRequest?: () => Promise<void>;
  onUpdateDialog: (dlgseq: string, sectionId: string, updatedDialog: DialogElement) => Promise<void>;
  onRefreshClips?: () => void;
}

export const DialogBar: React.FC<DialogBarProps> = ({
  dialog, displayId, chapterFileName, storyDirectory, isFilteredOut, hasAudioClip, isStaleClip = false, isTimestampStale = false, availableCharacters = [], availableEmotions = [], isSelected = false, isCurrentDialog = false, onToggleSelect, onOpened, onAssignCharacter,
  onSaveRequest, onUpdateDialog, onRefreshClips
}) => {
  const validationIssues = dialog.validationIssues || [];
  const hasValidationIssues = validationIssues.length > 0;
  const [showValidationDialog, setShowValidationDialog] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false);
  const [showContextMenu, setShowContextMenu] = useState(false);
  const [contextMenuPos, setContextMenuPos] = useState({ x: 0, y: 0 });
  const [editingAttr, setEditingAttr] = useState<string | null>(null);
  const [attrEditValue, setAttrEditValue] = useState<string>('');
  const [isGeneratingAudio, setIsGeneratingAudio] = useState(false);
  const [isEditingCharacter, setIsEditingCharacter] = useState(false);
  const [isEditingEmotion, setIsEditingEmotion] = useState(false);
  
  // Get current emotion from attributes
  const currentEmotion = dialog.attributes?.emotion || 'Neutral';
  const currentEmotionLower = currentEmotion.toLowerCase();
  const availableEmotionsLower = availableEmotions.map(e => e.toLowerCase());
  // Check for emotion issues from validation or from availableEmotions mismatch (case-insensitive)
  const emotionValidationIssue = validationIssues.find(issue => issue.code === 'invalid-emotion');
  const hasEmotionIssues = emotionValidationIssue !== undefined || (availableEmotions.length > 0 && !availableEmotionsLower.includes(currentEmotionLower));
  
  // Local state for text editing to prevent cursor jumping
  // We use local state during editing and only sync to parent on blur
  const [localText, setLocalText] = useState(dialog.text || '');
  const textareaRef = React.useRef<HTMLTextAreaElement>(null);
  const cursorPositionRef = React.useRef<number>(0);

  // Content staleness is computed client-side against the render signature
  // stored on the dialog (renderHash / render_hash attr). This lets the render
  // button flip yellow mid-edit and snap back to green on undo, without any
  // disk or Python round-trip. A short debounce avoids recomputing per key.
  const isNarration =
    dialog.character === 'Narrator' || !dialog.attributes?.character;
  const dialogTag: 'dialog' | 'narration' = isNarration ? 'narration' : 'dialog';
  const storedRenderHash =
    dialog.renderHash ||
    (typeof dialog.attributes?.render_hash === 'string' ? dialog.attributes.render_hash : undefined);

  const isContentDirty = React.useCallback(
    (text: string): boolean => {
      if (!storedRenderHash) return false; // never rendered -> not stale, just absent
      const normalized = normalizeDialogText(
        { ...dialog, text },
        dialogTag
      );
      return md5(normalized) !== storedRenderHash;
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [dialog, dialogTag, storedRenderHash]
  );

  const [isTextStale, setIsTextStale] = useState<boolean>(() => isContentDirty(localText));

  // Keep stale flag in sync when the underlying render signature changes
  // (e.g. after a render updates dialog.renderHash) or the text prop changes.
  React.useEffect(() => {
    setIsTextStale(isContentDirty(localText));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [storedRenderHash, dialog.text]);

  // Debounced recompute while the user types.
  React.useEffect(() => {
    const handle = setTimeout(() => {
      setIsTextStale(isContentDirty(localText));
    }, 300);
    return () => clearTimeout(handle);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [localText]);

  // Sync local text when dialog prop changes (e.g., from external updates)
  // but preserve cursor position if we're currently editing
  React.useEffect(() => {
    const newText = dialog.text || '';
    // Only update if the text actually changed and we're not currently focused
    if (newText !== localText && document.activeElement !== textareaRef.current) {
      setLocalText(newText);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dialog.text]);

  // Client-side audio player hook
  const { isPlaying: isPlayingAudio, play: playAudio, stop: stopAudio } = useAudioPlayer();

  const bgColor = getColorForCharacter(dialog.character);

  const isContentStaleNow = isStaleClip || isTextStale;

  // A dialog counts as "has been rendered" if a render signature exists in
  // memory (render_hash / dialog.renderHash) or a clip was discovered on disk.
  // The in-memory signature is authoritative after a render because the merged
  // hash can arrive before the clips listing refreshes; keying color only off
  // hasAudioClip would show a freshly rendered dialog as grey (never rendered).
  const hasRenderSignature = !!storedRenderHash;
  const hasRendered = hasAudioClip || hasRenderSignature;

  // Precedence: timestamp (blue) > edited text (yellow) > backend content stale
  // (orange) > in-sync (green) > never rendered (grey).
  const buttonColor = !hasRendered
    ? '#888'
    : isTimestampStale
      ? '#2196F3'
      : isTextStale
        ? '#ffc107'
        : isStaleClip
          ? '#ff9800'
          : '#4CAF50';

  // Log button state for debugging timestamp/color logic
  if (isTimestampStale || isContentStaleNow) {
    debugLog.info('DialogBar:render', 'Dialog button state', {
      dialogId: displayId || dialog.dlgseq,
      character: dialog.character,
      hasAudioClip,
      hasRenderSignature,
      hasRendered,
      isStaleClip,
      isTextStale,
      isTimestampStale,
      color: buttonColor
    });
  }

  const handleContextMenu = (e: React.MouseEvent) => {
    e.preventDefault();
    setShowContextMenu(true);
    setContextMenuPos({ x: e.pageX, y: e.pageY });
  };

  // Plain click: open (expand) this line and mark it as the currently
  // selected dialog. Ctrl/Cmd+Click adds/removes from the multi-selection.
  const handleHeaderClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    if ((e.ctrlKey || e.metaKey) && onToggleSelect) {
      onToggleSelect(dialog.dlgseq, dialog.sectionId || '0', dialog._index, e.shiftKey);
      return;
    }
    onOpened?.(dialog.dlgseq, dialog.sectionId || '0', dialog._index);
    setIsExpanded(!isExpanded);
  };


  const closeContextMenu = () => {
    setShowContextMenu(false);
  };

  const openValidationDialog = (e: React.MouseEvent) => {
    e.stopPropagation();
    setShowValidationDialog(true);
  };

  const closeValidationDialog = (e?: React.MouseEvent) => {
    e?.stopPropagation();
    setShowValidationDialog(false);
  };

  const getValidationTitle = (issue: DialogValidationIssue) => {
    switch (issue.code) {
      case 'missing-character':
        return 'Character Missing';
      case 'invalid-custom-voice':
        return 'Custom Voice Invalid';
      case 'invalid-voice-sample':
        return 'Voice Sample Invalid';
      case 'invalid-dialog-effects':
        return 'Dialog Effects Invalid';
      case 'invalid-emotion':
        return 'Emotion Invalid';
      default:
        return 'Validation Issue';
    }
  };

  const handleCharacterChange = async (newCharacter: string) => {
    await onUpdateDialog(dialog.dlgseq, dialog.sectionId || '0', {
      ...dialog,
      character: newCharacter,
      attributes: { ...dialog.attributes, character: newCharacter, dlgseq: dialog.dlgseq, section_seq: dialog.sectionId || '0' }
    });
    setIsEditingCharacter(false);
  };

  const handleEmotionChange = async (newEmotion: string) => {
    await onUpdateDialog(dialog.dlgseq, dialog.sectionId || '0', {
      ...dialog,
      attributes: { ...dialog.attributes, emotion: newEmotion, dlgseq: dialog.dlgseq, section_seq: dialog.sectionId || '0' }
    });
    setIsEditingEmotion(false);
  };

  const handleTextChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    // Store cursor position before React state update
    if (textareaRef.current) {
      cursorPositionRef.current = textareaRef.current.selectionStart;
    }
    // Update local state only - don't call parent yet
    setLocalText(e.target.value);
  };

  const handleTextBlur = async () => {
    // Immediate (non-debounced) staleness recompute so the button never lags by
    // the 300ms window when the user tabs/clicks away.
    setIsTextStale(isContentDirty(localText));
    // Only sync to parent if text actually changed
    if (localText !== (dialog.text || '')) {
      await onUpdateDialog(dialog.dlgseq, dialog.sectionId || '0', {
        ...dialog,
        text: localText,
        attributes: { ...dialog.attributes, dlgseq: dialog.dlgseq, section_seq: dialog.sectionId || '0' }
      });
    }
  };

  // Restore cursor position after React re-render
  React.useEffect(() => {
    if (textareaRef.current && document.activeElement === textareaRef.current) {
      textareaRef.current.setSelectionRange(cursorPositionRef.current, cursorPositionRef.current);
    }
  });

  const handleAttrClick = (key: string, value: string) => {
    setEditingAttr(key);
    setAttrEditValue(value);
  };

  const handleAttrSave = async () => {
    if (editingAttr) {
      await onUpdateDialog(dialog.dlgseq, dialog.sectionId || '0', {
        ...dialog,
        attributes: { ...dialog.attributes, [editingAttr]: attrEditValue, dlgseq: dialog.dlgseq, section_seq: dialog.sectionId || '0' }
      });
      setEditingAttr(null);
    }
  };

  const renderAttributes = () => {
    return Object.entries(dialog.attributes).map(([key, value]) => {
      // Don't show base attributes as badges
      if (key === 'character' || key === 'id' || key === 'dlgseq' || key === 'section_seq') return null;
      // Render bookkeeping (render_hash / rendered_at) is internal state used
      // by the staleness indicator; it is not meaningful to the user, so it is
      // excluded from the badge row. It stays in attributes and remains
      // editable through the right-click Edit Attributes menu.
      if (key === 'render_hash' || key === 'rendered_at') return null;

      return (
        <span key={key} className="attribute-badge" style={{ marginRight: '8px', fontSize: '0.8em', backgroundColor: 'rgba(0,0,0,0.1)', padding: '2px 6px', borderRadius: '4px' }}>
          <strong>{key}:</strong>{' '}
          {editingAttr === key ? (
            <input
              autoFocus
              type="text"
              value={attrEditValue}
              onChange={(e) => setAttrEditValue(e.target.value)}
              onBlur={handleAttrSave}
              onKeyDown={(e) => e.key === 'Enter' && handleAttrSave()}
              style={{
                width: '100px',
                color: '#fff',
                backgroundColor: 'rgba(0,0,0,0.5)',
                border: '1px solid #fff',
                borderRadius: '3px',
                padding: '2px 4px'
              }}
              onClick={(e) => e.stopPropagation()}
            />
          ) : (
            <span onClick={(e) => { e.stopPropagation(); handleAttrClick(key, value); }} style={{ cursor: 'pointer', textDecoration: 'underline' }}>
              {value}
            </span>
          )}
        </span>
      );
    });
  };

  if (isFilteredOut) {
    return (
      <div
        style={{
          marginBottom: '5px',
          padding: '4px 10px',
          fontSize: '0.8em',
          color: '#888',
          backgroundColor: 'rgba(0,0,0,0.03)',
          borderRadius: '4px',
          fontStyle: 'italic',
          display: 'flex',
          alignItems: 'center'
        }}
      >
        <span style={{ marginRight: '8px', opacity: 0.6 }}>#{displayId || dialog.dlgseq}</span>
        ... {dialog.character} ...
      </div>
    );
  }

  return (
    <div
      className="dialog-bar-container"
      style={{
        marginBottom: '10px',
        position: 'relative',
        maxWidth: '800px', // Restrict the maximum width of the dialogs to prevent them from stretching too wide
        margin: '0 auto 10px auto' // Center them if the container is wider than 800px
      }}
      onMouseLeave={closeContextMenu}
    >
      <div
        className="dialog-bar-header"
        style={{
          backgroundColor: bgColor,
          padding: '10px',
          borderRadius: isExpanded ? '4px 4px 0 0' : '4px',
          cursor: 'pointer',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          color: '#fff',
          fontWeight: 'bold',
          textShadow: '1px 1px 2px rgba(0,0,0,0.5)'
        }}
        onClick={handleHeaderClick}
        onContextMenu={handleContextMenu}
        data-selected={isSelected || undefined}
      >
        <div className="dialog-character" style={{ display: 'flex', alignItems: 'center' }}>
          {isCurrentDialog && (
            <span
              data-testid={`dialog-current-check-${dialog.dlgseq}`}
              aria-label="Currently selected dialog"
              title="Currently selected dialog"
              style={{ marginRight: 8, color: '#7fff9f', fontWeight: 700, fontSize: '1em' }}
            >
              ✓
            </span>
          )}
          <span style={{ marginRight: '10px', opacity: 0.8, fontSize: '0.9em' }}>#{displayId || dialog.dlgseq}</span>
          {hasValidationIssues && (
            <button
              onClick={openValidationDialog}
              onMouseEnter={() => setShowValidationDialog(true)}
              aria-label={`Validation issues for ${dialog.character}`}
              title={validationIssues.map((issue) => issue.message).join('\n')}
              style={{
                marginRight: '8px',
                background: '#d32f2f',
                color: '#fff',
                border: '1px solid rgba(255,255,255,0.4)',
                borderRadius: '50%',
                width: '20px',
                height: '20px',
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontWeight: 700,
                cursor: 'pointer',
                padding: 0,
                lineHeight: 1,
              }}
            >
              !
            </button>
          )}

          {/* Record / Generate Button */}
          <button
            onClick={async (e) => {
              e.stopPropagation();
              const chapterName = chapterFileName?.replace('.md', '.xml') || 'Unknown.xml';

              if (isGeneratingAudio) {
                  // Attempt to cancel
                  await PythonBridgeService.cancelAudio(chapterName);
                  setIsGeneratingAudio(false);
                  return;
              }

              if (onSaveRequest) {
                  await onSaveRequest();
              }

              const sectionNum = dialog.sectionId || '0';
              const dlgseq = dialog.dlgseq;

              setIsGeneratingAudio(true);
              try {
                  // Pass onRefreshClips as onGenerationComplete to update render state
                  // This ensures dialog turns from blue to green after successful re-render
                  const onGenerationComplete = onRefreshClips || undefined;

                  // Pass playAudio as the onPlay callback to use useAudioPlayer state management
                  await PythonBridgeService.playAudio(
                    chapterName,
                    sectionNum,
                    dlgseq,
                    onGenerationComplete,
                    false,
                    playAudio
                  );
              } finally {
                  setIsGeneratingAudio(false);
              }
            }}
            style={{
              background: buttonColor,
              border: '2px solid rgba(255,255,255,0.2)',
              borderRadius: '50%',
              width: '24px',
              height: '24px',
              color: '#fff',
              cursor: 'pointer',
              marginRight: '8px',
              padding: '0',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              opacity: isGeneratingAudio ? 0.8 : 1.0,
              boxShadow: hasRendered && !isContentStaleNow && !isTimestampStale
                ? '0px 0px 5px rgba(76,175,80,0.8)'
                : isTextStale
                  ? '0px 0px 5px rgba(255,193,7,0.8)'
                  : (isStaleClip ? '0px 0px 5px rgba(255,152,0,0.8)' : 'none')
            }}
            title={isGeneratingAudio
              ? "Stop Generating Audio..."
              : !hasRendered
                ? "No clip - Render Audio"
                : isTimestampStale
                  ? "Timestamp out of sync - Re-render to update timestamp"
                  : isTextStale
                    ? "Text edited - Re-render"
                    : isStaleClip
                      ? "Clip stale - Re-render"
                      : "In sync - Re-render Audio"
            }
          >
            {isGeneratingAudio ? (
              <span className="spinner-icon" style={{
                display: 'inline-block',
                width: '0.8em',
                height: '0.8em',
                border: '2px solid rgba(255,255,255,0.3)',
                borderRadius: '50%',
                borderTopColor: '#fff',
                animation: 'spin 1s ease-in-out infinite'
              }}></span>
            ) : (
              <span style={{
                display: 'inline-block',
                width: '10px',
                height: '10px',
                backgroundColor: '#fff',
                borderRadius: '50%'
              }}></span>
            )}
          </button>

          {/* Play Button: only offer playback when a clip file actually exists on
              disk (hasAudioClip). A render signature alone doesn't mean there's
              playable audio yet. */}
          {hasAudioClip && (
            <button
              onClick={async (e) => {
                e.stopPropagation();

                if (isPlayingAudio) {
                    stopAudio();
                    return;
                }

                // Construct the file path
                const chapterName = chapterFileName?.replace('.md', '.xml') || 'Unknown.xml';
                const sectionNum = (dialog.sectionId || '0').padStart(3, '0');
                const dlgseq = dialog.dlgseq.padStart(3, '0');
                const character = dialog.character;
                const chapterStem = chapterName.replace('.xml', '');
                const chapMatch = chapterName.match(/(\d+)/);
                const chapNum = chapMatch ? chapMatch[1].padStart(3, '0') : '000';

                const wavName = `chapter_${chapNum}_${sectionNum}_${dlgseq}_${character}.wav`;
                const storyDir = storyDirectory || 'Story-Default';
                const relativePath = `${storyDir}/story-audio/clips/${chapterStem}/${wavName}`;

                // Read audio file via Electron IPC and play as data URL
                try {
                  const dataUrl = await window.api?.readAudioFile?.(relativePath);
                  if (dataUrl) {
                    await playAudio(dataUrl);
                  } else {
                    console.error('Failed to read audio file: no data returned');
                  }
                } catch (err) {
                  console.error('Failed to play audio:', err);
                }
              }}
              style={{
                background: 'transparent',
                border: 'none',
                color: '#fff',
                cursor: 'pointer',
                marginRight: '8px',
                padding: '0',
                display: 'flex',
                alignItems: 'center',
                opacity: isPlayingAudio ? 0.8 : 0.9,
                fontSize: '1.2em'
              }}
              title={isPlayingAudio ? "Stop playback" : "Play Clip"}
            >
              {isPlayingAudio ? (
                <span style={{
                  display: 'inline-block',
                  width: '10px',
                  height: '10px',
                  backgroundColor: 'rgba(255,100,100,0.9)'
                }}>■</span>
              ) : '▶'}
            </button>
          )}

          <style>{`
            @keyframes spin {
              to { transform: rotate(360deg); }
            }
          `}</style>

          {isEditingCharacter ? (
            <select
              value={dialog.character}
              onChange={(e) => {
                e.stopPropagation();
                handleCharacterChange(e.target.value);
              }}
              onBlur={() => setIsEditingCharacter(false)}
              onClick={(e) => e.stopPropagation()}
              autoFocus
              style={{
                background: 'rgba(255,255,255,0.9)',
                color: '#000',
                border: '1px solid #ccc',
                borderRadius: '4px',
                padding: '2px 8px',
                fontSize: '0.9em',
                cursor: 'pointer'
              }}
            >
              {availableCharacters.map(charName => (
                <option key={charName} value={charName}>
                  {charName}
                </option>
              ))}
              {!availableCharacters.includes(dialog.character) && (
                <option value={dialog.character}>*{dialog.character} (New)</option>
              )}
            </select>
          ) : (
            <span
              onClick={(e) => {
                e.stopPropagation();
                if (availableCharacters.length > 0) {
                  setIsEditingCharacter(true);
                }
              }}
              title={availableCharacters.length > 0 ? (!availableCharacters.includes(dialog.character) ? "Unregistered Character - Click to change" : "Click to change character") : ""}
              style={{
                cursor: availableCharacters.length > 0 ? 'pointer' : 'default',
                padding: '2px 6px',
                borderRadius: '4px',
                backgroundColor: isEditingCharacter ? 'transparent' : (!availableCharacters.includes(dialog.character) ? 'rgba(255,152,0,0.3)' : 'rgba(255,255,255,0.1)'),
                border: !availableCharacters.includes(dialog.character) ? '1px solid rgba(255,152,0,0.8)' : '1px dashed transparent',
                display: 'inline-block',
                fontWeight: !availableCharacters.includes(dialog.character) ? 'bold' : 'normal',
                color: !availableCharacters.includes(dialog.character) ? '#ffb74d' : 'inherit'
              }}
              onMouseEnter={(e) => {
                if (availableCharacters.length > 0) {
                  e.currentTarget.style.border = '1px dashed rgba(255,255,255,0.8)';
                }
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.border = !availableCharacters.includes(dialog.character) ? '1px solid rgba(255,152,0,0.8)' : '1px dashed transparent';
              }}
            >
              {dialog.character}
            </span>
          )}

          {/* Emotion Dropdown */}
          {availableEmotions.length > 0 && (
            <div style={{ marginLeft: '12px', display: 'flex', alignItems: 'center' }}>
              <span style={{ marginRight: '6px', fontSize: '0.85em', opacity: 0.9 }}>Emotion:</span>
              {isEditingEmotion ? (
                <select
                  value={currentEmotion}
                  onChange={(e) => {
                    e.stopPropagation();
                    handleEmotionChange(e.target.value);
                  }}
                  onBlur={() => setIsEditingEmotion(false)}
                  onClick={(e) => e.stopPropagation()}
                  autoFocus
                  style={{
                    background: 'rgba(255,255,255,0.9)',
                    color: '#000',
                    border: hasEmotionIssues ? '2px solid #ff9800' : '1px solid #ccc',
                    borderRadius: '4px',
                    padding: '2px 8px',
                    fontSize: '0.85em',
                    cursor: 'pointer'
                  }}
                >
                  {availableEmotions.map(emotion => (
                    <option key={emotion} value={emotion}>
                      {emotion}
                    </option>
                  ))}
                </select>
              ) : (
                <span
                  onClick={(e) => {
                    e.stopPropagation();
                    setIsEditingEmotion(true);
                  }}
                  title={hasEmotionIssues ? "Unconfigured Emotion - Click to change" : "Click to change emotion"}
                  style={{
                    cursor: 'pointer',
                    padding: '2px 6px',
                    borderRadius: '4px',
                    backgroundColor: hasEmotionIssues ? 'rgba(255,152,0,0.3)' : 'rgba(255,255,255,0.1)',
                    border: hasEmotionIssues ? '2px solid #ff9800' : '1px dashed transparent',
                    display: 'inline-block',
                    fontWeight: hasEmotionIssues ? 'bold' : 'normal',
                    color: hasEmotionIssues ? '#ffb74d' : 'inherit'
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.border = '1px dashed rgba(255,255,255,0.8)';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.border = hasEmotionIssues ? '2px solid #ff9800' : '1px dashed transparent';
                  }}
                >
                  {currentEmotion}
                </span>
              )}
            </div>
          )}
        </div>
        <div className="dialog-attributes-summary" onClick={(e) => e.stopPropagation()}>
          {renderAttributes()}
        </div>
      </div>

      {isExpanded && (
        <div
          className="dialog-bar-content"
          style={{
            border: `2px solid ${bgColor}`,
            borderTop: 'none',
            borderRadius: '0 0 4px 4px',
            padding: '10px',
            backgroundColor: '#ffffff',
            cursor: 'default'
          }}
          onClick={(e) => e.stopPropagation()}
        >
          <textarea
            ref={textareaRef}
            value={localText}
            onChange={handleTextChange}
            onBlur={handleTextBlur}
            onClick={(e) => e.stopPropagation()}
            style={{
              width: '100%',
              minHeight: '80px',
              boxSizing: 'border-box',
              padding: '12px',
              color: '#000000',
              backgroundColor: '#ffffff',
              border: '1px solid #ccc',
              borderRadius: '4px',
              fontSize: '16px',
              fontFamily: 'inherit',
              lineHeight: '1.5'
            }}
          />
        </div>
      )}

      {showValidationDialog && hasValidationIssues && (
        <div
          onClick={(e) => e.stopPropagation()}
          style={{
            position: 'absolute',
            top: '42px',
            left: '12px',
            zIndex: 1100,
            background: '#fff5f5',
            color: '#222',
            border: '1px solid #d32f2f',
            borderRadius: '8px',
            padding: '10px 12px',
            minWidth: '280px',
            boxShadow: '0 4px 14px rgba(0,0,0,0.25)',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <strong style={{ color: '#b71c1c' }}>Validation Issues</strong>
            <button
              onClick={closeValidationDialog}
              style={{ background: 'transparent', border: 'none', cursor: 'pointer', color: '#b71c1c', fontWeight: 700 }}
            >
              ×
            </button>
          </div>
          <ul style={{ margin: 0, paddingLeft: '18px' }}>
            {validationIssues.map((issue, index) => (
              <li key={`${issue.code}-${index}`} style={{ marginBottom: '6px' }}>
                <strong>{getValidationTitle(issue)}:</strong> {issue.message}
              </li>
            ))}
          </ul>
        </div>
      )}

      {showContextMenu && (
        <div
          className="context-menu"
          style={{
            position: 'fixed',
            top: contextMenuPos.y,
            left: contextMenuPos.x,
            backgroundColor: 'white',
            border: '1px solid #ccc',
            boxShadow: '0 2px 5px rgba(0,0,0,0.2)',
            zIndex: 1000,
            padding: '5px 0',
            minWidth: '150px'
          }}
        >
          <div style={{ padding: '5px 10px', fontWeight: 'bold', borderBottom: '1px solid #eee', color: '#333' }}>Edit Attributes</div>
          {/* Phase 10.1/10.2: assign character via picker */}
          {onAssignCharacter && availableCharacters.length > 0 && (
            <div
              className="context-menu-assign"
              style={{ padding: '5px 15px', cursor: 'pointer', color: '#1a4d8f', fontWeight: 600 }}
              onClick={() => {
                closeContextMenu();
                onAssignCharacter(dialog.dlgseq, dialog.sectionId || '0', dialog._index);
              }}
              onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = '#f0f0f0')}
              onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
            >
              Assign Character…
            </div>
          )}
          {Object.keys(dialog.attributes)
            .filter(key => key !== 'render_hash' && key !== 'rendered_at') // internal render bookkeeping
            .map(key => (
              <div
                key={key}
                style={{ padding: '5px 15px', cursor: 'pointer', color: '#333' }}
                onClick={() => {
                  handleAttrClick(key, dialog.attributes[key]);
                  closeContextMenu();
                }}
                onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = '#f0f0f0')}
                onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
              >
                {key}
              </div>
            ))}
          {/* Allow adding new attributes */}
          <div
            style={{ padding: '5px 15px', cursor: 'pointer', fontStyle: 'italic', borderTop: '1px solid #eee', color: '#666' }}
            onClick={() => {
              const newAttr = prompt("New attribute name:");
              if (newAttr && !dialog.attributes[newAttr]) {
                onUpdateDialog(dialog.dlgseq, dialog.sectionId || '0', {
                  ...dialog,
                  attributes: { ...dialog.attributes, [newAttr]: '', dlgseq: dialog.dlgseq, section_seq: dialog.sectionId || '0' }
                });
              }
              closeContextMenu();
            }}
            onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = '#f0f0f0')}
            onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
          >
            + Add Attribute
          </div>
        </div>
      )}
    </div>
  );
};
