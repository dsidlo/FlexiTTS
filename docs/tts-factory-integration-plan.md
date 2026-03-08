# TTS Factory Integration Plan

**Task:** Request-20250306-054227:Task-20250306:Round-1  
**Project:** FlexiTTS  
**Target:** chapter_xml_to_audio.py  
**Date:** 2025-03-06

---

## Executive Summary

This document outlines the implementation plan for integrating the TTS factory pattern into `chapter_xml_to_audio.py`. The factory pattern provides a unified interface for both local (Qwen3-TTS) and remote (WebSocket) TTS providers.

**Current Status:** Partially integrated - basic factory usage exists but requires refinement for production use.

---

## 1. Current State Analysis

### 1.1 Existing Integration Points

The current code already has basic factory integration:

```python
# Lines 14-18: Import with fallback
try:
    from tts_factory import create_tts_provider, TTSProviderFactory as TTSFactory
except ImportError as e:
    TTSFactory = None
    create_tts_provider = None
    print(f"WARNING: TTS provider imports failed: {e}", file=sys.stderr)

# Lines 159-173: Provider instantiation
if not args.dry_run and create_tts_provider:
    tts_type = "remote" if args.tts_service else "local"
    print(f"Loading {tts_type} TTS provider...")
    try:
        provider = create_tts_provider(
            service_url=args.tts_service,
            voices_dir=voices_dir
        )
    except Exception as e:
        print(f"ERROR: Failed to initialize TTS provider: {e}", file=sys.stderr)
        raise RuntimeError(f"TTS provider initialization failed: {e}") from e
```

### 1.2 Identified Gaps

| Gap | Description | Impact |
|-----|-------------|--------|
| Import Path | Factory files are in same directory but import is relative | May fail in some execution contexts |
| Error Handling | Generic exception handling obscures specific errors | Harder to diagnose issues |
| Provider Validation | No pre-flight check if provider supports character config | Late failure at generation time |
| Fallback Strategy | No fallback from remote to local on generation failure | Single point of failure |
| Resource Cleanup | Provider close() called conditionally | Potential resource leaks |
| Configuration | No way to pass additional TTS config | Limited flexibility |

---

## 2. Implementation Approach

### 2.1 Step-by-Step Refactoring

#### Step 1: Robust Import Handling

**File:** `chapter_xml_to_audio.py`  
**Lines:** 1-20

```python
#!/usr/bin/env python3

import argparse
import os
import re
import sys
import yaml
import numpy as np
import soundfile as sf
import subprocess
import random
import string
from pathlib import Path
from xml.etree import ElementTree as ET
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from chapter_validate_xml import validate_and_fix_xml

# TTS Factory imports with graceful degradation
try:
    from tts_factory import create_tts_provider, TTSProviderFactory
    from tts_interface import TTSError, TTSConnectionError, TTSGenerationError
    TTS_FACTORY_AVAILABLE = True
except ImportError as e:
    TTS_FACTORY_AVAILABLE = False
    create_tts_provider = None
    TTSProviderFactory = None
    TTSError = Exception
    TTSConnectionError = Exception
    TTSGenerationError = Exception
    print(f"WARNING: TTS provider imports failed: {e}", file=sys.stderr)
    print("Audio generation will fail. Ensure GPU dependencies are installed.", file=sys.stderr)
```

**Rationale:**
- Adds `sys` import for stderr
- Centralizes availability flag
- Provides exception class fallbacks

#### Step 2: Enhanced CLI Arguments

**File:** `chapter_xml_to_audio.py`  
**Lines:** ~135-148 (argparse section)

