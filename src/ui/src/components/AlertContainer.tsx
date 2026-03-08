import React from 'react';
import { AlertToast } from './AlertToast';
import type { Alert } from '../hooks/useAlerts';

interface AlertContainerProps {
  alerts: Alert[];
  onDismiss: (id: string) => void;
}

export const AlertContainer: React.FC<AlertContainerProps> = ({ alerts, onDismiss }) => {
  if (alerts.length === 0) {
    return null;
  }

  return (
    <div
      style={{
        position: 'fixed',
        bottom: '20px',
        right: '20px',
        display: 'flex',
        flexDirection: 'column',
        gap: '10px',
        zIndex: 10000,
        pointerEvents: 'none' // Let clicks pass through empty areas
      }}
    >
      {alerts.map((alert) => (
        <div 
          key={alert.id}
          style={{ pointerEvents: 'auto' }} // Re-enable clicks on the toast
        >
          <AlertToast alert={alert} onDismiss={onDismiss} />
        </div>
      ))}
    </div>
  );
};

export default AlertContainer;
