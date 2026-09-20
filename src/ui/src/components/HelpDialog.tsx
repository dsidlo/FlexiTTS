import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';

/**
 * HelpDialog (Ctrl+?):
 * Independent, non-blocking help window with a subject list on the left and
 * help details on the right. Content lives in src/app-docs/*.md and is read
 * through the app-help-read IPC channel; the subject list is static (order
 * matters) but each entry maps to a doc file, so extending help means
 * dropping a new .md into src/app-docs/ and adding one row here.
 *
 * Search filters subjects by title and matches inside doc content snippets.
 * Markdown is rendered with a tiny built-in renderer (headings, tables,
 * code, bold/italic, lists) — no external dependency.
 */

export interface HelpSubject {
  /** Doc file name inside src/app-docs/. */
  doc: string;
  /** Title shown in the subject list. */
  title: string;
  /** One-line summary shown under the title. */
  summary: string;
}

export const HELP_SUBJECTS: HelpSubject[] = [
  { doc: 'index.md', title: 'Overview', summary: 'Getting around FlexiTTS' },
  { doc: 'quick-keys.md', title: 'Quick Keys', summary: 'Shortcuts and customization' },
  { doc: 'edit-text.md', title: 'Edit Text', summary: 'Markdown chapter editor' },
  { doc: 'chapter-dialog.md', title: 'Chapter Dialog', summary: 'Dialog lines, selection, rendering' },
  { doc: 'characters-dialog.md', title: 'Characters Dialog', summary: 'Voices, emotions, effects' },
];

export interface HelpDialogProps {
  open: boolean;
  onClose: () => void;
  /** Custom shortcut map from the global config (action id -> key label). */
  shortcutOverrides?: Record<string, string>;
  /** Optional initial subject to open (by doc file name). */
  initialSubject?: string;
  /**
   * 'overlay' renders the in-app modal (default).
   * 'panel' renders an inline pane suitable for docking beside the app
   * content (no fixed positioning, no focus trap, no overlay click-close).
   */
  mode?: 'overlay' | 'panel';
}

/** Render a minimal, safe subset of Markdown: headings, tables, code spans,
 * fenced code, bold, italics, lists, paragraphs. No HTML passthrough. */
