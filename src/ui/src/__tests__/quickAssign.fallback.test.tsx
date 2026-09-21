import { describe, it, expect, vi } from 'vitest';

// Regression: the quick-assign button must NOT early-return on empty
// multi-selection; handleAssignFromPicker falls back to the last-opened
// dialog. This guards the guard-removal that fixed the silent no-op.

describe('quick-assign fallback flow', () => {
  it('handler does not block when multi-selection is empty (source check)', async () => {
    const fs = await import('fs');
    const path = await import('path');
    const appSrc = fs.readFileSync(
      path.default.resolve(__dirname, '../../src/App.tsx'), 'utf8');
    const idx = appSrc.indexOf('onQuickAssign={(characterName)');
    expect(idx).toBeGreaterThan(-1);
    const block = appSrc.slice(idx, idx + 500);
    // The early-return guard must be gone
    expect(block).not.toContain("selectedDialogKeys.size === 0");
  });

  it('fallback in handleAssignFromPicker uses currentDialogKey', async () => {
    const fs = await import('fs');
    const path = await import('path');
    const appSrc = fs.readFileSync(
      path.default.resolve(__dirname, '../../src/App.tsx'), 'utf8');
    expect(appSrc).toContain("if (!currentDialogKey)");
    expect(appSrc).toContain("setSelectedDialogKeys(new Set([currentDialogKey]))");
    expect(appSrc).toContain("key === currentDialogKey");
  });
});
