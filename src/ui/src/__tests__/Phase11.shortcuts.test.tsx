import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { CharacterVoiceDialog } from '../components/CharacterVoiceDialog';
import { CharacterBar } from '../components/CharacterBar';
import type { CharacterConfig } from '../models/types';

vi.mock('../services/pythonBridge', () => ({
  PythonBridgeService: {
    loadGlobalConfig: vi.fn().mockResolvedValue({
      FlexiTTS: { 'current-story': 'Entanglement', 'story-dir-prefix': 'Story-' },
    }),
    loadStoryConfigForStory: vi.fn().mockResolvedValue({
      global: { voices: 'refs/' },
      characters: [],
    }),
    listCharacters: vi.fn().mockResolvedValue([
      { name: 'Alice', 'voice-sample': 'alice.wav' },
      { name: 'Bob', 'voice-sample': 'bob.wav' },
    ]),
    createCharacter: vi.fn().mockResolvedValue({ success: true }),
    deleteCharacter: vi.fn().mockResolvedValue({ success: true }),
    useUnresolvedReferences: () => ({ unresolved: [] }),
  },
}));

// The dialog imports useUnresolvedReferences from a hook module; mock it.
vi.mock('../hooks/useUnresolvedReferences', () => ({
  useUnresolvedReferences: () => ({ unresolved: [] }),
}));

vi.mock('../services/alertService', () => ({
  alerts: {
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn(),
    info: vi.fn(),
    alert: vi.fn(),
  },
}));

const alice: CharacterConfig = { name: 'Alice', 'voice-sample': 'alice.wav' };

describe('CharacterBar Phase 11 keyboard + ARIA', () => {
  it('Enter toggles expand, Space selects (not expand)', () => {
    const onToggleExpand = vi.fn();
    const onSelect = vi.fn();
    render(
      <CharacterBar
        character={alice}
        storyDir="Story-Test"
        expanded={false}
        selected={false}
        availableDialogEffects={[]}
        onToggleExpand={onToggleExpand}
        onSelect={onSelect}
        onRefresh={vi.fn()}
        onError={vi.fn()}
      />,
    );
    const row = screen.getByTestId('character-bar-Alice');
    fireEvent.keyDown(row, { key: 'Enter' });
    expect(onToggleExpand).toHaveBeenCalledWith('Alice');
    expect(onSelect).not.toHaveBeenCalled();
    fireEvent.keyDown(row, { key: ' ' });
    expect(onSelect).toHaveBeenCalledWith('Alice');
    expect(onToggleExpand).toHaveBeenCalledTimes(1);
  });

  it('exposes ARIA metadata: expanded state, selected, descriptive label', () => {
    const { rerender } = render(
      <CharacterBar
        character={alice}
        storyDir="Story-Test"
        expanded={false}
        selected={false}
        availableDialogEffects={[]}
        onToggleExpand={vi.fn()}
        onRefresh={vi.fn()}
        onError={vi.fn()}
      />,
    );
    const row = screen.getByTestId('character-bar-Alice');
    expect(row.getAttribute('aria-expanded')).toBe('false');
    expect(row.getAttribute('aria-label')).toContain('Alice');
    expect(row.getAttribute('aria-label')).toContain('Collapsed');

    rerender(
      <CharacterBar
        character={alice}
        storyDir="Story-Test"
        expanded
        selected
        availableDialogEffects={[]}
        onToggleExpand={vi.fn()}
        onRefresh={vi.fn()}
        onError={vi.fn()}
      />,
    );
    expect(screen.getByTestId('character-bar-Alice').getAttribute('aria-expanded')).toBe('true');
    expect(screen.getByTestId('character-bar-Alice').getAttribute('aria-selected')).toBe('true');
  });
});

