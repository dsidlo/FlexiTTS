import React, { useCallback, useMemo, useState } from 'react';
import type { CharacterConfig } from '../models/types';
import { PythonBridgeService } from '../services/pythonBridge';

import { EmotionRow } from './EmotionRow';
import { ReferenceField } from './ReferenceField';
import { VoiceSampleUploader } from './VoiceSampleUploader';

/**
 * Phase 6.2: CharacterBar - one row per character in the CharacterVoiceDialog.
 * Collapsed: name, language, speaker, preview affordance. Expanded: emotions
 * (via EmotionRow), SoX chain, and management actions. Keyboard accessible:
 * Enter toggles expansion, Delete handled by parent.
 */

export interface CharacterBarProps {
  character: CharacterConfig;
  storyDir: string;
  expanded: boolean;
  selected: boolean;
  /** Defined story-level dialog-effects names (dropdown choices). */
  availableDialogEffects: string[];
  voicesDir?: string;
  /** Phase 10.1: open the assign picker for the current dialog selection. */
  onQuickAssign?: () => void;
  /** Phase 11: true while this character's voice sample preview plays. */
  previewing?: boolean;
  /** Phase 11: toggle keyboard selection (Select/Space/Delete target). */
  onSelect?: (characterName: string) => void;
  onToggleExpand: (characterId: string) => void;
  onRefresh: () => void;
  onError: (message: string) => void;
  onSaved?: (message: string) => void;
}

const normalizeLanguage = (character: CharacterConfig): string => {
  const cv = character['custom-voice'] ?? (character as unknown as Record<string, unknown>)['qwen3-tts-custom-voice'];
  if (cv && typeof cv === 'object' && 'language' in cv) {
    return String((cv as Record<string, unknown>).language || '');
  }
  return '—';
};

const normalizeSpeaker = (character: CharacterConfig): string => {
  const cv = character['custom-voice'] ?? (character as unknown as Record<string, unknown>)['qwen3-tts-custom-voice'];
  if (cv && typeof cv === 'object' && 'speaker' in cv) {
    return String((cv as Record<string, unknown>).speaker || '');
  }
  return character['voice-sample'] || '—';
};

