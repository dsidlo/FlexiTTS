import { useEffect, useRef, useCallback } from 'react';
import type { AlertType } from './useAlerts';
import { setTtsWsStatus } from '../services/pythonBridge';
import { debugLog } from '../utils/debugLogger';

export interface TtsAlertMessage {
  type: 'alert';
  alertType: AlertType;
  message: string;
  source: 'tts-service';
  metadata?: {
    chapter?: string;
    section?: string;
    dialog?: string;
    character?: string;
    // Additional context for the alert
  };
}

export interface TtsStatusMessage {
  type: 'status';
  status: string;
  ready: boolean;
  cached: boolean;
}

export type TtsMessage = TtsAlertMessage | TtsStatusMessage;

export interface UseTtsAlertsOptions {
  enabled?: boolean;
  onAlert?: (alert: TtsAlertMessage) => void;
  onStatus?: (status: TtsStatusMessage) => void;
  onConnect?: () => void;
  onDisconnect?: () => void;
  onError?: (error: Event) => void;
}

export interface UseTtsAlertsReturn {
  connect: () => void;
  disconnect: () => void;
  isConnected: boolean;
}

const DEFAULT_WS_URL = 'ws://localhost:8765';
const RECONNECT_DELAY = 5000;

/**
 * Hook for listening to TTS service alerts via WebSocket
 * The TTS service sends alert messages that can be displayed to the user
 */
export function useTtsAlerts(options: UseTtsAlertsOptions = {}): UseTtsAlertsReturn {
  const logId = 'useTtsAlerts';
  const {
    enabled = true,
    onAlert,
    onStatus,
    onConnect,
    onDisconnect,
    onError
  } = options;

  const wsRef = useRef<WebSocket | null>(null);
  const isConnectedRef = useRef(false);
  const reconnectTimeoutRef = useRef<number | null>(null);
  const shouldReconnectRef = useRef(true);
  const connectAttemptInFlightRef = useRef(false);

  const disconnect = useCallback(() => {
    debugLog.info(logId, 'disconnect called', {
      hasSocket: Boolean(wsRef.current),
      readyState: wsRef.current?.readyState,
      reconnectPending: Boolean(reconnectTimeoutRef.current),
    });
    shouldReconnectRef.current = false;
    
    if (reconnectTimeoutRef.current) {
      window.clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    
    isConnectedRef.current = false;
    connectAttemptInFlightRef.current = false;
    setTtsWsStatus(false, false);
  }, []);

  const connect = useCallback(() => {
    debugLog.info(logId, 'connect called', {
      enabled,
      existingReadyState: wsRef.current?.readyState,
    });
    // Prevent multiple concurrent connection attempts
    if (!enabled || connectAttemptInFlightRef.current || wsRef.current?.readyState === WebSocket.OPEN || wsRef.current?.readyState === WebSocket.CONNECTING) {
      debugLog.info(logId, 'connect skipped', {
        enabled,
        connectAttemptInFlight: connectAttemptInFlightRef.current,
        existingReadyState: wsRef.current?.readyState,
      });
      return;
    }

    connectAttemptInFlightRef.current = true;

    shouldReconnectRef.current = true;

    try {
      debugLog.info(logId, 'opening websocket', { url: DEFAULT_WS_URL });
      const ws = new WebSocket(DEFAULT_WS_URL);
      
      ws.onopen = () => {
        connectAttemptInFlightRef.current = false;
        debugLog.info(logId, 'websocket open', { url: DEFAULT_WS_URL });
        console.log('[TTS Alerts] Connected to TTS service');
        isConnectedRef.current = true;
        setTtsWsStatus(true, false); // Connected but not yet known if ready
        onConnect?.();
      };

      ws.onmessage = (event) => {
        try {
          debugLog.info(logId, 'websocket raw message received', {
            rawType: typeof event.data,
            rawData: typeof event.data === 'string' ? event.data : '[non-string]',
          });
          const data: TtsMessage = JSON.parse(event.data);
          debugLog.info(logId, 'websocket parsed message', { data });
          
          if (data.type === 'alert') {
            debugLog.info(logId, 'websocket alert branch', {
              message: data.message,
              alertType: (data as TtsAlertMessage).alertType,
              metadata: (data as TtsAlertMessage).metadata,
            });
            console.log('[TTS Alerts] Received alert:', data.message);
            // Detect "TTS Service: Ready" alert and update ready status
            if (data.message === 'TTS Service: Ready') {
              console.log('[TTS Alerts] Detected ready alert, updating status');
              setTtsWsStatus(true, true);
            }
            onAlert?.(data as TtsAlertMessage);
          } else if (data.type === 'status') {
            debugLog.info(logId, 'websocket status branch', {
              status: data.status,
              ready: (data as TtsStatusMessage).ready,
              cached: (data as TtsStatusMessage).cached,
            });
            console.log('[TTS Alerts] Received status:', data.status);
            // Update ready status from server status message
            const isReady = data.status === 'ready' || (data as TtsStatusMessage).ready;
            setTtsWsStatus(true, isReady);
            onStatus?.(data as TtsStatusMessage);
          }
        } catch (err) {
          debugLog.exception(logId, 'Failed to parse websocket message', err, {
            rawData: typeof event.data === 'string' ? event.data : '[non-string]',
          });
          console.error('[TTS Alerts] Failed to parse message:', err);
        }
      };

      ws.onerror = (error) => {
        connectAttemptInFlightRef.current = false;
        debugLog.error(logId, 'websocket error', { error });
        console.error('[TTS Alerts] WebSocket error:', error);
        onError?.(error);
      };

      ws.onclose = () => {
        connectAttemptInFlightRef.current = false;
        debugLog.info(logId, 'websocket closed', {
          shouldReconnect: shouldReconnectRef.current,
          reconnectDelayMs: RECONNECT_DELAY,
        });
        console.log('[TTS Alerts] Disconnected from TTS service');
        isConnectedRef.current = false;
        setTtsWsStatus(false, false); // Mark as disconnected
        onDisconnect?.();

        // Attempt to reconnect after delay
        if (shouldReconnectRef.current) {
          reconnectTimeoutRef.current = window.setTimeout(() => {
            debugLog.info(logId, 'attempting reconnect');
            console.log('[TTS Alerts] Attempting to reconnect...');
            connect();
          }, RECONNECT_DELAY);
        }
      };

      wsRef.current = ws;
      debugLog.info(logId, 'websocket ref assigned', { readyState: ws.readyState });
    } catch (err) {
      debugLog.exception(logId, 'Failed to connect websocket', err);
      console.error('[TTS Alerts] Failed to connect:', err);
    }
  }, [enabled, onAlert, onStatus, onConnect, onDisconnect, onError]);

  // Auto-connect on mount if enabled
  useEffect(() => {
    if (enabled) {
      connect();
    }

    return () => {
      disconnect();
    };
  }, [enabled, connect, disconnect]);

  return {
    connect,
    disconnect,
    get isConnected() {
      return isConnectedRef.current;
    }
  };
}

export default useTtsAlerts;
