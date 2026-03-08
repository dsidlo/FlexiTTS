/**
 * Debug TTS Connection in Electron
 * Add this before your TTS client initialization
 */

const WebSocket = require('ws');

async function debugTTSConnection() {
  console.log('=== TTS Debug ===');
  
  // Test 1: Direct WebSocket
  try {
    const ws = new WebSocket('ws://localhost:8765');
    
    await new Promise((resolve, reject) => {
      ws.on('open', () => {
        console.log('✓ WebSocket connected');
        ws.send(JSON.stringify({ action: 'health' }));
      });
      
      ws.on('message', (data) => {
        const response = JSON.parse(data);
        console.log('✓ Health response:', response);
        if (response.ready) {
          console.log('✓ TTS is ready!');
        } else {
          console.log('⚠️ TTS warming up...');
        }
        ws.close();
        resolve();
      });
      
      ws.on('error', (e) => {
        console.error('✗ WebSocket error:', e.message);
        reject(e);
      });
      
      setTimeout(() => reject(new Error('Timeout')), 5000);
    });
    
  } catch (e) {
    console.error('✗ Connection failed:', e.message);
  }
  
  // Test 2: Python health check
  try {
    const { execSync } = require('child_process');
    const result = execSync(
      'uv run python check_tts_service.py --detailed',
      { 
        cwd: '/home/dsidlo/workspace/FlexiTTS/src/scripts',
        encoding: 'utf8',
        timeout: 10000
      }
    );
    console.log('✓ Python check:', result);
  } catch (e) {
    console.error('✗ Python check failed:', e.message);
  }
}

// Run this BEFORE your TTS client initialization
debugTTSConnection();

// Then wait for ready
async function waitForTTS(maxWait = 30000) {
  const start = Date.now();
  
  while (Date.now() - start < maxWait) {
    try {
      const ws = new WebSocket('ws://localhost:8765');
      
      const ready = await new Promise((resolve) => {
        ws.on('open', () => {
          ws.send(JSON.stringify({ action: 'health' }));
        });
        
        ws.on('message', (data) => {
          const response = JSON.parse(data);
          ws.close();
          resolve(response.ready);
        });
        
        ws.on('error', () => resolve(false));
        setTimeout(() => resolve(false), 3000);
      });
      
      if (ready) {
        console.log('✓ TTS ready after', Date.now() - start, 'ms');
        return true;
      }
      
    } catch (e) {
      // Ignore and retry
    }
    
    await new Promise(r => setTimeout(r, 500));
  }
  
  throw new Error('TTS not ready after ' + maxWait + 'ms');
}

module.exports = { debugTTSConnection, waitForTTS };

/* USAGE in main.js:
const { app } = require('electron');
const { waitForTTS } = require('./electron-debug-tts');

app.whenReady().then(async () => {
  try {
    await waitForTTS(30000); // Wait up to 30s
    console.log('TTS is ready, starting app...');
    // ... create windows, etc.
  } catch (e) {
    console.error('TTS failed:', e);
    // Show error dialog but don't block
  }
});
*/
