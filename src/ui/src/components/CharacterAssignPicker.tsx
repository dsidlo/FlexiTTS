import React, { useEffect, useMemo, useRef, useState } from 'react';
import type { CharacterConfig } from '../models/types';

/**
 * Phase 10: CharacterAssignPicker
 *
 * Modal used by Quick Assign (10.1) and Bulk Assign (10.2) to pick a
 * character for one or more selected dialog lines, and by Character
 * Switching (10.3) for A/B preview comparison.
 *
 * - List of characters with voice-type and emotion count.
 * - "Preview" plays the character's voice sample via read-audio-file.
 * - A/B mode plays two characters back-to-back on the same sample line
 *   for side-by-side comparison.
 * - window.prompt is banned in Electron; all interaction is inline.
 */

export interface CharacterAssignPickerProps {
  open: boolean;
  characters: Array<string | CharacterConfig>;
  /** Number of dialog lines that will receive the assignment. */
  targetCount: number;
  /** Heading shown at the top of the modal. */
  title?: string;
  /** When true, enables A/B compare checkboxes next to each character. */
  allowCompare?: boolean;
  onCancel: () => void;
  onAssign: (characterName: string) => void;
}

const isCharConfig = (c: string | CharacterConfig): c is CharacterConfig =>
  typeof c === 'object' && c !== null && 'name' in c;

const voiceTypeOf = (c: string | CharacterConfig): string => {
  if (!isCharConfig(c)) return '—';
  const cv = c['custom-voice'];
  if (cv && typeof cv === 'object' && 'speaker' in cv) return 'custom-voice';
  return c['voice-sample'] ? 'voice-sample' : '—';
};

