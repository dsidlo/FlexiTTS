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
import traceback
from pathlib import Path
from xml.etree import ElementTree as ET
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from chapter_validate_xml import validate_and_fix_xml
from chapter_render_state import (
    load_render_state,
    save_render_state,
    remove_stale_clip_files,
    update_render_state_with_new_clips,
    ChapterRenderState
)
from log_utils import setup_script_logging

logger = setup_script_logging('chapter_xml_to_audio')


def log_debug(event: str, **kwargs: Any) -> None:
    """Structured debug logging for key control flow and variables."""
    try:
        details = " ".join(f"{key}={repr(value)}" for key, value in kwargs.items())
        if details:
            logger.info(f"{event} {details}")
        else:
            logger.info(event)
    except Exception as e:
        logger.info(f"{event} log_error={e!r}")


def log_exception(event: str, exc: Exception, **kwargs: Any) -> None:
    try:
        logger.exception(f"{event} error_type={type(exc).__name__} error={exc!r} context={kwargs!r}")
        log_debug(event, error_type=type(exc).__name__, error=str(exc), traceback=traceback.format_exc(), **kwargs)
    except Exception as log_err:
        logger.info(f"{event} log_exception_error={log_err!r}")

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


def normalize_sequence_value(value: Optional[str], default: str = "000") -> str:
    if value is None:
        return default
    text = str(value).strip()
    if not text:
        return default
    return text.zfill(3)


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
    logger.info(f"parse_xml xml_path={xml_path}")
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
    root_tag = root.tag
    match = re.search(r"(\d+)", xml_path.name)
    chapter_num = match.group(1) if match else "000"
    utterances = []

    logger.info(f"parse_xml root_tag={root_tag} xml_path={xml_path}")
    print(f"[RESOURCE-ACCESS] Inspecting XML structure for audio generation", file=sys.stderr)
    print(f"  xml_path: {xml_path}", file=sys.stderr)
    print(f"  root: {root_tag}", file=sys.stderr)

    def append_utterances(nodes, section_num: str):
        for node in nodes:
            if node.tag in ("dialog", "narration"):
                legacy_id = node.attrib.get("id")
                dlgseq = normalize_sequence_value(node.attrib.get("dlgseq") or legacy_id, "000")
                emotion = node.attrib.get("emotion", "neutral")
                post_effects = node.attrib.get("post-effects")
                speaker = node.attrib.get("character", "unknown") if node.tag == "dialog" else "narrator"
                text = normalize_ws("".join(node.itertext()))
                if legacy_id and "dlgseq" not in node.attrib:
                    logger.warning(f"parse_xml found legacy id without dlgseq xml_path={xml_path} legacy_id={legacy_id}")
                    print(f"[RESOURCE-ACCESS] Legacy XML attribute fallback", file=sys.stderr)
                    print(f"  xml_path: {xml_path}", file=sys.stderr)
                    print(f"  fallback: id->dlgseq", file=sys.stderr)
                    print(f"  legacy_id: {legacy_id}", file=sys.stderr)
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

    sections = root.findall("section")
    if sections:
        for section in sections:
            section_num = normalize_sequence_value(section.attrib.get("seq"), "000")
            append_utterances(section, section_num)
    else:
        append_utterances(root, "000")

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


QWEN3_DOC_SUPPORTED_SPEAKERS = {
    "vivian",
    "serena",
    "uncle_fu",
    "dylan",
    "eric",
    "ryan",
    "aiden",
    "ono_anna",
    "sohee",
}


