import { useEffect, useRef, useCallback } from 'react';
import type { AlertType } from './useAlerts';
import { setTtsWsStatus } from '../services/pythonBridge';

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

  const disconnect = useCallback(() => {
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
    setTtsWsStatus(false, false);
  }, []);

  const connect = useCallback(() => {
    // Prevent multiple concurrent connection attempts
    if (!enabled || wsRef.current?.readyState === WebSocket.OPEN || wsRef.current?.readyState === WebSocket.CONNECTING) {
      return;
    }

    shouldReconnectRef.current = true;

    try {
      const ws = new WebSocket(DEFAULT_WS_URL);
      
      ws.onopen = () => {
        console.log('[TTS Alerts] Connected to TTS service');
        isConnectedRef.current = true;
        setTtsWsStatus(true, false); // Connected but not yet known if ready
        onConnect?.();
      };

      ws.onmessage = (event) => {
        try {
          const data: TtsMessage = JSON.parse(event.data);
          
          if (data.type === 'alert') {
            console.log('[TTS Alerts] Received alert:', data.message);
            // Detect "TTS Service: Ready" alert and update ready status
            if (data.message === 'TTS Service: Ready') {
              console.log('[TTS Alerts] Detected ready alert, updating status');
              setTtsWsStatus(true, true);
            }
            onAlert?.(data as TtsAlertMessage);
          } else if (data.type === 'status') {
            console.log('[TTS Alerts] Received status:', data.status);
            // Update ready status from server status message
            const isReady = data.status === 'ready' || (data as TtsStatusMessage).ready;
            setTtsWsStatus(true, isReady);
            onStatus?.(data as TtsStatusMessage);
          }
        } catch (err) {
          console.error('[TTS Alerts] Failed to parse message:', err);
        }
      };

      ws.onerror = (error) => {
        console.error('[TTS Alerts] WebSocket error:', error);
        onError?.(error);
      };

      ws.onclose = () => {
        console.log('[TTS Alerts] Disconnected from TTS service');
        isConnectedRef.current = false;
        setTtsWsStatus(false, false); // Mark as disconnected
        onDisconnect?.();

        // Attempt to reconnect after delay
        if (shouldReconnectRef.current) {
          reconnectTimeoutRef.current = window.setTimeout(() => {
            console.log('[TTS Alerts] Attempting to reconnect...');
            connect();
          }, RECONNECT_DELAY);
        }
      };

      wsRef.current = ws;
    } catch (err) {
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
