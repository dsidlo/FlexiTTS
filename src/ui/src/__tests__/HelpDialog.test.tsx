import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { HelpDialog, HELP_SUBJECTS, renderMarkdownToElements, docSnippet } from '../components/HelpDialog';

const docsByFile: Record<string, string> = {
  'index.md': '# FlexiTTS Help\n\nWelcome to FlexiTTS.\n\n## Sections\n\n- **Quick Keys** — shortcuts.',
  'quick-keys.md': '# Quick Keys\n\n| Key | Action |\n| --- | --- |\n| `Ctrl+?` | Open help |\n| `Ctrl+Shift+A` | Assign character |',
  'edit-text.md': '# Edit Text\n\nThe **Edit Text** button opens the Markdown editor.',
  'chapter-dialog.md': '# Chapter Dialog\n\n`Ctrl+Click` toggles selection.',
  'characters-dialog.md': '# Characters Dialog\n\nAuto-save with rollback.',
};

describe('HelpDialog (Ctrl+?)', () => {
  beforeEach(() => {
    (window as unknown as { api: { readHelpDoc: (doc: string) => Promise<string> } }).api = {
      readHelpDoc: vi.fn((doc: string) => Promise.resolve(docsByFile[doc] ?? '')),
    };
    window.sessionStorage.clear();
  });

  it('renders nothing when closed', () => {
    const { container } = render(<HelpDialog open={false} onClose={vi.fn()} />);
    expect(container.querySelector('[data-testid="help-dialog"]')).toBeNull();
  });

  it('lists all subjects on the left and loads content for the active subject', async () => {
    render(<HelpDialog open onClose={vi.fn()} />);
    expect(screen.getByTestId('help-subjects')).toBeInTheDocument();
    for (const s of HELP_SUBJECTS) {
      expect(screen.getByTestId(`help-subject-${s.doc.replace('.md', '')}`)).toBeInTheDocument();
    }
    await waitFor(() => {
      expect(screen.getByTestId('help-content-index')).toBeInTheDocument();
    });
    expect(screen.getByTestId('help-content-index')).toHaveTextContent('Welcome to FlexiTTS.');
  });

  it('switches subjects on click', async () => {
    render(<HelpDialog open onClose={vi.fn()} />);
    await waitFor(() => expect(screen.getByTestId('help-content-index')).toBeInTheDocument());
    fireEvent.click(screen.getByTestId('help-subject-quick-keys'));
    await waitFor(() => {
      expect(screen.getByTestId('help-content-quick-keys')).toBeInTheDocument();
    });
    expect(screen.getByTestId('help-details')).toHaveTextContent('Assign character');
  });

  it('search filters subjects by title and content', async () => {
    render(<HelpDialog open onClose={vi.fn()} />);
    await waitFor(() => expect(screen.getByTestId('help-content-index')).toBeInTheDocument());
    fireEvent.change(screen.getByTestId('help-search'), { target: { value: 'markdown editor' } });
    expect(screen.getByTestId('help-subject-edit-text')).toBeInTheDocument();
    expect(screen.queryByTestId('help-subject-quick-keys')).toBeNull();
    fireEvent.change(screen.getByTestId('help-search'), { target: { value: 'zzz-no-match' } });
    expect(screen.getByText('No matching topics.')).toBeInTheDocument();
  });

  it('closes via ✕, Esc, and overlay click', async () => {
    const onClose = vi.fn();
    render(<HelpDialog open onClose={onClose} />);
    await waitFor(() => expect(screen.getByTestId('help-content-index')).toBeInTheDocument());
    fireEvent.click(screen.getByTestId('help-close'));
    expect(onClose).toHaveBeenCalledTimes(1);
    fireEvent.keyDown(window, { key: 'Escape' });
    expect(onClose).toHaveBeenCalledTimes(2);
    fireEvent.click(screen.getByTestId('help-overlay'));
    expect(onClose).toHaveBeenCalledTimes(3);
  });

  it('shows an error when readHelpDoc is unavailable', async () => {
    (window as unknown as { api: unknown }).api = undefined;
    render(<HelpDialog open onClose={vi.fn()} />);
    await waitFor(() => {
      expect(screen.getByTestId('help-error')).toBeInTheDocument();
    });
    expect(screen.getByTestId('help-error')).toHaveTextContent('desktop app');
  });

  it('applies configured shortcut overrides to doc content', async () => {
    render(<HelpDialog open onClose={vi.fn()} shortcutOverrides={{ 'quick-assign': 'Ctrl+Alt+R' }} />);
    fireEvent.click(screen.getByTestId('help-subject-quick-keys'));
    await waitFor(() => {
      expect(screen.getByTestId('help-content-quick-keys')).toBeInTheDocument();
    });
    // The override label replaces the default in displayed tables
    const content = screen.getByTestId('help-content-quick-keys');
    expect(content).toHaveTextContent('Ctrl+Alt+R');
    expect(content.textContent).not.toContain('Ctrl+Shift+A');
  });
});

describe('renderMarkdownToElements', () => {
  it('renders headings, code spans, and emphasis', () => {
    const nodes = renderMarkdownToElements('# Title\n\nSome **bold** and `code` text.');
    expect(nodes.length).toBeGreaterThan(0);
  });

  it('renders tables into rows', () => {
    const md = '| Key | Action |\n| --- | --- |\n| `X` | Do it |';
    render(<div>{renderMarkdownToElements(md)}</div>);
    expect(screen.getByText('Do it')).toBeInTheDocument();
  });

  it('renders fenced code blocks as pre/code', () => {
    const md = '```yaml\nkey: value\n```';
    render(<div>{renderMarkdownToElements(md)}</div>);
    expect(screen.getByText('key: value')).toBeInTheDocument();
  });
});

describe('docSnippet', () => {
  it('returns first non-heading lines', () => {
    expect(docSnippet('# H\n\nFirst line.\nSecond.')).toBe('First line. Second.');
  });
});