def validate_character_voice_setup(config: Dict[str, Any], utterances: List[Utterance], voices_dir: Path) -> List[str]:
    """Validate character/voice configuration before generation starts.

    Checks local config/file prerequisites plus docs-based Qwen3 speaker validity:
    - each referenced speaker exists in story-config.yml
    - each voice-sample exists on disk
    - each custom-voice has a non-empty speaker
    - each custom-voice speaker matches the documented Qwen3 CustomVoice speaker set
    """
    errors: List[str] = []
    char_configs = {str(c.get("name", "")).strip().lower(): c for c in config.get("characters", []) if c.get("name")}
    seen_speakers = sorted({utt.speaker.strip().lower() for utt in utterances if utt.speaker and utt.kind == "dialog"})

    for speaker_key in seen_speakers:
        char_cfg = char_configs.get(speaker_key)
        if not char_cfg:
            errors.append(f"Character '{speaker_key}' is referenced in XML but missing from story-config.yml")
            continue

        custom_voice = char_cfg.get("custom-voice")
        voice_sample = char_cfg.get("voice-sample")

        if custom_voice:
            custom_speaker = str(custom_voice.get("speaker", "")).strip()
            if not custom_speaker:
                errors.append(f"Character '{speaker_key}' custom-voice speaker is missing")
                continue
            if custom_speaker.lower() not in QWEN3_DOC_SUPPORTED_SPEAKERS:
                allowed = ", ".join(sorted(QWEN3_DOC_SUPPORTED_SPEAKERS))
                errors.append(
                    f"Character '{speaker_key}' custom-voice speaker '{custom_speaker}' is not in documented Qwen3-TTS speakers: {allowed}"
                )
            continue

        if voice_sample:
            sample_text = str(voice_sample).strip()
            if not sample_text:
                errors.append(f"Character '{speaker_key}' voice-sample is empty")
                continue
            sample_path = Path(sample_text)
            resolved_sample = sample_path if sample_path.is_absolute() else (voices_dir / sample_path).resolve()
            if not resolved_sample.exists():
                errors.append(f"Character '{speaker_key}' voice-sample not found: {resolved_sample}")
            continue

        errors.append(f"Character '{speaker_key}' has neither voice-sample nor custom-voice configured")

    return errors


def emit_render_alert(provider, message: str, alert_type: str = "info", metadata: Optional[Dict[str, Any]] = None) -> bool:
    """Best-effort alert forwarding for chapter render progress."""
    log_debug(
        "emit_render_alert:enter",
        provider_type=type(provider).__name__ if provider is not None else None,
        has_provider=provider is not None,
        message=message,
        alert_type=alert_type,
        metadata=metadata,
    )
    if provider is None:
        log_debug("emit_render_alert:skip", reason="provider_none")
        return False
    send_sync = getattr(provider, "send_alert_sync", None)
    if not callable(send_sync):
        log_debug("emit_render_alert:skip", reason="send_alert_sync_missing", provider_type=type(provider).__name__)
        return False
    try:
        result = bool(send_sync(message, alert_type=alert_type, metadata=metadata or {}))
        log_debug("emit_render_alert:result", result=result, message=message, alert_type=alert_type)
        return result
    except Exception as e:
        logger.warning(f"emit_render_alert failed message={message} error={e}")
        log_debug("emit_render_alert:exception", error_type=type(e).__name__, error=str(e), message=message)
        return False


def move_path_to_trash_or_delete(path: Path) -> str:
    """Best-effort stale clip cleanup.

    Returns the cleanup method used: 'trash' or 'delete'.
    """
    try:
        from send2trash import send2trash  # type: ignore
        send2trash(str(path))
        return "trash"
    except Exception:
        path.unlink(missing_ok=True)
        return "delete"


def cleanup_stale_chapter_clips(chapter_clip_dir: Path, keep_paths: List[Path]) -> Tuple[int, List[str], List[Dict[str, str]]]:
    """Remove/trash stale wav clips after full chapter render.

    Keeps only the expected dialog-associated clip files for the current chapter.
    """
    keep_set = {str(path.resolve()) for path in keep_paths}
    removed_paths: List[str] = []
    removed_details: List[Dict[str, str]] = []

    if not chapter_clip_dir.exists():
        return 0, removed_paths, removed_details

    for wav_path in sorted(chapter_clip_dir.glob("*.wav")):
        resolved = str(wav_path.resolve())
        if resolved in keep_set:
            continue
        cleanup_method = move_path_to_trash_or_delete(wav_path)
        removed_paths.append(str(wav_path))
        removed_details.append({"path": str(wav_path), "method": cleanup_method})
        log_debug(
            "main:stale_clip_removed",
            clip_path=str(wav_path),
            method=cleanup_method,
            chapter_clip_dir=str(chapter_clip_dir),
        )

    return len(removed_paths), removed_paths, removed_details


