import { useState, useCallback, useRef } from 'react';

export type AlertType = 'info' | 'success' | 'warning' | 'error';
export type AlertSource = 'internal' | 'tts-service';

export interface Alert {
  id: string;
  message: string;
  type: AlertType;
  source: AlertSource;
  timestamp: Date;
  duration?: number; // Duration in ms, default 3000
}

export interface UseAlertsReturn {
  alerts: Alert[];
  addAlert: (message: string, type?: AlertType, source?: AlertSource, duration?: number) => string;
  removeAlert: (id: string) => void;
  clearAlerts: () => void;
}

/**
 * Hook for managing alert notifications
 * Alerts are displayed for a duration then automatically removed
 * Alerts stack vertically with most recent at the bottom
 */
export function useAlerts(): UseAlertsReturn {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const timeoutsRef = useRef<Map<string, number>>(new Map());

  const removeAlert = useCallback((id: string) => {
    // Clear any existing timeout
    const existingTimeout = timeoutsRef.current.get(id);
    if (existingTimeout) {
      window.clearTimeout(existingTimeout);
      timeoutsRef.current.delete(id);
    }

    setAlerts(prev => prev.filter(alert => alert.id !== id));
  }, []);

  const addAlert = useCallback((
    message: string,
    type: AlertType = 'info',
    source: AlertSource = 'internal',
    duration: number = 3000
  ): string => {
    const id = `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    const newAlert: Alert = {
      id,
      message,
      type,
      source,
      timestamp: new Date(),
      duration
    };

    setAlerts(prev => [...prev, newAlert]);

    // Set auto-dismiss timeout
    if (duration > 0) {
      const timeoutId = window.setTimeout(() => {
        removeAlert(id);
      }, duration);
      timeoutsRef.current.set(id, timeoutId);
    }

    return id;
  }, [removeAlert]);

  const clearAlerts = useCallback(() => {
    // Clear all timeouts
    timeoutsRef.current.forEach(timeoutId => {
      window.clearTimeout(timeoutId);
    });
    timeoutsRef.current.clear();
    setAlerts([]);
  }, []);

  return {
    alerts,
    addAlert,
    removeAlert,
    clearAlerts
  };
}
