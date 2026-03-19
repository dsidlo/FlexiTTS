# Phase 1 Complete: Decoupled chapter_xml_to_audio.py from chapter_render_state.py

## Summary of Changes

### What Was Removed from `chapter_xml_to_audio.py`

1. **Removed imports from `chapter_render_state.py`:**
   - `load_render_state`
   - `save_render_state`
   - `remove_stale_clip_files`
   - `update_render_state_with_new_clips`
   - `check_render_state`
   - `ChapterRenderState`

2. **Removed stale clip cleanup functions:**
   - `move_path_to_trash_or_delete()`
   - `cleanup_stale_chapter_clips()`

3. **Removed render state logic from `main()`:**
   - No longer calls `check_render_state()`
   - No longer calls `remove_stale_clip_files()`
   - No longer calls `update_render_state_with_new_clips()`
   - No longer performs stale dialog detection
   - No longer removes stale clips after full chapter render

### What `chapter_xml_to_audio.py` Still Does

The renderer is now a pure render executor:
1. ✅ Parse requested XML
2. ✅ Apply explicit filters (`--section`, `--dlgseq`, full chapter when requested)
3. ✅ Render clips
4. ✅ Return render results (clip paths / metadata via stdout)

### What `chapter_render_state.py` Still Provides (for UI use)

The state management module remains intact for UI consumption:
- `check_render_state()` - Check if chapter needs rendering
- `load_render_state()` / `save_render_state()` - Persist state
- `detect_stale_dialogs()` - Compute stale dialogs
- `compute_dialog_hash()` - Hash computation for change detection
- `get_render_state_json()` - Entry point for UI

## Phase 2: UI Responsibilities

The UI layer (TypeScript/React) now needs to:

### 1. Compute Stale Dialogs in UI
```typescript
// Before calling renderer, check state:
const renderState = await PythonBridgeService.checkChapterRenderState(chapterName, storyDir);
// renderState.stale_dialogs contains dialogs needing re-render
// renderState.needs_render indicates if any dialogs are stale
```

### 2. Set UI State for Re-render Indication
```typescript
// In TopBar.tsx
const [needsRender, setNeedsRender] = useState(false);
const [staleCount, setStaleCount] = useState(0);

// After checking render state:
setNeedsRender(renderState.needs_render);
setStaleCount(renderState.stale_count);
```

### 3. Pass Stale Info to DialogBar
```typescript
// In DialogBar.tsx - isStaleClip prop already exists
<DialogBar
  isStaleClip={staleDialogs.includes(dialog.dlgseq)}
  // ... other props
/>
```

### 4. Update `.chapter_rendered.json` from UI
After successful render, the UI should:
```typescript
// Call chapter_render_state.py to update state
await PythonBridgeService.updateRenderStateAfterRender(
  chapterName,
  storyDir,
  generatedClips  // Array of {section, dlgseq, clipPath}
);
```

**Note:** The UI currently calls `checkChapterRenderState()` which runs `chapter_render_state.py` as a script. This is the correct pattern - the UI owns the state file.

## Files Modified

- `src/scripts/chapter_xml_to_audio.py` - Decoupled from state management

## Files Unchanged (Still Used by UI)

- `src/scripts/chapter_render_state.py` - State management module
- `src/ui/src/services/pythonBridge.ts` - UI bridge (already uses state module)
- `src/ui/src/components/TopBar.tsx` - Already checks render state
- `src/ui/src/components/DialogBar.tsx` - Already receives `isStaleClip` prop

## Testing

Run the existing tests to ensure the decoupling didn't break anything:
```bash
cd /home/dsidlo/workspace/FlexiTTS
python3 -m pytest src/scripts/tests/test_integration_chapter_xml_to_audio.py -v
```

## Next Steps for Phase 2

1. **UI State Management:** Ensure UI properly computes stale dialogs before rendering
2. **Post-Render State Update:** Add UI-side call to update `.chapter_rendered.json` after successful render
3. **Button Wiring:** Update render buttons to use UI-computed stale state for visual indication
4. **Cleanup Ownership:** Move stale clip file cleanup to UI layer (if needed)
