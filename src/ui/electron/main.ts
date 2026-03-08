import { app, BrowserWindow, ipcMain, dialog } from 'electron';
import * as path from 'path';
import { spawn, ChildProcess } from 'child_process';
import * as fs from 'fs';
import * as jsyaml from 'js-yaml';
import { pathToFileURL } from 'url';

// Store active processes so they can be killed
const activeProcesses: Map<string, ChildProcess> = new Map();

// Store TTS service process for cleanup
let ttsServiceProcess: ChildProcess | null = null;

// Track if we're shutting down to prevent new operations
let isShuttingDown = false;

// Store project root for path validation - initialized once at module load time
const projectRoot: string = path.resolve(__dirname, '../../../');

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
    
    // Argument looks safe
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
  console.log(`[Cleanup] Killing ${activeProcesses.size} active Python processes...`);
  const procsToKill = Array.from(activeProcesses.entries());
  activeProcesses.clear(); // Clear immediately to prevent re-kill attempts
  
  procsToKill.forEach(([id, proc]) => {
    try {
      if (proc.pid && !proc.killed) {
        console.log(`[Cleanup] Killing ${id} (PID ${proc.pid})`);
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
      console.log(`[Cleanup] Failed to kill ${id}:`, e);
    }
  });
  
  // Also kill TTS warmup process if running
  if (ttsServiceProcess?.pid && !ttsServiceProcess.killed) {
    try {
      console.log(`[Cleanup] Killing TTS warmup process (PID ${ttsServiceProcess.pid})`);
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
      console.log('[Cleanup] Failed to kill TTS warmup process:', e);
    }
  }
}

// Force exit after cleanup timeout
function forceExitAfterDelay() {
  setTimeout(() => {
    console.log('[App] Force quitting after cleanup timeout');
    process.exit(0);
  }, 5000);
}

