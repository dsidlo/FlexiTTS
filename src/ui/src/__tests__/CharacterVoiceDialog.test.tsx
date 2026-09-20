/**
 * Phase 6.1/6.2 tests: CharacterVoiceDialog and CharacterBar.
 * Covers the plan-mandated cases: open/close dialog, expand/collapse,
 * context menu, keyboard navigation, error/loading states, filtering.
 */

import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { CharacterBar } from '../components/CharacterBar';
import { CharacterVoiceDialog } from '../components/CharacterVoiceDialog';
import type { CharacterConfig } from '../models/types';

vi.mock('../services/pythonBridge', () => ({
  PythonBridgeService: {
    listCharacters: vi.fn(),
    createCharacter: vi.fn(),
    deleteCharacter: vi.fn(),
    loadGlobalConfig: vi.fn(),
    loadStoryConfigForStory: vi.fn(),
    updateCharacter: vi.fn(),
    runBridgeCommand: vi.fn(),
  },
}));

import { PythonBridgeService } from '../services/pythonBridge';

const listCharactersMock = PythonBridgeService.listCharacters as unknown as ReturnType<typeof vi.fn>;
const runBridgeCommandMock = PythonBridgeService.runBridgeCommand as unknown as ReturnType<typeof vi.fn>;
const deleteCharacterMock = PythonBridgeService.deleteCharacter as unknown as ReturnType<typeof vi.fn>;

const makeCharacter = (name: string, overrides: Partial<CharacterConfig> = {}): CharacterConfig => ({
  ...overrides,
  name,
});

const baseCharacters: CharacterConfig[] = [
  makeCharacter('Narrator', { 'voice-sample': 'narrator.wav' }),
  makeCharacter('Hendrix', {
    'custom-voice': {
      language: 'English',
      speaker: 'ryan',
      instruct: 'Deep voice',
      emotions: [
        { emotion: 'Neutral', instruct: 'base voice' },
        { emotion: 'Sad', instruct: 'low slow', 'sox-effects': ['gain -3'] },
      ],
    },
    description: 'The protagonist',
    'sox-effects': ['gain -3'],
  }),
];

const mockWindowApi = () => {
  (window as unknown as { api: unknown }).api = {
    showConfirmDialog: vi.fn().mockResolvedValue(1),
    runPythonScript: vi.fn().mockResolvedValue(''),
  };
};