```python
def main():
    parser = argparse.ArgumentParser(
        description="Convert XML chapters to audio using TTS",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Use local TTS (default)
  %(prog)s chapter_01.xml
  
  # Use remote WebSocket TTS service
  %(prog)s chapter_01.xml --tts-service ws://localhost:8080
  
  # Use remote with local fallback
  %(prog)s chapter_01.xml --tts-service ws://host:8080 --tts-fallback
  
  # Dry run (no audio generation)
  %(prog)s chapter_01.xml --dry-run
        """
    )
    parser.add_argument("xml_file", nargs="?", help="Path to chapter XML file")
    parser.add_argument("--dry-run", action="store_true", help="Simulate without generating audio")
    parser.add_argument("--section", type=str, help="Process only specific section number")
    parser.add_argument("--dlgseq", type=str, help="Process only specific dialog sequence")
    parser.add_argument("--create-missing-clips", action="store_true", help="Generate only missing clips")
    parser.add_argument("--create-silent-clips", action="store_true", help="Add silent clips between utterances")
    
    # TTS Factory arguments
    tts_group = parser.add_argument_group("TTS Provider Options")
    tts_group.add_argument(
        "--tts-service", 
        type=str, 
        default=None, 
        metavar="URL",
        help="WebSocket TTS service URL (ws://host:port). If not set, uses local TTS."
    )
    tts_group.add_argument(
        "--tts-fallback",
        action="store_true",
        default=True,
        help="Enable fallback to local TTS if remote service fails (default: True)"
    )
    tts_group.add_argument(
        "--tts-no-fallback",
        action="store_true",
        help="Disable fallback to local TTS (fail fast on remote errors)"
    )
    tts_group.add_argument(
        "--tts-timeout",
        type=float,
        default=30.0,
        metavar="SECONDS",
        help="Timeout for TTS service operations (default: 30)"
    )
    tts_group.add_argument(
        "--tts-retries",
        type=int,
        default=4,
        metavar="COUNT",
        help="Number of retries for TTS service connection (default: 4)"
    )
    
    args = parser.parse_args()
    
    # Handle --tts-no-fallback negation
    if args.tts_no_fallback:
        args.tts_fallback = False
```

**Rationale:**
- Groups TTS-related arguments for clarity
- Adds `--tts-no-fallback` as explicit negation
- Provides timeout and retry configurability
- Includes helpful examples in epilog

#### Step 3: Provider Factory Integration

**File:** `chapter_xml_to_audio.py`  
**Lines:** ~160-190

```python
def initialize_tts_provider(args, voices_dir: Path) -> Optional[Any]:
    """Initialize TTS provider based on CLI arguments.
    
    Args:
        args: Parsed command-line arguments
        voices_dir: Directory containing voice reference samples
        
    Returns:
        Configured TTS provider or None in dry-run mode
        
    Raises:
        RuntimeError: If TTS factory is unavailable or initialization fails
    """
    if args.dry_run:
        return None
    
    if not TTS_FACTORY_AVAILABLE:
        raise RuntimeError(
            "TTS provider factory unavailable. "
            "Check that GPU dependencies are installed: pip install -r requirements.txt"
        )
    
    # Determine provider type
    tts_type = "remote" if args.tts_service else "local"
    print(f"Loading {tts_type} TTS provider...")
    
    # Build provider configuration
    provider_config = {
        "max_retries": args.tts_retries,
        "timeout": args.tts_timeout,
    }
    
    try:
        # Use factory for provider creation
        factory = TTSProviderFactory()
        provider = factory.create_provider(
            service_url=args.tts_service,
            voices_dir=voices_dir,
            enable_fallback=args.tts_fallback,
            config=provider_config
        )
        print(f"  Provider initialized: {provider.__class__.__name__}")
        return provider
        
    except TTSConnectionError as e:
        if args.tts_service and args.tts_fallback:
            print(f"  WARNING: Remote TTS connection failed: {e}")
            print("  Attempting fallback to local TTS...")
            try:
                provider = factory.create_provider(
                    service_url=None,  # Force local
                    voices_dir=voices_dir
                )
                print("  Fallback to local TTS successful")
                return provider
            except Exception as fallback_error:
                raise RuntimeError(
                    f"Both remote and fallback local TTS failed. "
                    f"Remote: {e}, Local: {fallback_error}"
                ) from fallback_error
        raise RuntimeError(f"TTS provider initialization failed: {e}") from e
        
    except Exception as e:
        raise RuntimeError(f"TTS provider initialization failed: {e}") from e
```

