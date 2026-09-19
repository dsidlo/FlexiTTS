/**
 * Phase 6.3-6.6 tests: EmotionRow, VoiceSampleUploader, SoXEffectBuilder,
 * AudioPreviewPlayer.
 */

import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { EmotionRow } from '../components/EmotionRow';
import { VoiceSampleUploader } from '../components/VoiceSampleUploader';
import { SoXEffectBuilder } from '../components/SoXEffectBuilder';
import { AudioPreviewPlayer } from '../components/AudioPreviewPlayer';

vi.mock('../services/pythonBridge', () => ({
  PythonBridgeService: {
    updateEmotion: vi.fn(),
    deleteEmotion: vi.fn(),
    setDefaultEmotion: vi.fn(),
    addEmotion: vi.fn(),
    runBridgeCommand: vi.fn(),
  },
}));

import { PythonBridgeService } from '../services/pythonBridge';

const updateEmotionMock = PythonBridgeService.updateEmotion as unknown as ReturnType<typeof vi.fn>;
const deleteEmotionMock = PythonBridgeService.deleteEmotion as unknown as ReturnType<typeof vi.fn>;
const setDefaultEmotionMock = PythonBridgeService.setDefaultEmotion as unknown as ReturnType<typeof vi.fn>;
const runBridgeCommandMock = PythonBridgeService.runBridgeCommand as unknown as ReturnType<typeof vi.fn>;

const mockWindowApi = (confirmResult = 1) => {
  (window as unknown as { api: unknown }).api = {
    showConfirmDialog: vi.fn().mockResolvedValue(confirmResult),
    readAudioFile: vi.fn().mockResolvedValue('data:audio/wav;base64,AAAA'),
  };
};

const noop = () => {};

describe('EmotionRow (Phase 6.3)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockWindowApi();
  });

  const baseProps = () => ({
    characterId: 'Hendrix',
    storyDir: 'Story-Test',
    onSaved: noop,
    onError: noop,
  });

  it('displays emotion name and instruct', () => {
    render(
      <EmotionRow
        {...baseProps()}
        emotion={{ emotion: 'Sad', instruct: 'low slow' }}
        isDefault={false}
      />,
    );
    expect(screen.getByTestId('emotion-row-Hendrix-Sad')).toHaveTextContent('Sad');
    expect(screen.getByTestId('emotion-row-Hendrix-Sad')).toHaveTextContent('low slow');
  });

  it('marks the default emotion with a star', () => {
    render(<EmotionRow {...baseProps()} emotion={{ emotion: 'Neutral' }} isDefault />);
    expect(screen.getByTestId('emotion-row-Hendrix-Neutral')).toHaveTextContent('★');
  });

  it('inline edit saves via updateEmotion', async () => {
    updateEmotionMock.mockResolvedValue({});
    render(<EmotionRow {...baseProps()} emotion={{ emotion: 'Sad', instruct: 'low' }} isDefault={false} />);
    fireEvent.click(screen.getByTestId('emotion-edit-Hendrix-Sad'));
    const nameInput = screen.getByTestId('emotion-name-input-Hendrix-Sad');
    fireEvent.change(nameInput, { target: { value: 'Melancholy' } });
    fireEvent.click(screen.getByTitle('Save'));
    await waitFor(() => {
      expect(updateEmotionMock).toHaveBeenCalledWith('Story-Test', 'Hendrix', 'Sad', {
        emotion: 'Melancholy',
        instruct: 'low',
      });
    });
  });

  it('rejects empty emotion name without calling the bridge', () => {
    updateEmotionMock.mockClear();
    const onError = vi.fn();
    render(<EmotionRow {...baseProps()} emotion={{ emotion: 'Sad', instruct: '' }} isDefault={false} onError={onError} />);
    fireEvent.click(screen.getByTestId('emotion-edit-Hendrix-Sad'));
    const nameInput = screen.getByTestId('emotion-name-input-Hendrix-Sad');
    fireEvent.change(nameInput, { target: { value: '   ' } });
    fireEvent.click(screen.getByTitle('Save'));
    expect(onError).toHaveBeenCalledWith('Emotion name cannot be empty.');
    expect(updateEmotionMock).not.toHaveBeenCalled();
  });

  it('delete requires confirmation and calls deleteEmotion', async () => {
    deleteEmotionMock.mockResolvedValue({ deleted: {}, remainingCount: 2 });
    render(<EmotionRow {...baseProps()} emotion={{ emotion: 'Sad', instruct: '' }} isDefault={false} />);
    fireEvent.click(screen.getByTestId('emotion-delete-Hendrix-Sad'));
    await waitFor(() => {
      expect(deleteEmotionMock).toHaveBeenCalledWith('Story-Test', 'Hendrix', 'Sad');
    });
  });

  it('set-default calls setDefaultEmotion', async () => {
    setDefaultEmotionMock.mockResolvedValue({});
    render(<EmotionRow {...baseProps()} emotion={{ emotion: 'Calm', instruct: '' }} isDefault={false} />);
    fireEvent.click(screen.getByTestId('emotion-default-Hendrix-Calm'));
    await waitFor(() => {
      expect(setDefaultEmotionMock).toHaveBeenCalledWith('Story-Test', 'Hendrix', 'Calm');
    });
  });
});

