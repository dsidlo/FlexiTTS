import type { AlertType } from '../hooks/useAlerts';

export type InternalAlertType = AlertType;

export interface InternalAlertOptions {
  type?: AlertType;
  duration?: number;
  source?: 'internal';
}

/**
 * Service for generating internal application alerts
 * This provides a clean API for the app to notify users of events
 */
export class AlertService {
  private static instance: AlertService | null = null;
  private alertListeners: Set<(message: string, type: AlertType, duration: number) => void> = new Set();

  static getInstance(): AlertService {
    if (!AlertService.instance) {
      AlertService.instance = new AlertService();
    }
    return AlertService.instance;
  }

  /**
   * Subscribe to internal alerts
   * Returns an unsubscribe function
   */
  subscribe(listener: (message: string, type: AlertType, duration: number) => void): () => void {
    this.alertListeners.add(listener);
    return () => {
      this.alertListeners.delete(listener);
    };
  }

  /**
   * Show an info alert
   */
  info(message: string, duration = 3000): void {
    this.notifyListeners(message, 'info', duration);
  }

  /**
   * Show a success alert
   */
  success(message: string, duration = 3000): void {
    this.notifyListeners(message, 'success', duration);
  }

  /**
   * Show a warning alert
   */
  warning(message: string, duration = 4000): void {
    this.notifyListeners(message, 'warning', duration);
  }

  /**
   * Show an error alert (longer duration by default)
   */
  error(message: string, duration = 6000): void {
    this.notifyListeners(message, 'error', duration);
  }

  /**
   * Generic alert with full control
   */
  alert(message: string, options: InternalAlertOptions = {}): void {
    const { type = 'info', duration = 3000 } = options;
    this.notifyListeners(message, type, duration);
  }

  private notifyListeners(message: string, type: AlertType, duration: number): void {
    this.alertListeners.forEach(listener => {
      try {
        listener(message, type, duration);
      } catch (err) {
        console.error('[AlertService] Error in alert listener:', err);
      }
    });
  }
}

// Export singleton instance
export const alertService = AlertService.getInstance();

// Export convenience functions for easy import
export const alerts = {
  info: (message: string, duration?: number) => alertService.info(message, duration),
  success: (message: string, duration?: number) => alertService.success(message, duration),
  warning: (message: string, duration?: number) => alertService.warning(message, duration),
  error: (message: string, duration?: number) => alertService.error(message, duration),
  alert: (message: string, options?: InternalAlertOptions) => alertService.alert(message, options)
};

export default alertService;
