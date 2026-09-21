import { useCallback, useEffect, useRef, useState } from 'react';
import { PythonBridgeService, getTtsWsStatus } from '../services/pythonBridge';
import { debugLog } from '../utils/debugLogger';
import { alerts } from '../services/alertService';

/**
 * Phase 12.1: Network error handling for the TTS service connection.
 *
 * Tracks connectivity via getTtsWsStatus polling and WebSocket events, and
 * provides a retry mechanism with exponential backoff (1s, 2s, 4s, ... up to
 * 30s). The UI shows an offline indicator when the TTS WebSocket is down,
 * with a Retry button.
 */

export interface UseTtsConnectivityOptions {
  /** Poll interval for connectivity checks (ms). */
  pollMs?: number;
  /** Whether polling is active. */
  enabled?: boolean;
}

export interface TtsConnectivity {
  /** True when the TTS WebSocket is connected (and service ready). */
  online: boolean;
  /** True while a retry/backoff sequence is in progress. */
  retrying: boolean;
  /** Human-readable description of the current backoff delay. */
  nextRetryInMs: number | null;
  /** How many retries have been attempted since going offline. */
  attempt: number;
  /** Manually trigger a reconnect attempt now. */
  retryNow: () => void;
  /**
   * True during the initial startup window: the app has just launched and is
   * still within the grace period before the offline banner shows. The UI
   * renders a green "Connecting to TTS service…" bar during this phase.
   */
  connecting: boolean;
}

const BASE_DELAY_MS = 1000;
const MAX_DELAY_MS = 30000;
/** Startup grace period: show green "connecting" instead of the offline
 * banner for this long after app launch before declaring the service
 * offline. Matches the TTS service warmup budget. */
const STARTUP_GRACE_MS = 30000;

export const useTtsConnectivity = (options: UseTtsConnectivityOptions = {}): TtsConnectivity => {
  const { pollMs = 3000, enabled = true } = options;
  const [online, setOnline] = useState<boolean>(() => getTtsWsStatus().isConnected && getTtsWsStatus().isReady);
  const [retrying, setRetrying] = useState(false);
  const [nextRetryInMs, setNextRetryInMs] = useState<number | null>(null);
  const [attempt, setAttempt] = useState(0);
  const attemptRef = useRef(0);
  const retryTimerRef = useRef<number | null>(null);
  // Startup grace: green "connecting" phase before the offline banner shows
  const mountedAtRef = useRef<number>(Date.now());
  const [connecting, setConnecting] = useState<boolean>(true);
  const autoRetryRef = useRef<number | null>(null);

  // Poll the shared status (set by useTtsAlerts)
  useEffect(() => {
    if (!enabled) return;
    const interval = window.setInterval(() => {
      const st = getTtsWsStatus();
      const up = st.isConnected && st.isReady;
      if (up) setConnecting(false);
      setOnline((prev) => {
        if (prev && !up) {
          // Just went offline: reset retry bookkeeping
          attemptRef.current = 0;
          setAttempt(0);
          setRetrying(false);
          setNextRetryInMs(null);
        }
        return up;
      });
    }, pollMs);
    return () => window.clearInterval(interval);
  }, [pollMs, enabled]);

  // Startup grace: stay in green "connecting" phase until online or the
  // grace window elapses; then hand over to the offline banner + backoff.
  useEffect(() => {
    if (!enabled) return;
    const elapsed = Date.now() - mountedAtRef.current;
    const remaining = STARTUP_GRACE_MS - elapsed;
    if (remaining <= 0) {
      setConnecting(false);
      return;
    }
    const t = window.setTimeout(() => {
      setConnecting(false);
      // Grace expired while still offline: kick the automatic retry chain.
      const st = getTtsWsStatus();
      if (!(st.isConnected && st.isReady) && !retryingRef.current) {
        retryNowRef.current();
      }
    }, remaining);
    return () => window.clearTimeout(t);
  }, [enabled, online]);

  const retryNow = useCallback(() => {
    void (async () => {
      setRetrying(true);
      try {
        const ok = await PythonBridgeService.startAndConnectTtsService();
        if (ok) {
          attemptRef.current = 0;
          setAttempt(0);
          setRetrying(false);
          setNextRetryInMs(null);
          setOnline(true);
          debugLog.info('useTtsConnectivity', 'retry succeeded');
          return;
        }
      } catch (e) {
        debugLog.warn('useTtsConnectivity', 'retry attempt failed', { error: String(e) });
      }
      // Exponential backoff for the next attempt
      attemptRef.current += 1;
      setAttempt(attemptRef.current);
      const delay = Math.min(BASE_DELAY_MS * 2 ** (attemptRef.current - 1), MAX_DELAY_MS);
      setNextRetryInMs(delay);
      setRetrying(false);
      window.setTimeout(() => {
        alerts.info('Retrying TTS connection…');
        retryNowRef.current();
      }, delay);
    })();
  }, []);

  // Stable self-reference for the backoff timer
  const retryNowRef = useRef<() => void>(retryNow);
  retryNowRef.current = retryNow;
  const retryingRef = useRef(retrying);
  retryingRef.current = retrying;

  // Clear backoff timers on unmount
  useEffect(() => () => {
    if (retryTimerRef.current) window.clearTimeout(retryTimerRef.current);
  }, []);

  // While in the startup connecting phase, auto-retry each poll cycle so a
  // slow warmup still gets connection attempts without user interaction.
  useEffect(() => {
    if (!enabled || !connecting || online || retrying) return;
    const t = window.setTimeout(() => {
      if (!retryingRef.current) {
        debugLog.info('useTtsConnectivity', 'auto-retry during startup connecting phase');
        retryNowRef.current();
      }
    }, 3000);
    autoRetryRef.current = t;
    return () => window.clearTimeout(t);
  }, [enabled, connecting, online, retrying]);

  // Clear auto-retry timer on unmount
  useEffect(() => () => {
    if (autoRetryRef.current) window.clearTimeout(autoRetryRef.current);
  }, []);

  return { online, retrying, nextRetryInMs, attempt, retryNow, connecting };
};

// Keep MAX_DELAY_MS referenced (documents the cap for readers)
void MAX_DELAY_MS;