describe('VoiceSampleUploader (Phase 6.4)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const baseProps = (overrides: Partial<Parameters<typeof VoiceSampleUploader>[0]> = {}) => ({
    storyDir: 'Story-Test',
    characterId: 'SampleChar',
    emotionId: null as string | null,
    onUploaded: noop,
    onError: noop,
    ...overrides,
  });

  function makeFile(name: string, size = 100): File {
    return new File([new ArrayBuffer(size)], name, { type: 'audio/wav' });
  }

  function setDataTransfer(file: File) {
    return { dataTransfer: { files: [file], preventDefault: noop } } as unknown as React.DragEvent;
  }

  it('renders drop zone and browse button', () => {
    render(<VoiceSampleUploader {...baseProps()} />);
    expect(screen.getByTestId('sample-uploader-SampleChar')).toBeInTheDocument();
    expect(screen.getByTestId('sample-browse-SampleChar')).toBeInTheDocument();
  });

  it('rejects unsupported format via onError', async () => {
    const onError = vi.fn();
    const onUploaded = vi.fn();
    render(<VoiceSampleUploader {...baseProps()} onUploaded={onUploaded} onError={onError} />);
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    Object.defineProperty(input, 'files', { value: [makeFile('tone.flac')] });
    fireEvent.change(input);
    await waitFor(() => expect(onError).toHaveBeenCalledWith(expect.stringContaining('Unsupported format')));
    expect(onUploaded).not.toHaveBeenCalled();
  });

  it('rejects oversized file via onError', async () => {
    const onError = vi.fn();
    render(<VoiceSampleUploader {...baseProps()} maxBytes={10} onUploaded={noop} onError={onError} />);
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    Object.defineProperty(input, 'files', { value: [makeFile('tone.wav', 100)] });
    fireEvent.change(input);
    await waitFor(() => expect(onError).toHaveBeenCalledWith(expect.stringContaining('size limit')));
  });

  it('accepts a valid wav upload via browse', async () => {
    runBridgeCommandMock.mockResolvedValue({ success: true, sample: { filename: 'X_tone.wav' } });
    const onUploaded = vi.fn();
    render(<VoiceSampleUploader {...baseProps()} onUploaded={onUploaded} onError={noop} />);
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    Object.defineProperty(input, 'files', { value: [makeFile('tone.wav')] });
    fireEvent.change(input);
    await waitFor(() => expect(onUploaded).toHaveBeenCalledWith('X_tone.wav'), { timeout: 5000 });
    expect(runBridgeCommandMock).toHaveBeenCalledWith([
      'upload-sample', 'Story-Test', 'SampleChar', '-', 'tone.wav', expect.any(String),
    ]);
  });

  it('handles drop event for valid file', async () => {
    runBridgeCommandMock.mockResolvedValue({ success: true, sample: { filename: 'X_drop.wav' } });
    const onUploaded = vi.fn();
    render(<VoiceSampleUploader {...baseProps()} onUploaded={onUploaded} onError={noop} />);
    const zone = screen.getByTestId('sample-uploader-SampleChar');
    fireEvent.drop(zone, setDataTransfer(makeFile('drop.wav')));
    await waitFor(() => expect(onUploaded).toHaveBeenCalledWith('X_drop.wav'), { timeout: 5000 });
  });
});

