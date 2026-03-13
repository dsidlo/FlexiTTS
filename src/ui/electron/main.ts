import { app, BrowserWindow, ipcMain, dialog } from 'electron';
import * as path from 'path';
import { spawn, ChildProcess } from 'child_process';
import * as fs from 'fs';
import * as jsyaml from 'js-yaml';
import { pathToFileURL } from 'url';

// Simple file logger - writes to /tmp/FlexiTTS.log only (no console output)
const LOG_FILE = '/tmp/FlexiTTS.log';
function writeLog(level: string, ...args: any[]) {
  const timestamp = new Date().toISOString();
  const message = args.map(a => typeof a === 'object' ? JSON.stringify(a) : String(a)).join(' ');
  const line = `[${timestamp}] ${level}: ${message}\n`;
  try {
    fs.appendFileSync(LOG_FILE, line);
  } catch (e) {
    // If we can't write to log file, silently fail
  }
}
const log = {
  info: (...args: any[]) => writeLog('INFO', ...args),
  error: (...args: any[]) => writeLog('ERROR', ...args),
  warn: (...args: any[]) => writeLog('WARN', ...args)
};

// Store active processes so they can be killed
const activeProcesses: Map<string, ChildProcess> = new Map();

// Store TTS service process for cleanup
let ttsServiceProcess: ChildProcess | null = null;

// Track if we're shutting down to prevent new operations
let isShuttingDown = false;
let shutdownInProgress = false;
let shutdownCompleted = false;

// Store project root for path validation - initialized once at module load time
const projectRoot: string = path.resolve(__dirname, '../../../../');

/**
 * Security: Validate that a path is within a parent directory
 * Prevents path traversal attacks
 * Uses path.relative() for proper comparison with case-normalization support
 */
function isPathWithinParent(childPath: string, parentPath: string): boolean {
  try {
    const child = path.normalize(path.resolve(childPath));
    const parent = path.normalize(path.resolve(parentPath));
    
    // Use path.relative() for proper path comparison
    // This handles case-insensitive filesystems and various edge cases
    const relative = path.relative(parent, child);
    
    // If relative path starts with '..', child is outside parent
    // If path.isAbsolute(relative), there's an error or inconsistency
    return !relative.startsWith('..') && !path.isAbsolute(relative);
  } catch (e) {
    return false;
  }
}

/**
 * Security: Sanitize path to prevent directory traversal
 */
function sanitizePath(inputPath: string): string {
  // Normalize path
  let sanitized = path.normalize(inputPath);
  
  // Remove any leading parent directory references
  while (sanitized.startsWith('..' + path.sep) || sanitized.startsWith('..')) {
    sanitized = sanitized.substring(3); // Remove '../' or '..'
    while (sanitized.startsWith(path.sep)) {
      sanitized = sanitized.substring(1);
    }
  }
  
  return sanitized;
}

/**
 * Security: Validate IPC arguments to prevent injection
 */
function validateScriptArguments(args: string[]): string[] {
  const validated: string[] = [];
  
  for (const arg of args) {
    // Reject arguments that could be malicious
    if (arg.includes(';') || arg.includes('&&') || arg.includes('||') || arg.includes('|')) {
      throw new Error('Invalid argument: contains shell metacharacters');
    }

    // Preserve URL arguments exactly; path normalization corrupts ws:// into ws:/
    if (/^[a-zA-Z][a-zA-Z0-9+.-]*:\/\//.test(arg)) {
      validated.push(arg);
      continue;
    }
    
    validated.push(sanitizePath(arg));
  }
  
  return validated;
}

/**
 * Security: Expand ~ to home directory safely
 */
function expandTilde(inputPath: string): string {
  if (inputPath.startsWith('~')) {
    const homeDir = process.env.HOME || process.env.USERPROFILE || '';
    return path.join(homeDir, inputPath.substring(1));
  }
  return inputPath;
}

// Kill all active Python processes
function killAllActiveProcesses() {
  log.info(`[Cleanup] Killing ${activeProcesses.size} active Python processes...`);
  const procsToKill = Array.from(activeProcesses.entries());
  activeProcesses.clear(); // Clear immediately to prevent re-kill attempts
  
  procsToKill.forEach(([id, proc]) => {
    try {
      if (proc.pid && !proc.killed) {
        log.info(`[Cleanup] Killing ${id} (PID ${proc.pid})`);
        proc.kill('SIGTERM');
        // Force kill after 2 seconds if still running
        setTimeout(() => {
          try {
            process.kill(proc.pid!, 'SIGKILL');
          } catch (e) {
            // Already dead
          }
        }, 2000);
      }
    } catch (e) {
      log.error(`[Cleanup] Failed to kill ${id}:`, e);
    }
  });
  
  // Also kill TTS warmup process if running
  if (ttsServiceProcess?.pid && !ttsServiceProcess.killed) {
    try {
      log.info(`[Cleanup] Killing TTS warmup process (PID ${ttsServiceProcess.pid})`);
      ttsServiceProcess.kill('SIGTERM');
      setTimeout(() => {
        if (ttsServiceProcess?.pid && !ttsServiceProcess.killed) {
          try {
            process.kill(ttsServiceProcess.pid, 'SIGKILL');
          } catch (e) {
            // Already dead
          }
        }
      }, 2000);
    } catch (e) {
      log.info('[Cleanup] Failed to kill TTS warmup process:', e);
    }
  }
}

function sleep(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms));
}

function getTtsServicePid(): number | null {
  try {
    const pidFile = '/tmp/FlexiTTS_tts_service.pid';
    if (!fs.existsSync(pidFile)) return null;
    const raw = fs.readFileSync(pidFile, 'utf-8').trim();
    const pid = Number.parseInt(raw, 10);
    return Number.isFinite(pid) ? pid : null;
  } catch (e) {
    log.warn('[App] Failed to read TTS PID file', e);
    return null;
  }
}

function isProcessRunning(pid: number): boolean {
  try {
    process.kill(pid, 0);
    return true;
  } catch (e) {
    return false;
  }
}

