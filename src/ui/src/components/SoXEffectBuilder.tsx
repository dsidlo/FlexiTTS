import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { PythonBridgeService } from '../services/pythonBridge';

/**
 * Phase 6.5: SoXEffectBuilder - visual pipeline editor for a character's
 * sox-effects: editable effect list, live command preview, and syntax
 * validation against POST /api/validate/sox (via the bridge).
 */

export interface SoXEffectBuilderProps {
  effects: string[];
  onChanged: (effects: string[]) => void;
  disabled?: boolean;
}

interface ValidationError {
  code: string;
  message: string;
  index?: number;
}

export const SoXEffectBuilder: React.FC<SoXEffectBuilderProps> = ({
  effects, onChanged, disabled = false,
}) => {
  const [draft, setDraft] = useState<string[]>(effects);
  const [validation, setValidation] = useState<{ isValid: boolean; errors: ValidationError[] } | null>(null);
  const [newEffect, setNewEffect] = useState('');
  const [editIndex, setEditIndex] = useState<number | null>(null);
  const [editValue, setEditValue] = useState('');

  // Debounced live validation
  useEffect(() => {
    if (draft.length === 0) {
      setValidation(null);
      return;
    }
    const handle = setTimeout(async () => {
      try {
        const result = await PythonBridgeService.runBridgeCommand([
          'validate-sox', JSON.stringify(draft),
        ]);
        if (result.success) {
          setValidation({ isValid: result.isValid, errors: result.errors ?? [] });
        }
      } catch {
        setValidation(null); // bridge unavailable; don't block editing
      }
    }, 300);
    return () => clearTimeout(handle);
  }, [draft]);

  const commit = useCallback((next: string[]) => {
    setDraft(next);
    onChanged(next);
  }, [onChanged]);

  const addEffect = useCallback(() => {
    const text = newEffect.trim();
    if (!text) return;
    commit([...draft, text]);
    setNewEffect('');
  }, [draft, newEffect, commit]);

  const removeEffect = useCallback((index: number) => {
    commit(draft.filter((_, i) => i !== index));
  }, [draft, commit]);

  const moveEffect = useCallback((index: number, delta: number) => {
    const target = index + delta;
    if (target < 0 || target >= draft.length) return;
    const next = [...draft];
    [next[index], next[target]] = [next[target], next[index]];
    commit(next);
  }, [draft, commit]);

  const errorForIndex = useMemo(
    () => new Map((validation?.errors ?? [])
      .filter((e) => typeof e.index === 'number')
      .map((e) => [e.index as number, e])),
    [validation],
  );

  const preview = useMemo(() => draft.join('\n'), [draft]);

  return (
    <div data-testid="sox-effect-builder" style={{ border: '1px solid #444', borderRadius: 6, padding: 10 }}>
      <div style={{ color: '#888', fontSize: 12, marginBottom: 6 }}>SoX Effects Pipeline</div>

      {draft.map((effect, index) => {
        const error = errorForIndex.get(index);
        const hasError = Boolean(error) || validation?.isValid === false && errorForIndex.size === 0;
        return (
          <div key={index} style={effectRowStyle(hasError)}>
            {editIndex === index ? (
              <input
                data-testid={`sox-edit-${index}`}
                value={editValue}
                onChange={(e) => setEditValue(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    const next = [...draft];
                    next[index] = editValue.trim();
                    commit(next);
                    setEditIndex(null);
                  } else if (e.key === 'Escape') {
                    setEditIndex(null);
                  }
                }}
                autoFocus
                style={inputStyle}
              />
            ) : (
              <span
                data-testid={`sox-effect-${index}`}
                style={{ flex: 1, fontFamily: 'monospace', fontSize: 12, color: hasError ? '#f66' : '#ddd' }}
                onDoubleClick={() => { setEditIndex(index); setEditValue(effect); }}
                title={error?.message ?? effect}
              >
                {effect}
              </span>
            )}
            <button style={tinyButtonStyle} onClick={() => moveEffect(index, -1)} disabled={index === 0} title="Move up" aria-label={`Move effect ${index + 1} up`}>↑</button>
            <button style={tinyButtonStyle} onClick={() => moveEffect(index, 1)} disabled={index === draft.length - 1} title="Move down" aria-label={`Move effect ${index + 1} down`}>↓</button>
            <button data-testid={`sox-remove-${index}`} style={tinyButtonStyle} onClick={() => removeEffect(index)} title="Remove" aria-label={`Remove effect ${index + 1}`}>✕</button>
          </div>
        );
      })}

      <div style={{ display: 'flex', gap: 6, marginTop: 6 }}>
        <input
          data-testid="sox-new-effect"
          value={newEffect}
          onChange={(e) => setNewEffect(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') { addEffect(); } }}
          placeholder="e.g. reverb 50"
          disabled={disabled}
          style={{ ...inputStyle, flex: 1 }}
        />
        <button
          data-testid="sox-add-effect"
          onClick={addEffect}
          disabled={disabled || !newEffect.trim()}
          style={{ ...smallButtonStyle, border: '1px solid #4a90d9', borderRadius: 3, color: '#8ab4f8' }}
        >
          Add
        </button>
      </div>

      {validation && !validation.isValid && (
        <div data-testid="sox-validation-errors" style={{ color: '#f66', fontSize: 11, marginTop: 6 }}>
          {validation.errors.slice(0, 3).map((e, i) => (
            <div key={i}>
              ⚠ {e.message}
              {e.code === 'UNKNOWN_EFFECT' && /\bnormalize\b/i.test(e.message) && (
                <button
                  data-testid={`sox-suggest-norm-${e.index ?? 0}`}
                  style={{ marginLeft: 6, background: 'transparent', border: '1px solid #8ab4f8', color: '#8ab4f8', borderRadius: 3, cursor: 'pointer', fontSize: 10, padding: '0 6px' }}
                  onClick={() => {
                    // Replace 'normalize' with 'norm' in the offending chain
                    const idx = e.index ?? 0;
                    const next = [...draft];
                    if (next[idx]) next[idx] = next[idx].replace(/\bnormalize\b/gi, 'norm');
                    commit(next);
                  }}
                >
                  Fix: use 'norm'
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      <div data-testid="sox-command-preview"
           style={{ marginTop: 8, padding: 6, background: '#111', borderRadius: 4, fontFamily: 'monospace', fontSize: 11, color: '#8ab4f8', whiteSpace: 'pre-wrap' }}>
        sox in.wav out.wav {preview}
      </div>
    </div>
  );
};

function effectRowStyle(hasError: boolean): React.CSSProperties {
  return {
    display: 'flex',
    alignItems: 'center',
    gap: 4,
    padding: '3px 4px',
    background: hasError ? 'rgba(255, 102, 102, 0.08)' : '#242424',
    borderRadius: 3,
    marginBottom: 3,
  };
}

const inputStyle: React.CSSProperties = {
  background: '#1a1a1a',
  color: '#ddd',
  border: '1px solid #444',
  borderRadius: 3,
  padding: '3px 6px',
  fontSize: 12,
};

const tinyButtonStyle: React.CSSProperties = {
  background: 'transparent',
  border: 'none',
  color: '#aaa',
  cursor: 'pointer',
  fontSize: 11,
  padding: '2px 4px',
};

const smallButtonStyle: React.CSSProperties = {
  background: 'transparent',
  border: 'none',
  cursor: 'pointer',
  color: '#ddd',
  fontSize: 12,
};