import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { AlertService, alertService, alerts } from '../services/alertService';
import type { AlertType } from '../hooks/useAlerts';

describe('AlertService', () => {
  let service: AlertService;
  let mockListener: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    // Get fresh instance
    service = AlertService.getInstance();
    mockListener = vi.fn();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  describe('singleton pattern', () => {
    it('should return same instance', () => {
      const instance1 = AlertService.getInstance();
      const instance2 = AlertService.getInstance();
      expect(instance1).toBe(instance2);
    });

    it('should exported singleton match getInstance', () => {
      expect(alertService).toBe(AlertService.getInstance());
    });
  });

  describe('subscribe/unsubscribe', () => {
    it('should subscribe listener', () => {
      const unsubscribe = service.subscribe(mockListener);
      service.info('Test message');
      expect(mockListener).toHaveBeenCalled();
      unsubscribe();
    });

    it('should return unsubscribe function', () => {
      const unsubscribe = service.subscribe(mockListener);
      expect(typeof unsubscribe).toBe('function');
      unsubscribe();
    });

    it('should unsubscribe listener', () => {
      const unsubscribe = service.subscribe(mockListener);
      unsubscribe();
      service.info('Test message');
      expect(mockListener).not.toHaveBeenCalled();
    });

    it('should support multiple listeners', () => {
      const mockListener2 = vi.fn();
      const unsubscribe1 = service.subscribe(mockListener);
      const unsubscribe2 = service.subscribe(mockListener2);

      service.info('Test message');

      expect(mockListener).toHaveBeenCalledWith('Test message', 'info', 3000);
      expect(mockListener2).toHaveBeenCalledWith('Test message', 'info', 3000);

      unsubscribe1();
      unsubscribe2();
    });

    it('should handle listener errors gracefully', () => {
      const errorListener = vi.fn().mockImplementation(() => {
        throw new Error('Listener error');
      });
      const goodListener = vi.fn();

      service.subscribe(errorListener);
      service.subscribe(goodListener);

      // Should not throw
      expect(() => service.info('Test')).not.toThrow();
      expect(goodListener).toHaveBeenCalled();
    });
  });

  describe('alert types', () => {
    it('should emit info alert with correct parameters', () => {
      const unsubscribe = service.subscribe(mockListener);
      service.info('Info message');

      expect(mockListener).toHaveBeenCalledWith('Info message', 'info', 3000);
      unsubscribe();
    });

    it('should emit success alert with correct parameters', () => {
      const unsubscribe = service.subscribe(mockListener);
      service.success('Success message');

      expect(mockListener).toHaveBeenCalledWith('Success message', 'success', 3000);
      unsubscribe();
    });

    it('should emit warning alert with correct parameters', () => {
      const unsubscribe = service.subscribe(mockListener);
      service.warning('Warning message');

      expect(mockListener).toHaveBeenCalledWith('Warning message', 'warning', 4000);
      unsubscribe();
    });

    it('should emit error alert with correct parameters', () => {
      const unsubscribe = service.subscribe(mockListener);
      service.error('Error message');

      expect(mockListener).toHaveBeenCalledWith('Error message', 'error', 6000);
      unsubscribe();
    });

    it('should support generic alert method', () => {
      const unsubscribe = service.subscribe(mockListener);
      service.alert('Generic message', { type: 'warning', duration: 5000 });

      expect(mockListener).toHaveBeenCalledWith('Generic message', 'warning', 5000);
      unsubscribe();
    });
  });

  describe('custom durations', () => {
    it('should support custom duration for info', () => {
      const unsubscribe = service.subscribe(mockListener);
      service.info('Info message', 5000);

      expect(mockListener).toHaveBeenCalledWith('Info message', 'info', 5000);
      unsubscribe();
    });

    it('should support custom duration for success', () => {
      const unsubscribe = service.subscribe(mockListener);
      service.success('Success message', 10000);

      expect(mockListener).toHaveBeenCalledWith('Success message', 'success', 10000);
      unsubscribe();
    });

    it('should support custom duration for warning', () => {
      const unsubscribe = service.subscribe(mockListener);
      service.warning('Warning message', 8000);

      expect(mockListener).toHaveBeenCalledWith('Warning message', 'warning', 8000);
      unsubscribe();
    });

    it('should support custom duration for error', () => {
      const unsubscribe = service.subscribe(mockListener);
      service.error('Error message', 15000);

      expect(mockListener).toHaveBeenCalledWith('Error message', 'error', 15000);
      unsubscribe();
    });

    it('should use defaults for generic alert', () => {
      const unsubscribe = service.subscribe(mockListener);
      service.alert('Generic message');

      expect(mockListener).toHaveBeenCalledWith('Generic message', 'info', 3000);
      unsubscribe();
    });
  });

  describe('convenience exports', () => {
    it('should expose alerts.info', () => {
      const unsubscribe = service.subscribe(mockListener);
      alerts.info('Info via alerts');

      // alerts.info delegates to alertService.info which uses default duration 3000
      expect(mockListener).toHaveBeenCalledWith('Info via alerts', 'info', 3000);
      unsubscribe();
    });

    it('should expose alerts.success', () => {
      const unsubscribe = service.subscribe(mockListener);
      alerts.success('Success via alerts');

      expect(mockListener).toHaveBeenCalledWith('Success via alerts', 'success', 3000);
      unsubscribe();
    });

    it('should expose alerts.warning', () => {
      const unsubscribe = service.subscribe(mockListener);
      alerts.warning('Warning via alerts');

      expect(mockListener).toHaveBeenCalledWith('Warning via alerts', 'warning', 4000);
      unsubscribe();
    });

    it('should expose alerts.error', () => {
      const unsubscribe = service.subscribe(mockListener);
      alerts.error('Error via alerts');

      expect(mockListener).toHaveBeenCalledWith('Error via alerts', 'error', 6000);
      unsubscribe();
    });

    it('should expose alerts.alert', () => {
      const unsubscribe = service.subscribe(mockListener);
      alerts.alert('Generic via alerts', { type: 'success', duration: 5000 });

      expect(mockListener).toHaveBeenCalledWith('Generic via alerts', 'success', 5000);
      unsubscribe();
    });
  });

  describe('default durations', () => {
    it('should default info to 3000ms', () => {
      const unsubscribe = service.subscribe(mockListener);
      service.info('Test');
      expect(mockListener).toHaveBeenCalledWith('Test', 'info', 3000);
      unsubscribe();
    });

    it('should default success to 3000ms', () => {
      const unsubscribe = service.subscribe(mockListener);
      service.success('Test');
      expect(mockListener).toHaveBeenCalledWith('Test', 'success', 3000);
      unsubscribe();
    });

    it('should default warning to 4000ms', () => {
      const unsubscribe = service.subscribe(mockListener);
      service.warning('Test');
      expect(mockListener).toHaveBeenCalledWith('Test', 'warning', 4000);
      unsubscribe();
    });

    it('should default error to 6000ms', () => {
      const unsubscribe = service.subscribe(mockListener);
      service.error('Test');
      expect(mockListener).toHaveBeenCalledWith('Test', 'error', 6000);
      unsubscribe();
    });
  });
});
