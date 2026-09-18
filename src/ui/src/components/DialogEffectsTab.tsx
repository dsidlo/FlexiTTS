import React, { useCallback, useEffect, useState } from 'react';
import { SoXEffectBuilder } from './SoXEffectBuilder';
import { PythonBridgeService } from '../services/pythonBridge';

/**
 * Phase 7T.2: Dialog Effects tab - list named dialog-effects with editable
 * SoX chains; add, delete, rename with propagation to referencing characters.
 */

export interface DialogEffectsTabProps {
  storyDir: string;
  onRefresh: () => void;
  onError: (message: string) => void;
}

interface DialogEffect {
  name: string;
  'sox-effects': string[];
}

export const DialogEffectsTab: React.FC<DialogEffectsTabProps> = ({
  storyDir, onRefresh, onError,
}) => {
  const [effects, setEffects] = useState<DialogEffect[]>([]);
  const [loading, setLoading] = useState(true);
  const [newName, setNewName] = useState('');
  const [dirty, setDirty] = useState<Set<string>>(new Set());
  const [confirmingDelete, setConfirmingDelete] = useState<string | null>(null);
  const [dependentCount, setDependentCount] = useState(0);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const r = await PythonBridgeService.runBridgeCommand(['list-dialog-effects', storyDir]);
      if (r.success) setEffects(r.dialogEffects as DialogEffect[]);
    } catch (e) {
      onError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [storyDir, onError]);

  useEffect(() => {
    void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [storyDir]);

  const addEffect = useCallback(async () => {
    const name = newName.trim();
    if (!name) return;
    try {
      const r = await PythonBridgeService.runBridgeCommand([
        'create-dialog-effect-stub', storyDir, name,
      ]);
      if (r.success) {
        setNewName('');
        await refresh();
        onRefresh();
      }
    } catch (e) {
      onError((e as Error).message);
    }
  }, [newName, storyDir, onRefresh, onError]);

  const saveEffect = useCallback(async (name: string, soxEffects: string[]) => {
    try {
      const r = await PythonBridgeService.runBridgeCommand([
        'update-dialog-effect', storyDir, name,
        JSON.stringify({ name, 'sox-effects': soxEffects }),
      ]);
      if (r.success) {
        setDirty((prev) => { const next = new Set(prev); next.delete(name); return next; });
        onRefresh();
      }
    } catch (e) {
      onError((e as Error).message);
    }
  }, [storyDir, onRefresh, onError]);

  const renameEffect = useCallback(async (oldName: string, newName: string) => {
    try {
      const r = await PythonBridgeService.runBridgeCommand([
        'update-dialog-effect', storyDir, oldName,
        JSON.stringify({ name: newName }),
      ]);
      if (r.success) {
        onRefresh();
      } else {
        onError(r.error || 'Rename failed');
      }
    } catch (e) {
      onError((e as Error).message);
    }
  }, [storyDir, onRefresh, onError]);

  const deleteEffect = useCallback(async (name: string) => {
    try {
      const r = await PythonBridgeService.runBridgeCommand([
        'delete-dialog-effect', storyDir, name,
      ]);
      if (r.success) {
        setConfirmingDelete(null);
        onRefresh();
      } else if (r.code === 'DIALOG_EFFECT_IN_USE') {
        // Parse dependents from the error message
        const msg = String(r.error ?? '');
        const match = msg.match(/referenced by characters: (.*)/);
        setDependentCount(match ? match[1].split(',').length : 0);
        setConfirmingDelete(name);
      }
    } catch (e) {
      onError((e as Error).message);
    }
  }, [storyDir, onRefresh, onError]);

  return (
    <div data-testid="dialog-effects-tab" style={{ padding: 8 }}>
      <div style={{ display: 'flex', gap: 6, marginBottom: 10 }}>
        <input
          data-testid="dialog-effect-new-name"
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') void addEffect(); }}
          placeholder="New dialog-effect name…"
          style={{ flex: 1, background: '#242424', color: '#ddd', border: '1px solid #444', borderRadius: 4, padding: '4px 8px', fontSize: 13 }}
        />
        <button
          data-testid="dialog-effect-add"
          style={{ border: '1px solid #4a90d9', borderRadius: 4, color: '#8ab4f8', background: 'transparent', cursor: 'pointer', padding: '4px 10px', fontSize: 12 }}
          onClick={() => void addEffect()}
          disabled={!newName.trim()}
        >
          Add
        </button>
      </div>
      {loading && <div style={{ color: '#888' }}>Loading effects…</div>}
      {effects.map((eff) => (
        <div key={eff.name} data-testid={`dialog-effect-entry-${eff.name}`} style={entryStyle}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
            <strong style={{ fontSize: 13 }}>{eff.name}</strong>
            {dirty.has(eff.name) && <span style={{ color: '#ff9800', fontSize: 10 }}>● unsaved</span>}
          </div>
          <SoXEffectBuilder
            effects={eff['sox-effects'] ?? []}
            onChanged={(next) => {
              setDirty((prev) => new Set(prev).add(eff.name));
              void saveEffect(eff.name, next);
            }}
          />
          <div style={{ display: 'flex', gap: 6, marginTop: 4 }}>
            <button
              data-testid={`dialog-effect-rename-${eff.name}`}
              style={smallButtonStyle}
              onClick={() => {
                const newName = window.prompt(`Rename '${eff.name}' to:`);
                if (newName && newName.trim() !== eff.name) void renameEffect(eff.name, newName.trim());
              }}
            >
              Rename
            </button>
            <button
              data-testid={`dialog-effect-delete-${eff.name}`}
              style={smallButtonStyle}
              onClick={() => void deleteEffect(eff.name)}
            >
              Delete
            </button>
          </div>
          {confirmingDelete === eff.name && (
            <div data-testid={`dialog-effect-dependents-${eff.name}`} style={warningStyle}>
              ⚠ {dependentCount} character(s) reference this effect. Unlink them first.
            </div>
          )}
        </div>
      ))}
      {!loading && effects.length === 0 && (
        <div style={{ color: '#666', fontSize: 12 }}>No dialog effects defined.</div>
      )}
    </div>
  );
};

const entryStyle: React.CSSProperties = {
  border: '1px solid #333',
  borderRadius: 6,
  padding: 8,
  marginBottom: 8,
  background: '#222',
};

const warningStyle: React.CSSProperties = {
  color: '#ff9800',
  fontSize: 11,
  marginTop: 4,
  padding: '4px 8px',
  background: 'rgba(255, 152, 0, 0.08)',
  borderRadius: 4,
};

const smallButtonStyle: React.CSSProperties = {
  background: 'transparent',
  border: '1px solid #555',
  color: '#ccc',
  borderRadius: 3,
  cursor: 'pointer',
  fontSize: 11,
  padding: '2px 8px',
};