**Rationale:**
- Encapsulates provider initialization logic
- Adds detailed error handling for connection issues
- Implements explicit fallback logic
- Provides user feedback during initialization

#### Step 4: Character Validation with Provider

**File:** `chapter_xml_to_audio.py`  
**Lines:** ~200-220 (character processing loop)

```python
def validate_character_support(provider, char_cfg: Dict[str, Any], character: str) -> bool:
    """Validate that the provider supports the character configuration.
    
    Args:
        provider: TTS provider instance
        char_cfg: Character configuration
        character: Character name for logging
        
    Returns:
        True if character is supported, False otherwise
    """
    if provider is None:
        return True  # Dry-run mode
    
    try:
        if not provider.supports_character(char_cfg):
            print(f"  WARNING: Character '{character}' not supported by "
                  f"{provider.__class__.__name__}")
            return False
        return True
    except Exception as e:
        print(f"  WARNING: Could not validate character support: {e}")
        # Continue anyway - let generation fail if truly unsupported
        return True

# ... in main processing loop:
for character, utts in by_character.items():
    print(f"Generating audio for {character}...")
    char_cfg = char_configs.get(character.lower())
    if not char_cfg:
        print(f"  No config for {character}, skipping")
        continue
    
    # Validate provider support for this character
    if not validate_character_support(provider, char_cfg, character):
        print(f"  Skipping {character} - not supported by current provider")
        continue
```

**Rationale:**
- Early validation prevents late failures
- Provides clear feedback about unsupported characters
- Gracefully handles validation errors

#### Step 5: Enhanced Generation with Error Handling

**File:** `chapter_xml_to_audio.py`  
**Lines:** ~260-290 (generation section)

```python
def generate_audio_with_fallback(
    provider, 
    utt: Utterance, 
    out_path: Path, 
    char_cfg: Dict[str, Any],
    voices_dir: Path,
    max_retries: int = 1
) -> Optional[Tuple[List[np.ndarray], int]]:
    """Generate audio with retry and fallback logic.
    
    Args:
        provider: Primary TTS provider
        utt: Utterance to generate
        out_path: Output file path
        char_cfg: Character configuration
        voices_dir: Voices directory for fallback creation
        max_retries: Number of retries on transient failures
        
    Returns:
        Tuple of (audio segments, sample_rate) or None if failed
    """
    lang = "English"
    instruct = f"Speak in a {utt.emotion} tone."
    
    is_custom = "custom-voice" in char_cfg
    if is_custom:
        cv = char_cfg["custom-voice"]
        lang = cv.get("language", "English")
        base_instruct = cv.get("instruct", "")
        instruct = f"{base_instruct}. {instruct}".strip(". ")
    
    last_error = None
    
    for attempt in range(max_retries):
        try:
            wavs, sr = provider.generate(
                text=utt.text,
                speaker=utt.speaker,
                emotion=utt.emotion,
                language=lang,
                output_path=out_path,
                instruct=instruct,
                char_config=char_cfg
            )
            return wavs, sr
            
        except TTSConnectionError as e:
            last_error = e
            print(f"    Connection error (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                import time
                time.sleep(2 ** attempt)  # Exponential backoff
                
        except TTSGenerationError as e:
            print(f"    Generation error: {e}")
            return None  # Don't retry generation errors
            
        except Exception as e:
            last_error = e
            print(f"    Error (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                import time
                time.sleep(1)
    
    print(f"    Failed after {max_retries} attempts: {last_error}")
    return None

# ... in main loop:
if not args.dry_run and provider:
    try:
        result = generate_audio_with_fallback(
            provider, utt, out_path, char_cfg, voices_dir
        )
        if result is None:
            continue  # Skip to next utterance
        
        wavs, sr = result
        for i, wav in enumerate(wavs):
            suffix = f"_s{str(i+1).zfill(3)}" if len(wavs) > 1 else ""
            sf.write(str(chapter_clip_dir / f"{base}{suffix}.wav"), wav, sr)
            
    except Exception as e:
        print(f"    Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        continue
```

