import React, { useState } from 'react';
import type { DialogElement } from '../models/types';
import { getColorForCharacter } from '../utils/colors';

import { PythonBridgeService } from '../services/pythonBridge';

interface DialogBarProps {
  dialog: DialogElement;
  displayId?: string;
  chapterFileName?: string; // Need this for chapter_xml_to_audio.py
  isFilteredOut?: boolean;
  hasAudioClip?: boolean;
  isRenderCooldown?: boolean;
  onUpdateDialog: (id: string, updatedDialog: DialogElement) => void;
  onRefreshClips?: () => void;
  triggerRenderCooldown?: () => void;
}

export const DialogBar: React.FC<DialogBarProps> = ({ 
  dialog, displayId, chapterFileName, isFilteredOut, hasAudioClip, 
  isRenderCooldown, onUpdateDialog, onRefreshClips, triggerRenderCooldown 
}) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const [showContextMenu, setShowContextMenu] = useState(false);
  const [contextMenuPos, setContextMenuPos] = useState({ x: 0, y: 0 });
  const [editingAttr, setEditingAttr] = useState<string | null>(null);
  const [attrEditValue, setAttrEditValue] = useState<string>('');
  const [isGeneratingAudio, setIsGeneratingAudio] = useState(false);
  const [isPlayingAudio, setIsPlayingAudio] = useState(false);

  const bgColor = getColorForCharacter(dialog.character, parseInt(dialog.id) || 0);

  const handleContextMenu = (e: React.MouseEvent) => {
    e.preventDefault();
    setShowContextMenu(true);
    setContextMenuPos({ x: e.pageX, y: e.pageY });
  };

  const closeContextMenu = () => {
    setShowContextMenu(false);
  };

  const handleTextChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    // Stop propagation so it doesn't trigger the expand/collapse from a parent
    e.stopPropagation();
    onUpdateDialog(dialog.id, { ...dialog, text: e.target.value });
  };

  const handleAttrClick = (key: string, value: string) => {
    setEditingAttr(key);
    setAttrEditValue(value);
  };

  const handleAttrSave = () => {
    if (editingAttr) {
      onUpdateDialog(dialog.id, {
        ...dialog,
        attributes: { ...dialog.attributes, [editingAttr]: attrEditValue }
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
              style={{ width: '80px', color: '#000' }}
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
        <span style={{ marginRight: '8px', opacity: 0.6 }}>#{displayId || dialog.id}</span>
        ... {dialog.character} ...
      </div>
    );
  }

  return (
    <div 
      className="dialog-bar-container" 
      style={{ marginBottom: '10px', position: 'relative' }}
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
          <span style={{ marginRight: '10px', opacity: 0.8, fontSize: '0.9em' }}>#{displayId || dialog.id}</span>
          
          {/* Record / Generate Button */}
          <button 
            onClick={async (e) => { 
              e.stopPropagation(); 
              const chapterName = chapterFileName || 'Unknown.xml';
              
              if (isGeneratingAudio) {
                  // Attempt to cancel
                  await PythonBridgeService.cancelAudio(chapterName);
                  setIsGeneratingAudio(false);
                  if (triggerRenderCooldown) triggerRenderCooldown();
                  return;
              }
              
              if (isRenderCooldown) return;
              
              const sectionNum = dialog.sectionId || '1';
              const dlgseq = dialog.id.replace('dialog-', '');
              
              setIsGeneratingAudio(true);
              try {
                  // Pass true to skipPlay, we only want to generate
                  await PythonBridgeService.playAudio(chapterName, sectionNum, dlgseq, undefined, true); 
                  if (onRefreshClips) onRefreshClips();
              } finally {
                  setIsGeneratingAudio(false);
              }
            }}
            disabled={!isGeneratingAudio && isRenderCooldown}
            style={{ 
              background: isRenderCooldown ? '#f44336' : (hasAudioClip ? '#4CAF50' : '#888'), 
              border: '2px solid rgba(255,255,255,0.2)', 
              borderRadius: '50%',
              width: '24px',
              height: '24px',
              color: '#fff', 
              cursor: (!isGeneratingAudio && isRenderCooldown) ? 'not-allowed' : 'pointer', 
              marginRight: '8px',
              padding: '0',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              opacity: (!isGeneratingAudio && isRenderCooldown) ? 0.7 : (isGeneratingAudio ? 0.8 : 1.0),
              boxShadow: (hasAudioClip && !isRenderCooldown) ? '0px 0px 5px rgba(76,175,80,0.8)' : 'none'
            }}
            title={isGeneratingAudio ? "Stop Generating Audio..." : isRenderCooldown ? "Cooling down CUDA..." : (hasAudioClip ? "Re-render Audio" : "Render Audio")}
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
                const chapterName = chapterFileName || 'Unknown.xml';
                
                if (isPlayingAudio) {
                    await PythonBridgeService.cancelAudio(chapterName);
                    setIsPlayingAudio(false);
                    return;
                }
                
                setIsPlayingAudio(true);
                try {
                    // Try to guess the wav file format based on the standard python output
                    // e.g. chapter_001_001_001_narrator.wav
                    // Or we can let pythonBridge have a direct play existing audio function.
                    const sectionNum = (dialog.sectionId || '1').padStart(3, '0');
                    const dlgseq = dialog.id.replace('dialog-', '').padStart(3, '0');
                    const character = dialog.character === 'Narrator' ? 'narrator' : dialog.character;
                    const chapterStem = chapterName.replace('.xml', '');
                    const chapMatch = chapterName.match(/(\d+)/);
                    const chapNum = chapMatch ? chapMatch[1].padStart(3, '0') : '000';
                    
                    // Possible filename format based on chapter_xml_to_audio.py:
                    // chapter_{chapter_num}_{section_num}_{dlgseq}_{speaker}.wav
                    const wavName = `chapter_${chapNum}_${sectionNum}_${dlgseq}_${character}.wav`;
                    const fullPath = `Story-Entanglement/story-audio/clips/${chapterStem}/${wavName}`;
                    
                    if (window.api && window.api.playSoundFile) {
                        await window.api.playSoundFile(fullPath);
                    } else {
                        console.log("Mock Play", fullPath);
                        await new Promise(r => setTimeout(r, 1000));
                    }
                } finally {
                    setIsPlayingAudio(false);
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
                }}></span>
              ) : '▶'}
            </button>
          )}

          <style>{`
            @keyframes spin {
              to { transform: rotate(360deg); }
            }
          `}</style>
          {dialog.character}
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
                onUpdateDialog(dialog.id, {
                  ...dialog,
                  attributes: { ...dialog.attributes, [newAttr]: '' }
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