export const CharacterAssignPicker: React.FC<CharacterAssignPickerProps> = ({
  open, characters, targetCount, title, allowCompare = false,
  onCancel, onAssign,
}) => {
  const [query, setQuery] = useState('');
  const [compare, setCompare] = useState<string[]>([]);
  const [previewing, setPreviewing] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  // Reset transient state when (re)opened
  useEffect(() => {
    if (open) {
      setQuery('');
      setCompare([]);
      setPreviewing(null);
      // Focus the search box for immediate keyboard filtering
      window.setTimeout(() => inputRef.current?.focus(), 0);
    }
  }, [open]);

  // Escape closes
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.stopPropagation();
        onCancel();
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [open, onCancel]);

  // Focus trap: keep Tab cycling inside the modal (Phase 11 preview, works now)
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key !== 'Tab') return;
      const dialog = document.getElementById('character-assign-picker');
      if (!dialog) return;
      const focusables = dialog.querySelectorAll<HTMLElement>(
        'button:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex="-1"])',
      );
      if (focusables.length === 0) return;
      const first = focusables[0];
      const last = focusables[focusables.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [open]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return characters;
    return characters.filter((c) => {
      const name = isCharConfig(c) ? c.name : c;
      return name.toLowerCase().includes(q);
    });
  }, [characters, query]);

  const stopAudio = () => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
      audioRef.current = null;
    }
    setPreviewing(null);
  };

  const playSample = async (name: string) => {
    const cfg = characters.find((c) => (isCharConfig(c) ? c.name : c) === name);
    const sample = isCharConfig(cfg as CharacterConfig)
      ? ((cfg as CharacterConfig)['voice-sample'] as string | undefined)
      : undefined;
    if (!sample || typeof window === 'undefined' || !window.api?.readAudioFile) {
      return;
    }
    stopAudio();
    setPreviewing(name);
    try {
      const storyDirGuess = (cfg as CharacterConfig & { _storyDir?: string })?._storyDir;
      const dataUrl = await window.api.readAudioFile(
        storyDirGuess ? `${storyDirGuess}/story-voice-refs/${sample}` : sample,
      );
      const audio = new Audio(dataUrl);
      audioRef.current = audio;
      audio.onended = () => setPreviewing(null);
      await audio.play();
    } catch {
      setPreviewing(null);
    }
  };

  const toggleCompare = (name: string) => {
    setCompare((prev) => {
      if (prev.includes(name)) return prev.filter((n) => n !== name);
      // Keep at most two for A/B
      return [...prev, name].slice(-2);
    });
  };

  const playCompare = async () => {
    if (compare.length < 2) return;
    stopAudio();
    setPreviewing(compare.join(' / '));
    for (const name of compare) {
      const cfg = characters.find((c) => (isCharConfig(c) ? c.name : c) === name);
      const sample = isCharConfig(cfg as CharacterConfig)
        ? ((cfg as CharacterConfig)['voice-sample'] as string | undefined)
        : undefined;
      if (!sample || !window.api?.readAudioFile) continue;
      try {
        const storyDirGuess = (cfg as CharacterConfig & { _storyDir?: string })?._storyDir;
        const dataUrl = await window.api.readAudioFile(
          storyDirGuess ? `${storyDirGuess}/story-voice-refs/${sample}` : sample,
        );
        await new Promise<void>((resolve) => {
          const audio = new Audio(dataUrl);
          audioRef.current = audio;
          audio.onended = () => resolve();
          audio.onerror = () => resolve();
          void audio.play();
        });
      } catch {
        // Skip characters whose samples cannot be read
      }
    }
    setPreviewing(null);
  };

  if (!open) return null;

  return (
    <div
      role="presentation"
      data-testid="character-assign-overlay"
      onClick={onCancel}
      style={{
        position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.45)',
        zIndex: 3000, display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}
    >
      <div
        id="character-assign-picker"
        role="dialog"
        aria-modal="true"
        aria-label={title ?? 'Assign character'}
        data-testid="character-assign-picker"
        onClick={(e) => e.stopPropagation()}
        style={{
          background: '#fff', color: '#222', borderRadius: 8, minWidth: 420, maxWidth: 560,
          maxHeight: '80vh', display: 'flex', flexDirection: 'column',
          boxShadow: '0 8px 30px rgba(0,0,0,0.35)', border: '1px solid #bbb',
        }}
      >
        <div style={{ padding: '12px 16px', borderBottom: '1px solid #ddd', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <strong>{title ?? `Assign character (${targetCount} line${targetCount === 1 ? '' : 's'} selected)`}</strong>
          <button
            type="button"
            aria-label="Close assign dialog"
            data-testid="assign-picker-close"
            onClick={onCancel}
            style={{ background: 'transparent', border: 'none', fontSize: 18, cursor: 'pointer', lineHeight: 1 }}
          >
            ×
          </button>
        </div>

        <div style={{ padding: '10px 16px', borderBottom: '1px solid #eee' }}>
          <input
            ref={inputRef}
            type="text"
            value={query}
            placeholder="Filter characters…"
            aria-label="Filter characters"
            data-testid="assign-picker-filter"
            onChange={(e) => setQuery(e.target.value)}
            style={{ width: '100%', padding: '6px 10px', borderRadius: 4, border: '1px solid #ccc', fontSize: 14 }}
          />
        </div>

        <div style={{ overflowY: 'auto', flex: 1, padding: '6px 8px' }}>
          {filtered.length === 0 && (
            <div style={{ padding: '14px', color: '#777', fontStyle: 'italic' }}>No characters match.</div>
          )}
          {filtered.map((c) => {
            const name = isCharConfig(c) ? c.name : c;
            const isCompare = compare.includes(name);
            return (
              <div
                key={name}
                data-testid={`assign-option-${name}`}
                style={{
                  display: 'flex', alignItems: 'center', gap: 8, padding: '8px 10px', borderRadius: 4,
                  background: isCompare ? '#eef4ff' : 'transparent',
                }}
              >
                <button
                  type="button"
                  className="assign-pick"
                  onClick={() => { stopAudio(); onAssign(name); }}
                  style={{
                    flex: 1, textAlign: 'left', padding: '6px 10px', background: 'transparent',
                    border: '1px solid transparent', borderRadius: 4, cursor: 'pointer', fontSize: 14,
                  }}
                  onMouseEnter={(e) => { e.currentTarget.style.background = '#f2f2f2'; e.currentTarget.style.borderColor = '#99c'; }}
                  onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.borderColor = 'transparent'; }}
                >
                  <span style={{ fontWeight: 600 }}>{name}</span>
                  <span style={{ marginLeft: 8, color: '#888', fontSize: 12 }}>{voiceTypeOf(c)}</span>
                </button>

                {isCharConfig(c) && (c as CharacterConfig)['voice-sample'] && (
                  <button
                    type="button"
                    aria-label={`Preview voice for ${name}`}
                    data-testid={`assign-preview-${name}`}
                    onClick={() => void playSample(name)}
                    style={{ padding: '4px 8px', cursor: 'pointer', borderRadius: 4, border: '1px solid #ccc', background: '#fafafa' }}
                    title="Preview voice sample"
                  >
                    {previewing === name ? '■' : '▶'}
                  </button>
                )}

                {allowCompare && isCharConfig(c) && (c as CharacterConfig)['voice-sample'] && (
                  <>
                    <label style={{ fontSize: 12, color: '#555', display: 'flex', alignItems: 'center', gap: 3 }}>
                      <input
                        type="checkbox"
                        aria-label={`Compare voice for ${name}`}
                        data-testid={`assign-compare-${name}`}
                        checked={isCompare}
                        onChange={() => toggleCompare(name)}
                      />
                      A/B
                    </label>
                  </>
                )}
              </div>
            );
          })}
        </div>

        {allowCompare && (
          <div style={{ padding: '10px 16px', borderTop: '1px solid #eee', display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
            <button
              type="button"
              data-testid="assign-compare-play"
              disabled={compare.length < 2}
              onClick={() => void playCompare()}
              style={{
                padding: '6px 14px', borderRadius: 4, cursor: compare.length < 2 ? 'not-allowed' : 'pointer',
                border: '1px solid #99c', background: compare.length === 2 ? '#eef4ff' : '#f5f5f5', opacity: compare.length < 2 ? 0.6 : 1,
              }}
              title="Play the two selected voices back-to-back"
            >
              {previewing && previewing.includes(' / ') ? 'Playing A/B…' : 'Play A/B'}
            </button>
          </div>
        )}

        <div style={{ padding: '10px 16px', borderTop: '1px solid #eee', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ fontSize: 12, color: '#777' }}>
            {targetCount} line{targetCount === 1 ? '' : 's'} selected · Enter picks first match
          </span>
          <button
            type="button"
            data-testid="assign-picker-cancel"
            onClick={onCancel}
            style={{ padding: '6px 14px', borderRadius: 4, cursor: 'pointer', border: '1px solid #ccc', background: '#f5f5f5' }}
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
};