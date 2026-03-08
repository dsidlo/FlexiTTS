/**
 * Electron Systemd Fix
 * 
 * Add this to the TOP of your Electron main.js/main.ts (before any other imports)
 * 
 * This prevents the systemd scope error:
 * "Failed to call method: org.freedesktop.systemd1.Manager.StartTransientUnit: 
 *  Unit app-org.chromium.Chromium-xxxx.scope already exists"
 */

// Fix 1: Disable systemd cgroup integration
process.env.ELECTRON_DISABLE_SECURITY_WARNINGS = 'true';
process.env.ELECTRON_ENABLE_SECURITY_WARNINGS = 'false';

// Disable systemd scope creation (prevents the "Unit already exists" error)
if (process.platform === 'linux') {
  // Method A: Disable via environment variable
  process.env.ELECTRON_NO_SANDBOX = '1';
  process.env.ELECTRON_DISABLE_SANDBOX = '1';
  
  // Method B: Disable Chrome's systemd integration
  process.env.CHROME_DESKTOP = 'electron-app';
  app.commandLine.appendSwitch('disable-features', 'CalculateNativeWinOcclusion');
}

// Fix 2: Add startup flags to prevent systemd issues
const { app } = require('electron');

// Must be called before app is ready
app.commandLine.appendSwitch('no-sandbox');
app.commandLine.appendSwitch('disable-setuid-sandbox');
app.commandLine.appendSwitch('disable-features', 'site-per-process');

// Disable GPU sandbox (can help with systemd issues)
app.commandLine.appendSwitch('disable-gpu-sandbox');

// ============================================================================
// Alternative: Run Electron wrapper script
// ============================================================================

/*
Instead of modifying main.js, you can also run Electron with flags:

In your package.json scripts:
"start": "electron --no-sandbox --disable-setuid-sandbox ."

Or create a wrapper script:
#!/bin/bash
export ELECTRON_NO_SANDBOX=1
export ELECTRON_DISABLE_SANDBOX=1
exec electron --no-sandbox --disable-setuid-sandbox "$@"
*/

// ============================================================================
// Cleanup on startup (optional but recommended)
// ============================================================================

const { spawn } = require('child_process');

function cleanupStaleScopes() {
  if (process.platform !== 'linux') return;
  
  // Kill any stale Electron scopes
  const cleanup = spawn('bash', ['-c', `
    systemctl --user list-units --type scope --state running 2>/dev/null | \\
    grep -E "chromium|electron" | \\
    awk '{print $1}' | \\
    xargs -r systemctl --user stop 2>/dev/null
  `], {
    stdio: 'ignore',
    detached: true
  });
  cleanup.unref();
}

// Run cleanup on startup
app.on('ready', () => {
  cleanupStaleScopes();
});

module.exports = { cleanupStaleScopes };
