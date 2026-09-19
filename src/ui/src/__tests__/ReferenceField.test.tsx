/**
 * Phase 6b tests: ReferenceField, UnresolvedReferences, stub flow integration.
 */

import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { ReferenceField } from '../components/ReferenceField';
import { UnresolvedReferencesPanel } from '../components/UnresolvedReferences';
import type { CharacterConfig } from '../models/types';

vi.mock('../services/pythonBridge', () => ({
  PythonBridgeService: {
    listCharacters: vi.fn(),
    createCharacter: vi.fn(),
    deleteCharacter: vi.fn(),
    updateCharacter: vi.fn(),
    loadGlobalConfig: vi.fn(),
    loadStoryConfigForStory: vi.fn(),
    runBridgeCommand: vi.fn(),
  },
}));

import { PythonBridgeService } from '../services/pythonBridge';

const runBridgeCommandMock = PythonBridgeService.runBridgeCommand as unknown as ReturnType<typeof vi.fn>;
const updateCharacterMock = PythonBridgeService.updateCharacter as unknown as ReturnType<typeof vi.fn>;

describe('ReferenceField (Phase 6b.1)', () => {
  it('renders with label and value', () => {
    render(<ReferenceField label="Speaker" value="ryan" choices={['ryan', 'aiden']} onCommit={noop} testId="ref" />);
    expect(screen.getByTestId('ref-input')).toHaveValue('ryan');
  });

  it('shows dropdown options on focus', () => {
    render(<ReferenceField label="Speaker" value="" choices={['ryan', 'aiden']} onCommit={noop} testId="ref" />);
    fireEvent.focus(screen.getByTestId('ref-input'));
    expect(screen.getByTestId('ref-option-ryan')).toBeInTheDocument();
    expect(screen.getByTestId('ref-option-aiden')).toBeInTheDocument();
  });

  it('shows all 9 speakers when no text has been typed', () => {
    const speakers = ['aiden', 'dylan', 'eric', 'ono_anna', 'ryan', 'serena', 'sohee', 'uncle_fu', 'vivian'];
    render(<ReferenceField label="Speaker" value="ryan" choices={speakers} onCommit={noop} testId="ref" />);
    fireEvent.focus(screen.getByTestId('ref-input'));
    for (const s of speakers) {
      expect(screen.getByTestId(`ref-option-${s}`)).toBeInTheDocument();
    }
  });

  it('picks an existing value from the list (satisfied, no red)', async () => {
    const onCommit = vi.fn();
    render(<ReferenceField label="Speaker" value="" choices={['ryan', 'aiden']} onCommit={onCommit} testId="ref" />);
    fireEvent.focus(screen.getByTestId('ref-input'));
    fireEvent.mouseDown(screen.getByTestId('ref-option-ryan'));
    await waitFor(() => expect(onCommit).toHaveBeenCalledWith('ryan'));
    const input = screen.getByTestId('ref-input') as HTMLInputElement;
    expect(input.getAttribute('aria-invalid')).toBe('false');
  });

  it('flags a typed unsatisfied value in red with tooltip', () => {
    const onCommit = vi.fn();
    render(<ReferenceField label="Effect" value="cave2" choices={['cave']} onCommit={onCommit} testId="ref" />);
    const input = screen.getByTestId('ref-input') as HTMLInputElement;
    expect(input.getAttribute('aria-invalid')).toBe('true');
    expect(input.title).toContain('cave2');
    expect(input.style.border).toContain('rgb(255, 102, 102)');
  });

  it('red clears when the reference is satisfied', () => {
    const { rerender } = render(
      <ReferenceField label="Effect" value="cave2" choices={[]} onCommit={noop} testId="ref" />,
    );
    expect((screen.getByTestId('ref-input') as HTMLInputElement).getAttribute('aria-invalid')).toBe('true');
    rerender(<ReferenceField label="Effect" value="cave2" choices={['cave2']} onCommit={noop} testId="ref" />);
    expect((screen.getByTestId('ref-input') as HTMLInputElement).getAttribute('aria-invalid')).toBe('false');
  });

  it('type-ahead filters choices', () => {
    render(<ReferenceField label="Speaker" value="" choices={['ryan', 'aiden', 'serena']} onCommit={noop} testId="ref" />);
    const input = screen.getByTestId('ref-input');
    fireEvent.focus(input);
    fireEvent.change(input, { target: { value: 'se' } });
    expect(screen.queryByTestId('ref-option-ryan')).not.toBeInTheDocument();
    expect(screen.getByTestId('ref-option-serena')).toBeInTheDocument();
  });

  it('Escape restores the previous value', () => {
    render(<ReferenceField label="Speaker" value="ryan" choices={['ryan']} onCommit={noop} testId="ref" />);
    const input = screen.getByTestId('ref-input');
    fireEvent.change(input, { target: { value: 'changed' } });
    fireEvent.keyDown(input, { key: 'Escape' });
    expect((input as HTMLInputElement).value).toBe('ryan');
  });

  it('Enter commits the typed value', () => {
    const onCommit = vi.fn();
    render(<ReferenceField label="Speaker" value="" choices={['ryan']} onCommit={onCommit} testId="ref" />);
    const input = screen.getByTestId('ref-input');
    fireEvent.focus(input);
    fireEvent.change(input, { target: { value: 'ryan' } });
    fireEvent.keyDown(input, { key: 'Enter' });
    expect(onCommit).toHaveBeenCalledWith('ryan');
  });
});

