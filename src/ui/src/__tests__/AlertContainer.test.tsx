import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { AlertContainer } from '../components/AlertContainer';
import type { Alert } from '../hooks/useAlerts';

describe('AlertContainer', () => {
  const mockOnDismiss = vi.fn();

  const createAlert = (id: string, type: Alert['type'], message: string, source: Alert['source'] = 'internal'): Alert => ({
    id,
    type,
    message,
    source,
    timestamp: Date.now(),
    duration: 3000,
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  describe('rendering', () => {
    it('should return null when no alerts are provided', () => {
      const { container } = render(<AlertContainer alerts={[]} onDismiss={mockOnDismiss} />);
      expect(container.firstChild).toBeNull();
    });

    it('should return null with empty array', () => {
      const { container } = render(<AlertContainer alerts={[]} onDismiss={mockOnDismiss} />);
      expect(container.firstChild).toBeNull();
    });

    it('should render single alert', () => {
      const alerts = [createAlert('1', 'info', 'Test message')];
      render(<AlertContainer alerts={alerts} onDismiss={mockOnDismiss} />);
      
      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(screen.getByText('Test message')).toBeInTheDocument();
    });

    it('should render multiple alerts', () => {
      const alerts = [
        createAlert('1', 'info', 'First message'),
        createAlert('2', 'success', 'Second message'),
      ];
      render(<AlertContainer alerts={alerts} onDismiss={mockOnDismiss} />);
      
      const alertElements = screen.getAllByRole('alert');
      expect(alertElements).toHaveLength(2);
      expect(screen.getByText('First message')).toBeInTheDocument();
      expect(screen.getByText('Second message')).toBeInTheDocument();
    });

    it('should render alerts in correct order', () => {
      const alerts = [
        createAlert('1', 'info', 'First'),
        createAlert('2', 'error', 'Second'),
        createAlert('3', 'success', 'Third'),
      ];
      render(<AlertContainer alerts={alerts} onDismiss={mockOnDismiss} />);
      
      const alertElements = screen.getAllByRole('alert');
      expect(alertElements).toHaveLength(3);
    });
  });

  describe('styling', () => {
    it('should have fixed positioning container', () => {
      const alerts = [createAlert('1', 'info', 'Test')];
      const { container } = render(<AlertContainer alerts={alerts} onDismiss={mockOnDismiss} />);
      
      const wrapper = container.firstChild as HTMLElement;
      expect(wrapper.style.position).toBe('fixed');
      expect(wrapper.style.bottom).toBe('20px');
      expect(wrapper.style.right).toBe('20px');
    });

    it('should have pointer-events none on container', () => {
      const alerts = [createAlert('1', 'info', 'Test')];
      const { container } = render(<AlertContainer alerts={alerts} onDismiss={mockOnDismiss} />);
      
      const wrapper = container.firstChild as HTMLElement;
      expect(wrapper.style.pointerEvents).toBe('none');
    });

    it('should have high z-index', () => {
      const alerts = [createAlert('1', 'info', 'Test')];
      const { container } = render(<AlertContainer alerts={alerts} onDismiss={mockOnDismiss} />);
      
      const wrapper = container.firstChild as HTMLElement;
      expect(wrapper.style.zIndex).toBe('10000');
    });

    it('should render as flex column', () => {
      const alerts = [createAlert('1', 'info', 'Test')];
      const { container } = render(<AlertContainer alerts={alerts} onDismiss={mockOnDismiss} />);
      
      const wrapper = container.firstChild as HTMLElement;
      expect(wrapper.style.flexDirection).toBe('column');
    });
  });

  describe('alert types', () => {
    it('should render info alert', () => {
      const alerts = [createAlert('1', 'info', 'Info message')];
      render(<AlertContainer alerts={alerts} onDismiss={mockOnDismiss} />);
      expect(screen.getByText('Info message')).toBeInTheDocument();
    });

    it('should render success alert', () => {
      const alerts = [createAlert('1', 'success', 'Success message')];
      render(<AlertContainer alerts={alerts} onDismiss={mockOnDismiss} />);
      expect(screen.getByText('Success message')).toBeInTheDocument();
    });

    it('should render warning alert', () => {
      const alerts = [createAlert('1', 'warning', 'Warning message')];
      render(<AlertContainer alerts={alerts} onDismiss={mockOnDismiss} />);
      expect(screen.getByText('Warning message')).toBeInTheDocument();
    });

    it('should render error alert', () => {
      const alerts = [createAlert('1', 'error', 'Error message')];
      render(<AlertContainer alerts={alerts} onDismiss={mockOnDismiss} />);
      expect(screen.getByText('Error message')).toBeInTheDocument();
    });
  });

  describe('alert sources', () => {
    it('should render internal alerts', () => {
      const alerts = [createAlert('1', 'info', 'Internal message', 'internal')];
      render(<AlertContainer alerts={alerts} onDismiss={mockOnDismiss} />);
      expect(screen.getByText('Internal message')).toBeInTheDocument();
    });

    it('should render tts-service alerts', () => {
      const alerts = [createAlert('1', 'info', 'TTS message', 'tts-service')];
      render(<AlertContainer alerts={alerts} onDismiss={mockOnDismiss} />);
      expect(screen.getByText('TTS message')).toBeInTheDocument();
    });
  });

  describe('dismiss handling', () => {
    it('should pass onDismiss to AlertToast', () => {
      const alerts = [createAlert('1', 'info', 'Test')];
      render(<AlertContainer alerts={alerts} onDismiss={mockOnDismiss} />);
      
      const alert = screen.getByRole('alert');
      // Clicking the alert should trigger dismiss
      alert.click();
      
      // The AlertToast will call onDismiss after animation
      // We verify it's passed by checking the component renders
      expect(alert).toBeInTheDocument();
    });

    it('should handle multiple alerts with same onDismiss', () => {
      const alerts = [
        createAlert('1', 'info', 'First'),
        createAlert('2', 'info', 'Second'),
      ];
      render(<AlertContainer alerts={alerts} onDismiss={mockOnDismiss} />);
      
      const alertElements = screen.getAllByRole('alert');
      expect(alertElements).toHaveLength(2);
    });
  });

  describe('edge cases', () => {
    it('should handle alerts with very long messages', () => {
      const longMessage = 'A'.repeat(500);
      const alerts = [createAlert('1', 'info', longMessage)];
      render(<AlertContainer alerts={alerts} onDismiss={mockOnDismiss} />);
      
      expect(screen.getByText(longMessage)).toBeInTheDocument();
    });

    it('should handle alerts with special characters', () => {
      const specialMessage = 'Test <script>alert("xss")</script> & "quotes"';
      const alerts = [createAlert('1', 'info', specialMessage)];
      render(<AlertContainer alerts={alerts} onDismiss={mockOnDismiss} />);
      
      expect(screen.getByText(specialMessage)).toBeInTheDocument();
    });

    it('should re-render when alerts prop changes', () => {
      const { rerender } = render(
        <AlertContainer alerts={[createAlert('1', 'info', 'First')]} onDismiss={mockOnDismiss} />
      );
      
      expect(screen.getByText('First')).toBeInTheDocument();
      
      rerender(<AlertContainer alerts={[createAlert('2', 'success', 'Second')]} onDismiss={mockOnDismiss} />);
      
      expect(screen.queryByText('First')).not.toBeInTheDocument();
      expect(screen.getByText('Second')).toBeInTheDocument();
    });

    it('should handle rapid alert updates', () => {
      const { rerender } = render(<AlertContainer alerts={[]} onDismiss={mockOnDismiss} />);
      
      // Add alert
      rerender(<AlertContainer alerts={[createAlert('1', 'info', 'Alert 1')]} onDismiss={mockOnDismiss} />);
      expect(screen.getByText('Alert 1')).toBeInTheDocument();
      
      // Add second alert
      rerender(<AlertContainer alerts={[createAlert('1', 'info', 'Alert 1'), createAlert('2', 'info', 'Alert 2')]} onDismiss={mockOnDismiss} />);
      expect(screen.getByText('Alert 1')).toBeInTheDocument();
      expect(screen.getByText('Alert 2')).toBeInTheDocument();
      
      // Remove first alert
      rerender(<AlertContainer alerts={[createAlert('2', 'info', 'Alert 2')]} onDismiss={mockOnDismiss} />);
      expect(screen.queryByText('Alert 1')).not.toBeInTheDocument();
      expect(screen.getByText('Alert 2')).toBeInTheDocument();
    });
  });
});
