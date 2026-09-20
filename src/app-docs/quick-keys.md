# Quick Keys

All keyboard shortcuts in FlexiTTS. Defaults are listed below; each one can
be overridden in `~/.config/FlexiTTS/FlexiTTS.yml` under `FlexiTTS.shortcuts`
(see *Customizing* at the bottom).

## Global

| Key | Action |
| --- | --- |
| `Ctrl+?` (Ctrl+Shift+/) | Open or close this help dialog |
| `Ctrl+Shift+A` | Assign a character to the selected dialog lines |
| `Esc` | Close the topmost dialog or deselect |

## Dialog lines (Chapter view)

| Key | Action |
| --- | --- |
| `Ctrl+Click` header | Add/remove a dialog line to the multi-selection |
| `Click` header | Expand or collapse the line |
| Right-click header | Edit attributes / assign character |

## Characters dialog

| Key | Action |
| --- | --- |
| `Ctrl+Z` | Undo last character-config edit |
| `Ctrl+Shift+Z` | Redo |
| `Esc` | Close the dialog |

## Editor (Edit Text)

| Key | Action |
| --- | --- |
| `Ctrl+S` | Save the Markdown chapter text |
| `Esc` | Leave the editor (when not typing) |

## Customizing

Open `~/.config/FlexiTTS/FlexiTTS.yml` and add a `shortcuts` map. Keys are
action ids, values are key descriptions like `Ctrl+Shift+A`.

```yaml
FlexiTTS:
  stories-dir: "/path/to/Stories"
  shortcuts:
    open-help: "Ctrl+?"
    quick-assign: "Ctrl+Shift+A"
    save-chapter: "Ctrl+S"
```

Supported modifiers: `Ctrl`, `Shift`, `Alt`. After saving the file, restart
FlexiTTS to apply the new bindings.