async function waitForTtsServiceExit(timeoutMs: number): Promise<boolean> {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    const pid = getTtsServicePid();
    if (!pid) {
      log.info('[App] TTS service PID file missing; assuming stopped');
      return true;
    }
    if (!isProcessRunning(pid)) {
      log.info(`[App] TTS service process ${pid} is no longer running`);
      try {
        fs.unlinkSync('/tmp/FlexiTTS_tts_service.pid');
      } catch (e) {
        // ignore
      }
      return true;
    }
    await sleep(100);
  }
  return false;
}

function runStopTtsService(force: boolean): Promise<boolean> {
  const { exec } = require('child_process');
  const cmd = force
    ? 'uv run python src/scripts/stop_tts_service.py --force --silent'
    : 'uv run python src/scripts/stop_tts_service.py --silent';

  log.info('[App] Invoking TTS stop command', { force, cmd });

  return new Promise((resolve) => {
    exec(cmd, {
      cwd: projectRoot,
      timeout: 10000
    }, (err: any, stdout: string, stderr: string) => {
      if (stdout?.trim()) log.info('[App] TTS stop stdout', stdout.trim());
      if (stderr?.trim()) log.warn('[App] TTS stop stderr', stderr.trim());
      if (err) {
        log.warn('[App] TTS stop command returned error', { force, error: String(err) });
        resolve(false);
        return;
      }
      resolve(true);
    });
  });
}

async function ensureTtsServiceStoppedOrWarn(): Promise<void> {
  const pidBefore = getTtsServicePid();
  if (!pidBefore) {
    log.info('[App] No TTS service PID file found during shutdown');
    return;
  }

  log.info('[App] TTS shutdown verification starting', { pidBefore });

  await runStopTtsService(false);
  if (await waitForTtsServiceExit(3000)) {
    log.info('[App] TTS service stopped after graceful shutdown');
    return;
  }

  const pidAfterTerm = getTtsServicePid();
  log.warn('[App] TTS service still running after SIGTERM window', { pidAfterTerm });

  await runStopTtsService(true);
  if (await waitForTtsServiceExit(3000)) {
    log.info('[App] TTS service stopped after forced shutdown');
    return;
  }

  const pidAfterKill = getTtsServicePid();
  log.error('[App] TTS service still running after forced shutdown', { pidAfterKill });

  await dialog.showMessageBox({
    type: 'warning',
    buttons: ['OK'],
    defaultId: 0,
    cancelId: 0,
    title: 'TTS Service Still Running',
    message: 'The TTS service is still running and could not be stopped automatically.',
    detail: pidAfterKill
      ? `The background TTS service (PID ${pidAfterKill}) is still running. Click OK to exit the app.`
      : 'The background TTS service may still be running. Click OK to exit the app.'
  });
}

async function performShutdownAndQuit() {
  if (shutdownCompleted) {
    log.info('[App] Shutdown already completed; quitting immediately');
    app.exit(0);
    return;
  }
  if (shutdownInProgress) {
    log.info('[App] Shutdown already in progress; ignoring duplicate request');
    return;
  }

  shutdownInProgress = true;
  isShuttingDown = true;
  log.info('[App] performShutdownAndQuit: starting cleanup');

  try {
    killAllActiveProcesses();
    await ensureTtsServiceStoppedOrWarn();
  } catch (e) {
    log.error('[App] Error during TTS shutdown sequence', e);
    try {
      await dialog.showMessageBox({
        type: 'warning',
        buttons: ['OK'],
        defaultId: 0,
        cancelId: 0,
        title: 'TTS Service Shutdown Error',
        message: 'An error occurred while stopping the TTS service.',
        detail: `${e}`
      });
    } catch {
      // ignore dialog failures
    }
  }

  try {
    killDevServerProcesses();
  } catch (e) {
    log.warn('[App] Failed to kill dev server processes', e);
  }

  shutdownCompleted = true;
  shutdownInProgress = false;
  log.info('[App] Shutdown complete; exiting application');
  app.exit(0);
}

// Kill dev server processes (vite, npm, concurrently) when app exits
function killDevServerProcesses() {
  const { exec } = require('child_process');
  
  log.info('[Cleanup] Killing dev server processes...');
  
  // Kill vite dev server on port 5173
  exec('pkill -f "vite --port 5173" 2>/dev/null || true', (err: any) => {
    if (!err) log.info('[Cleanup] Vite dev server killed');
  });
  
  // Kill npm processes related to our Electron app
  exec('pkill -f "npm run electron:dev" 2>/dev/null || true', () => {});
  exec('pkill -f "concurrently" 2>/dev/null || true', () => {});
  exec('pkill -f "wait-on" 2>/dev/null || true', () => {});
  
  // Try to kill by parent process chain - find and kill the npm start process
  // Get our parent PID and traverse up
  try {
    const ppid = process.ppid;
    if (ppid) {
      log.info(`[Cleanup] Our parent PID is ${ppid}`);
      // Kill the parent process group (npm/concurrently)
      setTimeout(() => {
        try {
          process.kill(ppid, 'SIGTERM');
          log.info(`[Cleanup] Sent SIGTERM to parent ${ppid}`);
        } catch (e) {
          // Parent may already be dead
        }
      }, 500);
    }
  } catch (e) {
    log.info('[Cleanup] Could not kill parent process:', e);
  }
}

// Handle creating/removing shortcuts on Windows when installing/uninstalling.
try {
  if (require('electron-squirrel-startup')) {
    app.quit();
  }
} catch (e) {
  // Ignore missing electron-squirrel-startup in dev mode
}

const createWindow = () => {
  // Create the browser window.
  const mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'), 
      nodeIntegration: false,
      contextIsolation: true,
    },
  });

  // Load the index.html of the app.
  // In development, the concurrently command runs Vite locally at port 5173
  // Since we aren't setting process.env.VITE_DEV_SERVER_URL in the npm script, we hardcode it for dev
  const isDev = !app.isPackaged;
  if (isDev) {
    mainWindow.loadURL('http://localhost:5173');
    mainWindow.webContents.openDevTools();
  } else {
    mainWindow.loadFile(path.join(__dirname, '../dist/index.html'));
  }
};

