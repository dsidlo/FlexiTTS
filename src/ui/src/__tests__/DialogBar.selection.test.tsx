import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
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

const makeDialog = (index: number, character: string): DialogElement => ({
  _index: index,
  dlgseq: String(index + 1),
  sectionId: '0',
  character,
  text: `Line ${index + 1}`,
  attributes: { dlgseq: String(index + 1), section_seq: '0', character },
});

describe('DialogBar Phase 10 selection and assign', () => {
  const baseProps = {
    availableCharacters: ['Alice', 'Bob'],
    onUpdateDialog: vi.fn().mockResolvedValue(undefined),
  };

  it('plain click expands, Ctrl+Click toggles selection', () => {
    const onToggleSelect = vi.fn();
    render(<DialogBar dialog={makeDialog(0, 'Alice')} {...baseProps} onToggleSelect={onToggleSelect} />);

    const header = screen.getByText('#1').closest('.dialog-bar-header') as HTMLElement;
    // Plain click: no selection toggle
    fireEvent.click(header);
    expect(onToggleSelect).not.toHaveBeenCalled();

    // Ctrl+Click: selection toggle
    fireEvent.click(header, { ctrlKey: true });
    expect(onToggleSelect).toHaveBeenCalledWith('1', '0', 0, false);

    // Meta+Click (macOS): selection toggle
    fireEvent.click(header, { metaKey: true });
    expect(onToggleSelect).toHaveBeenCalledWith('1', '0', 0, false);
  });

  it('marks the line as selected via data-selected', () => {
    render(<DialogBar dialog={makeDialog(0, 'Alice')} {...baseProps} isSelected />);
    const header = screen.getByText('#1').closest('.dialog-bar-header') as HTMLElement;
    expect(header.getAttribute('data-selected')).toBe('true');
  });

  it('context menu shows Assign Character entry and opens picker request', () => {
    const onAssignCharacter = vi.fn();
    render(<DialogBar dialog={makeDialog(0, 'Alice')} {...baseProps} onAssignCharacter={onAssignCharacter} />);

    const header = screen.getByText('#1').closest('.dialog-bar-header') as HTMLElement;
    fireEvent.contextMenu(header);
    const item = screen.getByText('Assign Character…');
    fireEvent.click(item);
    expect(onAssignCharacter).toHaveBeenCalledWith('1', '0', 0);
  });

  it('context menu hides Assign Character when no callback or no characters', () => {
    render(<DialogBar dialog={makeDialog(0, 'Alice')} availableCharacters={[]} onUpdateDialog={vi.fn()} />);
    const header = screen.getByText('#1').closest('.dialog-bar-header') as HTMLElement;
    fireEvent.contextMenu(header);
    expect(screen.queryByText('Assign Character…')).toBeNull();
  });
});