export const renderMarkdownToElements = (md: string): React.ReactNode[] => {
  const lines = md.split('\n');
  const nodes: React.ReactNode[] = [];
  let i = 0;
  let key = 0;

  const inline = (text: string): React.ReactNode => {
    // Split on `code`, **bold**, *italic* in one pass.
    const parts: React.ReactNode[] = [];
    const regex = /`([^`]+)`|\*\*([^*]+)\*\*|\*([^*]+)\*/g;
    let last = 0;
    let m: RegExpExecArray | null;
    while ((m = regex.exec(text)) !== null) {
      if (m.index > last) parts.push(text.slice(last, m.index));
      if (m[1] !== undefined) parts.push(<code key={`${key}-c-${m.index}`} style={{ background: '#f0f0f0', padding: '1px 5px', borderRadius: 3, fontFamily: 'monospace', fontSize: '0.92em' }}>{m[1]}</code>);
      else if (m[2] !== undefined) parts.push(<strong key={`${key}-b-${m.index}`}>{m[2]}</strong>);
      else if (m[3] !== undefined) parts.push(<em key={`${key}-i-${m.index}`}>{m[3]}</em>);
      last = m.index + m[0].length;
    }
    if (last < text.length) parts.push(text.slice(last));
    return <>{parts}</>;
  };

  while (i < lines.length) {
    const line = lines[i];
    if (line.startsWith('# ')) {
      nodes.push(<h2 key={key++} style={{ margin: '4px 0 10px', fontSize: 19 }}>{inline(line.slice(2))}</h2>);
      i++;
    } else if (line.startsWith('## ')) {
      nodes.push(<h3 key={key++} style={{ margin: '16px 0 6px', fontSize: 15, color: '#333' }}>{inline(line.slice(3))}</h3>);
      i++;
    } else if (line.startsWith('```')) {
      const buf: string[] = [];
      i++;
      while (i < lines.length && !lines[i].startsWith('```')) { buf.push(lines[i]); i++; }
      i++; // closing fence
      nodes.push(
        <pre key={key++} style={{ background: '#2d2d2d', color: '#d4d4d4', padding: 10, borderRadius: 6, overflowX: 'auto', fontSize: 12.5 }}>
          <code>{buf.join('\n')}</code>
        </pre>,
      );
    } else if (line.startsWith('|')) {
      // Markdown table: header row, separator, body rows
      const rows: string[][] = [];
      while (i < lines.length && lines[i].startsWith('|')) {
        const cells = lines[i].split('|').slice(1, -1).map((c) => c.trim());
        if (!cells.every((c) => /^-{2,}$/.test(c) || c === '')) rows.push(cells);
        i++;
      }
      if (rows.length > 0) {
        const [head, ...body] = rows;
        nodes.push(
          <table key={key++} style={{ borderCollapse: 'collapse', margin: '8px 0', width: '100%' }}>
            <thead>
              <tr>{head.map((c, ci) => <th key={ci} style={{ textAlign: 'left', borderBottom: '2px solid #999', padding: '5px 10px', fontSize: 13 }}>{inline(c)}</th>)}</tr>
            </thead>
            <tbody>
              {body.map((r, ri) => (
                <tr key={ri} style={{ background: ri % 2 === 1 ? '#fafafa' : 'transparent' }}>
                  {r.map((c, ci) => <td key={ci} style={{ borderBottom: '1px solid #e2e2e2', padding: '5px 10px', fontSize: 13 }}>{inline(c)}</td>)}
                </tr>
              ))}
            </tbody>
          </table>,
        );
      }
    } else if (/^[-*] /.test(line) || /^\d+\. /.test(line)) {
      const items: string[] = [];
      const ordered = /^\d+\. /.test(line);
      while (i < lines.length && (/^[-*] /.test(lines[i]) || /^\d+\. /.test(lines[i]))) {
        items.push(lines[i].replace(/^([-*]|\d+\.) /, ''));
        i++;
      }
      const ListTag = ordered ? 'ol' : 'ul';
      nodes.push(
        <ListTag key={key++} style={{ margin: '6px 0', paddingLeft: 22 }}>
          {items.map((it, ii) => <li key={ii} style={{ marginBottom: 4, fontSize: 13.5 }}>{inline(it)}</li>)}
        </ListTag>,
      );
    } else if (line.trim() === '') {
      i++;
    } else {
      // Paragraph: gather consecutive plain lines
      const buf: string[] = [line];
      i++;
      while (i < lines.length && lines[i].trim() !== '' && !/^(#|```|\||[-*] |\d+\. )/.test(lines[i])) {
        buf.push(lines[i]);
        i++;
      }
      nodes.push(<p key={key++} style={{ margin: '6px 0', fontSize: 13.5, lineHeight: 1.55 }}>{inline(buf.join(' '))}</p>);
    }
  }
  return nodes;
};

/** First ~2 lines of non-heading text, used for search snippets. */
export const docSnippet = (md: string): string =>
  md.split('\n').filter((l) => l.trim() !== '' && !l.startsWith('#')).slice(0, 2).join(' ').slice(0, 140);