// Ignore certificate errors for local dev server
app.commandLine.appendSwitch('ignore-certificate-errors');

// Add a CSP rule to suppress the warning during development
process.env.ELECTRON_DISABLE_SECURITY_WARNINGS = 'true';

function killExistingTtsWsServerProcesses(): Promise<void> {
  const { exec } = require('child_process');
  const scriptMatch = `${projectRoot}/src/scripts/tts_ws_server.py`;

  log.info(`[TTS Warmup] Checking for existing TTS server processes: ${scriptMatch}`);

  return new Promise((resolve) => {
    exec(`pkill -f "${scriptMatch}" 2>/dev/null || true`, (err: any, stdout: string, stderr: string) => {
      if (err) {
        log.warn('[TTS Warmup] pkill returned error while stopping existing TTS server', { err: String(err), stdout, stderr });
      } else {
        log.info('[TTS Warmup] Existing tts_ws_server.py processes terminated (if any)');
      }

      setTimeout(() => resolve(), 1000);
    });
  });
}

// Start TTS service on app startup
async function warmupTTSService() {
  log.info('[TTS Warmup] Starting TTS service warmup...');
  await killExistingTtsWsServerProcesses();
  
  return new Promise<void>((resolve) => {
    ttsServiceProcess = spawn('uv', ['run', 'python', 'src/scripts/start_tts_service.py'], {
      cwd: projectRoot,
      stdio: 'pipe'
    });
    
    let output = '';
    ttsServiceProcess.stdout?.on('data', (data) => {
      output += data.toString();
      log.info(`[TTS Warmup] ${data.toString().trim()}`);
    });
    
    ttsServiceProcess.stderr?.on('data', (data) => {
      log.error(`[TTS Warmup Error] ${data.toString().trim()}`);
    });
    
    ttsServiceProcess.on('close', (code) => {
      log.info(`[TTS Warmup] Process exited with code ${code}`);
      ttsServiceProcess = null;
      resolve();
    });
    
    // Timeout after 5 minutes (should be enough for warmup)
    setTimeout(() => {
      log.info('[TTS Warmup] Timeout - proceeding anyway');
      resolve();
    }, 300000);
  });
}

app.whenReady().then(async () => {
  // Initialize current story from global config
  try {
    const config = await loadGlobalConfig();
    log.info(`[App Init] Loaded global config:`, config);
    if (config?.FlexiTTS?.['current-story']) {
      const storyName = config.FlexiTTS['current-story'];
      const prefix = config.FlexiTTS?.['story-dir-prefix'] || 'Story-';
      currentStoryDirectory = `${prefix}${storyName}`;
      log.info(`[App Init] Loaded current story from config: ${currentStoryDirectory} (prefix=${prefix}, name=${storyName})`);
    } else {
      log.warn('[App Init] No current-story in global config');
    }
  } catch (err) {
    log.error('[App Init] Failed to load current story from config:', err);
  }
  
  // Start TTS warmup in background
  warmupTTSService().catch(e => log.error('[TTS Warmup] Failed:', e));
  
  // Create window immediately (don't wait for warmup)
  createWindow();
});

