import { md5 } from './md5';
import type { DialogElement } from '../models/types';

/** Attribute name carrying the stored render signature in the XML / model. */
export const RENDER_HASH_ATTR = 'render_hash';
/** Attribute name carrying the last-rendered timestamp (ms since epoch). */
export const RENDERED_AT_ATTR = 'rendered_at';

/**
 * Attributes that must never participate in the content signature.
 *
 * These are bookkeeping written *back* after a render; if they were included,
 * writing them would change the very hash they record (self-invalidation), and
 * they are not part of what the user is editing.
 */
const NON_CONTENT_ATTRS = new Set<string>([
  RENDER_HASH_ATTR,
  RENDERED_AT_ATTR,
  // Injected during XML parsing (see useChapter.parseChapterXML) and not present
  // in the source <dialog>/<narration> attributes that Python hashes.
  'section_seq',
]);

/**
 * Normalize a dialog exactly like Python's `normalize_dialog_text()`
 * (src/scripts/chapter_render_state.py) so the TS and Python hashes agree
 * byte-for-byte.
 *
 * Canonical string: `${speaker}|${emotion}|${dlgseq}|${text}|${attr_str}`
 * where attr_str is `k=v` pairs sorted by key, joined with `|`, skipping falsy
 * values and the non-content attributes above.
 */
export const normalizeDialogText = (
  dialog: Pick<DialogElement, 'text' | 'character'> & {
    attributes?: Record<string, unknown>;
    dlgseq?: string;
  },
  tag: 'dialog' | 'narration' = 'dialog'
): string => {
  const srcAttrs: Record<string, unknown> = { ...(dialog.attributes || {}) };

  // Speaker resolution mirrors the Python XML-element path: take the explicit
  // character attribute if present, else fall back from tag name, then normalize
  // narrator aliases to "Narrator". The DialogElement always carries a resolved
  // `character`, which takes precedence over the attributes bag.
  const rawSpeaker = (
    dialog.character ||
    (typeof srcAttrs.character === 'string' ? (srcAttrs.character as string) : undefined) ||
    (typeof srcAttrs.speaker === 'string' ? (srcAttrs.speaker as string) : undefined) ||
    (tag === 'narration' ? 'narrator' : 'unknown')
  );
  const speaker = ['narrator', 'narr'].includes(String(rawSpeaker).toLowerCase())
    ? 'Narrator'
    : String(rawSpeaker);

  const emotion =
    typeof srcAttrs.emotion === 'string' && srcAttrs.emotion
      ? srcAttrs.emotion
      : 'neutral';

  const dlgseq =
    (typeof srcAttrs.dlgseq === 'string' || typeof srcAttrs.dlgseq === 'number'
      ? String(srcAttrs.dlgseq)
      : undefined) ||
    (typeof srcAttrs.id === 'string' || typeof srcAttrs.id === 'number'
      ? String(srcAttrs.id)
      : undefined) ||
    dialog.dlgseq ||
    '000';

  // Python: ensure a consistent attrs dict by injecting the *normalized*
  // character/speaker when the source XML had no character attribute. (When the
  // XML did have one we leave the raw value untouched to match Python.)
  const attrs: Record<string, unknown> = { ...srcAttrs };
  if (attrs.character === undefined || attrs.character === null) {
    attrs.character = speaker;
  }

  // Whitespace normalization identical to Python:
  //   text.replace("\r", " ").replace("\n", " "); then " ".join(text.split())
  // Python's str.split() with no args splits on any run of whitespace (spaces,
  // tabs, newlines, unicode whitespace) and drops empties.
  const text = String(dialog.text ?? '')
    .replace(/\r/g, ' ')
    .replace(/\n/g, ' ');
  const normalizedText = text.split(/\s+/).filter(Boolean).join(' ');

  const keys = Object.keys(attrs)
    .filter((k) => !NON_CONTENT_ATTRS.has(k))
    .filter((k) => {
      const v = attrs[k];
      return v !== undefined && v !== null && v !== '' && v !== false;
    })
    .sort();

  const attrStr = keys.map((k) => `${k}=${attrs[k]}`).join('|');

  return `${speaker}|${emotion}|${dlgseq}|${normalizedText}|${attrStr}`;
};

/**
 * Compute the MD5 content signature of a dialog, matching Python's
 * `compute_dialog_hash()`.
 */
export const computeDialogHash = (
  dialog: Parameters<typeof normalizeDialogText>[0],
  tag: 'dialog' | 'narration' = 'dialog'
): string => md5(normalizeDialogText(dialog, tag));

/**
 * Return the stored render hash recorded on the dialog, if any.
 */
export const getStoredRenderHash = (
  dialog: Pick<DialogElement, 'attributes'>
): string | undefined => {
  const value = dialog.attributes?.[RENDER_HASH_ATTR];
  return typeof value === 'string' && value ? value : undefined;
};

/**
 * True when a clip has been rendered for this dialog (a render_hash exists) but
 * the current text/attributes no longer match it. False when never rendered
 * (no hash stored -> button shows "no clip" grey) or when in sync.
 */
export const isDialogContentStale = (
  dialog: Parameters<typeof computeDialogHash>[0] & Pick<DialogElement, 'attributes'>,
  tag: 'dialog' | 'narration' = 'dialog'
): boolean => {
  const stored = getStoredRenderHash(dialog);
  if (!stored) return false; // Never rendered -> not "stale", just absent.
  return computeDialogHash(dialog, tag) !== stored;
};