describe('UnresolvedReferencesPanel (Phase 6b.3)', () => {
  it('shows clear state when no unresolved refs', () => {
    render(<UnresolvedReferencesPanel unresolved={[]} onJump={noop} onCreateStub={noop} />);
    expect(screen.getByTestId('references-panel-clear')).toBeInTheDocument();
  });

  it('lists unresolved refs with jump and stub buttons', () => {
    const onJump = vi.fn();
    const onCreateStub = vi.fn();
    render(
      <UnresolvedReferencesPanel
        unresolved={[{ character: 'Echo', type: 'dialog-effects', value: 'ghost' }]}
        onJump={onJump}
        onCreateStub={onCreateStub}
      />,
    );
    expect(screen.getByTestId('references-panel')).toHaveTextContent('1 unresolved reference');
    fireEvent.click(screen.getByTestId('reference-jump-Echo'));
    expect(onJump).toHaveBeenCalledWith('Echo');
    fireEvent.click(screen.getByTestId('reference-stub-ghost'));
    expect(onCreateStub).toHaveBeenCalledWith('dialog-effects', 'ghost');
  });
});

describe('CharacterBar reference integration (Phase 6b)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('shows reference fields in expanded view for custom-voice characters', () => {
    const character: CharacterConfig = {
      name: 'Hendrix',
      'custom-voice': { language: 'English', speaker: 'ryan', instruct: '' },
    };
    render(
      <CharacterBar
        character={character}
        storyDir="Story-Test"
        expanded
        selected={false}
        availableDialogEffects={['cave']}
        onToggleExpand={vi.fn()}
        onRefresh={vi.fn()}
        onError={vi.fn()}
      />,
    );
    expect(screen.getByTestId('ref-speaker-Hendrix-input')).toBeInTheDocument();
    expect(screen.getByTestId('ref-dialog-effect-Hendrix-input')).toBeInTheDocument();
  });

  it('committing a new dialog-effect creates a stub then updates the character', async () => {
    runBridgeCommandMock.mockResolvedValue({ success: true });
    updateCharacterMock.mockResolvedValue({});
    const onRefresh = vi.fn();
    render(
      <CharacterBar
        character={{ name: 'Hendrix' }}
        storyDir="Story-Test"
        expanded
        selected={false}
        availableDialogEffects={[]}
        onToggleExpand={vi.fn()}
        onRefresh={onRefresh}
        onError={vi.fn()}
      />,
    );
    const input = screen.getByTestId('ref-dialog-effect-Hendrix-input');
    fireEvent.focus(input);
    fireEvent.change(input, { target: { value: 'ghost' } });
    fireEvent.keyDown(input, { key: 'Enter' });
    await waitFor(() => {
      // Stub generated first
      expect(runBridgeCommandMock).toHaveBeenCalledWith([
        'create-dialog-effect-stub', 'Story-Test', 'ghost',
      ]);
      expect(updateCharacterMock).toHaveBeenCalledWith('Story-Test', 'Hendrix', {
        dialogEffects: ['ghost'],
      });
      expect(onRefresh).toHaveBeenCalled();
    });
  });

  it('shows the uploader for sample-based characters', () => {
    render(
      <CharacterBar
        character={{ name: 'Ayana', 'voice-sample': 'ayana.wav' }}
        storyDir="Story-Test"
        expanded
        selected={false}
        availableDialogEffects={[]}
        onToggleExpand={vi.fn()}
        onRefresh={vi.fn()}
        onError={vi.fn()}
      />,
    );
    expect(screen.getByTestId('sample-uploader-Ayana')).toBeInTheDocument();
  });
});

// CharacterBar import needed for the describe above
import { CharacterBar } from '../components/CharacterBar';

const noop = () => {};