"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const electron_1 = require("electron");
electron_1.contextBridge.exposeInMainWorld('api', {
    runPythonScript: (scriptPath, args) => electron_1.ipcRenderer.invoke('run-python-script', scriptPath, args),
    readFile: (filePath) => electron_1.ipcRenderer.invoke('read-file', filePath),
    readAudioFile: (filePath) => electron_1.ipcRenderer.invoke('read-audio-file', filePath),
    writeFile: (filePath, content) => electron_1.ipcRenderer.invoke('write-file', filePath, content),
    showErrorDialog: (title, content) => electron_1.ipcRenderer.invoke('show-error-dialog', title, content),
    checkXmlExists: (chapterStem) => electron_1.ipcRenderer.invoke('check-xml-exists', chapterStem),
    showConfirmDialog: (title, message, detail) => electron_1.ipcRenderer.invoke('show-confirm-dialog', title, message, detail),
    listChapterClips: (chapterName) => electron_1.ipcRenderer.invoke('list-chapter-clips', chapterName),
    listChapterFiles: () => electron_1.ipcRenderer.invoke('list-chapter-files'),
    checkChapterAudio: (chapterName) => electron_1.ipcRenderer.invoke('check-chapter-audio', chapterName),
    playSoundFile: (filePath) => electron_1.ipcRenderer.invoke('play-sound-file', filePath),
    killProcess: (matchString) => electron_1.ipcRenderer.invoke('kill-process', matchString),
});
