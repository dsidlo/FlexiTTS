import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

const appendFileSync = vi.fn();
const existsSync = vi.fn();
const readFileSync = vi.fn();
const unlinkSync = vi.fn();

const appOn = vi.fn();
const appQuit = vi.fn();
const appExit = vi.fn();
const appWhenReady = vi.fn(() => Promise.resolve());
const appCommandLineAppendSwitch = vi.fn();
const browserWindowGetAllWindows = vi.fn(() => []);
const showMessageBox = vi.fn(() => Promise.resolve({ response: 0 }));

const execMock = vi.fn();
const spawnMock = vi.fn(() => ({
  stdout: { on: vi.fn() },
  stderr: { on: vi.fn() },
  on: vi.fn(),
  pid: 1234,
  killed: false,
  kill: vi.fn(),
}));

vi.mock('fs', () => ({
  default: {
    appendFileSync,
    existsSync,
    readFileSync,
    unlinkSync,
  },
  appendFileSync,
  existsSync,
  readFileSync,
  unlinkSync,
}));

vi.mock('electron', () => ({
  app: {
    on: appOn,
    quit: appQuit,
    exit: appExit,
    whenReady: appWhenReady,
    isPackaged: false,
    commandLine: {
      appendSwitch: appCommandLineAppendSwitch,
    },
  },
  BrowserWindow: Object.assign(
    vi.fn(() => ({
      loadURL: vi.fn(),
      loadFile: vi.fn(),
      webContents: { openDevTools: vi.fn() },
    })),
    { getAllWindows: browserWindowGetAllWindows }
  ),
  ipcMain: { handle: vi.fn() },
  dialog: { showMessageBox },
}));

vi.mock('child_process', () => ({
  default: {
    exec: execMock,
    spawn: spawnMock,
  },
  exec: execMock,
  spawn: spawnMock,
}));

vi.mock('js-yaml', () => ({
  load: vi.fn(),
  dump: vi.fn(),
}));

async function importMainModule() {
  return await import('../../electron/main');
}

async function flushAsync() {
  await Promise.resolve();
  await Promise.resolve();
  await vi.runAllTimersAsync();
  await Promise.resolve();
}

describe('electron shutdown TTS handling', () => {
  beforeEach(() => {
    vi.resetModules();
    vi.clearAllMocks();
    vi.useFakeTimers();

    appWhenReady.mockResolvedValue(undefined);
    browserWindowGetAllWindows.mockReturnValue([]);
    showMessageBox.mockResolvedValue({ response: 0 });

    execMock.mockImplementation((cmd: string, opts: any, cb: any) => {
      cb?.(null, '', '');
      return {};
    });

    existsSync.mockReturnValue(false);
    readFileSync.mockReturnValue('');
    unlinkSync.mockImplementation(() => {});
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('gracefully stops TTS service before exit when PID disappears within 3 seconds', async () => {
    existsSync.mockReturnValue(true);
    readFileSync.mockReturnValue('4321');

    const killSpy = vi.spyOn(process, 'kill').mockImplementation((pid: number, signal?: NodeJS.Signals | 0) => {
      if (signal === 0 && pid === 4321) {
        throw new Error('not running');
      }
      return true as any;
    });

    await importMainModule();

    const beforeQuitHandler = appOn.mock.calls.find(call => call[0] === 'before-quit')?.[1];
    expect(beforeQuitHandler).toBeTypeOf('function');

    const event = { preventDefault: vi.fn() };
    beforeQuitHandler(event);
    await flushAsync();

    expect(event.preventDefault).toHaveBeenCalled();
    expect(appOn).toHaveBeenCalledWith('before-quit', expect.any(Function));

    killSpy.mockRestore();
  });

  it('escalates to force kill and shows modal when TTS service still survives', async () => {
    existsSync.mockReturnValue(true);
    readFileSync.mockReturnValue('9999');

    const killSpy = vi.spyOn(process, 'kill').mockImplementation((pid: number, signal?: NodeJS.Signals | 0) => {
      if (signal === 0 && pid === 9999) {
        return true as any;
      }
      return true as any;
    });

    await importMainModule();

    const beforeQuitHandler = appOn.mock.calls.find(call => call[0] === 'before-quit')?.[1];
    expect(beforeQuitHandler).toBeTypeOf('function');

    const event = { preventDefault: vi.fn() };
    beforeQuitHandler(event);
    await flushAsync();

    expect(event.preventDefault).toHaveBeenCalled();
    expect(appOn).toHaveBeenCalledWith('before-quit', expect.any(Function));

    killSpy.mockRestore();
  });
});
