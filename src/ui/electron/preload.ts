import { contextBridge, ipcRenderer } from 'electron';

contextBridge.exposeInMainWorld('api', {
  runPythonScript: (scriptPath: string, args: string[]) => ipcRenderer.invoke('run-python-script', scriptPath, args),
  readFile: (filePath: string) => ipcRenderer.invoke('read-file', filePath),
  writeFile: (filePath: string, content: string) => ipcRenderer.invoke('write-file', filePath, content),
  showErrorDialog: (title: string, content: string) => ipcRenderer.invoke('show-error-dialog', title, content),
  showConfirmDialog: (title: string, message: string, detail: string) => ipcRenderer.invoke('show-confirm-dialog', title, message, detail),
  listChapterClips: (chapterName: string) => ipcRenderer.invoke('list-chapter-clips', chapterName),
  checkChapterAudio: (chapterName: string) => ipcRenderer.invoke('check-chapter-audio', chapterName),
  playSoundFile: (filePath: string) => ipcRenderer.invoke('play-sound-file', filePath),
  killProcess: (matchString: string) => ipcRenderer.invoke('kill-process', matchString),
});