export const CharacterBar: React.FC<CharacterBarProps> = ({
  character, storyDir, expanded, selected, availableDialogEffects,
  onToggleExpand, onRefresh, onError, onSaved, voicesDir, onQuickAssign, previewing = false, onSelect,
}) => {
  const [menuOpen, setMenuOpen] = useState(false);
  const [busy, setBusy] = useState(false);

  const language = useMemo(() => normalizeLanguage(character), [character]);
  const speaker = useMemo(() => normalizeSpeaker(character), [character]);
  const emotions = useMemo(() => {
    const cv = character['custom-voice'];
    if (cv?.emotions) return cv.emotions;
    const rec = character as unknown as Record<string, unknown>;
    return (rec['cloned-emotion'] as unknown[]) || [];
  }, [character]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      onToggleExpand(character.name);
    } else if (e.key === ' ' && !e.shiftKey) {
      // Phase 11: Space selects the character (preview is handled at dialog
      // level so the same key both selects and re-previews).
      e.preventDefault();
      onSelect?.(character.name);
    }
  }, [character.name, onToggleExpand, onSelect]);

  const handleContextMenu = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setMenuOpen(true);
  }, []);

  const handleDelete = useCallback(async () => {
    setMenuOpen(false);
    if (!window.api?.showConfirmDialog) return;
    const res = await window.api.showConfirmDialog(
      'Delete Character',
      `Delete character '${character.name}'?`,
      'This removes its voice configuration from story-config.yml.'
    );
    if (res !== 1) return; // 1 = confirm in our dialog convention
    setBusy(true);
    try {
      await PythonBridgeService.deleteCharacter(storyDir, character.name);
      onRefresh();
      onSaved?.(`Deleted character '${character.name}'`);
    } catch (e) {
      onError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }, [character.name, storyDir, onRefresh, onError]);

  const handleDuplicate = useCallback(async () => {
    setMenuOpen(false);
    setBusy(true);
    try {
      await PythonBridgeService.createCharacter(storyDir, {
        name: `${character.name} Copy`,
        language: language !== '—' ? language : 'English',
        ...(character['custom-voice']
          ? { voiceType: 'custom', voice: { ...character['custom-voice'] } }
          : character['voice-sample']
            ? { voiceType: 'sample', voice: { 'voice-sample': character['voice-sample'] } }
            : {}),
      });
      onRefresh();
    } catch (e) {
      onError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }, [character, storyDir, onRefresh, onError]);

  const dialogEffectChoices = useMemo(() => {
    // Choices come from the story's dialog-effects definitions; the parent
    // passes them via props when available. Empty here means no defined list.
    return availableDialogEffects;
  }, [availableDialogEffects]);

  const qwen3Speakers = ['aiden', 'dylan', 'eric', 'ono_anna', 'ryan', 'serena', 'sohee', 'uncle_fu', 'vivian'];

  const handleClearVoiceSample = useCallback(async () => {
    setBusy(true);
    try {
      await PythonBridgeService.updateCharacter(storyDir, character.name, {
        voiceSample: null,
      });
      onRefresh();
    } catch (e) {
      onError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }, [storyDir, character.name, onRefresh, onError]);

  const handleRemoveDialogEffect = useCallback(async (effectName: string) => {
    setBusy(true);
    try {
      await PythonBridgeService.updateCharacter(storyDir, character.name, {
        removeDialogEffect: effectName,
      });
      onRefresh();
    } catch (e) {
      onError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }, [storyDir, character.name, onRefresh, onError]);

  const handleCommitDialogEffect = useCallback(async (value: string) => {
    if (!value.trim()) return;
    setBusy(true);
    try {
      // If the reference is new (unsatisfied), generate a stub first
      const defined = dialogEffectChoices.some(
        (c) => c.toLowerCase() === value.trim().toLowerCase());
      if (!defined) {
        await PythonBridgeService.runBridgeCommand([
          'create-dialog-effect-stub', storyDir, value.trim(),
        ]);
      }
      await PythonBridgeService.updateCharacter(storyDir, character.name, {
        dialogEffects: [
          ...((character['dialog-effects'] ?? []) as string[]), value.trim(),
        ],
      });
      onRefresh();
    } catch (e) {
      onError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }, [storyDir, character.name, dialogEffectChoices, onRefresh, onError]);

  const handleCommitSpeaker = useCallback(async (value: string) => {
    if (!value.trim()) return;
    setBusy(true);
    try {
      await PythonBridgeService.updateCharacter(storyDir, character.name, {
        customVoice: { speaker: value.trim() },
      });
      onRefresh();
    } catch (e) {
      onError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }, [storyDir, character.name, onRefresh, onError]);

  const [newEmotionName, setNewEmotionName] = useState('');
  const [showEmotionInput, setShowEmotionInput] = useState(false);

  const handleAddEmotion = useCallback(async () => {
    setShowEmotionInput(true);
  }, []);

  const handleCreateEmotion = useCallback(async () => {
    const name = newEmotionName.trim();
    if (!name) return;
    setBusy(true);
    try {
      await PythonBridgeService.addEmotion(storyDir, character.name, {
        emotion: name,
        instruct: '',
      });
      setNewEmotionName('');
      setShowEmotionInput(false);
      onRefresh();
      onSaved?.(`Added emotion '${name}' to '${character.name}'`);
    } catch (e) {
      onError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }, [newEmotionName, storyDir, character.name, onRefresh, onError]);

  const rowStyle: React.CSSProperties = {
    border: selected ? '1px solid #4a90d9' : '1px solid #333',
    borderRadius: 6,
    marginBottom: 6,
    background: selected ? '#1e2a3a' : '#222',
  };

  return (
    <div
      data-testid={`character-bar-${character.name}`}
      style={rowStyle}
      role="button"
      tabIndex={0}
      onKeyDown={handleKeyDown}
      onContextMenu={handleContextMenu}
      aria-expanded={expanded}
      aria-selected={selected || undefined}
      aria-label={`${character.name} character row. ${expanded ? 'Expanded' : 'Collapsed'}. Enter to ${expanded ? 'collapse' : 'expand'}, Space to select.`}
      data-previewing={previewing || undefined}
    >
      <div
        style={{ ...rowStyle, cursor: 'pointer' }}
        onClick={() => onToggleExpand(character.name)}
      >
        <span style={{ marginRight: 8, display: 'inline-block', width: 12 }}>
          {expanded ? '▾' : '▸'}
        </span>
        <strong style={{ flex: 1 }}>{character.name}</strong>
        {onQuickAssign && (
          <button
            type="button"
            data-testid={`quick-assign-${character.name}`}
            aria-label={`Assign ${character.name} to selected dialog lines`}
            title="Assign this character to selected dialog lines (Ctrl+Click lines to select)"
            onClick={(e) => {
              e.stopPropagation();
              onQuickAssign();
            }}
            style={{
              marginRight: 8, padding: '2px 8px', borderRadius: 4, cursor: 'pointer',
              border: '1px solid #99c', background: '#eef4ff', fontSize: 12,
            }}
          >
            ⇥ Assign
          </button>
        )}
        <span style={{ color: '#888', marginRight: 12 }}>{language}</span>
        <span style={{ color: '#8ab4f8' }}>{speaker}</span>
        <div style={{ position: 'relative' }} onClick={(e) => e.stopPropagation()}>
          <button
            data-testid={`character-menu-${character.name}`}
            aria-label={`Menu for ${character.name}`}
            style={menuButtonStyle}
            onClick={() => setMenuOpen((o) => !o)}
            disabled={busy}
          >
            ⋮
          </button>
          {menuOpen && (
            <div style={menuStyle} role="menu">
              <button role="menuitem" style={menuItemStyle} onClick={handleDuplicate}>
                📋 Duplicate
              </button>
              <button role="menuitem" style={menuItemStyle} onClick={handleDelete}>
                🗑 Delete
              </button>
            </div>
          )}
        </div>
      </div>
      {expanded && (
        <div style={{ padding: '8px 12px', borderTop: '1px solid #333' }}>
          {character.description && (
            <div style={{ color: '#aaa', fontSize: 12, marginBottom: 6 }}>{character.description}</div>
          )}
          {Array.isArray(character['dialog-effects']) && character['dialog-effects'].length > 0 && (
            <div style={{ marginBottom: 6, display: 'flex', flexWrap: 'wrap', gap: 4, alignItems: 'center' }}>
              <span style={{ color: '#888', fontSize: 11 }}>Dialog effects:</span>
              {character['dialog-effects'].map((de) => (
                <span key={de} style={effectChipStyle}>
                  {de}
                  <button
                    data-testid={`dialog-effect-unlink-${character.name}-${de}`}
                    style={unlinkButtonStyle}
                    onClick={() => void handleRemoveDialogEffect(de)}
                    disabled={busy}
                    title={`Unlink '${de}' from this character`}
                    aria-label={`Unlink dialog effect ${de} from ${character.name}`}
                  >
                    ✕
                  </button>
                </span>
              ))}
            </div>
          )}

          {Array.isArray(character['sox-effects']) && character['sox-effects'].length > 0 && (
            <div style={{ color: '#888', fontSize: 12, fontFamily: 'monospace', marginBottom: 6 }}>
              SoX: {character['sox-effects'].join(' | ')}
            </div>
          )}

          {character['voice-sample'] && !character['custom-voice'] && (
            <button
              data-testid={`clear-voice-sample-${character.name}`}
              style={unlinkButtonStyle}
              onClick={() => void handleClearVoiceSample()}
              disabled={busy}
              title="Remove the voice-sample reference from this character"
              aria-label={`Clear voice sample for ${character.name}`}
            >
              Clear voice-sample: {character['voice-sample']}
            </button>
          )}

          {/* Phase 6b: reference fields for consistent cross-references */}
          <div style={{ display: 'flex', gap: 10, marginBottom: 8, alignItems: 'flex-end' }}>
            {character['custom-voice'] && (
              <ReferenceField
                label="Speaker"
                testId={`ref-speaker-${character.name}`}
                value={normalizeSpeaker(character)}
                choices={qwen3Speakers}
                onCommit={(v) => void handleCommitSpeaker(v)}
              />
            )}
            <ReferenceField
              label="Add dialog-effect"
              testId={`ref-dialog-effect-${character.name}`}
              value=""
              choices={dialogEffectChoices}
              onCommit={(v) => void handleCommitDialogEffect(v)}
              allowFreeText
            />
          </div>

          {character['voice-sample'] && !character['custom-voice'] && (
            <div style={{ marginBottom: 8 }}>
              <VoiceSampleUploader
                storyDir={storyDir}
                characterId={character.name}
                emotionId={null}
                voicesDir={voicesDir}
                onUploaded={onRefresh}
                onError={onError}
              />
            </div>
          )}
          {emotions.length > 0 ? (
            <div>
              {emotions.map((em, idx) => {
                return (
                  <EmotionRow
                    key={idx}
                    characterId={character.name}
                    emotion={em as { emotion?: string; name?: string; instruct?: string; 'sox-effects'?: string[] }}
                    isDefault={idx === 0}
                    storyDir={storyDir}
                    onSaved={onRefresh}
                    onError={onError}
                  />
                );
              })}
            </div>
          ) : (
            <div style={{ color: '#666', fontSize: 12 }}>No emotions configured</div>
          )}
          <div style={{ marginTop: 6 }}>
            {showEmotionInput ? (
              <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
                <input
                  data-testid={`emotion-new-name-${character.name}`}
                  autoFocus
                  value={newEmotionName}
                  onChange={(e) => setNewEmotionName(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') void handleCreateEmotion();
                    if (e.key === 'Escape') { setShowEmotionInput(false); setNewEmotionName(''); }
                  }}
                  placeholder="Emotion name…"
                  style={{ background: '#242424', color: '#ddd', border: '1px solid #444', borderRadius: 4, padding: '4px 8px', fontSize: 13, width: 140 }}
                />
                <button style={addEmotionButtonStyle} onClick={() => void handleCreateEmotion()} title="Create" aria-label={`Confirm new emotion for ${character.name}`}>✓</button>
                <button style={addEmotionButtonStyle} onClick={() => { setShowEmotionInput(false); setNewEmotionName(''); }} title="Cancel" aria-label={`Cancel new emotion for ${character.name}`}>✕</button>
              </div>
            ) : (
              <button
                data-testid={`emotion-add-${character.name}`}
                style={addEmotionButtonStyle}
                onClick={() => void handleAddEmotion()}
                disabled={busy}
                aria-label={`Add emotion to ${character.name}`}
              >
                ＋ Add Emotion
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

const menuButtonStyle: React.CSSProperties = {
  background: 'transparent',
  border: 'none',
  color: '#ccc',
  fontSize: 16,
  cursor: 'pointer',
  padding: '0 6px',
};

const menuStyle: React.CSSProperties = {
  position: 'absolute',
  right: 0,
  top: 24,
  background: '#2a2a2a',
  border: '1px solid #444',
  borderRadius: 4,
  zIndex: 1000,
  minWidth: 140,
};

const menuItemStyle: React.CSSProperties = {
  display: 'block',
  width: '100%',
  textAlign: 'left',
  background: 'transparent',
  border: 'none',
  color: '#ddd',
  padding: '8px 12px',
  cursor: 'pointer',
};
const addEmotionButtonStyle: React.CSSProperties = {
  background: 'transparent',
  border: '1px dashed #555',
  color: '#aaa',
  borderRadius: 4,
  cursor: 'pointer',
  padding: '3px 10px',
  fontSize: 12,
};

const effectChipStyle: React.CSSProperties = {
  display: 'inline-flex',
  alignItems: 'center',
  gap: 2,
  background: '#2a3a2a',
  border: '1px solid #3a5a3a',
  borderRadius: 4,
  padding: '1px 6px',
  fontSize: 11,
  color: '#8ac48a',
};

const unlinkButtonStyle: React.CSSProperties = {
  background: 'transparent',
  border: 'none',
  color: '#f66',
  cursor: 'pointer',
  fontSize: 10,
  padding: '0 2px',
};
