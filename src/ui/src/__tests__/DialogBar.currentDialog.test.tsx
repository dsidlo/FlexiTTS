import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { DialogBar } from '../components/DialogBar';
import type { DialogElement } from '../services/types';

const dialog: DialogElement = {
  dlgseq: '2', sectionId: '0', character: 'Narrator', kind: 'dialog',
  text: 'Hello', attributes: { emotion: 'Neutral', character: 'Narrator' },
  validationIssues: [],
} as unknown as DialogElement;

const baseProps = {
  dialog, displayId: '2',
  onUpdateDialog: vi.fn(),
};

describe('DialogBar current-dialog check-mark + open selection', () => {
  it('shows check-mark on the current dialog', () => {
    const { getByTestId } = render(
      <DialogBar {...baseProps} isCurrentDialog={true} />,
    );
    expect(getByTestId('dialog-current-check-2')).toBeTruthy();
  });

  it('does not show check-mark on non-current dialogs', () => {
    const { queryByTestId } = render(
      <DialogBar {...baseProps} isCurrentDialog={false} />,
    );
    expect(queryByTestId('dialog-current-check-2')).toBeNull();
  });

  it('plain click notifies onOpened (no Ctrl required)', () => {
    const onOpened = vi.fn();
    const onToggleSelect = vi.fn();
    const { getByText } = render(
      <DialogBar {...baseProps} onOpened={onOpened} onToggleSelect={onToggleSelect} />,
    );
    getByText('Narrator').closest('.dialog-bar-header')!.dispatchEvent(
      new MouseEvent('click', { bubbles: true, cancelable: true }),
    );
    expect(onOpened).toHaveBeenCalledWith('2', '0', undefined);
    expect(onToggleSelect).not.toHaveBeenCalled();
  });

  it('Ctrl+Click still toggles multi-selection (not open)', () => {
    const onOpened = vi.fn();
    const onToggleSelect = vi.fn();
    const { getByText } = render(
      <DialogBar {...baseProps} onOpened={onOpened} onToggleSelect={onToggleSelect} />,
    );
    const header = getByText('Narrator').closest('.dialog-bar-header')!;
    const ev = new MouseEvent('click', { bubbles: true, cancelable: true, ctrlKey: true });
    header.dispatchEvent(ev);
    expect(onToggleSelect).toHaveBeenCalled();
    expect(onOpened).not.toHaveBeenCalled();
  });
});