**Rationale:**
- Implements retry logic for transient failures
- Distinguishes between connection and generation errors
- Provides exponential backoff between retries
- Detailed error reporting

#### Step 6: Cleanup and Resource Management

**File:** `chapter_xml_to_audio.py`  
**Lines:** ~330-340 (end of main)

```python
def cleanup_provider(provider: Optional[Any]) -> None:
    """Safely cleanup TTS provider resources.
    
    Args:
        provider: TTS provider instance or None
    """
    if provider is None:
        return
    
    try:
        provider.close()
        print("TTS provider resources released")
    except Exception as e:
        print(f"Warning: Error during provider cleanup: {e}")

# ... at end of main():
try:
    # ... main processing logic ...
    pass
finally:
    cleanup_provider(provider)
```

**Rationale:**
- Ensures cleanup happens even on exceptions
- Handles cleanup errors gracefully
- Provides feedback about resource release

---

## 3. Backward Compatibility Strategy

### 3.1 Default Behavior

| Scenario | Behavior |
|----------|----------|
| No `--tts-service` | Uses local TTS (existing behavior preserved) |
| `--tts-service URL` | Uses remote TTS with fallback enabled |
| `--dry-run` | No TTS initialization, simulation mode |
| Missing dependencies | Clear error message with install instructions |

### 3.2 Migration Path

1. **Phase 1 (Current):** Factory integration is optional, existing code works
2. **Phase 2:** Add deprecation warnings for direct TTS usage
3. **Phase 3:** Require factory pattern, remove legacy code

### 3.3 Configuration Compatibility

The `story-config.yml` format remains unchanged:

```yaml
global:
  story-dir: ./story
  voices: refs

characters:
  - name: Narrator
    voice-sample: narrator_ref.wav
    
  - name: CustomCharacter
    custom-voice:
      speaker: "speaker_id"
      language: "English"
      instruct: "Speak clearly"
```

---

## 4. SoX Effects Integration

### 4.1 Current Integration

SoX effects are applied **after** TTS generation in `apply_sox_effects()`:

```python
# Lines 52-78: apply_sox_effects function
def apply_sox_effects(input_path: Path, effects_list: List[str], dry_run: bool = False):
    # Uses subprocess to run sox command
    cmd = ["sox", str(input_path), str(temp_path)] + effects_cmd
```

### 4.2 Integration with Factory Providers

The factory pattern does **not** change SoX integration:

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   TTS Provider  │────▶│  Audio Output   │────▶│  SoX Effects  │
│  (Local/Remote) │     │  (WAV file)     │     │  (Post-process)│
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

**Key Point:** The factory provider handles TTS generation only. SoX effects remain a post-processing step independent of the TTS source.

### 4.3 Effects Configuration

Effects are still defined in `story-config.yml`:

```yaml
dialog-effects:
  - name: radio
    sox-effects:
      - "highpass 1000"
      - "overdrive 10 20"
      - "echo 0.8 0.7 5 0.3"

characters:
  - name: RadioHost
    voice-sample: radio_host.wav
    dialog-effects:
      - radio
```

---

## 5. Implementation Checklist

### Phase 1: Foundation (Day 1)
- [ ] Add robust import handling with `TTS_FACTORY_AVAILABLE` flag
- [ ] Enhance CLI argument parsing with TTS argument group
- [ ] Create `initialize_tts_provider()` function
- [ ] Add `validate_character_support()` function

### Phase 2: Error Handling (Day 2)
- [ ] Implement `generate_audio_with_fallback()` function
- [ ] Add retry logic with exponential backoff
- [ ] Improve error messages with specific exception types
- [ ] Add `cleanup_provider()` function with try/finally

