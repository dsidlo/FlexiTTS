#!/usr/bin/env python3

import argparse
import os
import re
import yaml
import torch
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

# Import Qwen3-TTS
# Note: Ensure qwen_tts is in the python path or installed
try:
    from qwen_tts import Qwen3TTSModel
except ImportError:
    import sys
    sys.path.append(os.path.join(os.getcwd(), "Qwen3-TTS"))
    from qwen_tts import Qwen3TTSModel

@dataclass
class Utterance:
    chapter_num: str
    section_num: str
    dlgseq: str
    speaker: str
    emotion: str
    text: str
    kind: str # 'dialog' or 'narration'
    post_effects: Optional[str] = None

def normalize_ws(s: str) -> str:
    if not s:
        return ""
    s = s.replace("\r", " ").replace("\n", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s

def apply_sox_effects(input_path: Path, effects_list: List[str], dry_run: bool = False):
    """
    Apply sox effects to a wav file.
    The process is to use sox to apply the clip to a temp-<random_test>.wav file,
    then the original wav file is removed, and the temp wav file is renamed with
    the original file's full filename.
    """
    if not effects_list:
        return

    for effects_str in effects_list:
        if not effects_str:
            continue

        random_str = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
        temp_path = input_path.parent / f"temp-{random_str}.wav"
        
        # Split effects_str while respecting potential quotes (though simple split might work for most)
        # Sox expects effects as separate arguments.
        effects_cmd = effects_str.split()
        
        cmd = ["sox", str(input_path), str(temp_path)] + effects_cmd
        
        if dry_run:
            print(f"    [Dry-run] Would run: {' '.join(cmd)}")
            # For dry run, we don't actually create the temp file, 
            # so we can't continue the loop if it relies on the output of the previous step.
            # But we can still print what would happen.
            continue

        try:
            subprocess.run(cmd, check=True, capture_output=True)
            # Remove original and rename temp
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
    tree = ET.parse(xml_path)
    root = tree.getroot()
    
    # Try to extract chapter number from filename
    # chapter_001_... -> 001
    match = re.search(r"(\d+)", xml_path.name)
    chapter_num = match.group(1) if match else "000"
    
    utterances = []
    
    # Iterate through sections
    for section in root.findall("section"):
        section_num = section.attrib.get("seq", "000").zfill(3)
        
        for node in section:
            if node.tag in ("dialog", "narration"):
                dlgseq = node.attrib.get("dlgseq", "000").zfill(3)
                emotion = node.attrib.get("emotion", "neutral")
                post_effects = node.attrib.get("post-effects")
                
                if node.tag == "dialog":
                    speaker = node.attrib.get("character", "unknown")
                else:
                    speaker = "narrator"
                
                text = normalize_ws("".join(node.itertext()))
                if not text:
                    continue
                
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

def main():
    parser = argparse.ArgumentParser(description="Convert XML chapters to audio using Qwen3-TTS")
    parser.add_argument("xml_file", nargs="?", help="Path to the chapter XML file")
    parser.add_argument("--dry-run", action="store_true", help="Dry run: process XML but don't generate audio")
    parser.add_argument("--section", type=str, help="Only generate/regenerate audio for this section number (e.g., 1 or 001)")
    parser.add_argument("--dlgseq", type=str, help="Only generate/regenerate audio for this dlgseq number (e.g., 1 or 001)")
    parser.add_argument("--create-missing-clips", action="store_true", help="Only generate audio clips that are missing from the clips directory")
    parser.add_argument("--create-silent-clips", action="store_true", help="Create silent audio clips between clips, naming them with ~silence suffix")
    args = parser.parse_args()

    # Load config
    with open("story-config.yml", "r") as f:
        config = yaml.safe_load(f)
    
    global_cfg = config.get("global", {})
    story_dir = Path(global_cfg.get("story-dir", "."))
    story_xml_dir = story_dir / global_cfg.get("story-xml", "story-xml")
    story_audio_dir = story_dir / global_cfg.get("story-audio", "story-audio")
    clips_dir = story_dir / global_cfg.get("clips", "clips")
    voices_dir = story_dir / global_cfg.get("voices", "refs")
    clip_separation = float(global_cfg.get("clip-separation", 0))
    
    if args.xml_file:
        xml_path = Path(args.xml_file)
    else:
        # Look in story-xml directory
        xml_files = list(story_xml_dir.glob("*.xml"))
        if not xml_files:
            print(f"No XML files found in {story_xml_dir}")
            return
        # Default to the first one or ask? Requirement says "it looks for the file"
        xml_path = xml_files[0]
        print(f"No file path indicated, using {xml_path}")

    if not xml_path.exists():
        # Try relative to story_xml_dir if not found
        alt_path = story_xml_dir / xml_path.name
        if alt_path.exists():
            xml_path = alt_path
        else:
            print(f"File not found: {xml_path}")
            return

    # Validate XML before processing
    print(f"Validating {xml_path}...")
    if not validate_and_fix_xml(str(xml_path)):
        print(f"Aborting: XML validation failed for {xml_path}")
        return

    print(f"Processing {xml_path}...")
    full_utterances = parse_xml(xml_path)
    utterances = list(full_utterances)
    
    # Filter utterances if requested
    if args.section:
        target_section = args.section.zfill(3)
        utterances = [u for u in utterances if u.section_num == target_section]
        if not utterances:
            print(f"No utterances found for section {args.section}")
            return

    if args.dlgseq:
        target_dlgseq = args.dlgseq.zfill(3)
        utterances = [u for u in utterances if u.dlgseq == target_dlgseq]
        if not utterances:
            print(f"No utterances found for dlgseq {args.dlgseq}")
            return
            
    if args.section or args.dlgseq:
        print(f"Filtered to {len(utterances)} utterances.")
    
    # Group by character for optimization
    by_character = {}
    for utt in utterances:
        if utt.speaker not in by_character:
            by_character[utt.speaker] = []
        by_character[utt.speaker].append(utt)
        
    # Get voice samples from config
    char_configs = {}
    for char_info in config.get("characters", []):
        char_configs[char_info["name"].lower()] = char_info
    
    # Get dialog-effects from config (mapping name to list of effects)
    dialog_effects_cfg = {}
    for eff in config.get("dialog-effects", []):
        dialog_effects_cfg[eff["name"]] = eff.get("sox-effects", [])
    
    # Setup Qwen3-TTS
    if not args.dry_run:
        print("Loading Qwen3-TTS models...")
        # Clear CUDA memory if available before loading models
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            
        # Check if we need VoiceDesign or CustomVoice models
        need_custom = any("custom-voice" in cfg for cfg in char_configs.values())
        
        # Base model for voice cloning
        base_model = Qwen3TTSModel.from_pretrained(
            "Qwen/Qwen3-TTS-12Hz-1.7B-Base",
            device_map="cuda:0" if torch.cuda.is_available() else "cpu",
            dtype=torch.bfloat16 if torch.cuda.is_available() else torch.float32,
            attn_implementation="eager",
        )
        
        # Load CustomVoice model if needed (for speaker-id based custom voices)
        custom_model = None
        if need_custom:
             custom_model = Qwen3TTSModel.from_pretrained(
                "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice",
                device_map="cuda:0" if torch.cuda.is_available() else "cpu",
                dtype=torch.bfloat16 if torch.cuda.is_available() else torch.float32,
                attn_implementation="eager",
            )
    else:
        print("Dry run: skipping model loading.")
        base_model = None
        custom_model = None
    
    chapter_clip_dir = clips_dir / xml_path.stem
    chapter_clip_dir.mkdir(parents=True, exist_ok=True)
    story_audio_dir.mkdir(parents=True, exist_ok=True)
    
    # Cleanup unused clips if we are generating missing clips (which means we are doing a full render)
    if args.create_missing_clips:
        print("Cleaning up unused audio clips...")
        # Get all expected base filenames for this chapter from the FULL utterances list
        expected_bases = set()
        for utt in full_utterances:
            # We must zero-pad chapter/section/dlgseq exactly as they're formatted in files
            cnum = str(utt.chapter_num).zfill(3) if str(utt.chapter_num).isdigit() else utt.chapter_num
            snum = str(utt.section_num).zfill(3) if str(utt.section_num).isdigit() else utt.section_num
            dnum = str(utt.dlgseq).zfill(3) if str(utt.dlgseq).isdigit() else utt.dlgseq
            
            base_filename = f"chapter_{cnum}_{snum}_{dnum}_{utt.speaker.lower()}"
            expected_bases.add(base_filename)
            # Add fallback if speaker contains special chars
            safe_speaker = "".join([c if c.isalnum() else "_" for c in utt.speaker.lower()])
            safe_base_filename = f"chapter_{cnum}_{snum}_{dnum}_{safe_speaker}"
            expected_bases.add(safe_base_filename)
            
        # Get all actual files in the directory
        try:
            import send2trash
        except ImportError:
            print("Warning: send2trash not installed. Falls back to permanent deletion.")
            send2trash = None

        for audio_file in chapter_clip_dir.glob("*.wav"):
            # Extract base filename from actual file (remove _sXXX suffix and .wav)
            # Handle standard names and ~silence names
            file_stem = audio_file.stem.lower()
            # Remove ~silence if present to get to the base
            if file_stem.endswith("~silence"):
                file_stem = file_stem[:-8]
            # Remove _sXXX if present to get to the base
            submatch = re.search(r"_s\d+$", file_stem)
            if submatch:
                file_stem = file_stem[:submatch.start()]
                
            # Compare (check if stem exactly matches an expected base)
            is_expected = False
            for base in expected_bases:
                if file_stem == base:
                    is_expected = True
                    break
            
            if not is_expected:
                if not args.dry_run:
                    print(f"  Removing unused clip: {audio_file.name}")
                    try:
                        if send2trash:
                            send2trash.send2trash(str(audio_file))
                        else:
                            os.remove(audio_file)
                    except Exception as e:
                        print(f"  Failed to remove {audio_file.name}: {e}")
                else:
                    print(f"  [Dry-run] Would remove unused clip: {audio_file.name}")

    all_generated_clips = []

    for character, utts in by_character.items():
        print(f"Generating audio for {character}...")
        
        char_cfg = char_configs.get(character.lower())
        if not char_cfg:
            exception_msg = f"Warning: No configuration defined for {character}. Skipping."
            raise ValueError(exception_msg)
            
        is_custom = "custom-voice" in char_cfg
        
        try:
            prompt_items = None
            if not is_custom:
                voice_sample = char_cfg.get("voice-sample")
                if not voice_sample:
                    raise ValueError(f"No voice-sample or custom-voice for {character}")
                
                ref_audio_path = voices_dir / voice_sample
                if not ref_audio_path.exists():
                    raise ValueError(f"Voice sample file not found: {ref_audio_path}")

                if not args.dry_run:
                    prompt_items = base_model.create_voice_clone_prompt(
                        ref_audio=str(ref_audio_path),
                        ref_text="", 
                        x_vector_only_mode=True,
                    )
            
            for utt in utts:
                # Determine output path(s) first to check for existence
                # Note: Qwen3-TTS can return multiple wavs if it segments the text,
                # but usually it's one. The suffix _s001 is used for multiples.
                # If we want to check for existence, we usually look for the first one or the base name.
                # Since we don't know if it WILL segment until we run it, 
                # we'll check for the non-suffixed version or _s001.
                
                base_filename = f"chapter_{utt.chapter_num}_{utt.section_num}_{utt.dlgseq}_{utt.speaker}"
                primary_out_path = chapter_clip_dir / f"{base_filename}.wav"
                secondary_out_path = chapter_clip_dir / f"{base_filename}_s001.wav"
                
                if args.create_missing_clips:
                    if primary_out_path.exists() or secondary_out_path.exists():
                        print(f"  Skipping {base_filename} (already exists)")
                        # If it exists, we need to find all related segments to add them to all_generated_clips
                        # so the concatenation still works correctly.
                        existing_segments = sorted(list(chapter_clip_dir.glob(f"chapter_{utt.chapter_num}_{utt.section_num}_{utt.dlgseq}_{utt.speaker}*.wav")))
                        for path in existing_segments:
                            # Try to extract subseq from filename if present
                            # chapter_001_001_001.wav -> no subseq (0)
                            # chapter_001_001_001_s001.wav -> subseq (0)
                            # chapter_001_001_001_s002.wav -> subseq (1)
                            submatch = re.search(r"_s(\d+)\.wav$", path.name)
                            if submatch:
                                subseq = int(submatch.group(1)) - 1
                            else:
                                subseq = 0
                            all_generated_clips.append((utt, path, subseq))
                        continue

                # Use emotion as instruct prefix if custom-voice has its own instruct
                if is_custom:
                    custom_voice = char_cfg["custom-voice"]
                    lang = custom_voice.get("language", "English")
                    spk = custom_voice.get("speaker")
                    base_instruct = custom_voice.get("instruct", "")
                    instruct = f"{base_instruct}. Speak in a {utt.emotion} tone.".strip(". ")
                else:
                    lang = "English"
                    instruct = f"Speak in a {utt.emotion} tone."
                
                print(f"  Generating {character} {base_filename}...")
                
                if not args.dry_run:
                    if is_custom:
                        wavs, sr = custom_model.generate_custom_voice(
                            text=utt.text,
                            speaker=spk,
                            language=lang,
                            instruct=instruct,
                        )
                    else:
                        wavs, sr = base_model.generate_voice_clone(
                            text=utt.text,
                            language=lang,
                            voice_clone_prompt=prompt_items,
                            instruct=instruct,
                        )
                else:
                    # Mock output for dry run
                    wavs = [np.zeros(1000)]
                    sr = 24000
                
                for i, wav in enumerate(wavs):
                    suffix = f"_s{str(i+1).zfill(3)}" if len(wavs) > 1 else ""
                    filename = f"{base_filename}{suffix}.wav"
                    out_path = chapter_clip_dir / filename
                    if not args.dry_run:
                        sf.write(str(out_path), wav, sr)
                    else:
                        print(f"    [Dry-run] Would save clip to {out_path}")
                    
                    # Apply post-effects
                    # Effect 1: Character-specific effects
                    final_char_effects = []
                    
                    # 1a. Named dialog-effects from character config
                    if "dialog-effects" in char_cfg:
                        named_effs = char_cfg["dialog-effects"]
                        # If it's still a string (though it should be an array), wrap it
                        if isinstance(named_effs, str):
                            named_effs = [named_effs]
                        for named_eff in named_effs:
                            eff_list = dialog_effects_cfg.get(named_eff, [])
                            final_char_effects.extend(eff_list)
                    
                    # 1b. Direct sox-effects from character config
                    sox_effs = char_cfg.get("sox-effects", [])
                    if isinstance(sox_effs, str):
                        sox_effs = [sox_effs]
                    final_char_effects.extend(sox_effs)
                    
                    if final_char_effects:
                        print(f"    Applying character effects to {filename}...")
                        apply_sox_effects(out_path, final_char_effects, args.dry_run)
                    
    # Effect 2: Dialog-specific effects from XML
                    if utt.post_effects:
                        # Split by comma if multiple effects are specified
                        xml_named_effs = [e.strip() for e in utt.post_effects.split(",")]
                        for named_eff in xml_named_effs:
                            xml_effects = dialog_effects_cfg.get(named_eff)
                            if xml_effects:
                                print(f"    Applying XML post-effects '{named_eff}' to {filename}...")
                                apply_sox_effects(out_path, xml_effects, args.dry_run)
                            else:
                                print(f"    Warning: Named dialog-effect '{named_eff}' not found in config.")

                    all_generated_clips.append((utt, out_path, i))

                    # If --create-silent-clips is used and clip_separation > 0, 
                    # create a silent clip after this utterance clip.
                    # We only do this for the last segment of an utterance if it was segmented.
                    if args.create_silent_clips and clip_separation > 0 and i == len(wavs) - 1:
                        silence_filename = f"chapter_{utt.chapter_num}_{utt.section_num}_{utt.dlgseq}_~silence.wav"
                        silence_path = chapter_clip_dir / silence_filename
                        print(f"    Creating silent clip {silence_filename} ({clip_separation}s)...")
                        if not args.dry_run:
                            silence_data = generate_silence(clip_separation, sr)
                            sf.write(str(silence_path), silence_data, sr)
                        else:
                            print(f"    [Dry-run] Would save silent clip to {silence_path}")
                        
                        # We use a special Utterance-like object or just a marker for sorting
                        # but for simplicity in current sorting logic, let's create a dummy Utterance
                        silence_utt = Utterance(
                            chapter_num=utt.chapter_num,
                            section_num=utt.section_num,
                            dlgseq=utt.dlgseq,
                            speaker="~silence",
                            emotion="neutral",
                            text="",
                            kind="silence"
                        )
                        # We give it a high subseq so it sorts after the actual speech segments
                        all_generated_clips.append((silence_utt, silence_path, 999))
                
        except Exception as e:
            print(f"Error generating audio for {character}: {e}")

    # Get story-audio-post-process effects
    post_process_cfg = config.get("story-audio-post-process", {})
    post_process_effects = post_process_cfg.get("sox-effects")

    # Requirement 5.1 says: "The audio files should be placed into the 'story-audio:' directory path, 
    # and should use the same name as the original .xml file but the suffix of the file name should change to .wav"
    # This implies we should concatenate them in the correct order.
    
    if all_generated_clips:
        # If we filtered, we might not want to overwrite the whole chapter wav 
        # unless explicitly requested, but usually if you regenerate a clip, 
        # you'll want the full chapter wav to be updated too.
        # However, to do that correctly we need ALL clips, not just the filtered ones.
        
        if args.section or args.dlgseq:
            print("Selective regeneration: individual clips updated. Final chapter audio NOT updated automatically.")
            print(f"To update the final chapter audio, run without --section or --dlgseq (use --dry-run to test).")
            return

        # Sort by section_num, then dlgseq, then sub-sequence index to ensure correct order
        all_generated_clips.sort(key=lambda x: (x[0].section_num, x[0].dlgseq, x[2]))
    
        combined_wav = []
        final_sr = 24000 
    
        for utt, path, subseq in all_generated_clips:
            if not args.dry_run:
                data, sr = sf.read(str(path))
                final_sr = sr
                combined_wav.append(data)
                
                # If clip-separation > 0 and NOT using --create-silent-clips,
                # we add silence buffer here, EXCEPT after the last clip.
                # If using --create-silent-clips, the silence is already in all_generated_clips.
                if clip_separation > 0 and not args.create_silent_clips:
                    # Check if this is the last clip in the sorted list
                    if (utt, path, subseq) != all_generated_clips[-1]:
                        combined_wav.append(generate_silence(clip_separation, sr))
            else:
                print(f"    [Dry-run] Would append {path} to final audio")
                if clip_separation > 0 and not args.create_silent_clips:
                    if (utt, path, subseq) != all_generated_clips[-1]:
                        print(f"    [Dry-run] Would append {clip_separation}s silence")
            
        if combined_wav and not args.dry_run:
            final_audio = np.concatenate(combined_wav)
            final_wav_path = story_audio_dir / (xml_path.stem + ".wav")
            sf.write(str(final_wav_path), final_audio, final_sr)
            print(f"Final audio saved to {final_wav_path}")
            
            if post_process_effects:
                print(f"Applying story-audio-post-process effects to {final_wav_path.name}...")
                if isinstance(post_process_effects, str):
                    post_process_effects = [post_process_effects]
                apply_sox_effects(final_wav_path, post_process_effects, args.dry_run)
        elif args.dry_run:
            final_wav_path = story_audio_dir / (xml_path.stem + ".wav")
            print(f"    [Dry-run] Would save final audio to {final_wav_path}")
            if post_process_effects:
                print(f"    [Dry-run] Would apply story-audio-post-process effects to {final_wav_path.name}")

if __name__ == "__main__":
    main()
