import React, { useCallback, useEffect, useState } from 'react';
import type { CharacterConfig } from '../models/types';
import { PythonBridgeService } from '../services/pythonBridge';
import { CharacterBar } from './CharacterBar';

/**
 * Phase 6.1: CharacterVoiceDialog - top-level dialog listing CharacterBars
 * for the current story. Opened from a toolbar icon button; header has
 * search, settings, add, import and a character count badge.
 */

export interface CharacterVoiceDialogProps {
  storyDir: string;
  open: boolean;
  onClose: () => void;
  /** Notifies the parent that story-config.yml changed (reload config). */
  onConfigChanged?: () => void;
}

export const CharacterVoiceDialog: React.FC<CharacterVoiceDialogProps> = ({
  storyDir, open, onClose, onConfigChanged,
}) => {
  const [characters, setCharacters] = useState<CharacterConfig[]>([]);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState('');
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!storyDir) return;
    setLoading(true);
    setError(null);
    try {
      const list = await PythonBridgeService.listCharacters(storyDir);
      setCharacters(list);
      onConfigChanged?.();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [storyDir, onConfigChanged]);

  useEffect(() => {
    if (open) void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, storyDir]);

  const toggleExpand = useCallback((characterId: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(characterId)) next.delete(characterId);
      else next.add(characterId);
      return next;
    });
  }, []);

  const handleAddCharacter = useCallback(async () => {
    if (!storyDir) {
      setError('No story is loaded. Select a story first.');
      return;
    }
    if (!window.api?.showConfirmDialog) return;
    // Simple prompt-based creation (wizard comes with Phase 6b ReferenceField)
    const name = window.prompt('New character name:');
    if (!name) return;
    try {
      await PythonBridgeService.createCharacter(storyDir, {
        name: name.trim(),
        language: 'English',
        voiceType: 'custom',
        voice: { speaker: 'ryan', instruct: '' },
      });
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    }
  }, [storyDir, refresh]);

  const filtered = characters.filter((c) =>
    c.name.toLowerCase().includes(search.toLowerCase()),
  );

  if (!open) return null;

  return (
    <div
      data-testid="character-voice-dialog"
      style={{
        position: 'fixed',
        top: 60,
        left: 8,
        bottom: 8,
        width: 420,
        background: '#1a1a1a',
        border: '1px solid #444',
        borderRadius: 8,
        zIndex: 900,
        display: 'flex',
        flexDirection: 'column',
        color: '#ddd',
      }}
      role="dialog"
      aria-label="Character voices"
    >
      <div style={{ display: 'flex', alignItems: 'center', padding: '10px 12px', borderBottom: '1px solid #333', gap: 8 }}>
        <input
          data-testid="character-search"
          type="text"
          placeholder="Search characters…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{ flex: 1, background: '#242424', color: '#ddd', border: '1px solid #444', borderRadius: 4, padding: '4px 8px' }}
        />
        <button data-testid="character-add" style={toolbarButtonStyle} onClick={handleAddCharacter} title="Add character">＋</button>
        <button data-testid="character-refresh" style={toolbarButtonStyle} onClick={() => void refresh()} title="Reload">⟳</button>
        <button data-testid="character-close" style={toolbarButtonStyle} onClick={onClose} title="Close">✕</button>
      </div>
      <div style={{ padding: '4px 12px', color: '#888', fontSize: 12, borderBottom: '1px solid #333' }}>
        <span data-testid="character-count">{characters.length} characters</span>
      </div>
      <div style={{ flex: 1, overflowY: 'auto', padding: 8 }}>
        {loading && <div style={{ color: '#888', padding: 12 }}>Loading…</div>}
        {error && <div style={{ color: '#f66', padding: 12 }} data-testid="character-error">{error}</div>}
        {!loading && !error && filtered.length === 0 && (
          <div style={{ color: '#666', padding: 12 }}>No characters match.</div>
        )}
        {filtered.map((character) => (
          <CharacterBar
            key={character.name}
            character={character}
            storyDir={storyDir}
            expanded={expanded.has(character.name)}
            selected={false}
            onToggleExpand={toggleExpand}
            onRefresh={refresh}
            onError={setError}
          />
        ))}
      </div>
    </div>
  );
};

const toolbarButtonStyle: React.CSSProperties = {
  background: 'transparent',
  border: '1px solid #444',
  color: '#ddd',
  borderRadius: 4,
  cursor: 'pointer',
  padding: '4px 8px',
};