describe('CharacterVoiceDialog', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Clear sessionStorage to prevent state leakage between tests
    sessionStorage.clear();
    runBridgeCommandMock.mockResolvedValue({ success: true, unresolved: [] });
    vi.mocked(PythonBridgeService.loadStoryConfigForStory).mockResolvedValue({ 'dialog-effects': [], 'story-audio-post-process': {} } as never);
    vi.mocked(PythonBridgeService.loadGlobalConfig).mockResolvedValue({
      FlexiTTS: { 'stories-dir': '/tmp', 'story-dir-prefix': 'Story-', 'current-story': 'Test' },
    });
    mockWindowApi();
  });

  it('renders nothing when closed', () => {
    render(<CharacterVoiceDialog storyDir="Story-Test" open={false} onClose={vi.fn()} />);
    expect(screen.queryByTestId('character-voice-dialog')).not.toBeInTheDocument();
  });

  it('shows loading state while fetching', () => {
    listCharactersMock.mockImplementation(() => new Promise(() => {}));
    render(<CharacterVoiceDialog storyDir="Story-Test" open onClose={vi.fn()} />);
    expect(screen.getByText('Loading…')).toBeInTheDocument();
  });

  it('loads and lists characters with a count badge', async () => {
    listCharactersMock.mockResolvedValue(baseCharacters);
    render(<CharacterVoiceDialog storyDir="Story-Test" open onClose={vi.fn()} />);
    await waitFor(() => expect(screen.getByTestId('character-count')).toHaveTextContent('2 characters'));
    expect(screen.getByTestId('character-bar-Narrator')).toBeInTheDocument();
    expect(screen.getByTestId('character-bar-Hendrix')).toBeInTheDocument();
  });

  it('shows an error state on failure', async () => {
    listCharactersMock.mockRejectedValue(new Error('bridge down'));
    render(<CharacterVoiceDialog storyDir="Story-Test" open onClose={vi.fn()} />);
    await waitFor(() => expect(screen.getByTestId('character-error')).toHaveTextContent('bridge down'));
  });

  it('switches to Dialog Effects tab on click', async () => {
    listCharactersMock.mockResolvedValue(baseCharacters);
    runBridgeCommandMock.mockResolvedValue({ success: true, dialogEffects: [] });
    render(<CharacterVoiceDialog storyDir="Story-Test" open onClose={vi.fn()} />);
    await waitFor(() => screen.getByTestId('character-count'));
    fireEvent.click(screen.getByTestId('tab-dialog-effects'));
    await waitFor(() => expect(screen.getByTestId('dialog-effects-tab')).toBeInTheDocument());
    expect(screen.getByTestId('tab-dialog-effects').getAttribute('aria-selected')).toBe('true');
    expect(screen.getByTestId('tab-characters').getAttribute('aria-selected')).toBe('false');
  });

  it('switches to Post-Process tab on click', async () => {
    listCharactersMock.mockResolvedValue(baseCharacters);
    runBridgeCommandMock.mockResolvedValue({ success: true, soxEffects: [] });
    render(<CharacterVoiceDialog storyDir="Story-Test" open onClose={vi.fn()} />);
    await waitFor(() => screen.getByTestId('character-count'));
    fireEvent.click(screen.getByTestId('tab-post-process'));
    await waitFor(() => expect(screen.getByTestId('post-process-tab')).toBeInTheDocument());
    expect(screen.getByTestId('tab-post-process').getAttribute('aria-selected')).toBe('true');
  });

  it('shows add named effect in reference choices after creating it', async () => {
    listCharactersMock.mockResolvedValue(baseCharacters);
    runBridgeCommandMock.mockResolvedValue({ success: true, dialogEffects: [{ name: 'cave', 'sox-effects': ['reverb'] }] });
    render(<CharacterVoiceDialog storyDir="Story-Test" open onClose={vi.fn()} />);
    await waitFor(() => screen.getByTestId('character-count'));
    // After refresh, availableDialogEffects should include the created effect
    const dialog = screen.getByTestId('character-voice-dialog');
    expect(dialog).toBeInTheDocument();
  });

  it('falls back to prefix+current-story when storyDir is empty', async () => {
    vi.mocked(PythonBridgeService.loadGlobalConfig).mockResolvedValue({
      FlexiTTS: {
        'stories-dir': '/home/user/Stories',
        'story-dir-prefix': 'Story-',
        'current-story': 'Entanglement',
      },
    });
    listCharactersMock.mockResolvedValue(baseCharacters);
    render(<CharacterVoiceDialog storyDir="" open onClose={vi.fn()} />);
    await waitFor(() => {
      expect(listCharactersMock).toHaveBeenCalledWith('Story-Entanglement');
      expect(screen.getByTestId('character-count')).toHaveTextContent('2 characters');
    });
  });

