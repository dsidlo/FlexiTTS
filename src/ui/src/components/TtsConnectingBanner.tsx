import { useTtsConnectivity } from '../hooks';

/**
 * Startup TTS connection banners.
 *
 * Two phases, driven by useTtsConnectivity:
 * - connecting (first STARTUP_GRACE_MS = 30s): green "Connecting to TTS
 *   service…" bar with an auto-retry indicator. No user action needed.
 * - after grace, if still offline: the red offline banner with backoff
 *   countdown and a manual Retry button.
 *
 * Extracted from App.tsx so both banners are individually testable.
 */
export function TtsConnectingBanner({ connecting, online }: { connecting: boolean; online: boolean }) {
  if (!connecting || online) return null;
  return (
    <div
      role="status"
      aria-live="polite"
      data-testid="tts-connecting-banner"
      style={{
        display: 'flex', alignItems: 'center', gap: 10, padding: '6px 14px',
        background: '#1d3a1d', color: '#d7ffd7', borderBottom: '1px solid #3a3',
        fontSize: 13,
      }}
    >
      <span
        aria-hidden="true"
        data-testid="tts-connecting-indicator"
        style={{ display: 'inline-block', width: 10, height: 10, borderRadius: '50%', background: '#4caf50', animation: 'pulse 1.2s ease-in-out infinite' }}
      />
      <span>Connecting to TTS service…</span>
      <span style={{ marginLeft: 'auto', opacity: 0.7 }}>auto-retrying</span>
    </div>
  );
}

/** Convenience hook-based wrapper for App usage. */
export function TtsConnectionBanners() {
  const tts = useTtsConnectivity({ enabled: true });
  return (
    <>
      <TtsConnectingBanner connecting={tts.connecting} online={tts.online} />
    </>
  );
}
