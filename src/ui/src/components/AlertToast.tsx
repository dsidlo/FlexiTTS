import React, { useEffect, useState } from 'react';
import type { Alert } from '../hooks/useAlerts';

interface AlertToastProps {
  alert: Alert;
  onDismiss: (id: string) => void;
}

const typeStyles: Record<Alert['type'], { bg: string; border: string; icon: string }> = {
  info: {
    bg: 'rgba(59, 130, 246, 0.95)',
    border: 'rgba(59, 130, 246, 1)',
    icon: 'ℹ️'
  },
  success: {
    bg: 'rgba(34, 197, 94, 0.95)',
    border: 'rgba(34, 197, 94, 1)',
    icon: '✓'
  },
  warning: {
    bg: 'rgba(251, 191, 36, 0.95)',
    border: 'rgba(251, 191, 36, 1)',
    icon: '⚠️'
  },
  error: {
    bg: 'rgba(239, 68, 68, 0.95)',
    border: 'rgba(239, 68, 68, 1)',
    icon: '✕'
  }
};

const sourceLabels: Record<Alert['source'], string> = {
  internal: 'FlexiTTS',
  'tts-service': 'TTS Service'
};

export const AlertToast: React.FC<AlertToastProps> = ({ alert, onDismiss }) => {
  const [isVisible, setIsVisible] = useState(false);
  const [isExiting, setIsExiting] = useState(false);
  const styles = typeStyles[alert.type];

  useEffect(() => {
    // Trigger enter animation after mount
    requestAnimationFrame(() => {
      setIsVisible(true);
    });

    // Start exit animation before dismissal
    const exitTimeout = window.setTimeout(() => {
      setIsExiting(true);
    }, (alert.duration || 3000) - 300); // Start exit 300ms before end

    return () => {
      window.clearTimeout(exitTimeout);
    };
  }, [alert.duration]);

  const handleDismiss = () => {
    setIsExiting(true);
    setTimeout(() => {
      onDismiss(alert.id);
    }, 300);
  };

  return (
    <div
      style={{
        backgroundColor: styles.bg,
        borderLeft: `4px solid ${styles.border}`,
        color: 'white',
        padding: '12px 16px',
        borderRadius: '6px',
        boxShadow: '0 4px 12px rgba(0, 0, 0, 0.3)',
        display: 'flex',
        alignItems: 'flex-start',
        gap: '10px',
        minWidth: '300px',
        maxWidth: '500px',
        opacity: isVisible && !isExiting ? 1 : 0,
        transform: isVisible && !isExiting ? 'translateY(0)' : 'translateY(20px)',
        transition: 'opacity 300ms ease, transform 300ms ease',
        cursor: 'pointer',
        fontSize: '13px',
        lineHeight: 1.4
      }}
      onClick={handleDismiss}
      role="alert"
    >
      <span style={{ 
        fontSize: '16px', 
        fontWeight: 'bold',
        flexShrink: 0,
        width: '20px',
        textAlign: 'center'
      }}>
        {styles.icon}
      </span>
      
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ 
          fontWeight: 600, 
          marginBottom: '2px',
          fontSize: '11px',
          textTransform: 'uppercase',
          letterSpacing: '0.5px',
          opacity: 0.9
        }}>
          {sourceLabels[alert.source]}
        </div>
        <div style={{ 
          wordWrap: 'break-word',
          overflowWrap: 'break-word'
        }}>
          {alert.message}
        </div>
      </div>

      <button
        onClick={(e) => {
          e.stopPropagation();
          handleDismiss();
        }}
        style={{
          background: 'none',
          border: 'none',
          color: 'white',
          cursor: 'pointer',
          fontSize: '14px',
          padding: '0',
          marginLeft: '4px',
          opacity: 0.7,
          flexShrink: 0,
          width: '20px',
          height: '20px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          borderRadius: '3px'
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.opacity = '1';
          e.currentTarget.style.backgroundColor = 'rgba(255,255,255,0.2)';
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.opacity = '0.7';
          e.currentTarget.style.backgroundColor = 'transparent';
        }}
        aria-label="Dismiss alert"
      >
        ×
      </button>
    </div>
  );
};

export default AlertToast;
