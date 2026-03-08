/**
 * Electron TTS Service Integration
 * 
 * Add this to your Electron main process (main.js or main.ts)
 * 
 * Features:
 * - Auto-starts TTS service on app launch
 * - Monitors service health
 * - Auto-stops service on app exit (via cleanup hooks)
 * - Handles crashes and restarts
 */

const { spawn, execFile } = require('child_process');
const path = require('path');
const fs = require('fs');

// Configuration
const TTS_SERVICE_SCRIPT = path.join(__dirname, '../src/scripts/tts_ws_server.py');
const TTS_STOP_SCRIPT = path.join(__dirname, '../src/scripts/stop_tts_service.py');
const TTS_HEALTH_URL = 'ws://localhost:8765';
const START_TIMEOUT = 180000; // 180 seconds for model warmup
const HEALTH_CHECK_INTERVAL = 5000; // 5 seconds

let ttsService = null;
let healthCheckTimer = null;
let isShuttingDown = false;

/**
 * Check if TTS service is already running
 */
async function isTTSServiceRunning() {
  return new Promise((resolve) => {
    const { WebSocket } = require('ws');
    const ws = new WebSocket(TTS_HEALTH_URL);
    
    const timeout = setTimeout(() => {
      ws.terminate();
      resolve(false);
    }, 2000);

    ws.on('open', () => {
      ws.send(JSON.stringify({ action: 'health' }));
    });

    ws.on('message', (data) => {
      clearTimeout(timeout);
      ws.close();
      try {
        const response = JSON.parse(data);
        resolve(response.status === 'healthy' || response.status === 'warming_up');
      } catch {
        resolve(false);
      }
    });

    ws.on('error', () => {
      clearTimeout(timeout);
      resolve(false);
    });
  });
}

/**
 * Start TTS service as a detached process
 */
async function startTTSService() {
  if (await isTTSServiceRunning()) {
    console.log('✓ TTS service already running');
    startHealthMonitoring();
    return true;
  }

  console.log('🚀 Starting TTS service...');
  
  return new Promise((resolve, reject) => {
    const logFile = '/tmp/tts_service.log';
    const out = fs.openSync(logFile, 'a');
    const err = fs.openSync(logFile, 'a');

    ttsService = spawn('python3', [TTS_SERVICE_SCRIPT], {
      detached: true,
      stdio: ['ignore', out, err],
      cwd: path.dirname(TTS_SERVICE_SCRIPT)
    });

    ttsService.unref();

    // Wait for service to be ready
    const startTime = Date.now();
    const checkInterval = setInterval(async () => {
      if (Date.now() - startTime > START_TIMEOUT) {
        clearInterval(checkInterval);
        reject(new Error('TTS service startup timeout'));
        return;
      }

      if (await isTTSServiceRunning()) {
        clearInterval(checkInterval);
        console.log('✓ TTS service ready');
        startHealthMonitoring();
        resolve(true);
      }
    }, 1000);

    ttsService.on('error', (err) => {
      clearInterval(checkInterval);
      reject(new Error(`Failed to start TTS service: ${err.message}`));
    });
  });
}

/**
 * Stop TTS service gracefully
 */
async function stopTTSService() {
  if (isShuttingDown) return;
  isShuttingDown = true;

  console.log('🛑 Stopping TTS service...');
  
  // Stop health monitoring
  if (healthCheckTimer) {
    clearInterval(healthCheckTimer);
    healthCheckTimer = null;
  }

  return new Promise((resolve) => {
    // Use Python stop script for graceful shutdown
    const stopProcess = execFile('python3', [TTS_STOP_SCRIPT, '--silent'], {
      timeout: 10000
    }, (error, stdout, stderr) => {
      if (error) {
        console.error('⚠️  TTS service stop error:', error);
        // Fallback: kill by PID file
        killByPIDFile();
      } else {
        console.log('✓ TTS service stopped');
      }
      resolve();
    });

    // Force kill after 10 seconds
    setTimeout(() => {
      if (!stopProcess.killed) {
        stopProcess.kill();
        killByPIDFile();
        resolve();
      }
    }, 10000);
  });
}

/**
 * Kill TTS service by PID file (fallback)
 */
function killByPIDFile() {
  try {
    const pidFile = '/tmp/tts_service.pid';
    if (fs.existsSync(pidFile)) {
      const pid = parseInt(fs.readFileSync(pidFile, 'utf8').trim());
      if (!isNaN(pid)) {
        process.kill(pid, 'SIGTERM');
        console.log(`✓ Sent SIGTERM to TTS service (PID ${pid})`);
      }
      fs.unlinkSync(pidFile);
    }
  } catch (e) {
    console.error('Error killing TTS service:', e);
  }
}

/**
 * Monitor TTS service health
 */
function startHealthMonitoring() {
  if (healthCheckTimer) clearInterval(healthCheckTimer);
  
  healthCheckTimer = setInterval(async () => {
    const isHealthy = await isTTSServiceRunning();
    if (!isHealthy && !isShuttingDown) {
      console.error('⚠️  TTS service unhealthy, attempting restart...');
      try {
        await stopTTSService();
        isShuttingDown = false;
        await startTTSService();
      } catch (e) {
        console.error('Failed to restart TTS service:', e);
      }
    }
  }, HEALTH_CHECK_INTERVAL);
}

// ============================================================================
// ELECTRON APP INTEGRATION
// Add these to your main.js/main.ts
// ============================================================================

/*
const { app } = require('electron');

// Start TTS service when app is ready
app.whenReady().then(async () => {
  try {
    await startTTSService();
    // ... continue with app initialization
  } catch (e) {
    console.error('Failed to start TTS service:', e);
    // Optionally show error dialog or continue without TTS
  }
});

// Stop TTS service before app quits
app.on('before-quit', async (event) => {
  event.preventDefault(); // Prevent immediate quit
  await stopTTSService();
  app.exit(0);
});

// Handle window-all-closed
app.on('window-all-closed', async () => {
  if (process.platform !== 'darwin') {
    await stopTTSService();
    app.quit();
  }
});

// Handle SIGINT/SIGTERM (for command-line quit)
process.on('SIGINT', async () => {
  console.log('\nReceived SIGINT, cleaning up...');
  await stopTTSService();
  process.exit(0);
});

process.on('SIGTERM', async () => {
  console.log('Received SIGTERM, cleaning up...');
  await stopTTSService();
  process.exit(0);
});

// Handle crashes - try to cleanup
process.on('uncaughtException', async (err) => {
  console.error('Uncaught exception:', err);
  await stopTTSService();
  process.exit(1);
});
*/

// ============================================================================
// EXPORTS (for use in other modules)
// ============================================================================

module.exports = {
  startTTSService,
  stopTTSService,
  isTTSServiceRunning
};
