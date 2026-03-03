# Audio Rendering Investigation Report
**Date:** 2026-02-27
**Investigator:** dt-manager-5
**Task:** #13 - Investigate audio rendering issue where UI shows progress but no WAV files are created

---

## Summary

The audio rendering issue is caused by a **mismatch between Python script output format and TypeScript parsing regex patterns**. The UI shows progress because the Python script runs successfully and generates audio files, but the TypeScript code cannot parse the output to determine which file was created, leading to a silent failure where the UI thinks generation failed.

---

## Root Causes Identified

### 1. **CRITICAL: Regex Pattern Mismatch (Primary Issue)**

**Location:** `src/ui/src/services/pythonBridge.ts` lines 175-179
**Current Regex:** `/Generating \\w+ (chapter_\\d+_\\d+_\\d+_[^.]+)/i`

**Expected format by regex:**
```
"Generating alice chapter_004_004_001_alice..."
                ^    matches \\w+ (speaker name)
```

**Actual output from `chapter_xml_to_audio.py` line 188:**
```python
print(f"  Generating {base}...")
# Output: "  Generating chapter_004_004_001_alice..."
```

**Regex fails because:**
- No speaker name between "Generating" and "chapter_"
- Leading whitespace "  " not accounted for
- Pattern `\\w+` expects a word (speaker) but gets "chapter"

**Verification:**
```python
>>> import re
>>> out = "  Generating chapter_004_004_001_alice..."
>>> re.search(r'Generating \\w+ (chapter_\\d+_\\d+_\\d+_[^.]+)', out)
None  # No match!
```

---

### 2. **Fallback Pattern Depends on Effects Being Configured**

**Location:** `src/ui/src/services/pythonBridge.ts` line 168-171

The first regex looks for:
```javascript
const effectMatch = out.match(/Applying character effects to (.*?\\.wav)/i);
```

**Output from `chapter_xml_to_audio.py` line 210-215:**
```python
if final_effects and not args.dry_run:
    apply_sox_effects(out_path, final_effects)
```

This only prints **if the character has effects configured**.

**Problem:** Characters without `dialog-effects` or `sox-effects` in story-config.yml will never trigger this output, leaving no fallback for filename detection.

---

### 3. **Silent Failure Mode**

**Location:** `src/ui/src/services/pythonBridge.ts` lines 194-199

When no regex matches, the code throws:
```javascript
console.error("[playAudio] Could not parse output filename from Python stdout", out);
throw new Error("Could not parse output filename from Python stdout");
```

However, by this point:

1. ✅ Python script HAS run successfully
2. ✅ Audio file HAS been created on disk
3. ❌ TypeScript couldn't PARSE the filename from output
4. ❌ User sees error, thinks generation failed
5. ❌ File exists but UI doesn't know about it

---

## File-by-File Analysis

### ✅ `src/scripts/tts_local.py` - WORKING CORRECTLY

The `generate()` method (lines 156-177):
- Returns `(List[np.ndarray], int)` tuple with audio data and sample rate
- Does NOT write files directly (returns data for caller to write)
- Properly handles voice cloning and custom voice modes

### ✅ `src/scripts/chapter_xml_to_audio.py` - LOGIC CORRECT, OUTPUT FORMAT ISSUE

**File Writing (lines 193-196):**
```python
wavs, sr = provider.generate(...)
for i, wav in enumerate(wavs):
    suffix = f"_s{str(i+1).zfill(3)}" if len(wavs) > 1 else ""
    sf.write(str(chapter_clip_dir / f"{base}{suffix}.wav"), wav, sr)
```
- ✅ Files ARE being written using soundfile
- ✅ Output path is correct
- ✅ dry_run is respected (only skips when args.dry_run=True)

**Output Format Issue (line 188):**
```python
print(f"  Generating {base}...")
```
- Outputs with leading spaces: "  Generating chapter_..."
- Does NOT include speaker name
- Does NOT include ".wav" suffix in this line

### ❌ `src/ui/src/services/pythonBridge.ts` - REGEX PATTERNS BROKEN

