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

try:
    from tts_factory import create_tts_provider, TTSProviderFactory as TTSFactory
    from tts_interface import (
        TTSError,
        TTSConnectionError,
        TTSGenerationError,
        CharacterNotSupportedError
    )
except ImportError as e:
    TTSFactory = None
    create_tts_provider = None
    TTSError = None
    TTSConnectionError = None
    TTSGenerationError = None
    CharacterNotSupportedError = None
    print(f"WARNING: TTS provider imports failed: {e}", file=sys.stderr)
    print("Audio generation will fail. Ensure GPU dependencies are installed.", file=sys.stderr)


@dataclass
class Utterance:
    chapter_num: str
    section_num: str
    dlgseq: str
    speaker: str
    emotion: str
    text: str
    kind: str
    post_effects: Optional[str] = None


def normalize_ws(s: str) -> str:
    if not s:
        return ""
    s = s.replace("\r", " ").replace("\n", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def apply_sox_effects(input_path: Path, effects_list: List[str], dry_run: bool = False):
    if not effects_list:
        return

    for effects_str in effects_list:
        if not effects_str:
            continue

        random_str = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
        temp_path = input_path.parent / f"temp-{random_str}.wav"
        effects_cmd = effects_str.split()
        cmd = ["sox", str(input_path), str(temp_path)] + effects_cmd

        if dry_run:
            print(f"    [Dry-run] Would run: {' '.join(cmd)}")
            continue

        try:
            subprocess.run(cmd, check=True, capture_output=True)
            input_path.unlink()
            temp_path.rename(input_path)
        except subprocess.CalledProcessError as e:
            print(f"Error applying sox effects: {e.stderr.decode()}")
            if temp_path.exists():
                temp_path.unlink()
        except Exception as e:
            print(f"Unexpected error applying sox effects: {e}")
            if temp_path.exists():
                temp_path.unlink()


def parse_xml(xml_path: Path) -> List[Utterance]:
    print(f"[RESOURCE-ACCESS] Reading XML input", file=sys.stderr)
    print(f"  xml_path: {xml_path}", file=sys.stderr)
    print(f"  resourceType: xml", file=sys.stderr)
    print(f"  operation: read", file=sys.stderr)
    if not xml_path.exists():
        print(f"[RESOURCE-ACCESS] XML NOT found: {xml_path}", file=sys.stderr)
        raise FileNotFoundError(f"XML file not found: {xml_path}")
    print(f"[RESOURCE-ACCESS] Successfully read XML input", file=sys.stderr)
    print(f"  xml_path: {xml_path}", file=sys.stderr)
    tree = ET.parse(xml_path)
    root = tree.getroot()
    match = re.search(r"(\d+)", xml_path.name)
    chapter_num = match.group(1) if match else "000"
    utterances = []

    for section in root.findall("section"):
        section_num = section.attrib.get("seq", "000").zfill(3)
        for node in section:
            if node.tag in ("dialog", "narration"):
                dlgseq = node.attrib.get("dlgseq", "000").zfill(3)
                emotion = node.attrib.get("emotion", "neutral")
                post_effects = node.attrib.get("post-effects")
                speaker = node.attrib.get("character", "unknown") if node.tag == "dialog" else "narrator"
                text = normalize_ws("".join(node.itertext()))
                if text:
                    utterances.append(Utterance(
                        chapter_num=chapter_num.zfill(3),
                        section_num=section_num,
                        dlgseq=dlgseq,
                        speaker=speaker,
                        emotion=emotion,
                        text=text,
                        kind=node.tag,
                        post_effects=post_effects
                    ))
    return utterances


def generate_silence(duration: float, sr: int = 24000) -> np.ndarray:
    return np.zeros(int(sr * duration))


def find_config_file(xml_path: Optional[Path] = None) -> Optional[Path]:
    """Find story-config.yml based on XML file location or CWD."""
    # If XML path is provided, look in the story directory
    if xml_path:
        # XML is typically in Stories/{Story-Name}/story-xml/
        # Config should be in Stories/{Story-Name}/story-config.yml
        potential_config = xml_path.parent.parent / "story-config.yml"
        if potential_config.exists():
            return potential_config
    
    # Check Stories directories from project root
    stories_dir = Path("Stories")
    if stories_dir.exists():
        for story_dir in stories_dir.iterdir():
            if story_dir.is_dir() and story_dir.name.startswith("Story-"):
                config_file = story_dir / "story-config.yml"
                if config_file.exists():
                    return config_file
    
    # Fall back to CWD
    config_in_cwd = Path("story-config.yml")
    if config_in_cwd.exists():
        return config_in_cwd
    
    return None


def main():
    parser = argparse.ArgumentParser(description="Convert XML chapters to audio using TTS")
    parser.add_argument("xml_file", nargs="?", help="Path to chapter XML")
    parser.add_argument("--config", type=str, help="Path to story-config.yml (auto-detected if not provided)")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--section", type=str)
    parser.add_argument("--dlgseq", type=str)
    parser.add_argument("--create-missing-clips", action="store_true")
    parser.add_argument("--create-silent-clips", action="store_true")
    parser.add_argument("--tts-service", type=str, default=None, help="WebSocket TTS service URL")
    args = parser.parse_args()

    # Determine XML path first (needed for auto-detect)
    xml_path = Path(args.xml_file) if args.xml_file else None
    
    # Load config from explicit path, auto-detect, or fall back to CWD
    config_path = Path(args.config) if args.config else find_config_file(xml_path)
    
    if not config_path:
        print("Error: Could not find story-config.yml")
        print("Please provide --config path or run from a story directory")
        sys.exit(1)
    
    print(f"[RESOURCE-ACCESS] Loading story config", file=sys.stderr)
    print(f"  config_path: {config_path}", file=sys.stderr)
    print(f"  resourceType: yaml", file=sys.stderr)
    print(f"  operation: read", file=sys.stderr)
    try:
        if not config_path.exists():
            print(f"[RESOURCE-ACCESS] Config NOT found: {config_path}", file=sys.stderr)
            print(f"Error: Config file not found: {config_path}")
            sys.exit(1)
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
        print(f"[RESOURCE-ACCESS] Successfully loaded story config", file=sys.stderr)
        print(f"  config_path: {config_path}", file=sys.stderr)
        print(f"  has_characters: {'characters' in config}", file=sys.stderr)
        print(f"  has_global: {'global' in config}", file=sys.stderr)
    except FileNotFoundError:
        print(f"[RESOURCE-ACCESS] Config NOT found: {config_path}", file=sys.stderr)
        print(f"Error: Config file not found: {config_path}")
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"[RESOURCE-ACCESS] YAML parse error: {e}", file=sys.stderr)
        print(f"Error: Invalid YAML in config file: {e}")
        sys.exit(1)

    global_cfg = config.get("global", {})
    config_base_dir = config_path.parent.resolve()

    configured_story_dir = Path(global_cfg.get("story-dir", "."))
    story_dir = configured_story_dir if configured_story_dir.is_absolute() else (config_base_dir / configured_story_dir).resolve()
    if not story_dir.exists():
        story_dir = config_base_dir

    story_name = story_dir.name.replace("-", " ").title() if story_dir.name != "." else "Story"

    story_xml_cfg = Path(global_cfg.get("story-xml", "story-xml"))
    story_audio_cfg = Path(global_cfg.get("story-audio", "story-audio"))
    clips_cfg = Path(global_cfg.get("clips", "clips"))
    voices_cfg = Path(global_cfg.get("voices", "refs"))

    story_xml_dir = story_xml_cfg if story_xml_cfg.is_absolute() else (story_dir / story_xml_cfg).resolve()
    story_audio_dir = story_audio_cfg if story_audio_cfg.is_absolute() else (story_dir / story_audio_cfg).resolve()
    clips_dir = clips_cfg if clips_cfg.is_absolute() else (story_dir / clips_cfg).resolve()
    voices_dir = voices_cfg if voices_cfg.is_absolute() else (story_dir / voices_cfg).resolve()
    clip_separation = float(global_cfg.get("clip-separation", 0))

    story_audio_dir.mkdir(parents=True, exist_ok=True)

    # xml_path was determined earlier for auto-detect, but finalize it here
    if xml_path and not xml_path.is_absolute():
        candidate_paths = [
            (Path.cwd() / xml_path).resolve(),
            (config_base_dir / xml_path).resolve(),
            (story_dir / xml_path).resolve(),
            (story_xml_dir / xml_path.name).resolve(),
        ]
        for candidate in candidate_paths:
            if candidate.exists():
                xml_path = candidate
                break

    if not xml_path:
        xml_path = next(story_xml_dir.glob("*.xml"), None)
    if not xml_path or not xml_path.exists():
        print(f"XML file not found: {xml_path}")
        return

    print(f"Validating {xml_path}...")
    if not validate_and_fix_xml(str(xml_path)):
        print(f"XML validation failed")
        return

    print(f"Processing {xml_path}...")
    utterances = parse_xml(xml_path)

    if args.section:
        utterances = [u for u in utterances if u.section_num == args.section.zfill(3)]
    if args.dlgseq:
        utterances = [u for u in utterances if u.dlgseq == args.dlgseq.zfill(3)]

    by_character = {}
    for utt in utterances:
        by_character.setdefault(utt.speaker, []).append(utt)

    char_configs = {c["name"].lower(): c for c in config.get("characters", [])}
    dialog_effects_cfg = {e["name"]: e.get("sox-effects", []) for e in config.get("dialog-effects", [])}

    provider = None
    if not args.dry_run and create_tts_provider:
        tts_type = "remote" if args.tts_service else "local"
        print(f"Loading {tts_type} TTS provider...")
        
        # TTS provider configuration with timeout and retry settings
        tts_config = {
            "timeout": float(global_cfg.get("tts-timeout", 60.0)),
            "max_retries": int(global_cfg.get("tts-max-retries", 3)),
            "connection_timeout": float(global_cfg.get("tts-connection-timeout", 10.0)),
            "generation_timeout": float(global_cfg.get("tts-generation-timeout", 120.0))
        }
        
        try:
            import time
            print("  [TTS] Creating remote TTS provider...")
            provider_start = time.time()
            from tts_factory import TTSProviderFactory
            factory = TTSProviderFactory()
            # Use reasonable timeout (60s) for remote generation - should be fast when cached
            tts_config = {
                "timeout": 60.0,  # 60 seconds for generation
                "max_retries": 3
            }
            provider = factory.create_provider(
                service_url=args.tts_service,
                voices_dir=voices_dir,
                enable_fallback=False,  # Don't create local fallback - use remote only
                config=tts_config
            )
            provider_elapsed = time.time() - provider_start
            print(f"  [TTS] Provider created in {provider_elapsed:.1f}s (remote only, no fallback)")
            
            # Check service warmup status
            print("  [TTS] Checking service warmup status...")
            try:
                from tts_service import RemoteTTSProvider
                import asyncio
                health_provider = RemoteTTSProvider(args.tts_service)
                health = asyncio.run(health_provider.health_check())
                print(f"  [TTS] Service status: {health.get('status', 'unknown')}, ready: {health.get('ready', False)}, cached: {health.get('model_cached', False)}")
                health_provider.close()
            except Exception as e:
                print(f"  [TTS] Could not check warmup status: {e}")
        except TTSConnectionError as e:
            print(f"ERROR: TTS connection failed: {e}", file=sys.stderr)
            raise RuntimeError(f"TTS connection failed: {e}") from e
        except TTSGenerationError as e:
            print(f"ERROR: TTS initialization failed: {e}", file=sys.stderr)
            raise RuntimeError(f"TTS provider initialization failed: {e}") from e
        except TTSError as e:
            print(f"ERROR: TTS provider error: {e}", file=sys.stderr)
            raise RuntimeError(f"TTS provider error: {e}") from e
        except Exception as e:
            print(f"ERROR: Failed to initialize TTS provider: {e}", file=sys.stderr)
            raise RuntimeError(f"TTS provider initialization failed: {e}") from e
    elif not args.dry_run and create_tts_provider is None:
        raise RuntimeError(
            "TTS provider factory unavailable. "
            "Check that GPU dependencies are installed: pip install -r requirements.txt"
        )

    try:
        chapter_clip_dir = clips_dir / xml_path.stem
        chapter_clip_dir.mkdir(parents=True, exist_ok=True)

        all_generated_clips = []

        for character, utts in by_character.items():
            print(f"Generating audio for {character}...")
            char_cfg = char_configs.get(character.lower())
            if not char_cfg:
                print(f"No config for {character}, skipping")
                continue

            for utt in utts:
                base = f"chapter_{utt.chapter_num}_{utt.section_num}_{utt.dlgseq}_{utt.speaker}"
                out_path = chapter_clip_dir / f"{base}.wav"

                if args.create_missing_clips and out_path.exists():
                    print(f"  Skipping {base} (exists)")
                    all_generated_clips.append((utt, out_path, 0))
                    continue

                if not char_cfg:
                    continue

                is_custom = "custom-voice" in char_cfg
                if is_custom:
                    cv = char_cfg["custom-voice"]
                    lang = cv.get("language", "English")
                    base_instruct = cv.get("instruct", "")
                    instruct = f"{base_instruct}. Speak in a {utt.emotion} tone.".strip(". ")
                else:
                    lang = "English"
                    instruct = f"Speak in a {utt.emotion} tone."

                print(f"[RESOURCE-ACCESS] Generating audio clip", file=sys.stderr)
                print(f"  output_path: {out_path}", file=sys.stderr)
                print(f"  resourceType: audio", file=sys.stderr)
                print(f"  operation: write", file=sys.stderr)
                print(f"  speaker: {utt.speaker}", file=sys.stderr)
                print(f"  emotion: {utt.emotion}", file=sys.stderr)
                print(f"  textLength: {len(utt.text)}", file=sys.stderr)
                print(f"  Generating {base}...")
                import time
                gen_start = time.time()

                # Validate text length limit (2K character max)
                if len(utt.text) > 2000:
                    print(f"    ERROR: Text too long: {len(utt.text)} chars (max 2000)", file=sys.stderr)
                    print(f"    Truncating...", file=sys.stderr)
                    utt.text = utt.text[:2000]

                # Check if provider supports this character configuration
                if not args.dry_run and provider:
                    try:
                        if char_cfg and not provider.supports_character(char_cfg):
                            print(f"    WARNING: Provider does not fully support character config for {character}", file=sys.stderr)
                            print(f"    Attempting generation anyway...", file=sys.stderr)
                    except Exception as e:
                        print(f"    WARNING: Could not verify character support: {e}", file=sys.stderr)

                    try:
                        print(f"    [{time.strftime('%H:%M:%S')}] Starting generation...", file=sys.stderr)
                        wavs, sr = provider.generate(
                            text=utt.text,
                            speaker=utt.speaker,
                            emotion=utt.emotion,
                            language=lang,
                            output_path=out_path,
                            instruct=instruct,
                            char_config=char_cfg,
                            story=story_name,
                            chapter=utt.chapter_num,
                            section=utt.section_num,
                            dialog=utt.dlgseq
                        )
                        gen_elapsed = time.time() - gen_start
                        print(f"    [{time.strftime('%H:%M:%S')}] Generation complete in {gen_elapsed:.1f}s", file=sys.stderr)
                        print(f"[RESOURCE-ACCESS] Audio clip generated", file=sys.stderr)
                        print(f"  output_path: {out_path}", file=sys.stderr)
                        print(f"  wavCount: {len(wavs)}", file=sys.stderr)
                        print(f"  sampleRate: {sr}", file=sys.stderr)
                        for i, wav in enumerate(wavs):
                            suffix = f"_s{str(i+1).zfill(3)}" if len(wavs) > 1 else ""
                            clip_path = chapter_clip_dir / f"{base}{suffix}.wav"
                            sf.write(str(clip_path), wav, sr)
                            print(f"[RESOURCE-ACCESS] Audio clip written", file=sys.stderr)
                            print(f"  clip_path: {clip_path}", file=sys.stderr)
                            print(f"  resourceType: audio", file=sys.stderr)
                    except CharacterNotSupportedError as e:
                        print(f"    ERROR: Character not supported by TTS provider: {e}")
                        continue
                    except TTSConnectionError as e:
                        print(f"    ERROR: TTS connection failed: {e}")
                        print(f"    Check TTS service availability and network connectivity.")
                        # Don't fall back - --tts-service was explicitly requested
                        raise RuntimeError(f"TTS service connection failed: {e}") from e
                    except TTSGenerationError as e:
                        print(f"    ERROR: TTS generation failed: {e}")
                        print(f"    Text may be too complex or unsupported.")
                        continue
                    except TTSError as e:
                        print(f"    ERROR: TTS error: {e}")
                        continue
                    except Exception as e:
                        import traceback
                        print(f"    ERROR: Unexpected error during generation: {type(e).__name__}: {e}")
                        traceback.print_exc()
                        continue
                else:
                    print(f"    [Dry-run] Would generate: {base}")
                    sr = 24000

                all_generated_clips.append((utt, out_path, 0))

                # Apply effects
                final_effects = []
                if "dialog-effects" in char_cfg:
                    for name in char_cfg["dialog-effects"] if isinstance(char_cfg["dialog-effects"], list) else [char_cfg["dialog-effects"]]:
                        final_effects.extend(dialog_effects_cfg.get(name, []))
                final_effects.extend(char_cfg.get("sox-effects", []))
                if final_effects and not args.dry_run:
                    apply_sox_effects(out_path, final_effects)

                if utt.post_effects and not args.dry_run:
                    for name in utt.post_effects.split(","):
                        effects = dialog_effects_cfg.get(name.strip())
                        if effects:
                            apply_sox_effects(out_path, effects)

                if args.create_silent_clips and clip_separation > 0 and not args.dry_run:
                    silence_path = chapter_clip_dir / f"chapter_{utt.chapter_num}_{utt.section_num}_{utt.dlgseq}_~silence.wav"
                    sf.write(str(silence_path), generate_silence(clip_separation, sr), sr)
                    silence_utt = Utterance(
                        chapter_num=utt.chapter_num, section_num=utt.section_num, dlgseq=utt.dlgseq,
                        speaker="~silence", emotion="neutral", text="", kind="silence"
                    )
                    all_generated_clips.append((silence_utt, silence_path, 999))

        # Concatenate final audio
        if all_generated_clips:
            if args.section or args.dlgseq:
                print("Selective regeneration - final audio not updated")
                return

            all_generated_clips.sort(key=lambda x: (x[0].section_num, x[0].dlgseq, x[2]))

            if args.dry_run:
                print(f"[Dry-run] Would create chapter audio")
            else:
                combined = []
                final_sr = 24000
                for utt, path, subseq in all_generated_clips:
                    try:
                        data, sr = sf.read(str(path))
                        combined.append(data)
                        final_sr = sr
                        if clip_separation > 0 and not args.create_silent_clips:
                            if (utt, path, subseq) != all_generated_clips[-1]:
                                combined.append(generate_silence(clip_separation, sr))
                    except Exception as e:
                        print(f"Error reading {path}: {e}")

                if combined:
                    final_path = story_audio_dir / (xml_path.stem + ".wav")
                    print(f"[RESOURCE-ACCESS] Writing final audio", file=sys.stderr)
                    print(f"  final_path: {final_path}", file=sys.stderr)
                    print(f"  resourceType: audio", file=sys.stderr)
                    print(f"  operation: write", file=sys.stderr)
                    print(f"  audioLength: {len(combined)} clips", file=sys.stderr)
                    sf.write(str(final_path), np.concatenate(combined), final_sr)
                    print(f"[RESOURCE-ACCESS] Successfully wrote final audio", file=sys.stderr)
                    print(f"  final_path: {final_path}", file=sys.stderr)
                    print(f"Final audio: {final_path}")

                    post_effects = config.get("story-audio-post-process", {}).get("sox-effects", [])
                    if post_effects:
                        print(f"[RESOURCE-ACCESS] Applying post-effects", file=sys.stderr)
                        print(f"  audio_path: {final_path}", file=sys.stderr)
                        apply_sox_effects(final_path, post_effects if isinstance(post_effects, list) else [post_effects])
                        print(f"[RESOURCE-ACCESS] Post-effects applied", file=sys.stderr)
                        print(f"  audio_path: {final_path}", file=sys.stderr)

    finally:
        # Guaranteed cleanup: Close TTS provider to free resources
        if provider:
            try:
                provider.close()
                print("TTS provider closed successfully.")
            except Exception as e:
                print(f"Warning: Error closing TTS provider: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