// Kill dev server processes (vite, npm, concurrently) when app exits
function killDevServerProcesses() {
  const { exec } = require('child_process');
  
  console.log('[Cleanup] Killing dev server processes...');
  
  // Kill vite dev server on port 5173
  exec('pkill -f "vite --port 5173" 2>/dev/null || true', (err: any) => {
    if (!err) console.log('[Cleanup] Vite dev server killed');
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
      console.log(`[Cleanup] Our parent PID is ${ppid}`);
      // Kill the parent process group (npm/concurrently)
      setTimeout(() => {
        try {
          process.kill(ppid, 'SIGTERM');
          console.log(`[Cleanup] Sent SIGTERM to parent ${ppid}`);
        } catch (e) {
          // Parent may already be dead
        }
      }, 500);
    }
  } catch (e) {
    console.log('[Cleanup] Could not kill parent process:', e);
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

// Start TTS service on app startup
async function warmupTTSService() {
  console.log('[TTS Warmup] Starting TTS service warmup...');
  
  return new Promise<void>((resolve) => {
    ttsServiceProcess = spawn('uv', ['run', 'python', 'src/scripts/start_tts_service.py'], {
      cwd: projectRoot,
      stdio: 'pipe'
    });
    
    let output = '';
    ttsServiceProcess.stdout?.on('data', (data) => {
      output += data.toString();
      console.log(`[TTS Warmup] ${data.toString().trim()}`);
    });
    
    ttsServiceProcess.stderr?.on('data', (data) => {
      console.error(`[TTS Warmup Error] ${data.toString().trim()}`);
    });
    
    ttsServiceProcess.on('close', (code) => {
      console.log(`[TTS Warmup] Process exited with code ${code}`);
      ttsServiceProcess = null;
      resolve();
    });
    
    // Timeout after 5 minutes (should be enough for warmup)
    setTimeout(() => {
      console.log('[TTS Warmup] Timeout - proceeding anyway');
      resolve();
    }, 300000);
  });
}

app.whenReady().then(async () => {
  // Start TTS warmup in background
  warmupTTSService().catch(e => console.error('[TTS Warmup] Failed:', e));
  
  // Create window immediately (don't wait for warmup)
  createWindow();
});

app.on('window-all-closed', () => {
  isShuttingDown = true;
  console.log('[App] window-all-closed: Cleaning up...');
  
  // Kill all active Python processes
  killAllActiveProcesses();
  
  // Stop TTS service (runs in background, don't wait)
  const { exec } = require('child_process');
  exec('uv run python src/scripts/stop_tts_service.py --silent', {
    cwd: projectRoot,
    timeout: 10000
  }, (err: any) => {
    if (err) {
      console.log('[App] TTS service stop (may not be running)');
    } else {
      console.log('[App] TTS service stopped');
    }
  });
  
  // Kill dev server processes (vite, npm, concurrently)
  killDevServerProcesses();
  
  // Force exit after delay to ensure app quits
  forceExitAfterDelay();
  
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

// Also handle before-quit for macOS and other cases
app.on('before-quit', (event) => {
  isShuttingDown = true;
  console.log('[App] before-quit: Cleaning up...');
  
  // Kill all active Python processes
  killAllActiveProcesses();
  
  // Stop TTS service (async - don't block)
  const { exec } = require('child_process');
  exec('uv run python src/scripts/stop_tts_service.py --silent', {
    cwd: projectRoot,
    timeout: 10000
  }, (err: any) => {
    if (err) {
      console.log('[App] TTS service stop (may not be running)');
    } else {
      console.log('[App] TTS service stopped');
    }
  });
  
  // Kill dev server processes (vite, npm, concurrently)
  killDevServerProcesses();
  
  // Force exit after delay
  forceExitAfterDelay();
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});

// IPC Handlers for Python Scripts
// SECURITY: All handlers validate paths before file operations

ipcMain.handle('run-python-script', async (event, scriptPath: string, args: string[]) => {
  
  return new Promise((resolve, reject) => {
    try {
      // Validate arguments for security
      const validatedArgs = validateScriptArguments(args);
      
      console.log(`[IPC] run-python-script called: ${scriptPath} ${validatedArgs.join(' ')}`);
      
      // Security: Validate script path is within project
      const fullScriptPath = path.join(projectRoot, scriptPath);
      if (!isPathWithinParent(fullScriptPath, projectRoot)) {
        reject(new Error('Security: Script path is outside project directory'));
        return;
      }
      
      // Check if it's the validate_config.py call that might fail silently if uv isn't set up yet
      const isValidationCall = scriptPath.includes('validate_config.py');

      const pythonProcess = spawn('uv', ['run', 'python', scriptPath, ...validatedArgs], {
        cwd: projectRoot
      });
      
      // Store process to allow cancellation
      const procId = `python-${scriptPath}-${validatedArgs.join('-')}`;
      activeProcesses.set(procId, pythonProcess);

      let output = '';
      let errorOutput = '';

      pythonProcess.stdout.on('data', (data) => {
        console.log(`[Python stdout] ${data.toString()}`);
        output += data.toString();
      });

      pythonProcess.stderr.on('data', (data) => {
        console.error(`[Python stderr] ${data.toString()}`);
        errorOutput += data.toString();
      });

      pythonProcess.on('close', (code, signal) => {
        activeProcesses.delete(procId);
        console.log(`[Python] Process exited with code ${code} signal ${signal}`);
        if (signal === 'SIGTERM' || signal === 'SIGKILL') {
           reject(new Error(`Process cancelled by user`));
           return;
        }
        
        if (code !== 0) {
          if (isValidationCall) {
              console.warn(`[Python] Ignoring validation error code ${code}`);
              resolve(output);
          } else {
              reject(new Error(errorOutput || `Process exited with code ${code}`));
          }
        } else {
          resolve(output);
        }
      });
    } catch (e: any) {
      reject(new Error(`Security validation failed: ${e.message}`));
    }
  });
});

ipcMain.handle('kill-process', async (event, matchString: string) => {
  console.log(`[IPC] Request to kill process matching: ${matchString}`);
  let killed = false;
  
  // Validate matchString to prevent injection
  if (matchString.includes(';') || matchString.includes('&&') || matchString.includes('|')) {
    console.error('[Security] Rejecting kill-process with invalid matchString');
    return false;
  }
  
  Array.from(activeProcesses.entries()).forEach(([key, proc]) => {
     // A more generous matching scheme to catch audio play commands
     if (key.includes(matchString) || (key.startsWith('audio-') && matchString.includes('.xml'))) {
         console.log(`[IPC] Killing process: ${key}`);
         proc.kill('SIGKILL'); 
         killed = true;
     }
  });
  return killed;
});

ipcMain.handle('read-file', async (event, filePath: string) => {
  
  try {
    // Security: Sanitize input path
    const sanitizedPath = sanitizePath(filePath);
    const fullPath = path.join(projectRoot, sanitizedPath);
    
    // Security: Validate path is within project
    if (!isPathWithinParent(fullPath, projectRoot)) {
      throw new Error('Security: File path is outside project directory');
    }
    
    if (!fs.existsSync(fullPath)) {
      throw new Error(`File not found: ${filePath}`);
    }
    
    return fs.readFileSync(fullPath, 'utf-8');
  } catch (err: any) {
    throw new Error(`Failed to read file ${filePath}: ${err.message}`);
  }
});

ipcMain.handle('write-file', async (event, filePath: string, content: string) => {
  try {
    
    // Security: Sanitize path
    const sanitizedPath = sanitizePath(filePath);
    
    // Determine absolute path
    const fullPath = path.isAbsolute(sanitizedPath)
      ? sanitizedPath
      : path.join(projectRoot, sanitizedPath);
    
    // Security: Validate path is within project
    if (!isPathWithinParent(fullPath, projectRoot)) {
      throw new Error('Security: File path is outside project directory');
    }
    
    // Ensure directory exists
    const dir = path.dirname(fullPath);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }
    
    fs.writeFileSync(fullPath, content, 'utf-8');
    return true;
  } catch (err: any) {
    throw new Error(`Failed to write file ${filePath}: ${err.message}`);
  }
});

ipcMain.handle('read-audio-file', async (event, filePath: string) => {
  
  try {
    // Security: Sanitize and validate path
    const sanitizedPath = sanitizePath(filePath);
    const fullPath = path.join(projectRoot, sanitizedPath);
    
    if (!isPathWithinParent(fullPath, projectRoot)) {
      throw new Error('Security: Audio file path is outside project directory');
    }
    
    if (!fs.existsSync(fullPath)) {
      throw new Error(`Audio file not found: ${filePath}`);
    }
    
    const data = fs.readFileSync(fullPath);
    const base64 = data.toString('base64');
    return `data:audio/wav;base64,${base64}`;
  } catch (err: any) {
    throw new Error(`Failed to read audio file ${filePath}: ${err.message}`);
  }
});

// FlexiTTS Global Config Management
const GLOBAL_CONFIG_FILENAME = 'FlexiTTS.yaml';

function getGlobalConfigPath(): string {
  const homeDir = process.env.HOME || process.env.USERPROFILE || '';
  const configDir = process.env.XDG_CONFIG_HOME || path.join(homeDir, '.config');
  return path.join(configDir, 'FlexiTTS', GLOBAL_CONFIG_FILENAME);
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

ipcMain.handle('load-global-config', async () => {
  const configPath = getGlobalConfigPath();
  try {
    if (fs.existsSync(configPath)) {
      const content = fs.readFileSync(configPath, 'utf-8');
      return jsyaml.load(content);
    }
  } catch (err) {
    console.error(`Failed to load global config: ${err}`);
  }
  // Return default config if file doesn't exist or is unreadable
  const homeDir = process.env.HOME || process.env.USERPROFILE || '';
  const dataDir = process.env.XDG_DATA_HOME || path.join(homeDir, '.local', 'share');
  return {
    FlexiTTS: {
      'stories-dir': path.join(dataDir, 'FlexiTTS', 'stories'),
      'story-dir-prefix': 'Story-'
    }
  };
});

ipcMain.handle('save-global-config', async (event, configData: any) => {
  try {
    const configPath = getGlobalConfigPath();
    ensureGlobalConfigDir();
    const yamlContent = jsyaml.dump(configData, { indent: 2 });
    fs.writeFileSync(configPath, yamlContent, 'utf-8');
    return true;
  } catch (err) {
    console.error(`Failed to save global config: ${err}`);
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
      console.error(`Failed to load config for list-stories: ${err}`);
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
    console.error(`Failed to list stories: ${err}`);
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
  return currentStoryDirectory;
});

// Enhanced file operations that are story-aware
// SECURITY: All handlers validate paths to prevent directory traversal

ipcMain.handle('load-story-config', async (event, storyDir: string) => {
  
  try {
    // Security: Validate story directory name
    if (!/^[\w-]+$/.test(storyDir)) {
      throw new Error('Invalid story directory name');
    }
    
    // Build path and validate
    const configPath = path.join(projectRoot, storyDir, 'story-config.yml');
    
    // Make sure config is within project
    if (!isPathWithinParent(configPath, projectRoot)) {
      throw new Error('Security: Config path outside project');
    }
    
    if (!fs.existsSync(configPath)) {
      throw new Error(`Story config not found: ${storyDir}`);
    }
    
    const content = fs.readFileSync(configPath, 'utf-8');
    return jsyaml.load(content);
  } catch (err: any) {
    throw new Error(`Failed to load story config from ${storyDir}: ${err.message}`);
  }
});

ipcMain.handle('list-chapter-files-for-story', async (event, storyDir: string) => {
  
  try {
    // Security: Validate story directory name
    if (!/^[\w-]+$/.test(storyDir)) {
      throw new Error('Invalid story directory name');
    }
    
    const mdDirPath = path.join(projectRoot, storyDir, 'story-chapters');
    
    // Validate path is within project
    if (!isPathWithinParent(mdDirPath, projectRoot)) {
      throw new Error('Security: Chapter path outside project');
    }
    
    if (fs.existsSync(mdDirPath)) {
      return fs.readdirSync(mdDirPath)
               .filter(f => f.endsWith('.md') && fs.statSync(path.join(mdDirPath, f)).isFile())
               .map(f => `${storyDir}/story-chapters/${f}`);
    }
  } catch (err) {
    console.error(`Failed to read story-chapters directory for ${storyDir}: ${err}`);
  }

  // Fallback to story-xml
  const xmlDirPath = path.join(projectRoot, storyDir, 'story-xml');
  try {
    // Validate path is within project
    if (!isPathWithinParent(xmlDirPath, projectRoot)) {
      throw new Error('Security: XML path outside project');
    }
    
    if (fs.existsSync(xmlDirPath)) {
      return fs.readdirSync(xmlDirPath)
               .filter(f => f.endsWith('.xml'))
               .map(f => `${storyDir}/story-xml/${f}`);
    }
  } catch (err) {
    console.error(`Failed to read story-xml directory for ${storyDir}: ${err}`);
  }
  return [];
});

ipcMain.handle('check-xml-exists-for-story', async (event, chapterStem: string, storyDir: string) => {
  
  try {
    // Security: Validate inputs
    if (!/^[\w-]+$/.test(storyDir)) {
      throw new Error('Invalid story directory name');
    }
    
    if (!/^[\w-.]+$/.test(chapterStem)) {
      throw new Error('Invalid chapter stem');
    }
    
    const xmlPath = path.join(projectRoot, storyDir, 'story-xml', `${chapterStem}.xml`);
    
    // Validate path
    if (!isPathWithinParent(xmlPath, projectRoot)) {
      throw new Error('Security: XML path outside project');
    }
    
    return fs.existsSync(xmlPath);
  } catch (err) {
    console.error(`Failed to check if XML exists for ${storyDir}: ${err}`);
    return false;
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
      
      console.log(`Playing audio file: ${cmd} ${args.join(' ')}`);
      
      const playProcess = spawn(cmd, args);
      
      // Store audio process for cancellation
      const procId = `audio-${path.basename(filePath)}`;
      activeProcesses.set(procId, playProcess);
      
      playProcess.on('close', (code, signal) => {
        activeProcesses.delete(procId);
        if (signal === 'SIGTERM' || signal === 'SIGKILL') {
           console.log(`Audio playback cancelled.`);
           reject(new Error(`Playback cancelled`));
           return;
        }
        
        if (code !== 0) {
          console.warn(`Audio playback process exited with code ${code}`);
          resolve(void 0); 
        } else {
          resolve(void 0);
        }
      });
      
      playProcess.on('error', (err) => {
        console.error(`Failed to play audio: ${err.message}`);
        reject(err);
      });
    } catch (err: any) {
      reject(new Error(`Failed to play sound: ${err.message}`));
    }
  });
});