app.on('window-all-closed', () => {
  log.info('[App] window-all-closed received');
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

// Also handle before-quit for macOS and other cases
app.on('before-quit', (event) => {
  log.info('[App] before-quit received', { shutdownCompleted, shutdownInProgress });
  if (shutdownCompleted) {
    return;
  }
  event.preventDefault();
  void performShutdownAndQuit();
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});

// IPC Handlers for Python Scripts
// SECURITY: All handlers validate paths before file operations

/**
 * Execute a Python script and capture output
 * Reusable function for running Python scripts from main process
 */
async function executePythonScript(scriptPath: string, args: string[]): Promise<{ stdout: string; stderr: string; code: number | null }> {
  const config = await loadGlobalConfig();
  const storiesDir = getStoriesDirFromConfig(config);

  return new Promise((resolve, reject) => {
    try {
      // Validate arguments for security
      const validatedArgs = validateScriptArguments(args);
      
      log.info(`[Python] Executing: ${scriptPath} ${validatedArgs.join(' ')}`);
      
      // Security: Validate script path is within project
      const fullScriptPath = path.join(projectRoot, scriptPath);
      if (!isPathWithinParent(fullScriptPath, projectRoot)) {
        reject(new Error('Security: Script path is outside project directory'));
        return;
      }

      // Resolve story-relative args using global config stories-dir
      const resolvedArgs = validatedArgs.map((arg) => {
        if (arg.startsWith('Story-')) {
          return path.join(storiesDir, arg);
        }
        return arg;
      });
      log.info(`[Python] Resolved args: ${resolvedArgs.join(' ')}`);
      
      // Check if it's the validate_config.py call that might fail silently if uv isn't set up yet
      const isValidationCall = scriptPath.includes('validate_config.py');

      const pythonProcess = spawn('uv', ['run', 'python', scriptPath, ...resolvedArgs], {
        cwd: projectRoot
      });
      
      // Store process to allow cancellation
      const procId = `python-${scriptPath}-${validatedArgs.join('-')}`;
      activeProcesses.set(procId, pythonProcess);

      let output = '';
      let errorOutput = '';

      pythonProcess.stdout.on('data', (data) => {
        output += data.toString();
      });

      pythonProcess.stderr.on('data', (data) => {
        errorOutput += data.toString();
      });

      pythonProcess.on('close', (code, signal) => {
        activeProcesses.delete(procId);
        log.info(`[Python] Process exited with code ${code} signal ${signal}`);
        
        if (signal === 'SIGTERM' || signal === 'SIGKILL') {
           reject(new Error(`Process cancelled by user`));
           return;
        }
        
        if (code !== 0 && errorOutput.trim()) {
          if (isValidationCall) {
              log.warn(`[Python] Ignoring validation error code ${code}`);
              resolve({ stdout: output, stderr: errorOutput, code: 0 });
          } else {
              reject(new Error(errorOutput || `Process exited with code ${code}`));
          }
        } else {
          resolve({ stdout: output, stderr: errorOutput, code });
        }
      });
    } catch (e: any) {
      reject(new Error(`Security validation failed: ${e.message}`));
    }
  });
}

// IPC handler - wrapper around executePythonScript
ipcMain.handle('run-python-script', async (event, scriptPath: string, args: string[]) => {
  try {
    const result = await executePythonScript(scriptPath, args);
    return result.stdout;
  } catch (e: any) {
    throw e;
  }
});

ipcMain.handle('kill-process', async (event, matchString: string) => {
  log.info(`[IPC] Request to kill process matching: ${matchString}`);
  let killed = false;
  
  // Validate matchString to prevent injection
  if (matchString.includes(';') || matchString.includes('&&') || matchString.includes('|')) {
    log.error('[Security] Rejecting kill-process with invalid matchString');
    return false;
  }
  
  Array.from(activeProcesses.entries()).forEach(([key, proc]) => {
     // A more generous matching scheme to catch audio play commands
     if (key.includes(matchString) || (key.startsWith('audio-') && matchString.includes('.xml'))) {
         log.info(`[IPC] Killing process: ${key}`);
         proc.kill('SIGKILL'); 
         killed = true;
     }
  });
  return killed;
});

ipcMain.handle('read-file', async (event, filePath: string) => {
  const resourceType = filePath.endsWith('.md') ? 'markdown' : filePath.endsWith('.xml') ? 'xml' : filePath.endsWith('.wav') ? 'audio' : 'unknown';
  log.info(`[IPC][RESOURCE-ACCESS] read-file requested`, { filePath, resourceType, operation: 'read' });
  
  try {
    // Security: Sanitize input path
    let sanitizedPath = sanitizePath(filePath);
    log.info(`[IPC][RESOURCE-ACCESS] Sanitized path: ${sanitizedPath}`);
    
    // Load global config to get stories-dir
    const configPath = getGlobalConfigPath();
    let storiesDir: string | undefined;
    
    if (fs.existsSync(configPath)) {
      try {
        const configContent = fs.readFileSync(configPath, 'utf-8');
        const config = jsyaml.load(configContent) as any;
        storiesDir = config?.FlexiTTS?.['stories-dir'];
        if (storiesDir) {
          storiesDir = expandTilde(storiesDir);
          log.info(`[IPC][RESOURCE-ACCESS] Using stories-dir from config: ${storiesDir}`);
        }
      } catch (err) {
        log.warn(`[IPC][RESOURCE-ACCESS] Failed to load config for path resolution: ${err}`);
      }
    }
    
    // For story-related paths (starting with Story-), prepend the configured stories-dir
    if (sanitizedPath.startsWith('Story-')) {
      if (storiesDir) {
        sanitizedPath = path.join(storiesDir, sanitizedPath);
        log.info(`[IPC][RESOURCE-ACCESS] Resolved story path using config stories-dir: ${sanitizedPath}`);
      } else {
        // Fallback: use default Stories/ relative to project root
        sanitizedPath = path.join(projectRoot, 'Stories', sanitizedPath);
        log.info(`[IPC][RESOURCE-ACCESS] Resolved story path using fallback: ${sanitizedPath}`);
      }
    } else if (!path.isAbsolute(sanitizedPath)) {
      // For non-story paths, resolve relative to project root
      sanitizedPath = path.join(projectRoot, sanitizedPath);
    }
    
    const fullPath = path.normalize(sanitizedPath);
    log.info(`[IPC][RESOURCE-ACCESS] Final resolved full path: ${fullPath}`);
    
    // Security: Validate path is within project or stories directory
    if (!isPathWithinParent(fullPath, projectRoot) && (!storiesDir || !isPathWithinParent(fullPath, storiesDir))) {
      log.error(`[IPC][RESOURCE-ACCESS] Security: Path outside allowed directories: ${fullPath}`);
      throw new Error('Security: File path is outside allowed directories');
    }
    
    if (!fs.existsSync(fullPath)) {
      log.error(`[IPC][RESOURCE-ACCESS] File NOT found: ${fullPath}`);
      throw new Error(`File not found: ${filePath}`);
    }
    
    const content = fs.readFileSync(fullPath, 'utf-8');
    log.info(`[IPC][RESOURCE-ACCESS] Successfully read file`, { filePath, fullPath, resourceType, length: content.length });
    return content;
  } catch (err: any) {
    log.error(`[IPC][RESOURCE-ACCESS] Error reading file: ${err.message}`, { filePath });
    throw new Error(`Failed to read file ${filePath}: ${err.message}`);
  }
});

ipcMain.handle('write-file', async (event, filePath: string, content: string) => {
  const resourceType = filePath.endsWith('.md') ? 'markdown' : filePath.endsWith('.xml') ? 'xml' : 'unknown';
  log.info(`[IPC][RESOURCE-ACCESS] write-file requested`, { filePath, resourceType, operation: 'write', contentLength: content.length });
  
  try {
    // Security: Sanitize path
    let sanitizedPath = sanitizePath(filePath);
    log.info(`[IPC][RESOURCE-ACCESS] Sanitized write path: ${sanitizedPath}`);

    // Load global config to get stories-dir for story-relative writes
    const configPath = getGlobalConfigPath();
    let storiesDir: string | undefined;

    if (fs.existsSync(configPath)) {
      try {
        const configContent = fs.readFileSync(configPath, 'utf-8');
        const config = jsyaml.load(configContent) as any;
        storiesDir = config?.FlexiTTS?.['stories-dir'];
        if (storiesDir) {
          storiesDir = expandTilde(storiesDir);
          log.info(`[IPC][RESOURCE-ACCESS] Using stories-dir from config for write: ${storiesDir}`);
        }
      } catch (err) {
        log.warn(`[IPC][RESOURCE-ACCESS] Failed to load config for write path resolution: ${err}`);
      }
    }
    
    // Determine absolute path using same story-aware resolution as read-file
    if (sanitizedPath.startsWith('Story-')) {
      if (storiesDir) {
        sanitizedPath = path.join(storiesDir, sanitizedPath);
        log.info(`[IPC][RESOURCE-ACCESS] Resolved story write path using config stories-dir: ${sanitizedPath}`);
      } else {
        sanitizedPath = path.join(projectRoot, 'Stories', sanitizedPath);
        log.info(`[IPC][RESOURCE-ACCESS] Resolved story write path using fallback: ${sanitizedPath}`);
      }
    } else if (!path.isAbsolute(sanitizedPath)) {
      sanitizedPath = path.join(projectRoot, sanitizedPath);
      log.info(`[IPC][RESOURCE-ACCESS] Resolved non-story write path relative to project root: ${sanitizedPath}`);
    }

    const fullPath = path.normalize(sanitizedPath);
    log.info(`[IPC][RESOURCE-ACCESS] Final resolved write path: ${fullPath}`);
    
    // Allow log files to be written outside project/stories directories
    const isLogFile = fullPath === '/tmp/FlexiTTS.log' || fullPath.startsWith('/tmp/FlexiTTS');
    
    // Security: Validate path is within project or configured stories directory (skip for log files)
    if (!isLogFile && !isPathWithinParent(fullPath, projectRoot) && (!storiesDir || !isPathWithinParent(fullPath, storiesDir))) {
      log.error(`[IPC][RESOURCE-ACCESS] Security: Path outside allowed directories for write: ${fullPath}`);
      throw new Error('Security: File path is outside allowed directories');
    }
    
    // Ensure directory exists
    const dir = path.dirname(fullPath);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
      log.info(`[IPC][RESOURCE-ACCESS] Created parent directory for write`, { dir, filePath, fullPath });
    }
    
    // For log files, append instead of overwrite
    if (isLogFile) {
      fs.appendFileSync(fullPath, content, 'utf-8');
      log.info(`[IPC][RESOURCE-ACCESS] Appended to log file`, { path: fullPath });
    } else {
      fs.writeFileSync(fullPath, content, 'utf-8');
      log.info(`[IPC][RESOURCE-ACCESS] Successfully wrote file`, { filePath, fullPath, resourceType, contentLength: content.length });
    }
    return true;
  } catch (err: any) {
    log.error(`[IPC][RESOURCE-ACCESS] Failed to write file: ${err.message}`, { filePath });
    throw new Error(`Failed to write file ${filePath}: ${err.message}`);
  }
});

ipcMain.handle('read-audio-file', async (event, filePath: string) => {
  log.info(`[IPC][RESOURCE-ACCESS] read-audio-file requested`, { filePath, resourceType: 'audio', operation: 'read' });
  
  try {
    let sanitizedPath = sanitizePath(filePath);
    const configPath = getGlobalConfigPath();
    let storiesDir: string | undefined;

    if (fs.existsSync(configPath)) {
      try {
        const configContent = fs.readFileSync(configPath, 'utf-8');
        const config = jsyaml.load(configContent) as any;
        storiesDir = config?.FlexiTTS?.['stories-dir'];
        if (storiesDir) {
          storiesDir = expandTilde(storiesDir);
        }
      } catch (err) {
        log.warn(`[IPC][RESOURCE-ACCESS] Failed to load config for audio path resolution: ${err}`);
      }
    }

    if (sanitizedPath.startsWith('Story-')) {
      if (storiesDir) {
        sanitizedPath = path.join(storiesDir, sanitizedPath);
      } else {
        sanitizedPath = path.join(projectRoot, 'Stories', sanitizedPath);
      }
    } else if (!path.isAbsolute(sanitizedPath)) {
      sanitizedPath = path.join(projectRoot, sanitizedPath);
    }

    const fullPath = path.normalize(sanitizedPath);
    log.info(`[IPC][RESOURCE-ACCESS] Resolved audio path: ${fullPath}`);
    
    if (!isPathWithinParent(fullPath, projectRoot) && (!storiesDir || !isPathWithinParent(fullPath, storiesDir))) {
      log.error(`[IPC][RESOURCE-ACCESS] Security: Path outside allowed directories: ${fullPath}`);
      throw new Error('Security: Audio file path is outside allowed directories');
    }
    
    if (!fs.existsSync(fullPath)) {
      log.error(`[IPC][RESOURCE-ACCESS] Audio file NOT found: ${fullPath}`);
      throw new Error(`Audio file not found: ${filePath}`);
    }
    
    const data = fs.readFileSync(fullPath);
    const base64 = data.toString('base64');
    log.info(`[IPC][RESOURCE-ACCESS] Successfully read audio file`, { filePath, fullPath, length: data.length });
    return `data:audio/wav;base64,${base64}`;
  } catch (err: any) {
    log.error(`[IPC][RESOURCE-ACCESS] Failed to read audio file: ${err.message}`, { filePath });
    throw new Error(`Failed to read audio file ${filePath}: ${err.message}`);
  }
});

// FlexiTTS Global Config Management
const GLOBAL_CONFIG_FILENAME = 'FlexiTTS.yml'; // Default to .yml (more common), fallback to .yaml
const GLOBAL_CONFIG_FILENAME_ALT = 'FlexiTTS.yaml';

function getGlobalConfigPath(): string {
  const homeDir = process.env.HOME || process.env.USERPROFILE || '';
  const configDir = process.env.XDG_CONFIG_HOME || path.join(homeDir, '.config');
  const configSubdir = path.join(configDir, 'FlexiTTS');
  
  // Try .yml first, then .yaml
  const ymlPath = path.join(configSubdir, GLOBAL_CONFIG_FILENAME);
  const yamlPath = path.join(configSubdir, GLOBAL_CONFIG_FILENAME_ALT);
  
  if (fs.existsSync(ymlPath)) {
    log.info(`[getGlobalConfigPath] Found config: ${ymlPath}`);
    return ymlPath;
  } else if (fs.existsSync(yamlPath)) {
    log.info(`[getGlobalConfigPath] Found config: ${yamlPath}`);
    return yamlPath;
  } else {
    log.warn(`[getGlobalConfigPath] Config not found, defaulting to: ${ymlPath}`);
    return ymlPath;
  }
}

function ensureGlobalConfigDir(): string {
  const homeDir = process.env.HOME || process.env.USERPROFILE || '';
  const configDir = process.env.XDG_CONFIG_HOME || path.join(homeDir, '.config');
  const flexittsDir = path.join(configDir, 'FlexiTTS');
  if (!fs.existsSync(flexittsDir)) {
    fs.mkdirSync(flexittsDir, { recursive: true });
  }
  return flexittsDir;
}

function getStoriesDirFromConfig(config: any): string {
  const homeDir = process.env.HOME || process.env.USERPROFILE || '';
  const dataDir = process.env.XDG_DATA_HOME || path.join(homeDir, '.local', 'share');
  const defaultStoriesDir = path.join(dataDir, 'FlexiTTS', 'stories');
  
  if (config?.FlexiTTS?.['stories-dir']) {
    const configuredDir = config.FlexiTTS['stories-dir'];
    // Expand ~ safely using our function
    return expandTilde(configuredDir);
  }
  return defaultStoriesDir;
}

function getStoryDirPrefix(config: any): string {
  return config?.FlexiTTS?.['story-dir-prefix'] || 'Story-';
}

// Standalone function to load global config (used during app initialization)
async function loadGlobalConfig(): Promise<any> {
  const configPath = getGlobalConfigPath();
  log.info(`[loadGlobalConfig] Checking config path: ${configPath}`);
  try {
    if (fs.existsSync(configPath)) {
      log.info(`[loadGlobalConfig] Config file exists, reading...`);
      const content = fs.readFileSync(configPath, 'utf-8');
      const parsed = jsyaml.load(content);
      log.info(`[loadGlobalConfig] Successfully loaded config:`, parsed);
      return parsed;
    } else {
      log.warn(`[loadGlobalConfig] Config file NOT found at: ${configPath}`);
    }
  } catch (err) {
    log.error(`[loadGlobalConfig] Failed to load: ${err}`);
  }
  // Return default config if file doesn't exist
  const homeDir = process.env.HOME || process.env.USERPROFILE || '';
  const dataDir = process.env.XDG_DATA_HOME || path.join(homeDir, '.local', 'share');
  const defaultConfig = {
    FlexiTTS: {
      'stories-dir': path.join(dataDir, 'FlexiTTS', 'stories'),
      'story-dir-prefix': 'Story-'
    }
  };
  log.warn(`[loadGlobalConfig] Returning default config:`, defaultConfig);
  return defaultConfig;
}

ipcMain.handle('load-global-config', async () => {
  return loadGlobalConfig();
});

ipcMain.handle('save-global-config', async (event, configData: any) => {
  try {
    const configPath = getGlobalConfigPath();
    ensureGlobalConfigDir();
    const yamlContent = jsyaml.dump(configData, { indent: 2 });
    fs.writeFileSync(configPath, yamlContent, 'utf-8');
    return true;
  } catch (err) {
    log.error(`Failed to save global config: ${err}`);
    return false;
  }
});

ipcMain.handle('list-stories', async () => {
  try {
    // Load global config directly
    const configPath = getGlobalConfigPath();
    let config: any = null;
    
    try {
      if (fs.existsSync(configPath)) {
        const content = fs.readFileSync(configPath, 'utf-8');
        config = jsyaml.load(content);
      }
    } catch (err) {
      log.error(`Failed to load config for list-stories: ${err}`);
    }
    
    const storiesDir = getStoriesDirFromConfig(config);
    const storyPrefix = getStoryDirPrefix(config);
    
    if (!fs.existsSync(storiesDir)) {
      return [];
    }
    
    const entries = fs.readdirSync(storiesDir, { withFileTypes: true });
    const stories = entries
      .filter(entry => entry.isDirectory() && entry.name.startsWith(storyPrefix))
      .map(entry => {
        const displayName = entry.name.slice(storyPrefix.length);
        return {
          name: displayName,
          path: path.join(storiesDir, entry.name),
          directory_name: entry.name
        };
      })
      .sort((a, b) => a.name.localeCompare(b.name));
    
    return stories;
  } catch (err) {
    log.error(`Failed to list stories: ${err}`);
    return [];
  }
});

// Store current story state for the session
let currentStoryDirectory: string = '';

ipcMain.handle('set-current-story', async (event, storyDirectory: string) => {
  // Validate story directory name (alphanumeric, hyphens, underscores only)
  if (!/^[\w-]+$/.test(storyDirectory)) {
    throw new Error('Invalid story directory name');
  }
  currentStoryDirectory = storyDirectory;
  return true;
});

ipcMain.handle('get-current-story', async () => {
  log.info(`[get-current-story] Returning: ${currentStoryDirectory}`);
  return currentStoryDirectory;
});

// Enhanced file operations that are story-aware
// SECURITY: All handlers validate paths to prevent directory traversal

ipcMain.handle('load-story-config', async (event, storyDir: string) => {
  log.info(`[IPC][RESOURCE-ACCESS] load-story-config requested`);
  log.info(`  storyDir: ${storyDir}`);
  
  try {
    if (!/^[\w-]+$/.test(storyDir)) {
      throw new Error('Invalid story directory name');
    }

    const config = await loadGlobalConfig();
    const storiesDir = getStoriesDirFromConfig(config);
    const configPath = path.join(storiesDir, storyDir, 'story-config.yml');
    log.info(`[IPC][RESOURCE-ACCESS] Resolved config path: ${configPath}`);
    
    if (!isPathWithinParent(configPath, storiesDir)) {
      log.info(`[IPC][RESOURCE-ACCESS] Security: Path outside stories dir: ${configPath}`);
      throw new Error('Security: Config path outside stories directory');
    }
    
    if (!fs.existsSync(configPath)) {
      log.info(`[IPC][RESOURCE-ACCESS] Config not found: ${configPath}`);
      throw new Error(`Story config not found: ${storyDir}`);
    }
    
    const content = fs.readFileSync(configPath, 'utf-8');
    log.info(`[IPC][RESOURCE-ACCESS] Successfully loaded story config`, { storyDir, configPath, storiesDir, contentLength: content.length });
    return jsyaml.load(content);
  } catch (err: any) {
    log.error(`[IPC][RESOURCE-ACCESS] Failed to load story config: ${storyDir}: ${err.message}`);
    throw new Error(`Failed to load story config from ${storyDir}: ${err.message}`);
  }
});

ipcMain.handle('list-chapter-files-for-story', async (event, storyDir: string) => {
  try {
    if (!/^[\w-]+$/.test(storyDir)) {
      throw new Error('Invalid story directory name');
    }

    const config = await loadGlobalConfig();
    const storiesDir = getStoriesDirFromConfig(config);
    const mdDirPath = path.join(storiesDir, storyDir, 'story-chapters');
    
    if (!isPathWithinParent(mdDirPath, storiesDir)) {
      throw new Error('Security: Chapter path outside stories directory');
    }
    
    if (fs.existsSync(mdDirPath)) {
      return fs.readdirSync(mdDirPath)
               .filter(f => f.endsWith('.md') && fs.statSync(path.join(mdDirPath, f)).isFile())
               .map(f => `${storyDir}/story-chapters/${f}`);
    }

    const xmlDirPath = path.join(storiesDir, storyDir, 'story-xml');
    if (!isPathWithinParent(xmlDirPath, storiesDir)) {
      throw new Error('Security: XML path outside stories directory');
    }
    
    if (fs.existsSync(xmlDirPath)) {
      return fs.readdirSync(xmlDirPath)
               .filter(f => f.endsWith('.xml'))
               .map(f => `${storyDir}/story-xml/${f}`);
    }
  } catch (err) {
    log.error(`Failed to read story chapter directory for ${storyDir}: ${err}`);
  }
  return [];
});

ipcMain.handle('check-xml-exists-for-story', async (event, chapterStem: string, storyDir: string) => {
  try {
    if (!/^[\w-]+$/.test(storyDir)) {
      throw new Error('Invalid story directory name');
    }

    if (typeof chapterStem !== 'string' || !chapterStem.trim()) {
      throw new Error('Invalid chapter stem');
    }
    if (chapterStem.includes('/') || chapterStem.includes('\\') || chapterStem.includes('..')) {
      throw new Error('Security: Invalid chapter stem path content');
    }

    const config = await loadGlobalConfig();
    const storiesDir = getStoriesDirFromConfig(config);
    const xmlPath = path.join(storiesDir, storyDir, 'story-xml', `${chapterStem}.xml`);
    log.info(`[check-xml-exists-for-story] Checking XML path`, { storyDir, chapterStem, xmlPath });
    
    if (!isPathWithinParent(xmlPath, storiesDir)) {
      throw new Error('Security: XML path outside stories directory');
    }
    
    const exists = fs.existsSync(xmlPath);
    log.info(`[check-xml-exists-for-story] XML exists check complete`, { storyDir, chapterStem, xmlPath, exists });
    return exists;
  } catch (err) {
    log.error(`Failed to check if XML exists for ${storyDir}: ${err}`);
    return false;
  }
});

ipcMain.handle('check-story-file-exists', async (event, storyDir: string, relativePath: string) => {
  try {
    if (!/^[\w-]+$/.test(storyDir)) {
      throw new Error('Invalid story directory name');
    }

    if (typeof relativePath !== 'string' || !relativePath.trim()) {
      throw new Error('Invalid relative path');
    }

    if (path.isAbsolute(relativePath) || relativePath.includes('..')) {
      throw new Error('Security: Invalid relative path');
    }

    const config = await loadGlobalConfig();
    const storiesDir = getStoriesDirFromConfig(config);
    const storyRoot = path.join(storiesDir, storyDir);
    const targetPath = path.resolve(storyRoot, relativePath);

    if (!isPathWithinParent(targetPath, storyRoot)) {
      throw new Error('Security: Target path outside story directory');
    }

    const exists = fs.existsSync(targetPath);
    log.info(`[check-story-file-exists] File existence check complete`, { storyDir, relativePath, targetPath, exists });
    return exists;
  } catch (err) {
    log.error(`Failed to check story file existence for ${storyDir}: ${err}`);
    return false;
  }
});

// Legacy handler for backward compatibility - uses current story context
ipcMain.handle('check-xml-exists', async (event, chapterStem: string) => {
  try {
    const storyDir = currentStoryDirectory;
    if (!storyDir) {
      log.error('[check-xml-exists] No current story set');
      return false;
    }

    if (typeof chapterStem !== 'string' || !chapterStem.trim()) {
      throw new Error('Invalid chapter stem');
    }
    if (chapterStem.includes('/') || chapterStem.includes('\\') || chapterStem.includes('..')) {
      throw new Error('Security: Invalid chapter stem path content');
    }

    const config = await loadGlobalConfig();
    const storiesDir = getStoriesDirFromConfig(config);
    const xmlPath = path.join(storiesDir, storyDir, 'story-xml', `${chapterStem}.xml`);
    log.info(`[check-xml-exists] Checking XML path`, { storyDir, chapterStem, xmlPath });
    
    if (!isPathWithinParent(xmlPath, storiesDir)) {
      throw new Error('Security: XML path outside stories directory');
    }
    
    const exists = fs.existsSync(xmlPath);
    log.info(`[check-xml-exists] XML exists check complete`, { storyDir, chapterStem, xmlPath, exists });
    return exists;
  } catch (err) {
    log.error(`Failed to check if XML exists: ${err}`);
    return false;
  }
});

ipcMain.handle('list-chapter-clips', async (event, chapterName: string) => {
  try {
    const storyDir = currentStoryDirectory;
    if (!storyDir) return [];

    const stem = path.basename(chapterName, path.extname(chapterName));
    const config = await loadGlobalConfig();
    const storiesDir = getStoriesDirFromConfig(config);
    const clipsDir = path.join(storiesDir, storyDir, 'story-audio', 'clips', stem);

    if (!isPathWithinParent(clipsDir, storiesDir)) {
      throw new Error('Security: Clips path outside stories directory');
    }

    if (!fs.existsSync(clipsDir)) return [];

    return fs.readdirSync(clipsDir)
      .filter(f => f.toLowerCase().endsWith('.wav'))
      .sort((a, b) => a.localeCompare(b));
  } catch (err) {
    log.error(`Failed to list chapter clips for ${chapterName}: ${err}`);
    return [];
  }
});

ipcMain.handle('check-chapter-audio', async (event, chapterName: string) => {
  try {
    const storyDir = currentStoryDirectory;
    if (!storyDir) return false;

    const stem = path.basename(chapterName, path.extname(chapterName));
    const config = await loadGlobalConfig();
    const storiesDir = getStoriesDirFromConfig(config);
    const clipsDir = path.join(storiesDir, storyDir, 'story-audio', 'clips', stem);

    if (!isPathWithinParent(clipsDir, storiesDir)) {
      throw new Error('Security: Clips path outside stories directory');
    }

    return fs.existsSync(clipsDir) && fs.readdirSync(clipsDir).some(f => f.toLowerCase().endsWith('.wav'));
  } catch (err) {
    log.error(`Failed to check chapter audio for ${chapterName}: ${err}`);
    return false;
  }
});

// Check chapter render state
ipcMain.handle('check-chapter-render-state', async (event, chapterName: string, storyDir: string) => {
  try {
    const stem = path.basename(chapterName, path.extname(chapterName));
    const config = await loadGlobalConfig();
    const storiesDir = getStoriesDirFromConfig(config);
    
    // Validate paths
    if (!isPathWithinParent(storiesDir, projectRoot)) {
      throw new Error('Security: Stories path outside project root');
    }
    
    const xmlPath = path.join(storiesDir, storyDir, 'story-xml', chapterName);
    const storyName = storyDir.replace('Story-', '');
    
    // Call Python script to check render state
    log.info(`Checking render state for ${chapterName} in ${storyDir}`);
    
    const result = await executePythonScript('src/scripts/chapter_render_state.py', [
      xmlPath,
      storyDir,
      stem,
      storyName
    ]);
    
    // Parse JSON output
    try {
      const jsonOutput = JSON.parse(result.stdout);
      log.info(`Render state check complete: needs_render=${jsonOutput.needs_render}, stale_count=${jsonOutput.stale_count}`);
      return jsonOutput;
    } catch (parseErr) {
      log.error(`Failed to parse render state JSON: ${parseErr}`);
      return {
        needs_render: false,
        is_fully_rendered: true,
        stale_dialogs: [],
        stale_count: 0,
        error: 'Failed to parse render state'
      };
    }
  } catch (err) {
    log.error(`Failed to check chapter render state for ${chapterName}: ${err}`);
    return {
      needs_render: false,
      is_fully_rendered: true,
      stale_dialogs: [],
      stale_count: 0,
      error: (err as Error).message
    };
  }
});

// Play audio file
ipcMain.handle('play-sound-file', async (event, filePath: string) => {
  return new Promise((resolve, reject) => {
    
    try {
      // Security: Validate and sanitize path
      const sanitizedPath = sanitizePath(filePath);
      const fullPath = path.join(projectRoot, sanitizedPath);
      
      // Validate path is within project
      if (!isPathWithinParent(fullPath, projectRoot)) {
        throw new Error('Security: Audio file path outside project');
      }
      
      if (!fs.existsSync(fullPath)) {
        throw new Error(`Audio file not found: ${filePath}`);
      }
      
      // Choose appropriate command based on platform
      let cmd = '';
      let args: string[] = [];
      
      if (process.platform === 'darwin') {
        cmd = 'afplay';
        args = [fullPath];
      } else if (process.platform === 'win32') {
        cmd = 'powershell';
        args = ['-c', `(New-Object Media.SoundPlayer "${fullPath}").PlaySync()`];
      } else {
        cmd = 'aplay';
        args = [fullPath];
      }
      
      log.info(`Playing audio file: ${cmd} ${args.join(' ')}`);
      
      const playProcess = spawn(cmd, args);
      
      // Store audio process for cancellation
      const procId = `audio-${path.basename(filePath)}`;
      activeProcesses.set(procId, playProcess);
      
      playProcess.on('close', (code, signal) => {
        activeProcesses.delete(procId);
        if (signal === 'SIGTERM' || signal === 'SIGKILL') {
           log.info(`Audio playback cancelled.`);
           reject(new Error(`Playback cancelled`));
           return;
        }
        
        if (code !== 0) {
          log.warn(`Audio playback process exited with code ${code}`);
          resolve(void 0); 
        } else {
          resolve(void 0);
        }
      });
      
      playProcess.on('error', (err) => {
        log.error(`Failed to play audio: ${err.message}`);
        reject(err);
      });
    } catch (err: any) {
      reject(new Error(`Failed to play sound: ${err.message}`));
    }
  });
});

// Dialog handlers
ipcMain.handle('show-error-dialog', async (event, title: string, content: string) => {
  await dialog.showMessageBox({
    type: 'error',
    title: title || 'Error',
    message: content,
    buttons: ['OK']
  });
});

ipcMain.handle('show-confirm-dialog', async (event, title: string, message: string, detail: string) => {
  const result = await dialog.showMessageBox({
    type: 'question',
    title: title || 'Confirm',
    message: message,
    detail: detail,
    buttons: ['Yes', 'No'],
    defaultId: 1,
    cancelId: 1
  });
  return result.response === 0; // true if Yes clicked
});