### Phase 3: Testing (Day 3)
- [ ] Test local TTS (default) path
- [ ] Test remote TTS with mock service
- [ ] Test fallback from remote to local
- [ ] Test error handling for connection failures
- [ ] Verify SoX effects work with both providers

### Phase 4: Documentation (Day 4)
- [ ] Update `--help` output with examples
- [ ] Add troubleshooting section to README
- [ ] Document new CLI arguments
- [ ] Create migration guide if needed

---

## 6. Code Flow Diagram

```
chapter_xml_to_audio.py
│
├── argparse
│   └── --tts-service (optional)
│   └── --tts-fallback (default: True)
│   └── --tts-timeout (default: 30)
│   └── --tts-retries (default: 4)
│
├── initialize_tts_provider()
│   │
│   ├── if --tts-service:
│   │   └── TTSProviderFactory.create_provider(service_url=...)
│   │       └── RemoteTTSProvider with fallback
│   │
│   └── else:
│       └── TTSProviderFactory.create_provider(service_url=None)
│           └── LocalTTSProvider
│
├── process utterances
│   │
│   ├── validate_character_support()
│   │   └── provider.supports_character(char_cfg)
│   │
│   └── generate_audio_with_fallback()
│       │
│       ├── provider.generate() ──▶ Audio segments
│       │
│       └── on error: retry/fallback
│
├── apply_sox_effects()
│   └── subprocess(['sox', ...])
│
└── cleanup_provider()
    └── provider.close()
```

---

## 7. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Import errors in different environments | Medium | High | Use absolute imports with fallback |
| Remote service unavailable | Medium | Medium | Default fallback to local TTS |
| Performance regression | Low | Medium | Benchmark before/after, cache providers |
| Memory leaks | Low | High | Ensure `close()` called in finally block |
| Breaking existing workflows | Low | High | Maintain backward compatibility |

---

## 8. Testing Strategy

### 8.1 Unit Tests

```python
# test_tts_integration.py
import unittest
from unittest.mock import Mock, patch

class TestTTSIntegration(unittest.TestCase):
    
    def test_local_provider_creation(self):
        """Test that local provider is created when no service URL."""
        pass
    
    def test_remote_provider_creation(self):
        """Test that remote provider is created with service URL."""
        pass
    
    def test_fallback_on_connection_error(self):
        """Test fallback to local on remote connection failure."""
        pass
    
    def test_character_validation(self):
        """Test character support validation."""
        pass
```

### 8.2 Integration Tests

```bash
# Test local TTS (default)
./chapter_xml_to_audio.py chapter_01.xml --dry-run

# Test remote TTS
./chapter_xml_to_audio.py chapter_01.xml --tts-service ws://localhost:8080

# Test remote with no fallback
./chapter_xml_to_audio.py chapter_01.xml --tts-service ws://invalid --tts-no-fallback

# Test specific section with remote
./chapter_xml_to_audio.py chapter_01.xml --tts-service ws://localhost:8080 --section 1
```

---

## 9. Deliverables

1. **This Implementation Plan** (docs/tts-factory-integration-plan.md)
2. **Refactored chapter_xml_to_audio.py** (src/scripts/chapter_xml_to_audio.py)
3. **Test Suite** (tests/test_tts_integration.py)
4. **Documentation Updates** (README.md troubleshooting section)

---

## 10. Summary

The TTS factory integration plan provides:

1. **Backward Compatibility:** Default local TTS, all existing workflows preserved
2. **Enhanced CLI:** `--tts-service`, `--tts-fallback`, `--tts-timeout`, `--tts-retries`
3. **Robust Error Handling:** Specific exceptions, retry logic, graceful fallbacks
4. **Resource Management:** Guaranteed cleanup with try/finally pattern
5. **SoX Integration:** Unchanged - effects apply post-generation regardless of TTS source

**Estimated Effort:** 3-4 days for complete implementation and testing

**Approver:** _________________  **Date:** _________________