describe('SoXEffectBuilder (Phase 6.5)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders existing effects with command preview', () => {
    render(<SoXEffectBuilder effects={['reverb 50', 'gain +3']} onChanged={noop} />);
    expect(screen.getByTestId('sox-effect-0')).toHaveTextContent('reverb 50');
    expect(screen.getByTestId('sox-effect-1')).toHaveTextContent('gain +3');
    expect(screen.getByTestId('sox-command-preview')).toHaveTextContent('sox in.wav out.wav');
    expect(screen.getByTestId('sox-command-preview')).toHaveTextContent('reverb 50');
  });

  it('add effect appends and calls onChanged', () => {
    const onChanged = vi.fn();
    render(<SoXEffectBuilder effects={['gain +3']} onChanged={onChanged} />);
    fireEvent.change(screen.getByTestId('sox-new-effect'), { target: { value: 'reverb 50' } });
    fireEvent.click(screen.getByTestId('sox-add-effect'));
    expect(onChanged).toHaveBeenCalledWith(['gain +3', 'reverb 50']);
  });

  it('remove effect calls onChanged without it', () => {
    const onChanged = vi.fn();
    render(<SoXEffectBuilder effects={['reverb 50', 'gain +3']} onChanged={onChanged} />);
    fireEvent.click(screen.getByTestId('sox-remove-0'));
    expect(onChanged).toHaveBeenCalledWith(['gain +3']);
  });

  it('reorders effects via up button', () => {
    const onChanged = vi.fn();
    render(<SoXEffectBuilder effects={['reverb 50', 'gain +3']} onChanged={onChanged} />);
    const upButton = screen.getAllByTitle('Move up')[1];
    fireEvent.click(upButton);
    expect(onChanged).toHaveBeenCalledWith(['gain +3', 'reverb 50']);
  });

  it('suggests norm for normalize in validation errors', async () => {
    runBridgeCommandMock.mockResolvedValue({
      success: true,
      isValid: false,
      errors: [{ code: 'UNKNOWN_EFFECT', message: "Unknown SoX effect 'normalize'", index: 0 }],
    });
    const onChanged = vi.fn();
    render(<SoXEffectBuilder effects={['normalize']} onChanged={onChanged} />);
    // eslint-disable-next-line no-console
    console.log('RENDERED');
    await waitFor(() => {
      expect(screen.getByTestId('sox-validation-errors')).toBeInTheDocument();
      expect(screen.getByTestId('sox-suggest-norm-0')).toBeInTheDocument();
    }, { timeout: 5000 });
    // Click the fix button: chain updates to use 'norm'
    fireEvent.click(screen.getByTestId('sox-suggest-norm-0'));
    expect(onChanged).toHaveBeenCalledWith(['norm']);
  });

  it('validates via bridge and shows errors for unknown effect', async () => {
    runBridgeCommandMock.mockResolvedValue({
      success: true,
      isValid: false,
      errors: [{ code: 'UNKNOWN_EFFECT', message: "Unknown SoX effect 'frobnicate'", index: 0 }],
    });
    render(<SoXEffectBuilder effects={['frobnicate 5']} onChanged={noop} />);
    await waitFor(() => {
      expect(screen.getByTestId('sox-validation-errors')).toBeInTheDocument();
      expect(screen.getByTestId('sox-validation-errors')).toHaveTextContent("Unknown SoX effect 'frobnicate'");
    });
    // Error highlight on the offending row
    expect(screen.getByTestId('sox-effect-0')).toHaveStyle({ color: '#f66' });
  });


});

describe('AudioPreviewPlayer (Phase 6.6)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockWindowApi();
  });

  it('renders with filename title', () => {
    render(<AudioPreviewPlayer src="/path/to/clip.wav" />);
    expect(screen.getByTestId('audio-preview-player')).toBeInTheDocument();
    expect(screen.getByText('clip.wav')).toBeInTheDocument();
  });

  it('play button toggles', async () => {
    // jsdom lacks HTMLMediaElement.play; stub it
    Object.defineProperty(HTMLMediaElement.prototype, 'play', {
      configurable: true,
      value: vi.fn().mockResolvedValue(undefined),
    });
    Object.defineProperty(HTMLMediaElement.prototype, 'pause', {
      configurable: true,
      value: vi.fn(),
    });
    render(<AudioPreviewPlayer src="/path/to/clip.wav" />);
    fireEvent.click(screen.getByTestId('audio-play-toggle'));
    await waitFor(() => expect(screen.getByTitle('Stop')).toBeInTheDocument());
  });

  it('calls onError when playback unavailable', async () => {
    (window as unknown as { api: unknown }).api = { readAudioFile: undefined };
    const onError = vi.fn();
    render(<AudioPreviewPlayer src="/p/clip.wav" onError={onError} />);
    fireEvent.click(screen.getByTestId('audio-play-toggle'));
    await waitFor(() => expect(onError).toHaveBeenCalledWith('Audio playback unavailable.'));
  });
});