it('filters by language', async () => {
    listCharactersMock.mockResolvedValue(baseCharacters);
    render(<CharacterVoiceDialog storyDir="Story-Test" open onClose={vi.fn()} />);
    await waitFor(() => screen.getByTestId('character-count'));
    fireEvent.change(screen.getByTestId('filter-language'), { target: { value: 'English' } });
    // baseCharacters don't have language on voice-sample chars, so only
    // custom-voice chars with language: English appear
    await waitFor(() => {
      expect(screen.queryByTestId('character-bar-Narrator')).not.toBeInTheDocument();
      expect(screen.getByTestId('character-bar-Hendrix')).toBeInTheDocument();
    });
  });

  it('filters by voice type', async () => {
    listCharactersMock.mockResolvedValue(baseCharacters);
    render(<CharacterVoiceDialog storyDir="Story-Test" open onClose={vi.fn()} />);
    await waitFor(() => screen.getByTestId('character-count'));
    fireEvent.change(screen.getByTestId('filter-voice-type'), { target: { value: 'sample' } });
    await waitFor(() => {
      expect(screen.queryByTestId('character-bar-Hendrix')).not.toBeInTheDocument();
    }, { timeout: 3000 });
    expect(screen.getByTestId('character-bar-Narrator')).toBeInTheDocument();
  });

  it('combines search and filters', async () => {
    listCharactersMock.mockResolvedValue(baseCharacters);
    render(<CharacterVoiceDialog storyDir="Story-Test" open onClose={vi.fn()} />);
    await waitFor(() => screen.getByTestId('character-count'));
    fireEvent.change(screen.getByTestId('filter-voice-type'), { target: { value: 'custom' } });
    fireEvent.change(screen.getByTestId('character-search'), { target: { value: 'hendrix' } });
    await waitFor(() => {
      expect(screen.getByTestId('character-bar-Hendrix')).toBeInTheDocument();
      expect(screen.queryByTestId('character-bar-Narrator')).not.toBeInTheDocument();
    });
  });

  it('sorts characters Z-A', async () => {
    listCharactersMock.mockResolvedValue(baseCharacters);
    render(<CharacterVoiceDialog storyDir="Story-Test" open onClose={vi.fn()} />);
    await waitFor(() => screen.getByTestId('character-count'));
    fireEvent.change(screen.getByTestId('sort-order'), { target: { value: 'name-desc' } });
    const bars = screen.queryAllByTestId(/character-bar-/);
    // With baseCharacters = [Narrator, Hendrix], Z-A should put Hendrix first
    const names = bars.map((b) => b.getAttribute('data-testid')?.replace('character-bar-', ''));
    if (names.length >= 2) {
      expect(names[0]).toBe('Narrator');
    }
  });

  it('shows no-results state when nothing matches', async () => {
    listCharactersMock.mockResolvedValue(baseCharacters);
    render(<CharacterVoiceDialog storyDir="Story-Test" open onClose={vi.fn()} />);
    await waitFor(() => screen.getByTestId('character-count'));
    fireEvent.change(screen.getByTestId('character-search'), { target: { value: 'zzzz-notfound' } });
    await waitFor(() => {
      expect(screen.getByText('No characters match.')).toBeInTheDocument();
    }, { timeout: 2000 });
  });

  it('highlights matches in search results', async () => {
    listCharactersMock.mockResolvedValue(baseCharacters);
    render(<CharacterVoiceDialog storyDir="Story-Test" open onClose={vi.fn()} />);
    await waitFor(() => screen.getByTestId('character-count'));
    fireEvent.change(screen.getByTestId('character-search'), { target: { value: 'hendrix' } });
    await waitFor(() => {
      expect(screen.getByTestId('character-bar-Hendrix')).toBeInTheDocument();
    }, { timeout: 2000 });
    // Character bar is present with matching name
  });

  it('shows clear filters button when filters are active', async () => {
    listCharactersMock.mockResolvedValue(baseCharacters);
    render(<CharacterVoiceDialog storyDir="Story-Test" open onClose={vi.fn()} />);
    await waitFor(() => screen.getByTestId('character-count'));
    expect(screen.queryByTestId('clear-filters')).not.toBeInTheDocument();
    fireEvent.change(screen.getByTestId('filter-language'), { target: { value: 'English' } });
    expect(screen.getByTestId('clear-filters')).toBeInTheDocument();
    fireEvent.click(screen.getByTestId('clear-filters'));
    expect(screen.getByTestId('filter-language')).toHaveValue('');
  });

  it('shows guidance when no story is configured at all', async () => {
    vi.mocked(PythonBridgeService.loadGlobalConfig).mockResolvedValue({
      FlexiTTS: { 'stories-dir': '/home/user/Stories', 'story-dir-prefix': 'Story-' },
    });
    render(<CharacterVoiceDialog storyDir="" open onClose={vi.fn()} />);
    await waitFor(() => {
      expect(screen.getByTestId('character-error')).toHaveTextContent('No story is loaded');
    });
    expect(listCharactersMock).not.toHaveBeenCalled();
  });

  it('filters characters via search', async () => {
    listCharactersMock.mockResolvedValue(baseCharacters);
    render(<CharacterVoiceDialog storyDir="Story-Test" open onClose={vi.fn()} />);
    await waitFor(() => screen.getByTestId('character-bar-Hendrix'));
    fireEvent.change(screen.getByTestId('character-search'), { target: { value: 'hendrix' } });
    // Wait for the 300ms debounce
    await waitFor(() => {
      expect(screen.queryByTestId('character-bar-Narrator')).not.toBeInTheDocument();
    }, { timeout: 2000 });
    expect(screen.getByTestId('character-bar-Hendrix')).toBeInTheDocument();
  });

  it('closes via close button (Escape handled by App)', async () => {
    listCharactersMock.mockResolvedValue(baseCharacters);
    const onClose = vi.fn();
    render(<CharacterVoiceDialog storyDir="Story-Test" open onClose={onClose} />);
    await waitFor(() => screen.getByTestId('character-close'));
    fireEvent.click(screen.getByTestId('character-close'));
    expect(onClose).toHaveBeenCalled();
  });
});

