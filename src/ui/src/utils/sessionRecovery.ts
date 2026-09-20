import { debugLog } from '../utils/debugLogger';

/**
 * Phase 12.2: Session recovery checkpoint.
 *
 * While the user edits, a debounced checkpoint of unsaved content is stored
 * in sessionStorage (survives Electron renderer crashes/reloads, not full
 * app restarts of the OS — that is the plan's scope). On startup the app
 * checks for a checkpoint that does not match the on-disk content and offers
 * restore or discard.
 */

const KEY_PREFIX = 'flexitts-recovery';

const key = (storyDir: string): string => `${KEY_PREFIX}:${storyDir}`;

export interface RecoveryCheckpoint {
  /** Story directory name (e.g. Story-Entanglement). */
  storyDir: string;
  /** Chapter file path as loaded (may be Story-relative). */
  chapterFile: string;
  /** Chapter stem (file name without extension). */
  stem: string;
  /** Unsaved markdown content (editor), if any. */
  markdown: string | null;
  /** Unsaved chapter XML, if any. */
  xml: string | null;
  /** ISO timestamp of when the checkpoint was written. */
  savedAt: string;
}

export const saveRecoveryCheckpoint = (checkpoint: RecoveryCheckpoint): void => {
  try {
    sessionStorage.setItem(key(checkpoint.storyDir), JSON.stringify(checkpoint));
    debugLog.info('recovery:save', 'Checkpoint stored', { stem: checkpoint.stem, storyDir: checkpoint.storyDir });
  } catch {
    // sessionStorage may be unavailable in tests; checkpointing is best-effort
  }
};

export const loadRecoveryCheckpoint = (storyDir: string): RecoveryCheckpoint | null => {
  try {
    const raw = sessionStorage.getItem(key(storyDir));
    if (!raw) return null;
    const parsed = JSON.parse(raw) as RecoveryCheckpoint;
    if (!parsed || typeof parsed !== 'object' || !parsed.stem) return null;
    return parsed;
  } catch {
    return null;
  }
};

export const clearRecoveryCheckpoint = (storyDir: string): void => {
  try {
    sessionStorage.removeItem(key(storyDir));
  } catch {
    // ignore
  }
};

export const hasRecoveryData = (checkpoint: RecoveryCheckpoint | null): boolean =>
  !!checkpoint && (checkpoint.markdown !== null || checkpoint.xml !== null);