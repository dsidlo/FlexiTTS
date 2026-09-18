import React, { useCallback, useEffect, useState } from 'react';
import { PythonBridgeService } from '../services/pythonBridge';

/**
 * Phase 6b.3: Unresolved references panel.
 * Lists every red (unsatisfied) reference across all characters with
 * jump-to-field links, and drives the settings-icon count badge.
 */

export interface UnresolvedRef {
  character: string;
  type: string;
  value: string;
}

export function useUnresolvedReferences(storyDir: string, reloadKey: number) {
  const [unresolved, setUnresolved] = useState<UnresolvedRef[]>([]);
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    if (!storyDir) {
      setUnresolved([]);
      return;
    }
    setLoading(true);
    try {
      const r = await PythonBridgeService.runBridgeCommand(['list-references', storyDir]);
      if (r.success) setUnresolved(r.unresolved as UnresolvedRef[]);
    } catch {
      setUnresolved([]); // bridge unavailable; leave panel empty
    } finally {
      setLoading(false);
    }
  }, [storyDir]);

  useEffect(() => {
    void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [storyDir, reloadKey]);

  return { unresolved, loading, refresh };
}

export interface UnresolvedReferencesPanelProps {
  unresolved: UnresolvedRef[];
  onJump: (characterId: string) => void;
  onCreateStub: (type: string, value: string) => void;
}

export const UnresolvedReferencesPanel: React.FC<UnresolvedReferencesPanelProps> = ({
  unresolved, onJump, onCreateStub,
}) => {
  if (unresolved.length === 0) {
    return (
      <div data-testid="references-panel-clear" style={panelStyle}>
        <span style={{ color: '#7ac47a' }}>✓ All references satisfied</span>
      </div>
    );
  }
  return (
    <div data-testid="references-panel" style={{ ...panelStyle, borderColor: '#a55' }}>
      <div style={{ fontWeight: 600, color: '#f66', marginBottom: 4 }}>
        {unresolved.length} unresolved reference{unresolved.length > 1 ? 's' : ''}
      </div>
      {unresolved.map((ref, i) => (
        <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, padding: '2px 0' }}>
          <button
            data-testid={`reference-jump-${ref.character}`}
            style={jumpButtonStyle}
            onClick={() => onJump(ref.character)}
            title={`Go to ${ref.character}`}
          >
            {ref.character}
          </button>
          <span style={{ color: '#f66' }}>{ref.value}</span>
          {ref.type === 'dialog-effects' && (
            <button
              data-testid={`reference-stub-${ref.value}`}
              style={stubButtonStyle}
              onClick={() => onCreateStub(ref.type, ref.value)}
              title={`Create a stub dialog-effect named '${ref.value}'`}
            >
              Create stub
            </button>
          )}
        </div>
      ))}
    </div>
  );
};

const panelStyle: React.CSSProperties = {
  padding: '6px 10px',
  fontSize: 12,
  border: '1px solid #444',
  borderRadius: 6,
  marginBottom: 8,
};

const jumpButtonStyle: React.CSSProperties = {
  background: 'transparent',
  border: 'none',
  color: '#8ab4f8',
  cursor: 'pointer',
  fontSize: 12,
  padding: 0,
  textDecoration: 'underline',
};

const stubButtonStyle: React.CSSProperties = {
  background: 'transparent',
  border: '1px solid #888',
  color: '#ddd',
  borderRadius: 3,
  cursor: 'pointer',
  fontSize: 10,
  padding: '1px 6px',
  marginLeft: 'auto',
};

// Compatibility alias used by the dialog
export const onCommitStub = undefined as unknown as (type: string, value: string) => void;