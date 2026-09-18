import React, { useCallback, useMemo, useState } from 'react';
import type { CharacterConfig } from '../models/types';
import { PythonBridgeService } from '../services/pythonBridge';

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
  onToggleExpand: (characterId: string) => void;
  onRefresh: () => void;
  onError: (message: string) => void;
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
  character, storyDir, expanded, selected, onToggleExpand, onRefresh, onError,
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
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      onToggleExpand(character.name);
    }
  }, [character.name, onToggleExpand]);

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
      aria-expanded={expanded}
    >
      <div
        style={{ ...rowStyle, cursor: 'pointer' }}
        onClick={() => onToggleExpand(character.name)}
      >
        <span style={{ marginRight: 8, display: 'inline-block', width: 12 }}>
          {expanded ? '▾' : '▸'}
        </span>
        <strong style={{ flex: 1 }}>{character.name}</strong>
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
          {Array.isArray(character['sox-effects']) && character['sox-effects'].length > 0 && (
            <div style={{ color: '#888', fontSize: 12, fontFamily: 'monospace', marginBottom: 6 }}>
              SoX: {character['sox-effects'].join(' | ')}
            </div>
          )}
          {emotions.length > 0 ? (
            <div>
              {emotions.map((em, idx) => {
                const name = String((em as Record<string, unknown>).emotion ?? (em as Record<string, unknown>).name ?? idx);
                const instruct = String((em as Record<string, unknown>).instruct ?? '');
                return (
                  <div key={idx} data-testid={`emotion-row-${character.name}-${name}`}
                       style={{ display: 'flex', gap: 8, padding: '3px 0', fontSize: 13 }}>
                    <span style={{ width: 90 }}>{name}</span>
                    <span style={{ color: '#999', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {instruct || '—'}
                    </span>
                  </div>
                );
              })}
            </div>
          ) : (
            <div style={{ color: '#666', fontSize: 12 }}>No emotions configured</div>
          )}
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