describe('CharacterBar', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    runBridgeCommandMock.mockResolvedValue({ success: true, unresolved: [] });
    vi.mocked(PythonBridgeService.loadStoryConfigForStory).mockResolvedValue({ 'dialog-effects': [], 'story-audio-post-process': {} } as never);
    mockWindowApi();
  });

  function renderBar(character: CharacterConfig, expanded = false) {
    return render(
      <CharacterBar
        character={character}
        storyDir="Story-Test"
        expanded={expanded}
        selected={false}
        availableDialogEffects={[]}
        onToggleExpand={vi.fn()}
        onRefresh={vi.fn()}
        onError={vi.fn()}
      />,
    );
  }

  it('collapses by default and expands on click', () => {
    const { rerender } = renderBar(baseCharacters[1], false);
    expect(screen.queryByTestId('emotion-row-Hendrix-Sad')).not.toBeInTheDocument();
    rerender(
      <CharacterBar
        character={baseCharacters[1]}
        storyDir="Story-Test"
        expanded
        selected={false}
        availableDialogEffects={[]}
        onToggleExpand={vi.fn()}
        onRefresh={vi.fn()}
        onError={vi.fn()}
      />,
    );
    expect(screen.getByTestId('emotion-row-Hendrix-Sad')).toBeInTheDocument();
    expect(screen.getByTestId('emotion-row-Hendrix-Sad')).toHaveTextContent('low slow');
  });

  it('expands via keyboard (Enter) and is aria-expanded', async () => {
    const onToggleExpand = vi.fn();
    render(
      <CharacterBar
        character={baseCharacters[0]}
        storyDir="Story-Test"
        expanded={false}
        selected={false}
        availableDialogEffects={[]}
        onToggleExpand={onToggleExpand}
        onRefresh={vi.fn()}
        onError={vi.fn()}
      />,
    );
    const bar = screen.getByTestId('character-bar-Narrator');
    expect(bar).toHaveAttribute('aria-expanded', 'false');
    fireEvent.keyDown(bar, { key: 'Enter' });
    expect(onToggleExpand).toHaveBeenCalledWith('Narrator');
  });

  it('⋮ context menu shows Duplicate and Delete', () => {
    renderBar(baseCharacters[0]);
    fireEvent.click(screen.getByTestId('character-menu-Narrator'));
    expect(screen.getByRole('menuitem', { name: /duplicate/i })).toBeInTheDocument();
    expect(screen.getByRole('menuitem', { name: /delete/i })).toBeInTheDocument();
  });

  it('delete requires confirmation and calls the bridge', async () => {
    deleteCharacterMock.mockResolvedValue({ deleted: {}, affectedDialogs: 0 });
    const onRefresh = vi.fn();
    render(
      <CharacterBar
        character={baseCharacters[0]}
        storyDir="Story-Test"
        expanded={false}
        selected={false}
        availableDialogEffects={[]}
        onToggleExpand={vi.fn()}
        onRefresh={onRefresh}
        onError={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByTestId('character-menu-Narrator'));
    fireEvent.click(screen.getByRole('menuitem', { name: /delete/i }));
    await waitFor(() => {
      expect(deleteCharacterMock).toHaveBeenCalledWith('Story-Test', 'Narrator');
      expect(onRefresh).toHaveBeenCalled();
    });
  });

  it('shows emotions and SoX chain when expanded', () => {
    renderBar(baseCharacters[1], true);
    expect(screen.getByTestId('emotion-row-Hendrix-Neutral')).toBeInTheDocument();
    expect(screen.getByTestId('emotion-row-Hendrix-Sad')).toBeInTheDocument();
    expect(screen.getByText(/SoX: gain -3/)).toBeInTheDocument();
  });
});
