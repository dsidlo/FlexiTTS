import { describe, it, expect } from 'vitest';
import {
  normalizeDialogText,
  computeDialogHash,
  isDialogContentStale,
  getStoredRenderHash,
  RENDER_HASH_ATTR,
  RENDERED_AT_ATTR,
} from '../utils/dialogHash';
import type { DialogElement } from '../../models/types';

// Golden vectors generated from src/scripts/chapter_render_state.py
// `compute_dialog_hash()` / `normalize_dialog_text()` (with the render-attribute
// exclusion applied). The TS implementation must agree byte-for-byte with Python.
const makeDialog = (
  partial: { text: string; character?: string; dlgseq?: string; attributes?: Record<string, unknown> },
): Parameters<typeof normalizeDialogText>[0] => ({
  text: partial.text,
  character: partial.character ?? '',
  dlgseq: partial.dlgseq,
  attributes: partial.attributes,
});

describe('dialogHash parity with Python normalize_dialog_text', () => {
  const cases: Array<{
    name: string;
    attrs: Record<string, unknown>;
    text: string;
    tag: 'dialog' | 'narration';
    character: string;
    expectedNormalized: string;
    expectedHash: string;
  }> = [
    {
      name: 'simple dialog',
      attrs: { dlgseq: '1', character: 'Alice', emotion: 'happy' },
      text: 'Hello world',
      tag: 'dialog',
      character: 'Alice',
      expectedNormalized:
        'Alice|happy|1|Hello world|character=Alice|dlgseq=1|emotion=happy',
      expectedHash: 'e05f7444d423be078c7c855ae5b1eed8',
    },
    {
      name: 'narration with whitespace collapse + injected Narrator',
      attrs: { dlgseq: '2', emotion: 'atmospheric' },
      text: 'The  night   sky\n  bled into neon',
      tag: 'narration',
      character: 'Narrator',
      expectedNormalized:
        'Narrator|atmospheric|2|The night sky bled into neon|character=Narrator|dlgseq=2|emotion=atmospheric',
      expectedHash: 'dad99d8487ab5fc1f0e553868c13df60',
    },
    {
      name: 'dialog without emotion defaults to neutral',
      attrs: { dlgseq: '003', character: 'Bob' },
      text: 'Multi\nline\ttext  with spaces',
      tag: 'dialog',
      character: 'Bob',
      expectedNormalized: 'Bob|neutral|003|Multi line text with spaces|character=Bob|dlgseq=003',
      expectedHash: 'fdbeeb500b6709b0b89515e8657e5a87',
    },
    {
      name: 'render_hash and rendered_at are excluded from the signature',
      attrs: {
        dlgseq: '1',
        character: 'Alice',
        render_hash: 'abc123',
        rendered_at: '1700000000000',
        emotion: 'sad',
      },
      text: 'Trailing   ',
      tag: 'dialog',
      character: 'Alice',
      expectedNormalized: 'Alice|sad|1|Trailing|character=Alice|dlgseq=1|emotion=sad',
      expectedHash: '54f643bba620a201bb0a0cab672823a3',
    },
    {
      name: 'narration without character or emotion',
      attrs: { dlgseq: '7' },
      text: 'No emotion attr, no character',
      tag: 'narration',
      character: 'Narrator',
      expectedNormalized:
        'Narrator|neutral|7|No emotion attr, no character|character=Narrator|dlgseq=7',
      expectedHash: '868cab3a01dcf43c887cd855bc5af791',
    },
    {
      name: 'narr alias normalizes to Narrator; extra attrs sorted',
      attrs: { dlgseq: '9', character: 'narr', emotion: 'wary', tone: 'flat', pace: 'slow' },
      text: 'Attrs sorted order',
      tag: 'dialog',
      character: 'narr',
      expectedNormalized:
        'Narrator|wary|9|Attrs sorted order|character=narr|dlgseq=9|emotion=wary|pace=slow|tone=flat',
      expectedHash: 'e83beb21a7cb8bced37da7743f61e918',
    },
  ];

  for (const c of cases) {
    it(`normalizes: ${c.name}`, () => {
      expect(normalizeDialogText(makeDialog({ text: c.text, character: c.character, attributes: c.attrs }), c.tag)).toBe(
        c.expectedNormalized
      );
    });
    it(`hashes: ${c.name}`, () => {
      expect(computeDialogHash(makeDialog({ text: c.text, character: c.character, attributes: c.attrs }), c.tag)).toBe(
        c.expectedHash
      );
    });
  }

  it('ignores an injected parser-only section_seq attribute', () => {
    const withoutSection = computeDialogHash(
      makeDialog({ text: 'Hello world', character: 'Alice', attributes: { dlgseq: '1', emotion: 'happy' } }),
      'dialog'
    );
    const withSection = computeDialogHash(
      makeDialog({
        text: 'Hello world',
        character: 'Alice',
        attributes: { dlgseq: '1', emotion: 'happy', section_seq: '1' },
      }),
      'dialog'
    );
    expect(withSection).toBe(withoutSection);
  });
});

describe('isDialogContentStale', () => {
  const base: DialogElement = {
    dlgseq: '1',
    sectionId: '1',
    character: 'Alice',
    text: 'Hello world',
    attributes: { dlgseq: '1', character: 'Alice', emotion: 'happy', section_seq: '1' },
  };

  it('returns false when never rendered (no render_hash)', () => {
    expect(getStoredRenderHash(base)).toBeUndefined();
    expect(isDialogContentStale(base, 'dialog')).toBe(false);
  });

  it('returns false immediately after a render (hash matches)', () => {
    const hash = computeDialogHash(base, 'dialog');
    const rendered: DialogElement = {
      ...base,
      attributes: { ...base.attributes, [RENDER_HASH_ATTR]: hash, [RENDERED_AT_ATTR]: 1700000000000 },
    };
    expect(isDialogContentStale(rendered, 'dialog')).toBe(false);
  });

  it('returns true when the user edits text away from the rendered version', () => {
    const hash = computeDialogHash(base, 'dialog');
    const rendered: DialogElement = {
      ...base,
      attributes: { ...base.attributes, [RENDER_HASH_ATTR]: hash, [RENDERED_AT_ATTR]: 1700000000000 },
    };
    const edited: DialogElement = { ...rendered, text: 'Hello there world' };
    expect(isDialogContentStale(edited, 'dialog')).toBe(true);
  });

  it('returns false again when the edit is undone (back to green)', () => {
    const hash = computeDialogHash(base, 'dialog');
    const rendered: DialogElement = {
      ...base,
      attributes: { ...base.attributes, [RENDER_HASH_ATTR]: hash, [RENDERED_AT_ATTR]: 1700000000000 },
    };
    const edited: DialogElement = { ...rendered, text: 'Oops' };
    expect(isDialogContentStale(edited, 'dialog')).toBe(true);
    const undone: DialogElement = { ...edited, text: 'Hello world' };
    expect(isDialogContentStale(undone, 'dialog')).toBe(false);
  });
});
