import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { DialogBar } from '../components/DialogBar';
import type { DialogElement } from '../models/types';

vi.mock('../hooks/useAudioPlayer', () => ({
  useAudioPlayer: () => ({
    isPlaying: false,
    play: vi.fn(),
    stop: vi.fn(),
  }),
}));

vi.mock('../services/pythonBridge', () => ({
  PythonBridgeService: {
    cancelAudio: vi.fn(),
    playAudio: vi.fn(),
  },
}));

const baseDialog: DialogElement = {
  _index: 0,
  dlgseq: '1',
  sectionId: '0',
  character: 'Alice',
  text: 'Hello',
  attributes: {
    dlgseq: '1',
    section_seq: '0',
    character: 'Alice',
  },
};

describe('DialogBar validation rendering', () => {
  it('shows validation marker after character change updates parent dialog prop', async () => {
    const invalidDialog: DialogElement = {
      ...baseDialog,
      character: 'Hendrix-echo',
      attributes: {
        ...baseDialog.attributes,
        character: 'Hendrix-echo',
      },
      validationIssues: [
        {
          code: 'invalid-dialog-effects',
          message: "Character 'Hendrix-echo' dialog-effects entries 'caves', 'xxx' are not defined in story-config.yml dialog-effects.",
        },
        {
          code: 'invalid-voice-sample',
          message: "Character 'Hendrix-echo' voice-sample 'Hendricks-voice-x.wav' does not exist in Story-Fractured_Assistance.",
        },
      ],
    };

    const onUpdateDialog = vi.fn().mockResolvedValue(undefined);

    const { rerender } = render(
      <DialogBar
        dialog={baseDialog}
        availableCharacters={['Alice', 'Hendrix-echo']}
        onUpdateDialog={onUpdateDialog}
      />
    );

    fireEvent.click(screen.getByText('Alice'));
    fireEvent.change(screen.getByDisplayValue('Alice'), {
      target: { value: 'Hendrix-echo' },
    });

    await waitFor(() => {
      expect(onUpdateDialog).toHaveBeenCalled();
    });

    rerender(
      <DialogBar
        dialog={invalidDialog}
        availableCharacters={['Alice', 'Hendrix-echo']}
        onUpdateDialog={onUpdateDialog}
      />
    );

    expect(screen.getByRole('button', { name: /Validation issues for Hendrix-echo/i })).toBeInTheDocument();
  });
});
