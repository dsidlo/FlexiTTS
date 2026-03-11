import { contextBridge, ipcRenderer } from 'electron';

// Import types from shared/types.ts
import type { FlexiTTSConfig, StoryInfo } from '../shared/types';

contextBridge.exposeInMainWorld('api', {
  runPythonScript: (scriptPath: string, args: string[]) => ipcRenderer.invoke('run-python-script', scriptPath, args),
  readFile: (filePath: string) => ipcRenderer.invoke('read-file', filePath),
  readAudioFile: (filePath: string) => ipcRenderer.invoke('read-audio-file', filePath),
  writeFile: (filePath: string, content: string) => ipcRenderer.invoke('write-file', filePath, content),
  showErrorDialog: (title: string, content: string) => ipcRenderer.invoke('show-error-dialog', title, content),
  checkXmlExists: (chapterStem: string) => ipcRenderer.invoke('check-xml-exists', chapterStem),
  showConfirmDialog: (title: string, message: string, detail: string) => ipcRenderer.invoke('show-confirm-dialog', title, message, detail),
  listChapterClips: (chapterName: string) => ipcRenderer.invoke('list-chapter-clips', chapterName),
  listChapterFiles: () => ipcRenderer.invoke('list-chapter-files'),
  checkChapterAudio: (chapterName: string) => ipcRenderer.invoke('check-chapter-audio', chapterName),
  playSoundFile: (filePath: string) => ipcRenderer.invoke('play-sound-file', filePath),
  killProcess: (matchString: string) => ipcRenderer.invoke('kill-process', matchString),
  // FlexiTTS Global Config and Story Management
  loadGlobalConfig: () => ipcRenderer.invoke('load-global-config'),
  saveGlobalConfig: (configData: FlexiTTSConfig) => ipcRenderer.invoke('save-global-config', configData),
  listStories: () => ipcRenderer.invoke('list-stories'),
  setCurrentStory: (storyDirectory: string) => ipcRenderer.invoke('set-current-story', storyDirectory),
  getCurrentStory: () => ipcRenderer.invoke('get-current-story'),
  loadStoryConfig: (storyDir: string) => ipcRenderer.invoke('load-story-config', storyDir),
  listChapterFilesForStory: (storyDir: string) => ipcRenderer.invoke('list-chapter-files-for-story', storyDir),
  checkXmlExistsForStory: (chapterStem: string, storyDir: string) => ipcRenderer.invoke('check-xml-exists-for-story', chapterStem, storyDir),
  checkStoryFileExists: (storyDir: string, relativePath: string) => ipcRenderer.invoke('check-story-file-exists', storyDir, relativePath),
});
