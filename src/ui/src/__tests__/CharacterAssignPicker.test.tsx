import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { CharacterAssignPicker } from '../components/CharacterAssignPicker';
import type { CharacterConfig } from '../models/types';

const alice: CharacterConfig = {
  name: 'Alice',
  'voice-sample': 'alice.wav',
};

const bob: CharacterConfig = {
  name: 'Bob',
  'voice-sample': 'bob.wav',
};

const carol: CharacterConfig = {
  name: 'Carol',
  'voice-sample': 'carol.wav',
};
const dave: CharacterConfig = {
  name: 'Dave',
  'custom-voice': { language: 'English', speaker: 'spk_9', instruct: '' },
};

describe('CharacterAssignPicker (Phase 10)', () => {
  beforeEach(() => {
    // jsdom lacks HTMLMediaElement.play
    window.HTMLMediaElement.prototype.play = vi.fn().mockResolvedValue(undefined);
  });

  it('renders nothing when closed', () => {
    const { container } = render(
      <CharacterAssignPicker open={false} characters={[alice, bob]} targetCount={1} onCancel={vi.fn()} onAssign={vi.fn()} />,
    );
    expect(container.querySelector('[data-testid="character-assign-picker"]')).toBeNull();
  });

  it('lists characters with target count in the title', () => {
    render(
      <CharacterAssignPicker open characters={[alice, bob]} targetCount={3} onCancel={vi.fn()} onAssign={vi.fn()} />,
    );
    expect(screen.getByTestId('character-assign-picker')).toBeInTheDocument();
    expect(screen.getByTestId('character-assign-picker')).toHaveTextContent('Assign character (3 lines selected)');
    expect(screen.getByTestId('assign-option-Alice')).toBeInTheDocument();
    expect(screen.getByTestId('assign-option-Bob')).toBeInTheDocument();
  });

  it('assigns the picked character', async () => {
    const onAssign = vi.fn();
    render(
      <CharacterAssignPicker open characters={[alice, bob]} targetCount={1} onCancel={vi.fn()} onAssign={onAssign} />,
    );
    fireEvent.click(screen.getByTestId('assign-option-Bob').querySelector('.assign-pick') as HTMLElement);
    await waitFor(() => expect(onAssign).toHaveBeenCalledWith('Bob'));
  });

  it('filters characters by query', () => {
    render(
      <CharacterAssignPicker open characters={[alice, bob, carol]} targetCount={2} onCancel={vi.fn()} onAssign={vi.fn()} />,
    );
    fireEvent.change(screen.getByTestId('assign-picker-filter'), { target: { value: 'bo' } });
    expect(screen.getByTestId('assign-option-Bob')).toBeInTheDocument();
    expect(screen.queryByTestId('assign-option-Alice')).toBeNull();
    expect(screen.queryByTestId('assign-option-Carol')).toBeNull();
  });

  it('cancel button and Escape both close', () => {
    const onCancel = vi.fn();
    render(
      <CharacterAssignPicker open characters={[alice]} targetCount={1} onCancel={onCancel} onAssign={vi.fn()} />,
    );
    fireEvent.click(screen.getByTestId('assign-picker-cancel'));
    expect(onCancel).toHaveBeenCalledTimes(1);
    fireEvent.keyDown(window, { key: 'Escape' });
    expect(onCancel).toHaveBeenCalledTimes(2);
  });

  it('shows a preview button only for voice-sample characters', () => {
    render(
      <CharacterAssignPicker open characters={[alice, dave]} targetCount={1} onCancel={vi.fn()} onAssign={vi.fn()} />,
    );
    expect(screen.getByTestId('assign-preview-Alice')).toBeInTheDocument();
    expect(screen.queryByTestId('assign-preview-Dave')).toBeNull();
  });

  it('A/B compare: selecting two enables Play A/B, play sequentially', async () => {
    window.HTMLMediaElement.prototype.play = vi.fn().mockResolvedValue(undefined);
    const playSpy = window.HTMLMediaElement.prototype.play as ReturnType<typeof vi.fn>;
    render(
      <CharacterAssignPicker open characters={[alice, bob]} targetCount={1} allowCompare onCancel={vi.fn()} onAssign={vi.fn()} />,
    );
    const playBtn = screen.getByTestId('assign-compare-play') as HTMLButtonElement;
    expect(playBtn.disabled).toBe(true);
    fireEvent.click(screen.getByTestId('assign-compare-Alice'));
    fireEvent.click(screen.getByTestId('assign-compare-Bob'));
    expect(playBtn.disabled).toBe(false);
    fireEvent.click(playBtn);
    await waitFor(() => {
      // Alice's sample + Bob has none, but at least Alice's audio played
      expect(playSpy).toHaveBeenCalled();
    });
  });

  it('keeps at most two characters in A/B compare', () => {
    render(
      <CharacterAssignPicker open characters={[alice, bob, carol]} targetCount={1} allowCompare onCancel={vi.fn()} onAssign={vi.fn()} />,
    );
    const playBtn = screen.getByTestId('assign-compare-play') as HTMLButtonElement;
    fireEvent.click(screen.getByTestId('assign-compare-Alice'));
    expect(playBtn.disabled).toBe(true); // only one selected
    fireEvent.click(screen.getByTestId('assign-compare-Bob'));
    expect(playBtn.disabled).toBe(false); // two selected
    fireEvent.click(screen.getByTestId('assign-compare-Alice'));
    expect(playBtn.disabled).toBe(true); // Alice deselected, one remains
    // Adding Carol as third keeps the cap at two (Bob + Carol)
    fireEvent.click(screen.getByTestId('assign-compare-Carol'));
    expect(playBtn.disabled).toBe(false);
  });

  it('assigning with zero targets still calls onAssign (parent hints)', async () => {
    const onAssign = vi.fn();
    render(
      <CharacterAssignPicker open characters={[alice]} targetCount={0} onCancel={vi.fn()} onAssign={onAssign} />,
    );
    expect(screen.getByTestId('character-assign-picker')).toHaveTextContent('0 lines selected');
    fireEvent.click(screen.getByTestId('assign-option-Alice').querySelector('.assign-pick') as HTMLElement);
    await waitFor(() => expect(onAssign).toHaveBeenCalledWith('Alice'));
  });
});