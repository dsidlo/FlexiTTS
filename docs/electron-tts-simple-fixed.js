/**
 * Electron TTS Service Integration - FIXED with systemd workarounds
 * 
 * Add this to your main.js BEFORE the app is ready
 */

const { spawn, exec } = require('child_process');
const { app } = require('electron');
const path = require('path');

// ============================================================================
// SYSTEMD FIX - Must be before app ready
// ============================================================================

if (process.platform === 'linux') {
  // Disable sandbox to prevent systemd scope errors
  app.commandLine.appendSwitch('no-sandbox');
  app.commandLine.appendSwitch('disable-setuid-sandbox');
  
  // Also disable via env vars
  process.env.ELECTRON_NO_SANDBOX = '1';
  
  // Optional: Clean up stale scopes on startup
  try {
    const { spawn: spawn_sync } = require('child_process');
    spawn_sync('bash', ['-c', 
      'systemctl --user list-units --type scope --state running 2>/dev/null | grep -i chromium | awk "{print $1}" | xargs -r systemctl --user stop 2>/dev/null || true'
    ], { stdio: 'ignore' });
  } catch (e) { /* ignore */ }
}

// Paths to Python scripts (adjust as needed)
const SCRIPT_DIR = path.join(__dirname, '../src/scripts');
const START_SCRIPT = path.join(SCRIPT_DIR, 'start_tts_service.py');
const STOP_SCRIPT = path.join(SCRIPT_DIR, 'stop_tts_service.py');

let ttsProcess = null;
let isShuttingDown = false;

/**
 * Start TTS service
 */
function startTTS() {
  return new Promise((resolve, reject) => {
    console.log('🚀 Starting TTS service...');
    
    // Use Python directly (not uv run) to avoid PATH issues
    const pythonCmd = process.platform === 'win32' ? 'python' : 'python3';
    
    ttsProcess = spawn(pythonCmd, [START_SCRIPT], {
      cwd: SCRIPT_DIR,
      stdio: 'pipe',  // Use pipe so we can capture output
      detached: false, // Keep attached so we can kill it
      env: {
        ...process.env,
        PYTHONUNBUFFERED: '1'
      }
    });

    let output = '';
    ttsProcess.stdout?.on('data', (data) => {
      output += data.toString();
      console.log('[TTS]', data.toString().trim());
    });
    
    ttsProcess.stderr?.on('data', (data) => {
      console.error('[TTS Error]', data.toString().trim());
    });

    // If service already running, we'll get quick success
    const timeout = setTimeout(() => {
      if (output.includes('already running') || output.includes('ready')) {
        console.log('✓ TTS already running');
        resolve();
      }
    }, 3000);

    ttsProcess.on('close', (code) => {
      clearTimeout(timeout);
      if (code === 0 || output.includes('already running')) {
        resolve();
      } else {
        reject(new Error(`TTS start failed with code ${code}`));
      }
    });

    ttsProcess.on('error', reject);
    
    // Fallback resolve after timeout
    setTimeout(() => resolve(), 8000);
  });
}

/**
 * Stop TTS service
 */
function stopTTS() {
  return new Promise((resolve) => {
    if (isShuttingDown) {
      resolve();
      return;
    }
    isShuttingDown = true;
    
    console.log('🛑 Stopping TTS service...');
    
    // Kill our spawned process if we have one
    if (ttsProcess && !ttsProcess.killed) {
      try {
        ttsProcess.kill('SIGTERM');
        console.log('Sent SIGTERM to TTS process');
      } catch (e) {
        console.error('Error killing TTS process:', e);
      }
    }
    
    // Use stop script as backup
    const pythonCmd = process.platform === 'win32' ? 'python' : 'python3';
    exec(`${pythonCmd} "${STOP_SCRIPT}" --silent`, {
      cwd: SCRIPT_DIR,
      timeout: 10000,
      env: { ...process.env }  // Keep environment
    }, (error) => {
      if (error) console.error('Stop script error:', error.message);
      resolve();
    });
    
    // Timeout fallback
    setTimeout(resolve, 5000);
  });
}

// ============================================================================
// APP EVENTS
// ============================================================================

// Start TTS when app launches
app.whenReady().then(async () => {
  try {
    await startTTS();
    console.log('✓ TTS service ready');
  } catch (e) {
    console.error('⚠️  TTS start error:', e.message);
    // Continue anyway - TTS might already be running
  }
});

// CRITICAL: Stop TTS when app exits
app.on('before-quit', async (e) => {
  if (isShuttingDown) return;
  e.preventDefault();
  await stopTTS();
  app.exit(0);
});

app.on('window-all-closed', async () => {
  if (process.platform !== 'darwin') {
    await stopTTS();
    app.quit();
  }
});

// Handle signals
process.on('SIGINT', async () => {
  await stopTTS();
  process.exit(0);
});

process.on('SIGTERM', async () => {
  await stopTTS();
  process.exit(0);
});

process.on('uncaughtException', async (err) => {
  console.error('Uncaught:', err);
  await stopTTS();
  process.exit(1);
});
