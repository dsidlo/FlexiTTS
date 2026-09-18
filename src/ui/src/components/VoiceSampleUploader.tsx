import React, { useCallback, useRef, useState } from 'react';
import { PythonBridgeService } from '../services/pythonBridge';

/**
 * Phase 6.4: VoiceSampleUploader - drag-drop zone with file picker fallback
 * for uploading voice samples to a character/emotion via the bridge.
 */

const ACCEPTED_EXTENSIONS = ['.wav', '.mp3', '.ogg'];
const DEFAULT_MAX_BYTES = 50 * 1024 * 1024;

async function readFileBytes(file: File): Promise<Uint8Array> {
  // jsdom's File lacks arrayBuffer(); FileReader works in both jsdom and
  // real browsers.
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(new Uint8Array(reader.result as ArrayBuffer));
    reader.onerror = () => reject(new Error(`Cannot read file: ${file.name}`));
    reader.readAsArrayBuffer(file);
  });
}

export interface VoiceSampleUploaderProps {
  storyDir: string;
  characterId: string;
  emotionId?: string | null;
  maxBytes?: number;
  onUploaded: (filename: string) => void;
  onError: (message: string) => void;
}

export const VoiceSampleUploader: React.FC<VoiceSampleUploaderProps> = ({
  storyDir, characterId, emotionId, maxBytes = DEFAULT_MAX_BYTES, onUploaded, onError,
}) => {
  const [dragOver, setDragOver] = useState(false);
  const [progress, setProgress] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const upload = useCallback(async (file: File) => {
    const name = file.name.toLowerCase();
    if (!ACCEPTED_EXTENSIONS.some((ext) => name.endsWith(ext))) {
      onError(`Unsupported format. Accepted: ${ACCEPTED_EXTENSIONS.join(', ')}`);
      return;
    }
    if (file.size > maxBytes) {
      onError(`File exceeds size limit (${Math.round(maxBytes / (1024 * 1024))} MiB).`);
      return;
    }
    setProgress(`Uploading ${file.name}…`);
    try {
      const bytes = await readFileBytes(file);
      // Binary-safe base64 without spread (large files)
      let binary = '';
      const chunk = 0x8000;
      for (let i = 0; i < bytes.length; i += chunk) {
        binary += String.fromCharCode.apply(null, [
          ...bytes.subarray(i, i + chunk),
        ] as unknown as number[]);
      }
      const base64 = btoa(binary);
      const result = await PythonBridgeService.runBridgeCommand([
        'upload-sample', storyDir, characterId,
        emotionId ?? '-', file.name, base64,
      ]);
      if (!result.success) {
        throw new Error(result.error || 'Upload failed');
      }
      setProgress(null);
      onUploaded(result.sample?.filename ?? file.name);
    } catch (e) {
      setProgress(null);
      onError((e as Error).message);
    }
  }, [storyDir, characterId, emotionId, maxBytes, onUploaded, onError]);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files?.[0];
    if (file) void upload(file);
  }, [upload]);

  const handleBrowse = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) void upload(file);
    e.target.value = '';
  }, [upload]);

  return (
    <div
      data-testid={`sample-uploader-${characterId}${emotionId ? `-${emotionId}` : ''}`}
      onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
      onDragLeave={() => setDragOver(false)}
      onDrop={handleDrop}
      style={{
        border: dragOver ? '2px dashed #4a90d9' : '2px dashed #555',
        borderRadius: 6,
        padding: 10,
        textAlign: 'center',
        color: dragOver ? '#4a90d9' : '#888',
        fontSize: 12,
        background: dragOver ? 'rgba(74, 144, 217, 0.08)' : 'transparent',
      }}
    >
      <div>Drop audio file here (.wav / .mp3 / .ogg)</div>
      <button
        data-testid={`sample-browse-${characterId}${emotionId ? `-${emotionId}` : ''}`}
        style={browseStyle}
        onClick={() => inputRef.current?.click()}
      >
        Browse Files
      </button>
      <input
        ref={inputRef}
        type="file"
        accept=".wav,.mp3,.ogg"
        style={{ display: 'none' }}
        onChange={handleBrowse}
      />
      {progress && (
        <div style={{ marginTop: 6 }}>
          <div style={{ height: 4, background: '#333', borderRadius: 2, overflow: 'hidden' }}>
            <div style={{ height: '100%', width: '100%', background: '#4a90d9', animation: 'p6b-progress 1.2s ease-in-out' }} />
          </div>
          <div style={{ marginTop: 4, color: '#8ab4f8', fontSize: 11 }}>{progress}</div>
        </div>
      )}
    </div>
  );
};

const browseStyle: React.CSSProperties = {
  marginTop: 6,
  background: 'transparent',
  border: '1px solid #555',
  color: '#ccc',
  borderRadius: 4,
  cursor: 'pointer',
  padding: '3px 10px',
  fontSize: 12,
};