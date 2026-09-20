# Edit Text

The **Edit Text** button (top bar) switches the main window to the Markdown
editor for the current chapter. Chapter source lives in
`Story-<name>/story-chapters/<chapter>.md`; the dialog XML is regenerated
from it when you save.

## Workflow

1. Click **Edit Text** to enter the editor. The chapter's Markdown loads in
   a plain-text area.
2. Edit freely. The dialog list is replaced by the editor while active.
3. Click **Save** (or `Ctrl+S`) to write the file. Dialog lines are
   regenerated from the new text.
4. Click the same button again (now **Close Editor**) to return to the
   dialog view.

## Behavior notes

- The editor shows unsaved-change state in the top bar; switching chapters
  with unsaved edits warns first.
- After saving, the chapter's dialog lines refresh so new/removed lines show
  up in the Chapter view.
- Characters and emotions are not assigned here — they live in the
  `story-config.yml` and are attached per line in the Chapter view (see
  *Chapter Dialog*).

## Tips

- Keep one paragraph per dialog line; the XML generator maps them to
  `dlgseq` numbers automatically.
- Narration blocks stay unassigned and render with the Narrator voice.