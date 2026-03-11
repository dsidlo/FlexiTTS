import { describe, expect, it, vi, beforeEach } from 'vitest';
import type { DialogElement, StoryConfig } from '../models/types';
import { getDialogValidationKey, validateChapterDialogs } from '../utils/dialogValidation';

vi.mock('../services/pythonBridge', () => ({
  PythonBridgeService: {
    checkStoryFileExists: vi.fn(),
  },
}));

import { PythonBridgeService } from '../services/pythonBridge';

const makeDialog = (character: string): DialogElement => ({
  _index: 0,
  dlgseq: '001',
  sectionId: '001',
  character,
  text: 'Hello',
  attributes: { dlgseq: '001', section_seq: '001', character },
});

const baseConfig: StoryConfig = {
  global: {
    'story-dir': 'Story-Default/',
    voices: 'refs/',
    chapters: 'story-chapters/',
    'story-xml': 'story-xml/',
    logs: 'logs/',
    'story-audio': 'story-audio/',
    clips: 'story-audio/clips/',
    'clip-separation': 0,
  },
  'llm-xml-generator': [],
  'dialog-effects': [],
  'story-audio-post-process': {},
  characters: [],
};

describe('validateChapterDialogs', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(PythonBridgeService.checkStoryFileExists).mockResolvedValue(true);
  });

  it('flags missing character', async () => {
    const dialog = makeDialog('Alice');
    const issues = await validateChapterDialogs([dialog], baseConfig);
    expect(issues[getDialogValidationKey(dialog)]?.[0]?.code).toBe('missing-character');
  });

  it('flags invalid custom voice speaker', async () => {
    const dialog = makeDialog('Alice');
    const config: StoryConfig = {
      ...baseConfig,
      characters: [{ name: 'Alice', 'custom-voice': { speaker: 'Bogus', language: 'English', instruct: '' } }],
    };
    const issues = await validateChapterDialogs([dialog], config);
    expect(issues[getDialogValidationKey(dialog)]?.[0]?.code).toBe('invalid-custom-voice');
  });

  it('flags missing voice sample', async () => {
    const dialog = makeDialog('Alice');
    const config: StoryConfig = {
      ...baseConfig,
      characters: [{ name: 'Alice' }],
    };
    const issues = await validateChapterDialogs([dialog], config);
    expect(issues[getDialogValidationKey(dialog)]?.[0]?.code).toBe('invalid-voice-sample');
  });

  it('flags missing voice sample file', async () => {
    const dialog = makeDialog('Alice');
    const config: StoryConfig = {
      ...baseConfig,
      characters: [{ name: 'Alice', 'voice-sample': 'refs/alice.wav' }],
    };
    vi.mocked(PythonBridgeService.checkStoryFileExists).mockResolvedValue(false);

    const issues = await validateChapterDialogs([dialog], config, 'Story-Default');
    expect(issues[getDialogValidationKey(dialog)]?.[0]?.code).toBe('invalid-voice-sample');
    expect(PythonBridgeService.checkStoryFileExists).toHaveBeenCalledWith('Story-Default', 'refs/alice.wav');
  });

  it('resolves voice samples relative to the story voices directory', async () => {
    const dialog = makeDialog('Echo');
    const config: StoryConfig = {
      ...baseConfig,
      global: {
        ...baseConfig.global,
        voices: 'story-voice-refs/',
      },
      characters: [{ name: 'Echo', 'voice-sample': 'Ayana-voice.wav' }],
    };

    vi.mocked(PythonBridgeService.checkStoryFileExists)
      .mockResolvedValueOnce(false)
      .mockResolvedValueOnce(true);

    const issues = await validateChapterDialogs([dialog], config, 'Story-Fractured_Assistance');
    expect(issues[getDialogValidationKey(dialog)]).toBeUndefined();
    expect(PythonBridgeService.checkStoryFileExists).toHaveBeenNthCalledWith(1, 'Story-Fractured_Assistance', 'Ayana-voice.wav');
    expect(PythonBridgeService.checkStoryFileExists).toHaveBeenNthCalledWith(2, 'Story-Fractured_Assistance', 'story-voice-refs/Ayana-voice.wav');
  });

  it('flags undefined named dialog-effects on characters in a single issue', async () => {
    const dialog = makeDialog('Echo');
    const config: StoryConfig = {
      ...baseConfig,
      'dialog-effects': [{ name: 'cave' }],
      characters: [{ name: 'Echo', 'voice-sample': 'echo.wav', 'dialog-effects': ['cave', 'ghost', 'radio'] }],
    };

    const issues = await validateChapterDialogs([dialog], config, 'Story-Default');
    expect(issues[getDialogValidationKey(dialog)]).toEqual([
      {
        code: 'invalid-dialog-effects',
        message: "Character 'Echo' dialog-effects entries 'ghost', 'radio' are not defined in story-config.yml dialog-effects.",
      },
    ]);
  });

  it('flags invalid dialog-effects even when a normalized voice-sample path exists', async () => {
    const dialog = makeDialog('Hendrix-echo');
    const config: StoryConfig = {
      ...baseConfig,
      global: { ...baseConfig.global, voices: 'refs/' },
      'dialog-effects': [{ name: 'cave' }],
      characters: [{ name: 'Hendrix-echo', 'voice-sample': 'Hendricks-voice-x.wav', 'dialog-effects': ['cave', 'caves', 'xxx'] }],
    };

    vi.mocked(PythonBridgeService.checkStoryFileExists).mockImplementation(async (_storyDir, relativePath) => {
      return relativePath === 'refs/Hendricks-voice.wav';
    });

    const issues = await validateChapterDialogs([dialog], config, 'Story-Default');
    expect(issues[getDialogValidationKey(dialog)]).toEqual([
      {
        code: 'invalid-dialog-effects',
        message: "Character 'Hendrix-echo' dialog-effects entries 'caves', 'xxx' are not defined in story-config.yml dialog-effects.",
      },
    ]);
  });

  it('accepts multiple valid named dialog-effects on characters', async () => {
    const dialog = makeDialog('Echo');
    const config: StoryConfig = {
      ...baseConfig,
      'dialog-effects': [{ name: 'cave' }, { name: 'radio' }],
      characters: [{ name: 'Echo', 'voice-sample': 'echo.wav', 'dialog-effects': ['cave', 'radio'] }],
    };

    const issues = await validateChapterDialogs([dialog], config, 'Story-Default');
    expect(issues[getDialogValidationKey(dialog)]).toBeUndefined();
  });

  it('accepts valid custom voice', async () => {
    const dialog = makeDialog('Alice');
    const config: StoryConfig = {
      ...baseConfig,
      characters: [{ name: 'Alice', 'custom-voice': { speaker: 'Vivian', language: 'English', instruct: '' } }],
    };
    const issues = await validateChapterDialogs([dialog], config);
    expect(issues[getDialogValidationKey(dialog)]).toBeUndefined();
  });
});
