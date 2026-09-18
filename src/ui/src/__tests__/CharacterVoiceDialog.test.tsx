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
  },
}));

import { PythonBridgeService } from '../services/pythonBridge';

const listCharactersMock = PythonBridgeService.listCharacters as unknown as ReturnType<typeof vi.fn>;
const deleteCharacterMock = PythonBridgeService.deleteCharacter as unknown as ReturnType<typeof vi.fn>;

const makeCharacter = (name: string, overrides: Partial<CharacterConfig> = {}): CharacterConfig => ({
  name,
  'voice-sample': `${name.toLowerCase()}.wav`,
  ...overrides,
});

const baseCharacters: CharacterConfig[] = [
  makeCharacter('Narrator'),
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
    expect(screen.queryByTestId('character-bar-Narrator')).not.toBeInTheDocument();
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
    mockWindowApi();
  });

  function renderBar(character: CharacterConfig, expanded = false) {
    return render(
      <CharacterBar
        character={character}
        storyDir="Story-Test"
        expanded={expanded}
        selected={false}
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