def main():
    log_debug("main:start", argv=sys.argv)
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
    log_debug(
        "main:args_parsed",
        xml_file=args.xml_file,
        config=args.config,
        dry_run=args.dry_run,
        section=args.section,
        dlgseq=args.dlgseq,
        create_missing_clips=args.create_missing_clips,
        create_silent_clips=args.create_silent_clips,
        tts_service=args.tts_service,
    )

    # Determine XML path first (needed for auto-detect)
    xml_path = Path(args.xml_file) if args.xml_file else None
    
    # Load config from explicit path, auto-detect, or fall back to CWD
    config_path = Path(args.config) if args.config else find_config_file(xml_path)
    
    log_debug("main:config_resolved", xml_path=str(xml_path) if xml_path else None, config_path=str(config_path) if config_path else None)
    if not config_path:
        log_debug("main:exit", reason="config_not_found")
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
    log_debug("main:config_loaded", config_base_dir=str(config_base_dir), global_keys=sorted(global_cfg.keys()), character_count=len(config.get("characters", [])))

    configured_story_dir = Path(global_cfg.get("story-dir", "."))
    story_dir = configured_story_dir if configured_story_dir.is_absolute() else (config_base_dir / configured_story_dir).resolve()
    if not story_dir.exists():
        log_debug("main:story_dir_fallback", configured_story_dir=str(configured_story_dir), attempted_story_dir=str(story_dir), fallback=str(config_base_dir))
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
    log_debug(
        "main:paths_resolved",
        story_name=story_name,
        story_dir=str(story_dir),
        story_xml_dir=str(story_xml_dir),
        story_audio_dir=str(story_audio_dir),
        clips_dir=str(clips_dir),
        voices_dir=str(voices_dir),
        clip_separation=clip_separation,
    )

    story_audio_dir.mkdir(parents=True, exist_ok=True)

    def resolve_voice_sample_path(voice_sample: str) -> str:
        sample_path = Path(voice_sample)
        if sample_path.is_absolute():
            return str(sample_path)
        return str((voices_dir / sample_path).resolve())

    # Normalize character voice-sample paths against global.voices
    for char_cfg in config.get("characters", []):
        voice_sample = char_cfg.get("voice-sample")
        if voice_sample:
            resolved_voice_sample = resolve_voice_sample_path(voice_sample)
            log_debug(
                "main:voice_sample_resolved",
                character=char_cfg.get("name"),
                original=voice_sample,
                resolved=resolved_voice_sample,
            )
            char_cfg["voice-sample"] = resolved_voice_sample

    # xml_path was determined earlier for auto-detect, but finalize it here
    if xml_path and not xml_path.is_absolute():
        log_debug("main:xml_path_relative", original=str(xml_path))
        candidate_paths = [
            (Path.cwd() / xml_path).resolve(),
            (config_base_dir / xml_path).resolve(),
            (story_dir / xml_path).resolve(),
            (story_xml_dir / xml_path.name).resolve(),
        ]
        log_debug("main:xml_candidates", candidates=[str(candidate) for candidate in candidate_paths])
        for candidate in candidate_paths:
            if candidate.exists():
                xml_path = candidate
                log_debug("main:xml_candidate_selected", candidate=str(candidate))
                break

    if not xml_path:
        xml_path = next(story_xml_dir.glob("*.xml"), None)
        log_debug("main:xml_autodetect", selected=str(xml_path) if xml_path else None)
    if not xml_path or not xml_path.exists():
        log_debug("main:exit", reason="xml_not_found", xml_path=str(xml_path) if xml_path else None)
        print(f"XML file not found: {xml_path}")
        return

    log_debug("main:xml_final", xml_path=str(xml_path))
    print(f"Validating {xml_path}...")
    validation_ok = validate_and_fix_xml(str(xml_path))
    log_debug("main:xml_validation_result", xml_path=str(xml_path), validation_ok=validation_ok)
    if not validation_ok:
        log_debug("main:exit", reason="xml_validation_failed", xml_path=str(xml_path))
        print(f"XML validation failed")
        return

    print(f"Processing {xml_path}...")
    utterances = parse_xml(xml_path)
    log_debug("main:utterances_parsed", count=len(utterances), xml_path=str(xml_path))

    if args.dry_run:
        print("Dry-run summary: sections and utterances detected")
        sections_summary = {}
        for utt in utterances:
            sections_summary.setdefault(utt.section_num, []).append(utt)
        if not sections_summary:
            print("  No sections or utterances found.")
        for section in sorted(sections_summary.keys()):
            print(f"Section {section} ({len(sections_summary[section])} utterance(s)):")
            for utt in sections_summary[section]:
                preview = (utt.text[:57] + '...') if len(utt.text) > 60 else utt.text
                print(f"  [{utt.kind}] dlgseq={utt.dlgseq} speaker={utt.speaker} emotion={utt.emotion} :: {preview}")

    preflight_errors = validate_character_voice_setup(config, utterances, voices_dir)
    if preflight_errors:
        log_debug("main:preflight_validation_failed", error_count=len(preflight_errors), errors=preflight_errors)
        print("Preflight validation failed:")
        for error in preflight_errors:
            print(f"- {error}")
        if args.dry_run:
            print("Continuing dry-run despite preflight issues.")
        else:
            return

    if args.section:
        before_count = len(utterances)
        utterances = [u for u in utterances if u.section_num == args.section.zfill(3)]
        log_debug("main:filter_section", requested=args.section, normalized=args.section.zfill(3), before=before_count, after=len(utterances))
    if args.dlgseq:
        before_count = len(utterances)
        utterances = [u for u in utterances if u.dlgseq == args.dlgseq.zfill(3)]
        log_debug("main:filter_dlgseq", requested=args.dlgseq, normalized=args.dlgseq.zfill(3), before=before_count, after=len(utterances))

    by_character = {}
    for utt in utterances:
        by_character.setdefault(utt.speaker, []).append(utt)
    log_debug("main:utterances_grouped", speakers={speaker: len(items) for speaker, items in by_character.items()})

    char_configs = {c["name"].lower(): c for c in config.get("characters", [])}
    dialog_effects_cfg = {e["name"]: e.get("sox-effects", []) for e in config.get("dialog-effects", [])}
    log_debug("main:config_maps_ready", character_keys=sorted(char_configs.keys()), dialog_effect_names=sorted(dialog_effects_cfg.keys()))

    provider = None
    if not args.dry_run and create_tts_provider:
        tts_type = "remote" if args.tts_service else "local"
        log_debug("main:provider_init_start", tts_type=tts_type, tts_service=args.tts_service, create_tts_provider_available=bool(create_tts_provider))
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
            log_debug("main:provider_init_success", provider_type=type(provider).__name__, provider_elapsed=round(provider_elapsed, 3), service_url=args.tts_service)
            
            # Check service warmup status
            print("  [TTS] Checking service warmup status...")
            try:
                from tts_service import RemoteTTSProvider
                import asyncio
                health_provider = RemoteTTSProvider(args.tts_service)
                health = asyncio.run(health_provider.health_check())
                print(f"  [TTS] Service status: {health.get('status', 'unknown')}, ready: {health.get('ready', False)}, cached: {health.get('model_cached', False)}")
                log_debug("main:provider_health", health=health)
                health_provider.close()
                if not health.get('ready', False):
                    log_debug("main:provider_health_not_ready", health=health, service_url=args.tts_service)
                    raise RuntimeError(f"TTS service not ready: {health}")
            except Exception as e:
                log_debug("main:provider_health_failed", error_type=type(e).__name__, error=str(e))
                print(f"  [TTS] Could not check warmup status: {e}")
        except TTSConnectionError as e:
            log_debug("main:provider_init_failed", error_type=type(e).__name__, error=str(e), stage="connection")
            print(f"ERROR: TTS connection failed: {e}", file=sys.stderr)
            raise RuntimeError(f"TTS connection failed: {e}") from e
        except TTSGenerationError as e:
            log_debug("main:provider_init_failed", error_type=type(e).__name__, error=str(e), stage="generation")
            print(f"ERROR: TTS initialization failed: {e}", file=sys.stderr)
            raise RuntimeError(f"TTS provider initialization failed: {e}") from e
        except TTSError as e:
            log_debug("main:provider_init_failed", error_type=type(e).__name__, error=str(e), stage="tts_error")
            print(f"ERROR: TTS provider error: {e}", file=sys.stderr)
            raise RuntimeError(f"TTS provider error: {e}") from e
        except Exception as e:
            log_debug("main:provider_init_failed", error_type=type(e).__name__, error=str(e), stage="unexpected")
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

        # Load and check render state
        render_state = load_render_state(clips_dir, xml_path.stem)
        render_state.story = story_name
        render_state.chapter = xml_path.stem[:3].lstrip('0') or '001'
        render_state.xml_path = str(xml_path)
        render_state.clips_dir = str(chapter_clip_dir)
        
        from chapter_render_state import compute_file_md5, parse_xml_dialogs
        render_state.xml_hash = compute_file_md5(xml_path)
        
        # Check for stale/missing dialogs
        current_dialogs = parse_xml_dialogs(xml_path)
        stale_dialogs = []
        
        for dialog_id, current_hash in current_dialogs.items():
            stored_state = render_state.dialogs.get(dialog_id)
            
            if stored_state is None:
                stale_dialogs.append(dialog_id)
                log_debug("main:dialog_new", dialog_id=dialog_id, reason="never_rendered")
                continue
            
            if stored_state.hash != current_hash:
                stale_dialogs.append(dialog_id)
                log_debug("main:dialog_changed", dialog_id=dialog_id, reason="hash_mismatch")
                continue
            
            # Check if clip file still exists
            if stored_state.clip_file:
                clip_path = chapter_clip_dir / stored_state.clip_file
                if not clip_path.exists():
                    stale_dialogs.append(dialog_id)
                    stored_state.clip_exists = False
                    log_debug("main:dialog_missing", dialog_id=dialog_id, reason="file_deleted")
        
        render_state.stale_dialogs = stale_dialogs
        render_state.needs_render = len(stale_dialogs) > 0
        
        # Delete stale clip files to force re-rendering
        if stale_dialogs and args.create_missing_clips:
            log_debug("main:deleting_stale_clips", count=len(stale_dialogs))
            removed = remove_stale_clip_files(render_state, clips_dir, xml_path.stem)
            if removed:
                log_debug("main:stale_clips_removed", count=len(removed), files=removed)
        
        all_generated_clips = []
        expected_clip_paths: List[Path] = []

        for character, utts in by_character.items():
            print(f"Generating audio for {character}...")
            char_cfg = char_configs.get(character.lower())
            log_debug("main:character_loop", character=character, utterance_count=len(utts), char_config_found=bool(char_cfg))
            if not char_cfg:
                log_debug("main:character_skipped", reason="missing_character_config", character=character)
                print(f"No config for {character}, skipping")
                continue

            for utt in utts:
                base = f"chapter_{utt.chapter_num}_{utt.section_num}_{utt.dlgseq}_{utt.speaker}"
                out_path = chapter_clip_dir / f"{base}.wav"
                log_debug(
                    "main:utterance_start",
                    character=character,
                    chapter=utt.chapter_num,
                    section=utt.section_num,
                    dlgseq=utt.dlgseq,
                    speaker=utt.speaker,
                    emotion=utt.emotion,
                    kind=utt.kind,
                    text_length=len(utt.text),
                    out_path=str(out_path),
                )

                if args.create_missing_clips and out_path.exists():
                    log_debug("main:utterance_skipped", reason="clip_exists", out_path=str(out_path), base=base)
                    print(f"  Skipping {base} (exists)")
                    expected_clip_paths.append(out_path)
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
                log_debug("main:utterance_voice_mode", speaker=utt.speaker, is_custom=is_custom, language=lang, instruct=instruct)

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

                render_metadata = {
                    "story": story_name,
                    "chapter": utt.chapter_num,
                    "section": utt.section_num,
                    "dialog": utt.dlgseq,
                    "character": utt.speaker,
                    "emotion": utt.emotion,
                    "kind": utt.kind,
                    "text_length": len(utt.text),
                    "text_preview": utt.text[:120],
                    "clip_path": str(out_path),
                    "stage": "rendering",
                }
                log_debug("main:render_alert_start_attempt", message=f"Rendering {utt.kind} {utt.dlgseq} for {utt.speaker}", metadata=render_metadata)
                alert_sent = emit_render_alert(
                    provider,
                    f"Rendering {utt.kind} {utt.dlgseq} for {utt.speaker}",
                    alert_type="info",
                    metadata=render_metadata,
                )
                logger.info(
                    f"render_alert_start sent={alert_sent} story={story_name} chapter={utt.chapter_num} "
                    f"section={utt.section_num} dialog={utt.dlgseq} speaker={utt.speaker}"
                )

                # Validate text length limit (2K character max)
                if len(utt.text) > 2000:
                    print(f"    ERROR: Text too long: {len(utt.text)} chars (max 2000)", file=sys.stderr)
                    print(f"    Truncating...", file=sys.stderr)
                    utt.text = utt.text[:2000]

                # Check if provider supports this character configuration
                if not args.dry_run and provider:
                    try:
                        supports_character = provider.supports_character(char_cfg) if char_cfg else True
                        log_debug("main:supports_character_checked", character=character, supports_character=supports_character)
                        if char_cfg and not supports_character:
                            print(f"    WARNING: Provider does not fully support character config for {character}", file=sys.stderr)
                            print(f"    Attempting generation anyway...", file=sys.stderr)
                    except Exception as e:
                        log_debug("main:supports_character_failed", character=character, error_type=type(e).__name__, error=str(e))
                        print(f"    WARNING: Could not verify character support: {e}", file=sys.stderr)

                    try:
                        log_debug("main:provider_generate_call", service_url=args.tts_service, speaker=utt.speaker, chapter=utt.chapter_num, section=utt.section_num, dialog=utt.dlgseq, text_length=len(utt.text))
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
                        log_debug("main:provider_generate_success", speaker=utt.speaker, chapter=utt.chapter_num, section=utt.section_num, dialog=utt.dlgseq, wav_count=len(wavs), sample_rate=sr, elapsed_seconds=round(gen_elapsed, 3))
                        print(f"[RESOURCE-ACCESS] Audio clip generated", file=sys.stderr)
                        print(f"  output_path: {out_path}", file=sys.stderr)
                        print(f"  wavCount: {len(wavs)}", file=sys.stderr)
                        print(f"  sampleRate: {sr}", file=sys.stderr)
                        log_debug(
                            "main:clip_generation_adopted",
                            speaker=utt.speaker,
                            chapter=utt.chapter_num,
                            section=utt.section_num,
                            dialog=utt.dlgseq,
                            requested_output_path=str(out_path),
                            chapter_clip_dir=str(chapter_clip_dir),
                            base_name=base,
                            wav_count=len(wavs),
                            sample_rate=sr,
                            provider_type=type(provider).__name__ if provider else None,
                        )
                        written_clip_paths = []
                        for i, wav in enumerate(wavs):
                            suffix = f"_s{str(i+1).zfill(3)}" if len(wavs) > 1 else ""
                            clip_path = chapter_clip_dir / f"{base}{suffix}.wav"
                            sf.write(str(clip_path), wav, sr)
                            expected_clip_paths.append(clip_path)
                            written_clip_paths.append(str(clip_path))
                            print(f"[RESOURCE-ACCESS] Audio clip written", file=sys.stderr)
                            print(f"  clip_path: {clip_path}", file=sys.stderr)
                            print(f"  resourceType: audio", file=sys.stderr)
                            log_debug(
                                "main:clip_written_final",
                                speaker=utt.speaker,
                                chapter=utt.chapter_num,
                                section=utt.section_num,
                                dialog=utt.dlgseq,
                                clip_index=i + 1,
                                clip_path=str(clip_path),
                                base_name=base,
                                wav_count=len(wavs),
                                sample_rate=sr,
                            )

                        success_metadata = {
                            **render_metadata,
                            "stage": "rendered",
                            "duration_seconds": round(gen_elapsed, 3),
                            "sample_rate": sr,
                            "wav_count": len(wavs),
                            "clip_paths": written_clip_paths,
                        }
                        log_debug("main:render_alert_success_attempt", message=f"Rendered {utt.kind} {utt.dlgseq} for {utt.speaker}", metadata=success_metadata)
                        alert_sent = emit_render_alert(
                            provider,
                            f"Rendered {utt.kind} {utt.dlgseq} for {utt.speaker}",
                            alert_type="success",
                            metadata=success_metadata,
                        )
                        logger.info(
                            f"render_alert_success sent={alert_sent} story={story_name} chapter={utt.chapter_num} "
                            f"section={utt.section_num} dialog={utt.dlgseq} speaker={utt.speaker} duration={gen_elapsed:.3f}s"
                        )
                    except CharacterNotSupportedError as e:
                        log_exception("main:render_character_not_supported", e, speaker=utt.speaker, chapter=utt.chapter_num, section=utt.section_num, dialog=utt.dlgseq, clip_path=str(out_path))
                        failure_metadata = {**render_metadata, "stage": "failed", "error": str(e), "error_type": type(e).__name__}
                        log_debug("main:render_alert_failure_attempt", message=f"Failed {utt.kind} {utt.dlgseq} for {utt.speaker}", metadata=failure_metadata)
                        emit_render_alert(
                            provider,
                            f"Failed {utt.kind} {utt.dlgseq} for {utt.speaker}",
                            alert_type="error",
                            metadata=failure_metadata,
                        )
                        print(f"    ERROR: Character not supported by TTS provider: {e}")
                        continue
                    except TTSConnectionError as e:
                        log_exception("main:render_tts_connection_error", e, speaker=utt.speaker, chapter=utt.chapter_num, section=utt.section_num, dialog=utt.dlgseq, clip_path=str(out_path), service_url=args.tts_service)
                        failure_metadata = {**render_metadata, "stage": "failed", "error": str(e), "error_type": type(e).__name__}
                        log_debug("main:render_alert_failure_attempt", message=f"Failed {utt.kind} {utt.dlgseq} for {utt.speaker}", metadata=failure_metadata)
                        emit_render_alert(
                            provider,
                            f"Failed {utt.kind} {utt.dlgseq} for {utt.speaker}",
                            alert_type="error",
                            metadata=failure_metadata,
                        )
                        print(f"    ERROR: TTS connection failed: {e}")
                        print(f"    Check TTS service availability and network connectivity.")
                        # Don't fall back - --tts-service was explicitly requested
                        raise RuntimeError(f"TTS service connection failed: {e}") from e
                    except TTSGenerationError as e:
                        log_exception("main:render_tts_generation_error", e, speaker=utt.speaker, chapter=utt.chapter_num, section=utt.section_num, dialog=utt.dlgseq, clip_path=str(out_path), service_url=args.tts_service)
                        failure_metadata = {**render_metadata, "stage": "failed", "error": str(e), "error_type": type(e).__name__}
                        log_debug("main:render_alert_failure_attempt", message=f"Failed {utt.kind} {utt.dlgseq} for {utt.speaker}", metadata=failure_metadata)
                        emit_render_alert(
                            provider,
                            f"Failed {utt.kind} {utt.dlgseq} for {utt.speaker}",
                            alert_type="error",
                            metadata=failure_metadata,
                        )
                        print(f"    ERROR: TTS generation failed: {e}")
                        print(f"    Text may be too complex or unsupported.")
                        continue
                    except TTSError as e:
                        log_exception("main:render_tts_error", e, speaker=utt.speaker, chapter=utt.chapter_num, section=utt.section_num, dialog=utt.dlgseq, clip_path=str(out_path), service_url=args.tts_service)
                        failure_metadata = {**render_metadata, "stage": "failed", "error": str(e), "error_type": type(e).__name__}
                        log_debug("main:render_alert_failure_attempt", message=f"Failed {utt.kind} {utt.dlgseq} for {utt.speaker}", metadata=failure_metadata)
                        emit_render_alert(
                            provider,
                            f"Failed {utt.kind} {utt.dlgseq} for {utt.speaker}",
                            alert_type="error",
                            metadata=failure_metadata,
                        )
                        print(f"    ERROR: TTS error: {e}")
                        continue
                    except Exception as e:
                        log_exception("main:render_unexpected_error", e, speaker=utt.speaker, chapter=utt.chapter_num, section=utt.section_num, dialog=utt.dlgseq, clip_path=str(out_path), service_url=args.tts_service)
                        failure_metadata = {**render_metadata, "stage": "failed", "error": str(e), "error_type": type(e).__name__}
                        log_debug("main:render_alert_failure_attempt", message=f"Failed {utt.kind} {utt.dlgseq} for {utt.speaker}", metadata=failure_metadata)
                        emit_render_alert(
                            provider,
                            f"Failed {utt.kind} {utt.dlgseq} for {utt.speaker}",
                            alert_type="error",
                            metadata=failure_metadata,
                        )
                        print(f"    ERROR: Unexpected error during generation: {type(e).__name__}: {e}")
                        traceback.print_exc()
                        continue
                else:
                    log_debug("main:dry_run_generation", base=base, sample_rate=24000)
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
                    log_debug("main:apply_character_effects", out_path=str(out_path), effects=final_effects)
                    apply_sox_effects(out_path, final_effects)

                if utt.post_effects and not args.dry_run:
                    for name in utt.post_effects.split(","):
                        effects = dialog_effects_cfg.get(name.strip())
                        if effects:
                            log_debug("main:apply_post_effects", out_path=str(out_path), effect_name=name.strip(), effects=effects)
                            apply_sox_effects(out_path, effects)

                if args.create_silent_clips and clip_separation > 0 and not args.dry_run:
                    silence_path = chapter_clip_dir / f"chapter_{utt.chapter_num}_{utt.section_num}_{utt.dlgseq}_~silence.wav"
                    sf.write(str(silence_path), generate_silence(clip_separation, sr), sr)
                    expected_clip_paths.append(silence_path)
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

                    # Update render state with newly generated clips
                    if not args.dry_run:
                        updated_state = update_render_state_with_new_clips(
                            render_state,
                            all_generated_clips,
                            clips_dir,
                            xml_path.stem
                        )
                        log_debug(
                            "main:render_state_updated",
                            dialog_count=len(updated_state.dialogs),
                            is_fully_rendered=updated_state.is_fully_rendered,
                            needs_render=updated_state.needs_render,
                        )
                    
                    stale_removed_count, stale_removed_paths, stale_removed_details = cleanup_stale_chapter_clips(
                        chapter_clip_dir,
                        expected_clip_paths,
                    )
                    log_debug(
                        "main:stale_clip_cleanup_complete",
                        chapter_clip_dir=str(chapter_clip_dir),
                        expected_clip_count=len(expected_clip_paths),
                        removed_count=stale_removed_count,
                        removed_paths=stale_removed_paths,
                    )

                    chapter_success_metadata = {
                        "story": story_name,
                        "chapter": all_generated_clips[0][0].chapter_num if all_generated_clips else None,
                        "kind": "chapter",
                        "stage": "rendered",
                        "chapter_xml": str(xml_path),
                        "final_audio_path": str(final_path),
                        "clip_count": len(all_generated_clips),
                        "sample_rate": final_sr,
                        "stale_clip_cleanup_removed_count": stale_removed_count,
                        "stale_clip_cleanup_removed": stale_removed_details,
                    }
                    log_debug(
                        "main:chapter_render_alert_success_attempt",
                        message=f"Rendered chapter audio {xml_path.stem}",
                        metadata=chapter_success_metadata,
                    )
                    chapter_alert_sent = emit_render_alert(
                        provider,
                        f"Rendered chapter audio {xml_path.stem}",
                        alert_type="success",
                        metadata=chapter_success_metadata,
                    )
                    logger.info(
                        f"chapter_render_alert_success sent={chapter_alert_sent} story={story_name} "
                        f"chapter={chapter_success_metadata['chapter']} final_audio_path={final_path} "
                        f"clip_count={len(all_generated_clips)} sample_rate={final_sr} "
                        f"stale_removed_count={stale_removed_count}"
                    )

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
