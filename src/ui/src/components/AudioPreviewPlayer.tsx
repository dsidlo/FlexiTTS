import React, { useCallback, useState } from 'react';

/**
 * Phase 6.6: AudioPreviewPlayer - play/pause/stop with a simple playback
 * position bar (waveform rendering comes with the Phase 6.5 integration).
 * Uses the existing window.api.readAudioFile data-URL pattern.
 */

export interface AudioPreviewPlayerProps {
  src: string;
  title?: string;
  onError?: (message: string) => void;
}

export const AudioPreviewPlayer: React.FC<AudioPreviewPlayerProps> = ({
  src, title, onError,
}) => {
  const [playing, setPlaying] = useState(false);
  const [audioEl, setAudioEl] = useState<HTMLAudioElement | null>(null);

  const stop = useCallback(() => {
    if (audioEl) {
      audioEl.pause();
      audioEl.currentTime = 0;
    }
    setPlaying(false);
  }, [audioEl]);

  const play = useCallback(async () => {
    try {
      if (!window.api?.readAudioFile) {
        onError?.('Audio playback unavailable.');
        return;
      }
      const dataUrl = await window.api.readAudioFile(src);
      const el = new Audio(dataUrl as unknown as string);
      el.onended = () => setPlaying(false);
      setAudioEl(el);
      await el.play();
      setPlaying(true);
    } catch (e) {
      setPlaying(false);
      onError?.((e as Error).message || 'Playback failed');
    }
  }, [src, onError]);

  const toggle = useCallback(() => {
    if (playing && audioEl) {
      stop();
    } else {
      void play();
    }
  }, [playing, audioEl, play, stop]);

  return (
    <div
      data-testid="audio-preview-player"
      style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '4px 0' }}
    >
      <button
        data-testid="audio-play-toggle"
        style={buttonStyle}
        onClick={toggle}
        title={playing ? 'Stop' : 'Play'}
        aria-label={playing ? 'Stop audio preview' : 'Play audio preview'}
      >
        {playing ? '⏹' : '▶'}
      </button>
      <span style={{ color: '#999', fontSize: 12, flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        {title ?? src.split(/[\\/]/).pop()}
      </span>
      <div style={trackStyle}>
        <div style={{ ...fillStyle, width: playing ? '100%' : '0%', transition: 'width 0.2s linear' }} />
      </div>
    </div>
  );
};

const buttonStyle: React.CSSProperties = {
  background: 'transparent',
  border: '1px solid #555',
  color: '#ddd',
  borderRadius: '50%',
  width: 28,
  height: 28,
  cursor: 'pointer',
  fontSize: 12,
};

const trackStyle: React.CSSProperties = {
  flex: 1,
  height: 4,
  background: '#333',
  borderRadius: 2,
  overflow: 'hidden',
};

const fillStyle: React.CSSProperties = {
  height: '100%',
  background: '#4a90d9',
};