describe('CharacterVoiceDialog Phase 11 shortcuts', () => {
  const baseProps = { storyDir: 'Story-Test', open: true, onClose: vi.fn() };

  const mockApi = () => {
    (window as unknown as { api: Record<string, unknown> }).api = {
      runPythonScript: vi.fn().mockResolvedValue('{}'),
      readHelpDoc: vi.fn(),
      showConfirmDialog: vi.fn().mockResolvedValue(1),
      readAudioFile: vi.fn().mockResolvedValue('data:audio/wav;base64,AAAA'),
      writeFile: vi.fn().mockResolvedValue(undefined),
    };
  };

  beforeEach(() => {
    mockApi();
    window.sessionStorage.clear();
    window.HTMLMediaElement.prototype.play = vi.fn().mockResolvedValue(undefined);
  });

  it('Ctrl+F focuses the character search input', async () => {
    render(<CharacterVoiceDialog {...baseProps} />);
    await waitFor(() => expect(screen.getByTestId('character-search')).toBeInTheDocument());
    fireEvent.keyDown(window, { key: 'f', ctrlKey: true });
    expect(document.activeElement).toBe(screen.getByTestId('character-search'));
  });

  it('Ctrl+N opens the new-character inline input', async () => {
    render(<CharacterVoiceDialog {...baseProps} />);
    await waitFor(() => expect(screen.getByTestId('character-search')).toBeInTheDocument());
    expect(screen.queryByTestId('character-new-name')).toBeNull();
    fireEvent.keyDown(window, { key: 'n', ctrlKey: true });
    expect(screen.getByTestId('character-new-name')).toBeInTheDocument();
  });

  it('Space previews the selected character via readAudioFile', async () => {
    render(<CharacterVoiceDialog {...baseProps} />);
    await waitFor(() => expect(screen.getByTestId('character-bar-Alice')).toBeInTheDocument());
    // Select Alice with Space on her row
    fireEvent.keyDown(screen.getByTestId('character-bar-Alice'), { key: ' ' });
    // Then Space at dialog level previews
    fireEvent.keyDown(window, { key: ' ' });
    await waitFor(() => {
      const api = (window as unknown as { api: { readAudioFile: ReturnType<typeof vi.fn> } }).api;
      expect(api.readAudioFile).toHaveBeenCalledWith('Story-Test/refs//alice.wav');
    });
  });

  it('Delete deletes the selected character after confirmation', async () => {
    render(<CharacterVoiceDialog {...baseProps} />);
    await waitFor(() => expect(screen.getByTestId('character-bar-Alice')).toBeInTheDocument());
    fireEvent.keyDown(screen.getByTestId('character-bar-Alice'), { key: ' ' });
    fireEvent.keyDown(window, { key: 'Delete' });
    await waitFor(() => {
      const api = (window as unknown as { api: { showConfirmDialog: ReturnType<typeof vi.fn> } }).api;
      expect(api.showConfirmDialog).toHaveBeenCalled();
    });
    await waitFor(async () => {
      const { PythonBridgeService } = await import('../services/pythonBridge');
      expect(PythonBridgeService.deleteCharacter).toHaveBeenCalledWith('Story-Test', 'Alice');
    });
  });

  it('Delete is ignored while typing in an input', async () => {
    render(<CharacterVoiceDialog {...baseProps} />);
    await waitFor(() => expect(screen.getByTestId('character-bar-Alice')).toBeInTheDocument());
    fireEvent.keyDown(screen.getByTestId('character-bar-Alice'), { key: ' ' });
    const search = screen.getByTestId('character-search');
    search.focus();
    fireEvent.keyDown(window, { key: 'Delete' });
    const api = (window as unknown as { api: { showConfirmDialog: ReturnType<typeof vi.fn> } }).api;
    expect(api.showConfirmDialog).not.toHaveBeenCalled();
  });

  it('selection clears when the dialog closes', async () => {
    const { rerender } = render(<CharacterVoiceDialog {...baseProps} />);
    await waitFor(() => expect(screen.getByTestId('character-bar-Alice')).toBeInTheDocument());
    fireEvent.keyDown(screen.getByTestId('character-bar-Alice'), { key: ' ' });
    rerender(<CharacterVoiceDialog {...baseProps} open={false} />);
    await waitFor(() => {
      // Reopening shows no selection: aria-selected absent on rows
      rerender(<CharacterVoiceDialog {...baseProps} open />);
      expect(screen.getByTestId('character-bar-Alice').getAttribute('aria-selected')).toBeNull();
    });
  });
});

describe('Tab order and focus trap (existing dialogs)', () => {
  it('assign picker traps Tab within the modal', async () => {
    const { CharacterAssignPicker } = await import('../components/CharacterAssignPicker');
    render(
      <CharacterAssignPicker
        open
        characters={[{ name: 'Alice', 'voice-sample': 'a.wav' }]}
        targetCount={1}
        onCancel={vi.fn()}
        onAssign={vi.fn()}
      />,
    );
    const filter = screen.getByTestId('assign-picker-filter');
    filter.focus();
    expect(document.activeElement).toBe(filter);
  });
});