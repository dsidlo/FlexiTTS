import { app, BrowserWindow, ipcMain, dialog } from 'electron';
import * as path from 'path';
import { spawn, ChildProcess } from 'child_process';
import * as fs from 'fs';

// Store active processes so they can be killed
const activeProcesses: Map<string, ChildProcess> = new Map();

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

app.whenReady().then(createWindow);

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});

// IPC Handlers for Python Scripts

ipcMain.handle('run-python-script', async (event, scriptPath: string, args: string[]) => {
  return new Promise((resolve, reject) => {
    console.log(`[IPC] run-python-script called: ${scriptPath} ${args.join(' ')}`);
    // Determine absolute path to python script
    // __dirname is src/ui/dist-electron. So ../../../ is the FlexiTTS project root.
    const projectRoot = path.resolve(__dirname, '../../../'); 
    
    // Check if it's the validate_config.py call that might fail silently if uv isn't set up yet
    const isValidationCall = scriptPath.includes('validate_config.py');

    // We run python scripts via uv (if available), otherwise fallback to plain python
    // On some setups, `uv run python` might fail to find the `.venv`
    // We can just rely on standard python if uv fails, but for now we'll pass the exact command args.
    const pythonProcess = spawn('uv', ['run', 'python', scriptPath, ...args], {
      cwd: projectRoot // Run from project root
    });
    
    // Store process to allow cancellation
    // Generate a unique process ID based on script and arguments
    const procId = `python-${scriptPath}-${args.join('-')}`;
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
        // Validation script failing shouldn't bring down the UI immediately if it's just a config parsing error
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
  });
});

ipcMain.handle('kill-process', async (event, matchString: string) => {
  console.log(`[IPC] Request to kill process matching: ${matchString}`);
  let killed = false;
  
  // We need to look through the active processes to see if the matchString
  // is found either in the key (the name/args) or in the general target.
  // In the case of audio, the key is audio-<filename>
  for (const [key, proc] of activeProcesses.entries()) {
     // A more generous matching scheme to catch audio play commands
     if (key.includes(matchString) || (key.startsWith('audio-') && matchString.includes('.xml'))) {
         console.log(`[IPC] Killing process: ${key}`);
         // Using SIGKILL for immediate termination, as SIGTERM might be ignored or caught
         proc.kill('SIGKILL'); 
         killed = true;
     }
  }
  return killed;
});

ipcMain.handle('read-file', async (event, filePath: string) => {
  const projectRoot = path.resolve(__dirname, '../../../');
  const fullPath = path.join(projectRoot, filePath);
  try {
    return fs.readFileSync(fullPath, 'utf-8');
  } catch (err: any) {
    throw new Error(`Failed to read file ${filePath}: ${err.message}`);
  }
});

ipcMain.handle('write-file', async (event, filePath: string, content: string) => {
  const projectRoot = path.resolve(__dirname, '../../../');
  const fullPath = path.join(projectRoot, filePath);
  try {
    fs.writeFileSync(fullPath, content, 'utf-8');
    return true;
  } catch (err: any) {
    throw new Error(`Failed to write file ${filePath}: ${err.message}`);
  }
});

ipcMain.handle('list-chapter-files', async () => {
  const projectRoot = path.resolve(__dirname, '../../../');
  // First check if story-chapters exists (the new source of truth)
  const mdDirPath = path.join(projectRoot, 'Story-Entanglement', 'story-chapters');
  try {
    if (fs.existsSync(mdDirPath)) {
      // Return .md files, ignoring directories like story-notes
      return fs.readdirSync(mdDirPath)
               .filter(f => f.endsWith('.md') && fs.statSync(path.join(mdDirPath, f)).isFile())
               // Format return to look like relative paths expected by UI
               .map(f => `Story-Entanglement/story-chapters/${f}`);
    }
  } catch (err) {
    console.error(`Failed to read story-chapters directory: ${err}`);
  }

  // Fallback to story-xml for backwards compatibility / robustness
  const xmlDirPath = path.join(projectRoot, 'Story-Entanglement', 'story-xml');
  try {
    if (fs.existsSync(xmlDirPath)) {
      return fs.readdirSync(xmlDirPath)
               .filter(f => f.endsWith('.xml'))
               .map(f => `Story-Entanglement/story-xml/${f}`);
    }
  } catch (err) {
    console.error(`Failed to read story-xml directory: ${err}`);
  }
  return [];
});

ipcMain.handle('check-xml-exists', async (event, chapterStem: string) => {
  const projectRoot = path.resolve(__dirname, '../../../');
  const xmlPath = path.join(projectRoot, 'Story-Entanglement', 'story-xml', `${chapterStem}.xml`);
  try {
    return fs.existsSync(xmlPath);
  } catch (err) {
    console.error(`Failed to check if XML exists: ${err}`);
    return false;
  }
});

ipcMain.handle('show-error-dialog', async (event, title: string, message: string) => {
  dialog.showErrorBox(title, message);
});

ipcMain.handle('show-confirm-dialog', async (event, title: string, message: string, detail: string) => {
  const result = dialog.showMessageBoxSync({
    type: 'warning',
    buttons: ['Save', 'Discard', 'Cancel'],
    defaultId: 0,
    cancelId: 2,
    title: title,
    message: message,
    detail: detail
  });
  return result; // 0 = Save, 1 = Discard, 2 = Cancel
});

ipcMain.handle('list-chapter-clips', async (event, chapterName: string) => {
  const projectRoot = path.resolve(__dirname, '../../../');
  // chapterName might be passed as 01-Hendrix.xml or 01-Hendrix.md
  const chapterStem = chapterName.replace('.xml', '').replace('.md', '');
  const dirPath = path.join(projectRoot, 'Story-Entanglement', 'story-audio', 'clips', chapterStem);
  try {
    if (fs.existsSync(dirPath)) {
      return fs.readdirSync(dirPath).filter(f => f.endsWith('.wav'));
    }
  } catch (err) {
    console.error(`Failed to read clips directory: ${err}`);
  }
  return [];
});

ipcMain.handle('check-chapter-audio', async (event, chapterName: string) => {
  const projectRoot = path.resolve(__dirname, '../../../');
  const chapterStem = chapterName.replace('.xml', '');
  const filePath = path.join(projectRoot, 'Story-Entanglement', 'story-audio', `${chapterStem}.wav`);
  try {
    return fs.existsSync(filePath);
  } catch (err) {
    console.error(`Failed to check chapter audio file: ${err}`);
  }
  return false;
});

// Play audio file
ipcMain.handle('play-sound-file', async (event, filePath: string) => {
  return new Promise((resolve, reject) => {
    // Determine absolute path to the wav file
    // The relative path provided should be from the project root
    const projectRoot = path.resolve(__dirname, '../../../');
    const fullPath = path.join(projectRoot, filePath);
    
    // Choose appropriate command based on platform
    let cmd = '';
    let args: string[] = [];
    
    if (process.platform === 'darwin') {
      cmd = 'afplay';
      args = [fullPath];
    } else if (process.platform === 'win32') {
      // Use powershell to play sound on Windows natively
      cmd = 'powershell';
      args = ['-c', `(New-Object Media.SoundPlayer "${fullPath}").PlaySync()`];
    } else {
      // Linux, assume aplay exists (often part of alsa-utils)
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
        // We'll still resolve instead of reject so the UI doesn't crash, 
        // but it means playback might have failed.
        resolve(void 0); 
      } else {
        resolve(void 0);
      }
    });
    
    playProcess.on('error', (err) => {
      console.error(`Failed to play audio: ${err.message}`);
      reject(err);
    });
  });
});