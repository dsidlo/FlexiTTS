import React, { useEffect, useState } from 'react';
import type { DialogElement, DialogValidationIssue } from '../models/types';
import { getColorForCharacter } from '../utils/colors';
import { useAudioPlayer } from '../hooks/useAudioPlayer';

import { PythonBridgeService } from '../services/pythonBridge';

interface DialogBarProps {
  dialog: DialogElement;
  displayId?: string;
  chapterFileName?: string; // Need this for chapter_xml_to_audio.py
  storyDirectory?: string; // Story directory for path construction (e.g., 'Story-Entanglement')
  isFilteredOut?: boolean;
  hasAudioClip?: boolean;
  availableCharacters?: string[];
  onSaveRequest?: () => Promise<void>;
  onUpdateDialog: (dlgseq: string, sectionId: string, updatedDialog: DialogElement) => Promise<void>;
  onRefreshClips?: () => void;
}

export const DialogBar: React.FC<DialogBarProps> = ({
  dialog, displayId, chapterFileName, storyDirectory, isFilteredOut, hasAudioClip, availableCharacters = [],
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

  // Client-side audio player hook
  const { isPlaying: isPlayingAudio, play: playAudio, stop: stopAudio } = useAudioPlayer();

  const bgColor = getColorForCharacter(dialog.character, parseInt(dialog.dlgseq) || 0);

  const handleContextMenu = (e: React.MouseEvent) => {
    e.preventDefault();
    setShowContextMenu(true);
    setContextMenuPos({ x: e.pageX, y: e.pageY });
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

  const handleTextChange = async (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    // Stop propagation so it doesn't trigger the expand/collapse from a parent
    e.stopPropagation();
    await onUpdateDialog(dialog.dlgseq, dialog.sectionId || '0', {
      ...dialog,
      text: e.target.value,
      attributes: { ...dialog.attributes, dlgseq: dialog.dlgseq, section_seq: dialog.sectionId || '0' }
    });
  };

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
        onClick={(e) => {
          e.stopPropagation();
          setIsExpanded(!isExpanded);
        }}
        onContextMenu={handleContextMenu}
      >
        <div className="dialog-character" style={{ display: 'flex', alignItems: 'center' }}>
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
                  // Pass playAudio as the onPlay callback to use useAudioPlayer state management
                  await PythonBridgeService.playAudio(chapterName, sectionNum, dlgseq, undefined, false, playAudio);
                  if (onRefreshClips) onRefreshClips();
              } finally {
                  setIsGeneratingAudio(false);
              }
            }}
            style={{
              background: hasAudioClip ? '#4CAF50' : '#888',
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
              boxShadow: hasAudioClip ? '0px 0px 5px rgba(76,175,80,0.8)' : 'none'
            }}
            title={isGeneratingAudio ? "Stop Generating Audio..." : (hasAudioClip ? "Re-render Audio" : "Render Audio")}
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

          {/* Play Button */}
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
            value={dialog.text || ''}
            onChange={handleTextChange}
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
          {Object.keys(dialog.attributes).map(key => (
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
