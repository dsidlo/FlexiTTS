import React, {useCallback, useEffect, useMemo, useState, useRef } from 'react';
import type { CharacterConfig } from '../models/types';
import { PythonBridgeService } from '../services/pythonBridge';
import { CharacterBar } from './CharacterBar';
import { UnresolvedReferencesPanel, useUnresolvedReferences } from './UnresolvedReferences';
import { alerts } from '../services/alertService';
import { DialogEffectsTab } from './DialogEffectsTab';
import { PostProcessTab } from './PostProcessTab';

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
  /** Phase 10.1: quick-assign callback per character (opens assign picker). */
  onQuickAssign?: (characterName: string) => void;
}

export const CharacterVoiceDialog: React.FC<CharacterVoiceDialogProps> = ({
  storyDir, open, onClose, onConfigChanged, onQuickAssign,
}) => {
  const [characters, setCharacters] = useState<CharacterConfig[]>([]);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  // Phase 11: selected character (keyboard-driven) and preview audio
  const [selectedCharacterName, setSelectedCharacterName] = useState<string | null>(null);
  const [previewingCharacter, setPreviewingCharacter] = useState<string | null>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);
  const previewAudioRef = useRef<HTMLAudioElement | null>(null);
  const [filterLanguage, setFilterLanguage] = useState('');
  const [filterVoiceType, setFilterVoiceType] = useState('');
  const [filterMinEmotions, setFilterMinEmotions] = useState(0);
  const [sortOrder, setSortOrder] = useState<'name-asc' | 'name-desc'>('name-asc');
  const [undoStack, setUndoStack] = useState<string[]>([]);
  const [redoStack, setRedoStack] = useState<string[]>([]);
  const [expanded, setExpanded] = useState<Set<string>>(() => {
    try {
      const saved = sessionStorage.getItem('flexitts-expanded-characters');
      return new Set(saved ? JSON.parse(saved) : []);
    } catch { return new Set(); }
  });
  const importInputRef = React.useRef<HTMLInputElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [newCharName, setNewCharName] = useState('');
  const [showNewCharInput, setShowNewCharInput] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);
  const [activeTab, setActiveTab] = useState<'characters' | 'dialog-effects' | 'post-process'>(() => {
    try {
      return (sessionStorage.getItem('flexitts-active-tab') as 'characters' | 'dialog-effects' | 'post-process') || 'characters';
    } catch { return 'characters'; }
  });
  const [postProcessEffects, setPostProcessEffects] = useState<string[]>([]);
  const [postProcessDirty, setPostProcessDirty] = useState(false);
  const { unresolved } = useUnresolvedReferences(storyDir, reloadKey);
  const [availableDialogEffects, setAvailableDialogEffects] = useState<string[]>([]);
  const [voicesDirPath, setVoicesDirPath] = useState<string>('');

  const refresh = useCallback(async () => {
    if (!open) return;
    setLoading(true);
    setError(null);
    try {
      // When the parent hasn't resolved a story yet (startup race), fall back
      // to the persisted global config: prefix + current-story, matching how
      // App.tsx resolves it. The user's config stores the bare name
      // (e.g. "Entanglement") with story-dir-prefix "Story-".
      let dir = storyDir;
      if (!dir) {
        const globalConfig = await PythonBridgeService.loadGlobalConfig();
        const flex = (globalConfig as { FlexiTTS?: Record<string, string> })?.FlexiTTS ?? {};
        const name = flex['current-story'];
        if (!name) {
          setError('No story is loaded. Select a story first.');
          setLoading(false);
          return;
        }
        dir = `${flex['story-dir-prefix'] || 'Story-'}${name}`;
      }
      const list = await PythonBridgeService.listCharacters(dir);
      setCharacters(list);
      const rawConfig = (await PythonBridgeService.loadStoryConfigForStory(dir)) ?? {};
      setAvailableDialogEffects(
        ((rawConfig as unknown as Record<string, unknown>)['dialog-effects'] as Array<Record<string, unknown>> ?? []).map((e) => String(e?.name ?? '')).filter(Boolean),
      );
      setPostProcessEffects(((rawConfig as unknown as Record<string, unknown>)['story-audio-post-process'] as Record<string, unknown>)?.['sox-effects'] as string[] ?? []);
      setVoicesDirPath(`${dir}/${((rawConfig as unknown as Record<string, unknown>)['global'] as Record<string, unknown>)?.['voices'] ?? 'story-voice-refs'}`);
      setReloadKey((k) => k + 1);
      onConfigChanged?.();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [storyDir, open, onConfigChanged]);

  useEffect(() => {
    if (open) void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, storyDir]);

  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [open, onClose]);

  // Persist expanded characters and active tab across dialog reopens
  useEffect(() => {
    try { sessionStorage.setItem('flexitts-expanded-characters', JSON.stringify([...expanded])); } catch {}
  }, [expanded]);
  useEffect(() => {
    try { sessionStorage.setItem('flexitts-active-tab', activeTab); } catch {}
  }, [activeTab]);

  // Undo/Redo: snapshot config content on each refresh (post-mutation)
  useEffect(() => {
    if (!open || !storyDir) return;
    let cancelled = false;
    (async () => {
      try {
        const cfg = await PythonBridgeService.loadStoryConfigForStory(storyDir);
        const text = JSON.stringify(cfg, null, 2);
        if (cancelled) return;
        setUndoStack((prev) => {
          if (prev.length > 0 && prev[prev.length - 1] === text) return prev;
          const next = [...prev, text];
          return next.slice(-50); // keep last 50
        });
        setRedoStack([]);
      } catch {}
    })();
    return () => { cancelled = true; };
  }, [storyDir, reloadKey, open]);

  const handleUndo = useCallback(async () => {
    if (undoStack.length < 2) return;
    // The current state is the last entry; the previous is second-to-last
    const currentText = undoStack[undoStack.length - 1];
    const previousText = undoStack[undoStack.length - 2];
    if (!window.api?.writeFile) return;
    try {
      const cfgPath = `${storyDir}/story-config.yml`;
      // Parse the previous snapshot back to YAML for writing
      const jsyaml = (await import('js-yaml')).default;
      const previousObj = JSON.parse(previousText);
      await window.api.writeFile(cfgPath, jsyaml.dump(previousObj, { sortKeys: false }));
      setRedoStack((prev) => [...prev, currentText]);
      setUndoStack((prev) => prev.slice(0, -1));
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    }
  }, [undoStack, storyDir, refresh]);

  const handleRedo = useCallback(async () => {
    if (redoStack.length === 0) return;
    if (!window.api?.writeFile) return;
    try {
      const redoText = redoStack[redoStack.length - 1];
      const cfgPath = `${storyDir}/story-config.yml`;
      const redoObj = JSON.parse(redoText);
      const jsyaml = (await import('js-yaml')).default ?? (await import('js-yaml'));
      await window.api.writeFile(cfgPath, (jsyaml as any).dump ? (jsyaml as any).dump(redoObj, { sortKeys: false }) : redoText);
      setUndoStack((prev) => [...prev, redoText]);
      setRedoStack((prev) => prev.slice(0, -1));
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    }
  }, [redoStack, storyDir, refresh]);

  // Ctrl+Z / Ctrl+Shift+Z keyboard shortcuts
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.ctrlKey && e.key === 'z' && !e.shiftKey) { e.preventDefault(); void handleUndo(); }
      else if (e.ctrlKey && e.key === 'Z' && e.shiftKey) { e.preventDefault(); void handleRedo(); }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [open, handleUndo, handleRedo]);

  // Phase 11: Ctrl+N (new character), Delete (delete selected), Ctrl+F
  // (focus search), Space (preview selected character's voice sample).
  const handleDeleteSelected = useCallback(async () => {
    if (!selectedCharacterName || !storyDir) return;
    if (!window.api?.showConfirmDialog) return;
    const res = await window.api.showConfirmDialog(
      'Delete Character',
      `Delete character '${selectedCharacterName}'?`,
      'This removes its voice configuration from story-config.yml.'
    );
    if (res !== 1) return;
    try {
      await PythonBridgeService.deleteCharacter(storyDir, selectedCharacterName);
      setSelectedCharacterName(null);
      alerts.success(`Deleted character '${selectedCharacterName}'`);
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    }
  }, [selectedCharacterName, storyDir, refresh]);

  const stopPreview = useCallback(() => {
    if (previewAudioRef.current) {
      previewAudioRef.current.pause();
      previewAudioRef.current.currentTime = 0;
      previewAudioRef.current = null;
    }
    setPreviewingCharacter(null);
  }, []);

  const previewSelectedCharacter = useCallback(async () => {
    const character = characters.find((c) => c.name === selectedCharacterName);
    const sample = character?.['voice-sample'] as string | undefined;
    if (!sample || typeof window === 'undefined' || !window.api?.readAudioFile || !voicesDirPath) {
      return;
    }
    stopPreview();
    setPreviewingCharacter(selectedCharacterName ?? null);
    try {
      const dataUrl = await window.api.readAudioFile(`${voicesDirPath}/${sample}`);
      const audio = new Audio(dataUrl);
      previewAudioRef.current = audio;
      audio.onended = () => setPreviewingCharacter(null);
      await audio.play();
    } catch {
      setPreviewingCharacter(null);
    }
  }, [characters, selectedCharacterName, voicesDirPath, stopPreview]);

  useEffect(() => {
    if (!open || activeTab !== 'characters') return;
    const handler = (e: KeyboardEvent) => {
      if (e.ctrlKey && !e.shiftKey && !e.altKey && (e.key === 'n' || e.key === 'N')) {
        e.preventDefault();
        setShowNewCharInput(true);
      } else if (e.key === 'Delete' && selectedCharacterName && !showNewCharInput) {
        // Only when not typing in an input
        const el = document.activeElement as HTMLElement | null;
        if (el && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.isContentEditable)) return;
        e.preventDefault();
        void handleDeleteSelected();
      } else if (e.ctrlKey && (e.key === 'f' || e.key === 'F')) {
        e.preventDefault();
        searchInputRef.current?.focus();
        searchInputRef.current?.select();
      } else if (e.key === ' ' && selectedCharacterName) {
        const el = document.activeElement as HTMLElement | null;
        if (el && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.tagName === 'BUTTON' || el.isContentEditable)) return;
        e.preventDefault();
        void previewSelectedCharacter();
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [open, activeTab, selectedCharacterName, showNewCharInput, handleDeleteSelected, previewSelectedCharacter]);

  // Clear selection/preview when the dialog closes
  useEffect(() => {
    if (!open) {
      setSelectedCharacterName(null);
      stopPreview();
    }
  }, [open, stopPreview]);

  const handleTabKeyDown = useCallback((e: React.KeyboardEvent) => {
    const order: Array<'characters' | 'dialog-effects' | 'post-process'> = ['characters', 'dialog-effects', 'post-process'];
    const idx = order.indexOf(activeTab);
    if (e.key === 'ArrowRight') {
      e.preventDefault();
      setActiveTab(order[(idx + 1) % order.length]);
    } else if (e.key === 'ArrowLeft') {
      e.preventDefault();
      setActiveTab(order[(idx - 1 + order.length) % order.length]);
    }
  }, []);

  const toggleExpand = useCallback((characterId: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(characterId)) next.delete(characterId);
      else next.add(characterId);
      return next;
    });
  }, []);

  const handleAddCharacter = useCallback(async () => {
    setShowNewCharInput(true);
  }, []);

  const handleCreateCharacter = useCallback(async () => {
    const name = newCharName.trim();
    if (!name) return;
    if (!storyDir) {
      setError('No story is loaded. Select a story first.');
      return;
    }
    try {
      await PythonBridgeService.createCharacter(storyDir, {
        name,
        language: 'English',
        voiceType: 'custom',
        voice: { speaker: 'ryan', instruct: '' },
      });
      setNewCharName('');
      setShowNewCharInput(false);
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    }
  }, [newCharName, storyDir, refresh]);

  const handleImport = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    e.target.value = '';
    try {
      const content = await file.text();
      const blob = new Blob([content], { type: file.type || 'application/octet-stream' });
      const dataFile = new File([blob], file.name);
      // The bridge import command needs a file path; use the bridge with base64
      const buffer = await new Promise<ArrayBuffer>((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result as ArrayBuffer);
        reader.onerror = () => reject(new Error('Cannot read import file'));
        reader.readAsArrayBuffer(dataFile);
      });
      const bytes = new Uint8Array(buffer);
      let binary = '';
      const chunkSize = 0x8000;
      for (let i = 0; i < bytes.length; i += chunkSize) {
        binary += String.fromCharCode.apply(null, [...bytes.subarray(i, i + chunkSize)] as unknown as number[]);
      }
      const result = await PythonBridgeService.runBridgeCommand([
        'import-characters', storyDir, btoa(binary), 'keep-both',
      ]);
      if (!result.success) {
        setError(result.error || 'Import failed');
        return;
      }
      await refresh();
    } catch (err) {
      setError((err as Error).message);
    }
  }, [storyDir, refresh]);

  const handleCreateStub = useCallback(async (type: string, value: string) => {
    try {
      if (type === 'dialog-effects') {
        await PythonBridgeService.runBridgeCommand([
          'create-dialog-effect-stub', storyDir, value,
        ]);
        await refresh();
      }
    } catch (e) {
      setError((e as Error).message);
    }
  }, [refresh]);

  // Debounce search input (300ms)
  useEffect(() => {
    const handle = setTimeout(() => setDebouncedSearch(search), 300);
    return () => clearTimeout(handle);
  }, [search]);

  const filtered = useMemo(() => {
    let result = characters.filter((c) =>
      c.name.toLowerCase().includes(debouncedSearch.toLowerCase()),
    );
    // Filter by language
    if (filterLanguage) {
      result = result.filter((c) => {
        const cv = c['custom-voice'] ?? (c as unknown as Record<string, unknown>)['qwen3-tts-custom-voice'];
        if (cv && typeof cv === 'object' && 'language' in cv) {
          return String((cv as Record<string, unknown>).language || '').toLowerCase() === filterLanguage.toLowerCase();
        }
        return filterLanguage === '';
      });
    }
    // Filter by voice type
    if (filterVoiceType === 'custom') {
      result = result.filter((c) => Boolean(c['custom-voice']));
    } else if (filterVoiceType === 'sample') {
      result = result.filter((c) => Boolean(c['voice-sample']));
    }
    // Filter by minimum emotion count
    if (filterMinEmotions > 0) {
      result = result.filter((c) => {
        const cv = c['custom-voice'];
        const emotions = (cv && typeof cv === 'object' && Array.isArray(cv.emotions)) ? cv.emotions.length : 0;
        const cloned = Array.isArray(c['cloned-emotion']) ? c['cloned-emotion'].length : 0;
        return (emotions + cloned) >= filterMinEmotions;
      });
    }
    // Sort
    result = [...result].sort((a, b) => {
      const cmp = a.name.localeCompare(b.name);
      return sortOrder === 'name-asc' ? cmp : -cmp;
    });
    return result;
  }, [characters, debouncedSearch, filterLanguage, filterVoiceType, filterMinEmotions, sortOrder]);

  if (!open) return null;

  return (
    <div
      data-testid="character-voice-dialog"
      style={{
        position: 'fixed',
        top: 60,
        left: 8,
        bottom: 8,
        width: 560,
        background: '#1a1a1a',
        border: '1px solid #444',
        borderRadius: 8,
        zIndex: 900,
        display: 'flex',
        flexDirection: 'column',
        color: '#ddd',
      }}
      role="dialog"
      aria-modal="true"
      aria-label="Character voices"
    >
      <div style={{ display: 'flex', alignItems: 'center', padding: '10px 12px', borderBottom: '1px solid #333', gap: 8 }}>
        <input
          ref={searchInputRef}
          data-testid="character-search"
          type="text"
          aria-label="Search characters"
          placeholder="Search characters…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{ flex: 1, background: '#242424', color: '#ddd', border: '1px solid #444', borderRadius: 4, padding: '4px 8px' }}
        />
        {showNewCharInput ? (
          <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
            <input
              data-testid="character-new-name"
              autoFocus
              value={newCharName}
              onChange={(e) => setNewCharName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') void handleCreateCharacter();
                if (e.key === 'Escape') { setShowNewCharInput(false); setNewCharName(''); }
              }}
              placeholder="Character name…"
              style={{ background: '#242424', color: '#ddd', border: '1px solid #444', borderRadius: 4, padding: '4px 8px', fontSize: 13, width: 160 }}
            />
            <button data-testid="character-create-confirm" style={toolbarButtonStyle} onClick={() => void handleCreateCharacter()} title="Create">✓</button>
            <button style={toolbarButtonStyle} onClick={() => { setShowNewCharInput(false); setNewCharName(''); }} title="Cancel">✕</button>
          </div>
        ) : (
          <button data-testid="character-add" style={toolbarButtonStyle} onClick={handleAddCharacter} title="Add character">＋</button>
        )}
        <button
          data-testid="character-import"
          style={toolbarButtonStyle}
          onClick={() => importInputRef.current?.click()}
          title="Import characters"
        >
          ⇩
        </button>
        <input
          ref={importInputRef}
          type="file"
          accept=".yml,.yaml,.json,.zip"
          style={{ display: 'none' }}
          onChange={(e) => void handleImport(e)}
        />
        <button data-testid="character-refresh" style={toolbarButtonStyle} onClick={() => void refresh()} title="Reload">⟳</button>
        <button data-testid="character-undo" style={toolbarButtonStyle} onClick={() => void handleUndo()} disabled={undoStack.length < 2} title="Undo (Ctrl+Z)">↩</button>
        <button data-testid="character-redo" style={toolbarButtonStyle} onClick={() => void handleRedo()} disabled={redoStack.length === 0} title="Redo (Ctrl+Shift+Z)">↪</button>
        <button data-testid="character-close" style={toolbarButtonStyle} onClick={onClose} title="Close">✕</button>
      </div>
      <div style={{ display: 'flex', gap: 6, padding: '4px 12px', borderBottom: '1px solid #333', alignItems: 'center', flexWrap: 'wrap' }}>
        <select
          data-testid="filter-language"
          value={filterLanguage}
          onChange={(e) => setFilterLanguage(e.target.value)}
          style={filterSelectStyle}
          title="Filter by language"
        >
          <option value="">Language: All</option>
          <option value="English">English</option>
          <option value="Chinese">Chinese</option>
          <option value="Japanese">Japanese</option>
          <option value="Korean">Korean</option>
        </select>
        <select
          data-testid="filter-voice-type"
          value={filterVoiceType}
          onChange={(e) => setFilterVoiceType(e.target.value)}
          style={filterSelectStyle}
          title="Filter by voice type"
        >
          <option value="">Voice: All</option>
          <option value="custom">Custom Voice</option>
          <option value="sample">Sample-Based</option>
        </select>
        <select
          data-testid="filter-emotions"
          value={filterMinEmotions}
          onChange={(e) => setFilterMinEmotions(Number(e.target.value))}
          style={filterSelectStyle}
          title="Filter by emotion count"
        >
          <option value={0}>Emotions: Any</option>
          <option value={1}>1+ emotions</option>
          <option value={3}>3+ emotions</option>
          <option value={5}>5+ emotions</option>
        </select>
        <select
          data-testid="sort-order"
          value={sortOrder}
          onChange={(e) => setSortOrder(e.target.value as 'name-asc' | 'name-desc')}
          style={filterSelectStyle}
          title="Sort order"
        >
          <option value="name-asc">Sort: A-Z</option>
          <option value="name-desc">Sort: Z-A</option>
        </select>
        {(filterLanguage || filterVoiceType || filterMinEmotions > 0) && (
          <button
            data-testid="clear-filters"
            style={{ ...filterSelectStyle, border: 'none', color: '#8ab4f8', cursor: 'pointer', fontSize: 11 }}
            onClick={() => { setFilterLanguage(''); setFilterVoiceType(''); setFilterMinEmotions(0); }}
          >
            Clear filters
          </button>
        )}
      </div>
      <div style={{ padding: '4px 12px', color: '#888', fontSize: 12, borderBottom: '1px solid #333' }}>
        <span data-testid="character-count">{characters.length} characters</span>
      </div>
      <div role="tablist" aria-label="Character dialog sections" style={{ display: 'flex', borderBottom: '2px solid #333', }} onKeyDown={handleTabKeyDown}>
        {([
          ['characters', '🎭 Characters'],
          ['dialog-effects', '🔊 Dialog Effects'],
          ['post-process', '📊 Post-Process'],
        ] as const).map(([tab, label]) => (
          <button
            key={tab}
            data-testid={`tab-${tab === 'dialog-effects' ? 'dialog-effects' : tab === 'post-process' ? 'post-process' : 'characters'}`}
            onClick={() => setActiveTab(tab)}
            style={{
              flex: 1,
              padding: '6px 4px',
              background: 'transparent',
              border: 'none',
              borderBottom: activeTab === tab ? '2px solid #4a90d9' : '2px solid transparent',
              color: activeTab === tab ? '#8ab4f8' : '#888',
              cursor: 'pointer',
              fontSize: 12,
              fontWeight: activeTab === tab ? 600 : 400,
            }}
            role="tab"
            aria-selected={activeTab === tab}
          >
            {label}
          </button>
        ))}
      </div>
      <div style={{ padding: '0 8px' }}>
        <UnresolvedReferencesPanel
          unresolved={unresolved}
          onJump={(characterId) => {
            setExpanded((prev) => new Set(prev).add(characterId));
          }}
          onCreateStub={handleCreateStub}
        />
      </div>
      {activeTab === 'dialog-effects' && (
        <DialogEffectsTab
          storyDir={storyDir}
          onRefresh={refresh}
          onError={setError}
        />
      )}
      {activeTab === 'post-process' && (
        <PostProcessTab
          storyDir={storyDir}
          effects={postProcessEffects}
          onEffectsChanged={(effs) => {
            setPostProcessEffects(effs);
            setPostProcessDirty(true);
          }}
          onError={setError}
          dirty={postProcessDirty}
          onSaved={() => setPostProcessDirty(false)}
        />
      )}
      <div style={{ flex: 1, overflowY: 'auto', padding: 8, display: activeTab === 'characters' ? 'block' : 'none' }}>
        {loading && activeTab === 'characters' && <div style={{ color: '#888', padding: 12 }}>Loading…</div>}
        {error && activeTab === 'characters' && <div style={{ color: '#f66', padding: 12 }} data-testid="character-error">{error}</div>}
        {activeTab === 'characters' && !loading && filtered.length === 0 && (
          <div style={{ color: '#666', padding: 12 }}>No characters match.</div>
        )}
        {activeTab === 'characters' && filtered.map((character: CharacterConfig) => (
          <CharacterBar
            key={character.name}
            character={character}
            storyDir={storyDir}
            expanded={expanded.has(character.name)}
            selected={selectedCharacterName === character.name}
            previewing={previewingCharacter === character.name}
            onSelect={(name) => setSelectedCharacterName((cur) => (cur === name ? null : name))}
            availableDialogEffects={availableDialogEffects}
            voicesDir={voicesDirPath}
            onQuickAssign={onQuickAssign ? () => onQuickAssign(character.name) : undefined}
            onToggleExpand={toggleExpand}
            onRefresh={refresh}
            onError={setError}
            onSaved={(msg) => alerts.success(msg)}
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
const filterSelectStyle: React.CSSProperties = {
  background: '#242424',
  color: '#ddd',
  border: '1px solid #444',
  borderRadius: 4,
  padding: '3px 6px',
  fontSize: 11,
  cursor: 'pointer',
};
