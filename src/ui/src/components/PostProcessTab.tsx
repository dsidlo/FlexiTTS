import React, { useCallback, useState } from 'react';
import { SoXEffectBuilder } from './SoXEffectBuilder';
import { PythonBridgeService } from '../services/pythonBridge';

/**
 * Phase 7T.3: Story Post-Process tab - edit the global
 * story-audio-post-process.sox-effects chain.
 */

export interface PostProcessTabProps {
  storyDir: string;
  effects: string[];
  onEffectsChanged: (effects: string[]) => void;
  onError: (message: string) => void;
  dirty: boolean;
  onSaved: () => void;
}

export const PostProcessTab: React.FC<PostProcessTabProps> = ({
  storyDir, effects, onEffectsChanged, onError, dirty, onSaved,
}) => {
  const [saving, setSaving] = useState(false);

  const save = useCallback(async (next: string[]) => {
    setSaving(true);
    try {
      const r = await PythonBridgeService.runBridgeCommand([
        'set-post-process', storyDir, JSON.stringify(next),
      ]);
      if (r.success) onSaved();
      else onError(r.error || 'Save failed');
    } catch (e) {
      onError((e as Error).message);
    } finally {
      setSaving(false);
    }
  }, [storyDir, onSaved, onError]);

  return (
    <div data-testid="post-process-tab" style={{ padding: 8 }}>
      <div style={{ color: '#888', fontSize: 12, marginBottom: 8 }}>
        Applied after the final full chapter audio file is created.
        {dirty && <span style={{ color: '#ff9800' }}> ● unsaved changes</span>}
      </div>
      <SoXEffectBuilder
        effects={effects}
        onChanged={onEffectsChanged}
      />
      <button
        data-testid="post-process-save"
        style={{ marginTop: 8, border: '1px solid #4a90d9', borderRadius: 4, color: '#8ab4f8', background: 'transparent', cursor: 'pointer', padding: '4px 12px', fontSize: 12 }}
        onClick={() => void save(effects)}
        disabled={saving || !dirty}
        aria-label="Save post-process chain"
      >
        {saving ? 'Saving…' : 'Save Post-Process Chain'}
      </button>
    </div>
  );
};