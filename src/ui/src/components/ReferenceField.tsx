import React, { useCallback, useMemo, useRef, useState } from 'react';

/**
 * Phase 6b.1: ReferenceField - combo box for key values that require data
 * consistency (story-config.yml cross-references).
 *
 * - Dropdown of available choices with type-ahead filtering
 * - Free-text entry allowed; a typed value that matches nothing is flagged
 *   "unsatisfied" and rendered with a red highlight + explanatory tooltip
 * - The highlight clears the moment the reference is satisfied
 * - Keyboard: ArrowUp/Down navigate, Enter commits, Escape cancels edit
 *
 * Stub behavior is delegated to the caller via `onCommitUnsatisfied` (6b.2).
 */

export interface ReferenceFieldProps {
  label: string;
  value: string;
  choices: string[];
  /** Called on commit (Enter or blur) with the final value. */
  onCommit: (value: string) => void;
  /** Optional checker: true when the current value satisfies its reference. */
  isSatisfied?: (value: string, choices: string[]) => boolean;
  /** Tooltip text describing the unmet reference when unsatisfied. */
  unsatisfiedHint?: (value: string) => string;
  allowFreeText?: boolean;
  testId?: string;
  disabled?: boolean;
}

export function isValueSatisfiedDefault(value: string, choices: string[]): boolean {
  if (!value.trim()) return true; // empty is neutral (not red)
  return choices.some((c) => c.toLowerCase() === value.trim().toLowerCase());
}

export const ReferenceField: React.FC<ReferenceFieldProps> = ({
  label, value, choices, onCommit, isSatisfied = isValueSatisfiedDefault,
  allowFreeText = true, testId, disabled = false,
}) => {
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState(value);
  const [highlightIndex, setHighlightIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  const filtered = useMemo(() => {
    if (!open) return choices;
    const q = draft.trim().toLowerCase();
    // If the draft equals the committed value (user hasn't typed), show all
    // choices rather than filtering to the current value's matches
    if (q === value.trim().toLowerCase()) return choices;
    return choices.filter((c) => c.toLowerCase().includes(q));
  }, [choices, draft, open, value]);

  const commitValue = useCallback((next: string) => {
    setDraft(next);
    setOpen(false);
    onCommit(next);
  }, [onCommit]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (open && filtered.length > 0) {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setHighlightIndex((i) => (i + 1) % filtered.length);
        return;
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault();
        setHighlightIndex((i) => (i - 1 + filtered.length) % filtered.length);
        return;
      }
      if (e.key === 'Enter' && open) {
        e.preventDefault();
        commitValue(filtered[highlightIndex] ?? draft);
        return;
      }
    }
    if (e.key === 'Enter') {
      e.preventDefault();
      commitValue(draft);
      return;
    }
    if (e.key === 'Escape') {
      e.preventDefault();
      setDraft(value);
      setOpen(false);
    }
  }, [open, filtered, highlightIndex, draft, commitValue, value]);

  const isUnsatisfied = !isSatisfied(value, choices);

  return (
    <div style={{ position: 'relative' }}>
      <label style={{ display: 'block', color: '#888', fontSize: 11, marginBottom: 2 }}>
        {label}
      </label>
      <div style={{ display: 'flex', gap: 4 }}>
        <input
          ref={inputRef}
          data-testid={testId ? `${testId}-input` : undefined}
          value={draft}
          disabled={disabled}
          onChange={(e) => {
            setDraft(e.target.value);
            setOpen(true);
            setHighlightIndex(0);
          }}
          onFocus={() => setOpen(true)}
          onBlur={() => {
            // Commit on blur only when the value changed
            if (draft !== value) onCommit(draft);
            // Defer close so option clicks register
            setTimeout(() => setOpen(false), 150);
          }}
          onKeyDown={handleKeyDown}
          style={{
            ...inputStyle,
            ...(isUnsatisfied ? unsatisfiedStyle : {}),
          }}
          title={isUnsatisfied ? `Unsatisfied reference: '${value}' does not match any available choice` : undefined}
          aria-invalid={isUnsatisfied}
        />
        <button
          data-testid={testId ? `${testId}-toggle` : undefined}
          style={dropdownButtonStyle}
          onClick={() => setOpen((o) => !o)}
          disabled={disabled}
          tabIndex={-1}
          aria-label={`Toggle ${label} choices`}
        >
          ▾
        </button>
      </div>
      {open && filtered.length > 0 && (
        <div style={dropdownStyle} role="listbox">
          {filtered.map((choice, idx) => (
            <div
              key={choice}
              role="option"
              aria-selected={idx === highlightIndex}
              data-testid={testId ? `${testId}-option-${choice}` : undefined}
              style={{
                ...optionStyle,
                background: idx === highlightIndex ? '#2a3a4a' : 'transparent',
              }}
              onMouseDown={(e) => {
                e.preventDefault(); // keep input focus
                commitValue(choice);
              }}
            >
              {choice}
            </div>
          ))}
        </div>
      )}
      {open && filtered.length === 0 && allowFreeText && draft.trim() && (
        <div style={freeTextHintStyle}>
          New value — will be created as a stub on commit
        </div>
      )}
    </div>
  );
};

const inputStyle: React.CSSProperties = {
  flex: 1,
  background: '#242424',
  color: '#ddd',
  border: '1px solid #444',
  borderRadius: 3,
  padding: '4px 8px',
  fontSize: 13,
  minWidth: 0,
};

const unsatisfiedStyle: React.CSSProperties = {
  border: '1px solid #f66',
  color: '#f66',
  background: 'rgba(255, 102, 102, 0.08)',
};

const dropdownButtonStyle: React.CSSProperties = {
  background: 'transparent',
  border: '1px solid #444',
  color: '#aaa',
  borderRadius: 3,
  cursor: 'pointer',
  fontSize: 10,
  padding: '4px 6px',
};

const dropdownStyle: React.CSSProperties = {
  position: 'absolute',
  left: 0,
  right: 40,
  top: '100%',
  background: '#2a2a2a',
  border: '1px solid #444',
  borderRadius: 4,
  zIndex: 1100,
  maxHeight: 200,
  overflowY: 'auto',
  marginTop: 2,
};

const optionStyle: React.CSSProperties = {
  padding: '5px 10px',
  cursor: 'pointer',
  fontSize: 13,
  color: '#ddd',
};

const freeTextHintStyle: React.CSSProperties = {
  marginTop: 2,
  fontSize: 10,
  color: '#8ab4f8',
};