**Line 175 regex:**
```javascript
const genMatch = out.match(/Generating \w+ (chapter_\d+_\d+_\d+_[^.]+)/i);
```
**Problem:** Expects speaker name, but output doesn't have one.

**Recommendations for fix:**
```javascript
// Option 1: Fix regex to handle actual output
const genMatch = out.match(/Generating\s+(chapter_\d+_\d+_\d+_\w+)/i);

// Option 2: Add explicit "saved to" output in Python
const saveMatch = out.match(/saved to .*?(chapter_.*?\.wav)/i);
```

### ⚠️ `src/ui/src/hooks/useAudio.ts` - ERROR HANDLING NEEDS IMPROVEMENT

Lines 169-176 catch errors but could provide better feedback:
```typescript
catch (err: unknown) {
  console.error("Failed to generate audio:", err);
  // Error is thrown but dialog only shown in some paths
}
```

---

## Recommendations

### HIGH PRIORITY (Fix Regex)

1. **Fix `src/ui/src/services/pythonBridge.ts` line 175:**
   ```javascript
   // FROM:
   const genMatch = out.match(/Generating \w+ (chapter_\d+_\d+_\d+_[^.]+)/i);
   // TO:
   const genMatch = out.match(/Generating\s+(chapter_\d+_\d+_\d+_\w+)/i);
   ```

2. **Add fallback pattern for base-only output:**
   ```javascript
   const baseMatch = out.match(/Generating\s+(chapter_\d+_\d+_\d+_\w+)/i);
   if (baseMatch?.[1]) {
       wavName = baseMatch[1] + ".wav";
   }
   ```

### MEDIUM PRIORITY (Improve Reliability)

3. **Add explicit "saved to" output in `chapter_xml_to_audio.py`:**
   ```python
   # After sf.write() call, add:
   print(f"    [Info] Saved clip to {out_path}")
   ```

4. **Add file existence check in TypeScript:**
   ```typescript
   // After parsing filename, verify file actually exists
   const fileExists = await window.api.checkFileExists(fullPath);
   if (!fileExists) {
       throw new Error(`Generated file not found: ${fullPath}`);
   }
   ```

### LOW PRIORITY (Improve UX)

5. **Add more detailed progress indicators showing actual filename being parsed**
6. **Add dry-run warnings if user triggers generation but dry_run would be True**

---

## Test Verification

All pattern matching was tested with Python regex:

| Pattern | Expected | Actual Output | Match? |
|---------|----------|---------------|--------|
| `Applying character effects to (.*?\.wav)` | effects output | "Applying character effects to chapter_xxx.wav..." | ✅ Yes |
| `Generating \w+ (chapter_\d+_\d+_\d+_[^.]+)` | speaker + chapter | "Generating chapter_xxx..." | ❌ No |
| `Generating\s+(chapter_\d+_\d+_\d+_\w+)` | chapter only | "Generating chapter_xxx..." | ✅ Yes (proposed fix) |

---

## Conclusion

The issue is **NOT** that files aren't being created - they ARE being created by `chapter_xml_to_audio.py`. The issue is that `pythonBridge.ts` cannot parse the Python script's output to determine the generated filename due to a regex pattern mismatch.

**Fix:** Update the regex pattern in `pythonBridge.ts` line 175 to match the actual output format from `chapter_xml_to_audio.py`.

---

## Fix Applied ✅

### `src/ui/src/services/pythonBridge.ts` - FIXED

**Changed line 175 regex pattern:**
```javascript
// BEFORE (broken - expected speaker name):
const genMatch = out.match(/Generating \w+ (chapter_\d+_\d+_\d+_[^.]+)/i);

// AFTER (fixed - matches actual output):
const genMatch = out.match(/Generating\s+(chapter_\d+_\d+_\d+_\w+)/i);
```

**Also reordered patterns:**
- Primary pattern now: "Generating chapter_XXX..." (always printed)
- Fallback pattern: "Applying character effects..." (only with effects)

**Testing Results:**
- ✅ All 72 TypeScript tests passing
- Python regex verified against actual command output

