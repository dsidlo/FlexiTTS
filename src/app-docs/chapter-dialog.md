# Chapter Dialog

The main window shows every dialog line of the chapter as a **DialogBar**.

## Line anatomy

- **Header** (colored by character): `#<line number>`, render button, and
  the character name. Click to expand/collapse.
- **Expanded view**: the line text (editable inline) and attributes such as
  `emotion`.

## Selecting and assigning

- `Click` a header to expand/collapse it.
- `Ctrl+Click` (or `Cmd+Click`) toggles the line in the multi-selection.
- Right-click a header for the context menu: edit attributes or
  **Assign Character…**.
- With lines selected, press `Ctrl+Shift+A` to open the character picker.
  Picking a character re-assigns every selected line in one pass, validates,
  and auto-saves the chapter XML.

## Rendering audio

- The ▶ button on a header renders that single line through the TTS service
  (start-on-click, click again to cancel).
- Button colors: gray = not rendered, yellow = rendered but stale (text or
  voice config changed), green = rendered and in sync, blue = timestamp
  needs refresh.

## Attributes

Right-click a header → **Edit Attributes** lists every XML attribute of the
line. Click one to edit inline, or **+ Add Attribute** to append a new one.
`render_hash` / `rendered_at` bookkeeping attributes are hidden.