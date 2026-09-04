import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, fireEvent, act } from '@testing-library/react';
import { DialogBar } from '../components/DialogBar';
import type { DialogElement } from '../models/types';
import { computeDialogHash } from '../utils/dialogHash';

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

// Find the round render/generate button (the one whose background reflects staleness).
const getRenderButton = (container: HTMLElement): HTMLElement => {
  const buttons = Array.from(container.querySelectorAll('button'));
  const btn = buttons.find((b) => {
    const bg = (b as HTMLElement).style.background;
    return bg && bg.includes('rgb');
  });
  if (!btn) throw new Error('render button not found');
  return btn as HTMLElement;
};

// Expand the dialog and return its textarea.
const expandAndGetTextarea = (container: HTMLElement): HTMLTextAreaElement => {
  const header = container.querySelector('.dialog-bar-header') as HTMLElement;
  if (!header) throw new Error('header not found');
  fireEvent.click(header);
  const ta = container.querySelector('textarea');
  if (!ta) throw new Error('textarea not found after expand');
  return ta as HTMLTextAreaElement;
};

const GREEN = '76, 175, 80'; // #4CAF50
const YELLOW = '255, 193, 7'; // #ffc107

describe('DialogBar staleness indicator (client-side MD5)', () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  const renderRenderedDialog = (text = 'Hello world') => {
    const base: DialogElement = {
      _index: 0,
      dlgseq: '1',
      sectionId: '1',
      character: 'Alice',
      text,
      attributes: { dlgseq: '1', section_seq: '1', character: 'Alice' },
    };
    const renderHash = computeDialogHash(base, 'dialog');
    const rendered: DialogElement = {
      ...base,
      renderHash,
      attributes: { ...base.attributes, render_hash: renderHash },
    };
    const onUpdateDialog = vi.fn().mockResolvedValue(undefined);
    const utils = render(
      <DialogBar
        dialog={rendered}
        hasAudioClip={true}
        isStaleClip={false}
        isTimestampStale={false}
        availableCharacters={['Alice']}
        onUpdateDialog={onUpdateDialog}
      />
    );
    return { rendered, onUpdateDialog, ...utils };
  };

  it('starts green immediately after a render (hash matches)', () => {
    const { container } = renderRenderedDialog();
    expect(getRenderButton(container).style.background).toContain(GREEN);
  });

  it('turns yellow after typing (debounced) when text diverges from render_hash', () => {
    const { container } = renderRenderedDialog();

    const textarea = expandAndGetTextarea(container);
    fireEvent.change(textarea, { target: { value: 'Hello there, brave new world' } });

    // Advance past the 300ms debounce window.
    act(() => {
      vi.advanceTimersByTime(350);
    });

    expect(getRenderButton(container).style.background).toContain(YELLOW);
  });

  it('returns to green when the edit is undone to the rendered text', () => {
    const { container } = renderRenderedDialog('Hello world');

    const textarea = expandAndGetTextarea(container);

    fireEvent.change(textarea, { target: { value: 'Something else entirely' } });
    act(() => {
      vi.advanceTimersByTime(350);
    });
    expect(getRenderButton(container).style.background).toContain(YELLOW);

    // Undo back to the exact rendered text.
    fireEvent.change(textarea, { target: { value: 'Hello world' } });
    act(() => {
      vi.advanceTimersByTime(350);
    });
    expect(getRenderButton(container).style.background).toContain(GREEN);
  });

  it('recomputes immediately on blur even before the debounce fires', () => {
    const { container } = renderRenderedDialog();

    const textarea = expandAndGetTextarea(container);
    fireEvent.change(textarea, { target: { value: 'Changed text' } });

    // Blur without advancing timers -> immediate recompute.
    act(() => {
      fireEvent.blur(textarea);
    });

    expect(getRenderButton(container).style.background).toContain(YELLOW);
  });

  it('shows green as soon as the parent supplies an updated renderHash (post-render)', () => {
    const { container, rerender, rendered } = renderRenderedDialog('Hello world');

    const textarea = expandAndGetTextarea(container);
    const newText = 'Hello world, re-rendered';
    fireEvent.change(textarea, { target: { value: newText } });
    fireEvent.blur(textarea); // syncs text to parent (mocked) 
    act(() => {
      vi.advanceTimersByTime(350);
    });
    expect(getRenderButton(container).style.background).toContain(YELLOW);

    // Parent re-renders with the text and a fresh renderHash matching it.
    const newHash = computeDialogHash({ ...rendered, text: 'Hello world, re-rendered' }, 'dialog');
    rerender(
      <DialogBar
        dialog={{
          ...rendered,
          text: 'Hello world, re-rendered',
          renderHash: newHash,
          attributes: { ...rendered.attributes, render_hash: newHash },
        }}
        hasAudioClip={true}
        isStaleClip={false}
        isTimestampStale={false}
        availableCharacters={['Alice']}
        onUpdateDialog={vi.fn()}
      />
    );

    // Local text syncs to the new prop; hash now matches.
    expect(getRenderButton(container).style.background).toContain(GREEN);
  });
});
