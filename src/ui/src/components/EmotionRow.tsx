import React, { useCallback, useState } from 'react';
import { PythonBridgeService } from '../services/pythonBridge';

/**
 * Phase 6.3: EmotionRow - one emotion per row with inline editing.
 * Features: inline edit mode, default star toggle, delete, drag handle
 * (visual only; reorder via up/down buttons for keyboard accessibility).
 */

export interface EmotionRowProps {
  characterId: string;
  emotion: { emotion?: string; name?: string; instruct?: string; 'sox-effects'?: string[] };
  isDefault: boolean;
  storyDir: string;
  onSaved: () => void;
  onError: (message: string) => void;
}

export const EmotionRow: React.FC<EmotionRowProps> = ({
  characterId, emotion, isDefault, storyDir, onSaved, onError,
}) => {
  const emotionName = String(emotion.emotion ?? emotion.name ?? '');
  const [editing, setEditing] = useState(false);
  const [draftName, setDraftName] = useState(emotionName);
  const [draftInstruct, setDraftInstruct] = useState(String(emotion.instruct ?? ''));
  const [busy, setBusy] = useState(false);

  const startEdit = useCallback(() => {
    setDraftName(emotionName);
    setDraftInstruct(String(emotion.instruct ?? ''));
    setEditing(true);
  }, [emotion]);

  const save = useCallback(async () => {
    const trimmed = draftName.trim();
    if (!trimmed) {
      onError('Emotion name cannot be empty.');
      return;
    }
    setBusy(true);
    try {
      await PythonBridgeService.updateEmotion(storyDir, characterId, emotionName, {
        emotion: trimmed,
        instruct: draftInstruct,
      });
      setEditing(false);
      onSaved();
    } catch (e) {
      onError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }, [draftName, draftInstruct, storyDir, characterId, emotionName, onSaved, onError]);

  const remove = useCallback(async () => {
    if (!window.api?.showConfirmDialog) return;
    const res = await window.api.showConfirmDialog(
      'Delete Emotion',
      `Delete emotion '${emotionName}'?`,
      `From character '${characterId}'.`
    );
    if (res !== 1) return;
    setBusy(true);
    try {
      await PythonBridgeService.deleteEmotion(storyDir, characterId, emotionName);
      onSaved();
    } catch (e) {
      onError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }, [emotionName, characterId, storyDir, onSaved, onError]);

  const setDefault = useCallback(async () => {
    setBusy(true);
    try {
      await PythonBridgeService.setDefaultEmotion(storyDir, characterId, emotionName);
      onSaved();
    } catch (e) {
      onError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }, [emotionName, characterId, storyDir, onSaved, onError]);

  if (editing) {
    return (
      <div data-testid={`emotion-edit-${characterId}-${emotionName}`} style={editRowStyle}>
        <input
          data-testid={`emotion-name-input-${characterId}-${emotionName}`}
          value={draftName}
          onChange={(e) => setDraftName(e.target.value)}
          style={inputStyle}
          aria-label="Emotion name"
        />
        <input
          data-testid={`emotion-instruct-input-${characterId}-${emotionName}`}
          value={draftInstruct}
          onChange={(e) => setDraftInstruct(e.target.value)}
          style={{ ...inputStyle, flex: 1 }}
          placeholder="Instruct text…"
          aria-label="Emotion instruct"
        />
        <button style={smallButtonStyle} onClick={() => void save()} disabled={busy} title="Save" aria-label={`Save emotion ${emotionName}`}>✓</button>
        <button style={smallButtonStyle} onClick={() => setEditing(false)} disabled={busy} title="Cancel" aria-label={`Cancel editing emotion ${emotionName}`}>✕</button>
      </div>
    );
  }

  return (
    <div data-testid={`emotion-row-${characterId}-${emotionName}`} style={rowStyle}>
      <span style={{ width: 90, fontWeight: isDefault ? 600 : 400 }}>
        {isDefault && <span title="Default emotion">★ </span>}
        {emotionName}
      </span>
      <span style={instructStyle} title={String(emotion.instruct ?? '')}>
        {String(emotion.instruct ?? '') || '—'}
      </span>
      <button data-testid={`emotion-edit-${characterId}-${emotionName}`} style={smallButtonStyle} onClick={startEdit} title="Edit" aria-label={`Edit emotion ${emotionName}`}>✏️</button>
      <button data-testid={`emotion-default-${characterId}-${emotionName}`} style={smallButtonStyle} onClick={() => void setDefault()} disabled={busy || isDefault} title="Set as default" aria-label={`Set emotion ${emotionName} as default`}>⭐</button>
      <button data-testid={`emotion-delete-${characterId}-${emotionName}`} style={smallButtonStyle} onClick={() => void remove()} disabled={busy} title="Delete">🗑</button>
    </div>
  );
};

const rowStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: 6,
  padding: '3px 0',
  fontSize: 13,
};

const editRowStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: 6,
  padding: '4px 0',
};

const inputStyle: React.CSSProperties = {
  background: '#242424',
  color: '#ddd',
  border: '1px solid #444',
  borderRadius: 3,
  padding: '3px 6px',
  fontSize: 13,
};

const smallButtonStyle: React.CSSProperties = {
  background: 'transparent',
  border: 'none',
  cursor: 'pointer',
  fontSize: 12,
  padding: '2px 4px',
};

const instructStyle: React.CSSProperties = {
  color: '#999',
  flex: 1,
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap',
};