export const HelpDialog: React.FC<{
  open: boolean;
  onClose: () => void;
  shortcutOverrides?: Record<string, string>;
  initialSubject?: string;
  mode?: 'overlay' | 'panel';
}> = ({ open, onClose, shortcutOverrides, initialSubject, mode = 'overlay' }) => {
  const [activeDoc, setActiveDoc] = useState<string>(initialSubject ?? 'index.md');
  const [contents, setContents] = useState<Record<string, string>>({});
  const [query, setQuery] = useState('');
  const [error, setError] = useState<string | null>(null);
  const searchRef = useRef<HTMLInputElement>(null);

  // Reset transient state when (re)opened
  useEffect(() => {
    if (open) {
      setQuery('');
      setError(null);
      setActiveDoc(initialSubject ?? 'index.md');
      window.setTimeout(() => searchRef.current?.focus(), 0);
    }
  }, [open, initialSubject]);

  // Load all subjects once when opened (docs are small; cache in state)
  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    (async () => {
      if (typeof window === 'undefined' || !window.api?.readHelpDoc) {
        if (!cancelled) setError('Help is only available inside the FlexiTTS desktop app.');
        return;
      }
      try {
        const loaded: Record<string, string> = {};
        for (const s of HELP_SUBJECTS) {
          loaded[s.doc] = await window.api.readHelpDoc(s.doc);
        }
        if (!cancelled) setContents(loaded);
      } catch (e) {
        if (!cancelled) setError((e as Error).message);
      }
    })();
    return () => { cancelled = true; };
  }, [open]);

  // Esc closes (topmost dialog convention)
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.stopPropagation();
        onClose();
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [open, onClose]);

  // Focus trap (overlay mode only; a docked pane shares the app's tab order)
  useEffect(() => {
    if (!open || mode !== 'overlay') return;
    const handler = (e: KeyboardEvent) => {
      if (e.key !== 'Tab') return;
      const dialog = document.getElementById('help-dialog');
      if (!dialog) return;
      const focusables = dialog.querySelectorAll<HTMLElement>(
        'button:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex="-1"])',
      );
      if (focusables.length === 0) return;
      const first = focusables[0];
      const last = focusables[focusables.length - 1];
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [open, mode]);

  // Apply configured shortcut overrides to the displayed key tables
  const applyShortcuts = useCallback((md: string): string => {
    if (!shortcutOverrides) return md;
    let out = md;
    const mapping: Array<[string, RegExp]> = [
      ['open-help', /Ctrl\+\?/g],
      ['quick-assign', /Ctrl\+Shift\+A/g],
      ['save-chapter', /Ctrl\+S/g],
    ];
    for (const [action, re] of mapping) {
      const custom = shortcutOverrides[action];
      if (custom) out = out.replace(re, custom);
    }
    return out;
  }, [shortcutOverrides]);

  const filteredSubjects = useMemoSafe(() => {
    const q = query.trim().toLowerCase();
    if (!q) return HELP_SUBJECTS;
    return HELP_SUBJECTS.filter((s) => {
      const body = contents[s.doc] ?? '';
      return s.title.toLowerCase().includes(q) || s.summary.toLowerCase().includes(q) || body.toLowerCase().includes(q);
    });
  }, [query, contents]);

  const activeContent = contents[activeDoc];

  if (!open) return null;

  const isOverlay = mode === 'overlay';

  if (!isOverlay) {
    // Docked pane: fills its parent (parent controls size via flexbox)
    return (
      <div
        id="help-dialog"
        role="complementary"
        aria-label="FlexiTTS Help"
        data-testid="help-dialog"
        style={{
          display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0,
          background: '#fff', color: '#222', borderLeft: '1px solid #aaa', overflow: 'hidden',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '10px 14px', borderBottom: '1px solid #ddd', background: '#f7f7f7' }}>
          <span style={{ fontSize: 15, fontWeight: 700 }}>❓ Help</span>
          <input
            type="text"
            value={query}
            placeholder="Search help…"
            aria-label="Search help topics"
            data-testid="help-search"
            onChange={(e) => setQuery(e.target.value)}
            style={{ flex: 1, maxWidth: 260, padding: '4px 9px', borderRadius: 5, border: '1px solid #bbb', fontSize: 12.5 }}
          />
          <div style={{ flex: 1 }} />
          <button
            type="button"
            aria-label="Close help pane"
            data-testid="help-close"
            onClick={onClose}
            style={{ background: 'transparent', border: 'none', fontSize: 18, cursor: 'pointer', lineHeight: 1 }}
          >
            ✕
          </button>
        </div>
        <div style={{ display: 'flex', flex: 1, minHeight: 0 }}>
          <nav
            aria-label="Help subjects"
            data-testid="help-subjects"
            style={{ width: 190, borderRight: '1px solid #e2e2e2', overflowY: 'auto', background: '#fcfcfc', padding: '8px 6px' }}
          >
            {filteredSubjects.map((s) => (
              <button
                key={s.doc}
                type="button"
                data-testid={`help-subject-${s.doc.replace('.md', '')}`}
                onClick={() => setActiveDoc(s.doc)}
                style={{
                  display: 'block', width: '100%', textAlign: 'left', padding: '7px 10px', marginBottom: 4,
                  borderRadius: 6, border: 'none', cursor: 'pointer', background: activeDoc === s.doc ? '#e3ecff' : 'transparent',
                  fontWeight: activeDoc === s.doc ? 700 : 500,
                }}
              >
                <div style={{ fontSize: 13 }}>{s.title}</div>
                <div style={{ fontSize: 11, color: '#777' }}>{s.summary}</div>
              </button>
            ))}
          </nav>
          <section
            aria-label="Help details"
            data-testid="help-details"
            style={{ flex: 1, overflowY: 'auto', padding: '12px 18px', minWidth: 0 }}
          >
            {error && <div data-testid="help-error" style={{ color: '#b71c1c', padding: 12 }}>{error}</div>}
            {!error && !activeContent && <div style={{ color: '#888', padding: 12 }}>Loading…</div>}
            {!error && activeContent && (
              <div data-testid={`help-content-${activeDoc.replace('.md', '')}`}>
                {renderMarkdownToElements(applyShortcuts(activeContent))}
              </div>
            )}
          </section>
        </div>
      </div>
    );
  }

  return (
    <div
      role="presentation"
      data-testid="help-overlay"
      onClick={onClose}
      style={{
        position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)',
        zIndex: 4000, display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}
    >
      <div
        id="help-dialog"
        role="dialog"
        aria-modal="true"
        aria-label="FlexiTTS Help"
        data-testid="help-dialog"
        onClick={(e) => e.stopPropagation()}
        style={{
          background: '#fff', color: '#222', borderRadius: 10, width: 860, maxWidth: '92vw',
          height: 620, maxHeight: '88vh', display: 'flex', flexDirection: 'column',
          boxShadow: '0 10px 40px rgba(0,0,0,0.4)', border: '1px solid #aaa', overflow: 'hidden',
        }}
      >
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '10px 14px', borderBottom: '1px solid #ddd', background: '#f7f7f7' }}>
          <span style={{ fontSize: 17, fontWeight: 700 }}>❓ FlexiTTS Help</span>
          <input
            ref={searchRef}
            type="text"
            value={query}
            placeholder="Search help…"
            aria-label="Search help topics"
            data-testid="help-search"
            onChange={(e) => setQuery(e.target.value)}
            style={{ flex: 1, maxWidth: 320, padding: '5px 10px', borderRadius: 5, border: '1px solid #bbb', fontSize: 13 }}
          />
          <div style={{ flex: 1 }} />
          <button
            type="button"
            aria-label="Close help"
            data-testid="help-close"
            onClick={onClose}
            style={{ background: 'transparent', border: 'none', fontSize: 20, cursor: 'pointer', lineHeight: 1 }}
          >
            ✕
          </button>
        </div>

        {/* Body: subjects | details */}
        <div style={{ display: 'flex', flex: 1, minHeight: 0 }}>
          <nav
            aria-label="Help subjects"
            data-testid="help-subjects"
            style={{ width: 220, borderRight: '1px solid #e2e2e2', overflowY: 'auto', background: '#fcfcfc', padding: '8px 6px' }}
          >
            {filteredSubjects.length === 0 && (
              <div style={{ padding: 10, color: '#888', fontStyle: 'italic', fontSize: 13 }}>No matching topics.</div>
            )}
            {filteredSubjects.map((s) => (
              <button
                key={s.doc}
                type="button"
                data-testid={`help-subject-${s.doc.replace('.md', '')}`}
                onClick={() => setActiveDoc(s.doc)}
                style={{
                  display: 'block', width: '100%', textAlign: 'left', padding: '8px 10px', marginBottom: 4,
                  borderRadius: 6, border: 'none', cursor: 'pointer', background: activeDoc === s.doc ? '#e3ecff' : 'transparent',
                  fontWeight: activeDoc === s.doc ? 700 : 500,
                }}
                onMouseEnter={(e) => { if (activeDoc !== s.doc) e.currentTarget.style.background = '#f0f0f0'; }}
                onMouseLeave={(e) => { if (activeDoc !== s.doc) e.currentTarget.style.background = 'transparent'; }}
              >
                <div style={{ fontSize: 13.5 }}>{s.title}</div>
                <div style={{ fontSize: 11.5, color: '#777' }}>{s.summary}</div>
              </button>
            ))}
          </nav>

          <section
            aria-label="Help details"
            data-testid="help-details"
            style={{ flex: 1, overflowY: 'auto', padding: '14px 22px', minWidth: 0 }}
          >
            {error && <div data-testid="help-error" style={{ color: '#b71c1c', padding: 12 }}>{error}</div>}
            {!error && !activeContent && <div style={{ color: '#888', padding: 12 }}>Loading…</div>}
            {!error && activeContent && (
              <div data-testid={`help-content-${activeDoc.replace('.md', '')}`}>
                {renderMarkdownToElements(applyShortcuts(activeContent))}
              </div>
            )}
          </section>
        </div>

        {/* Footer */}
        <div style={{ padding: '8px 14px', borderTop: '1px solid #e5e5e5', display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: '#f7f7f7' }}>
          <span style={{ fontSize: 12, color: '#777' }}>Docs: src/app-docs/ · Customize keys in ~/.config/FlexiTTS/FlexiTTS.yml</span>
          <span style={{ fontSize: 12, color: '#777' }}>Esc to close</span>
        </div>
      </div>
    </div>
  );
};

/** useMemo wrapper that tolerates undefined deps (tiny local helper). */
function useMemoSafe<T>(factory: () => T, deps: unknown[]): T {
  // eslint-disable-next-line react-hooks/rules-of-hooks
  return useMemo(factory, deps);
}
