/**
 * Simple Electron TTS Service Integration
 * Minimal version using Python scripts directly
 */

const { spawn, exec } = require('child_process');
const { app } = require('electron');
const path = require('path');

// Paths to Python scripts
const SCRIPT_DIR = path.join(__dirname, '../src/scripts');
const START_SCRIPT = path.join(SCRIPT_DIR, 'start_tts_service.py');
const STOP_SCRIPT = path.join(SCRIPT_DIR, 'stop_tts_service.py');

let ttsProcess = null;

/**
 * Start TTS service using the Python start script
 */
function startTTS() {
  return new Promise((resolve, reject) => {
    console.log('🚀 Starting TTS service...');
    
    ttsProcess = spawn('python3', [START_SCRIPT], {
      cwd: SCRIPT_DIR,
      stdio: 'inherit' // Show output in console
    });

    ttsProcess.on('close', (code) => {
      if (code === 0) {
        console.log('✓ TTS service started successfully');
        resolve();
      } else {
        reject(new Error(`TTS service start failed with code ${code}`));
      }
    });

    ttsProcess.on('error', reject);
    
    // If already running, script exits quickly with code 0
    setTimeout(() => resolve(), 5000);
  });
}

/**
 * Stop TTS service using the Python stop script
 */
function stopTTS() {
  return new Promise((resolve) => {
    console.log('🛑 Stopping TTS service...');
    
    exec(`python3 "${STOP_SCRIPT}" --silent`, {
      cwd: SCRIPT_DIR,
      timeout: 10000
    }, (error, stdout, stderr) => {
      if (error) {
        console.error('⚠️  Stop error:', error.message);
      } else {
        console.log('✓ TTS service stopped');
      }
      resolve();
    });
    
    // Timeout fallback
    setTimeout(resolve, 5000);
  });
}

// ============================================================================
// APP EVENTS - Add this to your main.js
// ============================================================================

// Start TTS when app launches
app.whenReady().then(async () => {
  try {
    await startTTS();
  } catch (e) {
    console.error('TTS start error:', e);
  }
});

// Stop TTS when app exits
app.on('before-quit', async (e) => {
  e.preventDefault();
  await stopTTS();
  app.exit(0);
});

// For macOS
app.on('window-all-closed', async () => {
  if (process.platform !== 'darwin') {
    await stopTTS();
    app.quit();
  }
});

// SIGINT/SIGTERM handling
process.on('SIGINT', async () => {
  await stopTTS();
  process.exit(0);
});

process.on('SIGTERM', async () => {
  await stopTTS();
  process.exit(0);
});
