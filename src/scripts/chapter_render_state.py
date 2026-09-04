#!/usr/bin/env python3
"""
Chapter Render State Management

Manages .chapter_rendered.json files that track:
- MD5 hash of chapter XML file
- MD5 hash of each dialog's text+attributes
- Timestamp of each rendered clip
- File existence validation

Enables fast "needs render?" checks and selective re-rendering.
"""

import hashlib
import json
import time
from pathlib import Path
from typing import Dict, List, Any
from dataclasses import dataclass
from xml.etree import ElementTree as ET

from log_utils import setup_script_logging

logger = setup_script_logging("chapter_render_state")


@dataclass
class DialogRenderState:
    """State for a single dialog.

    Per new design: Only store MD5 signatures and timestamps.
    Everything else is derived from observation of XML + filesystem.
    """

    dialog_id: str  # Format: "{section}_{dlgseq}"
    hash: str  # MD5 of normalized dialog content (the signature)
    rendered_at: int = 0  # Unix timestamp (milliseconds) when last rendered

    def to_dict(self) -> Dict[str, Any]:
        """Only persist essential signature and timestamp data."""
        return {
            "dialog_id": self.dialog_id,
            "hash": self.hash,
            "rendered_at": self.rendered_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DialogRenderState":
        """Load from minimal persisted format."""
        return cls(
            dialog_id=data.get("dialog_id", ""),
            hash=data.get("hash", ""),
            rendered_at=data.get("rendered_at", 0),
        )


@dataclass
class ChapterRenderState:
    """Complete render state for a chapter.

    Per new design: This is derived from observation of current XML
    and filesystem state. The persisted JSON only holds signatures
    (MD5 hashes) and timestamps for efficient comparison.
    """

    version: int = 1
    story: str = ""
    chapter: str = ""
    xml_hash: str = ""  # Last known XML hash (for change detection)
@dataclass
class ChapterRenderState:
    """
    Minimal signature cache for render state tracking.
    
    IMPORTANT: This is NOT application state - it is a signature cache only.
    All render state (needs_render, stale_dialogs, timestamp_stale, etc.) is 
    DERIVED AT RUNTIME from observation of XML + filesystem vs this cache.
    
    Fields stored in .chapter_rendered.json:
    - version: File format version
    - story/chapter: Identifiers
    - xml_hash: Last known XML signature (updated after successful render)
    - xml_path/clips_dir: Path references
    - dialogs: Map of dialog_id → {hash, rendered_at} (signatures + timestamps only)
    - chapter_rendered_at: When chapter audio file was last created
    """
    version: int = 1
    story: str = ""
    chapter: str = ""
    xml_hash: str = ""  # MD5 of XML at last successful render
    xml_path: str = ""
    clips_dir: str = ""
    dialogs: Dict[str, DialogRenderState] = None  # Only stores signatures + timestamps
    chapter_rendered_at: int = 0  # When the chapter as a whole was last rendered (chapter audio file)
    # Note: stale_dialogs, needs_render, timestamp_stale are COMPUTED AT RUNTIME
    # and NOT stored in the signature cache. See get_comprehensive_render_state().

    def __post_init__(self):
        if self.dialogs is None:
            self.dialogs = {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert to minimal persisted format - only signatures and timestamps."""
        return {
            "version": self.version,
            "story": self.story,
            "chapter": self.chapter,
            "xml_hash": self.xml_hash,  # Last known good XML signature
            "xml_path": self.xml_path,
            "clips_dir": self.clips_dir,
            "dialogs": {k: v.to_dict() for k, v in self.dialogs.items()},
            "chapter_rendered_at": self.chapter_rendered_at,
            # Note: All computed fields (needs_render, stale_dialogs, timestamp_stale, etc.)
            # are DERIVED AT RUNTIME and NOT persisted. See get_comprehensive_render_state().
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChapterRenderState":
        """Load from persisted signature store. All state is computed from observation."""
        dialogs = {}
        for k, v in data.get("dialogs", {}).items():
            dialogs[k] = DialogRenderState.from_dict(v)

        return cls(
            version=data.get("version", 1),
            story=data.get("story", ""),
            chapter=data.get("chapter", ""),
            xml_hash=data.get("xml_hash", ""),
            xml_path=data.get("xml_path", ""),
            clips_dir=data.get("clips_dir", ""),
            dialogs=dialogs,
            chapter_rendered_at=data.get("chapter_rendered_at", 0),
            # Note: stale_dialogs, needs_render, timestamp_stale are COMPUTED AT RUNTIME
            # We do NOT load them from file - they're derived fresh each check.
        )


def compute_md5(content: str) -> str:
    """Compute MD5 hash of a string."""
    return hashlib.md5(content.encode("utf-8")).hexdigest()


def compute_dialog_hash(element_or_utt: Any) -> str:
    """Single canonical function for computing a dialog's hash.

    This is the ONLY place that should compute MD5 for dialog content
    (text + attributes). Used by both change detection and state updates.
    Follows the 'Consistent Hash Computation' requirement in the docs.
    """
    normalized = normalize_dialog_text(element_or_utt)
    return compute_md5(normalized)


def compute_file_md5(file_path: Path) -> str:
    """Compute MD5 hash of a file."""
    if not file_path.exists():
        return ""
    with open(file_path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()


def normalize_dialog_text(element_or_utt: Any) -> str:
    """Normalize dialog text + all attributes for consistent hashing.
    Supports both XML Element and Utterance. Sorted attrs prevent order issues.
    This ensures changing one dialog does not affect others.
    """
    if isinstance(element_or_utt, ET.Element) or hasattr(element_or_utt, "itertext"):
        # XML Element - canonical path (XML is source of truth)
        text = "".join(element_or_utt.itertext()).strip()
        attrs = dict(element_or_utt.attrib)
        # Normalize speaker for consistency with Utterance path
        raw_speaker = (
            attrs.get("character")
            or attrs.get("speaker")
            or ("narrator" if element_or_utt.tag == "narration" else "unknown")
        )
        speaker = "Narrator" if raw_speaker.lower() in ("narrator", "narr") else raw_speaker
        emotion = attrs.get("emotion", "neutral")
        dlgseq = attrs.get("dlgseq", attrs.get("id", "000"))
        # Ensure consistent attrs dict
        if "character" not in attrs:
            attrs["character"] = speaker
        # Render bookkeeping lives in the XML now; it must not feed back into the
        # content signature or writing it would invalidate the very hash it records.
        for _k in ("render_hash", "rendered_at", "section_seq"):
            attrs.pop(_k, None)
    else:
        # Utterance dataclass from chapter_xml_to_audio
        text = getattr(element_or_utt, "text", "")
        raw_speaker = getattr(element_or_utt, "speaker", "Narrator")
        speaker = (
            "Narrator" if str(raw_speaker).lower() in ("narrator", "narr") else str(raw_speaker)
        )
        emotion = getattr(element_or_utt, "emotion", "neutral")
        dlgseq = getattr(element_or_utt, "dlgseq", "000")
        attrs = {"character": speaker, "emotion": emotion, "dlgseq": dlgseq}

    # Use identical whitespace normalization as chapter_xml_to_audio.py
    text = text.replace("\r", " ").replace("\n", " ")
    text = " ".join(text.split())

    # Include all attributes (sorted for determinism) - same for both paths
    attr_str = "|".join(f"{k}={attrs[k]}" for k in sorted(attrs.keys()) if attrs[k])

    # Deterministic normalized string - MUST be identical for Element and Utterance
    normalized = f"{speaker}|{emotion}|{dlgseq}|{text}|{attr_str}"
    return normalized


def get_state_file_path(clips_dir: Path, chapter_stem: str) -> Path:
    """Get path to .chapter_rendered.json file."""
    chapter_clip_dir = clips_dir / chapter_stem
    chapter_clip_dir.mkdir(parents=True, exist_ok=True)
    return chapter_clip_dir / ".chapter_rendered.json"


def load_render_state(clips_dir: Path, chapter_stem: str) -> ChapterRenderState:
    """Load existing render state from disk."""
    state_path = get_state_file_path(clips_dir, chapter_stem)

    if not state_path.exists():
        logger.info(f"No existing render state found at {state_path}")
        return ChapterRenderState()

    try:
        with open(state_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        state = ChapterRenderState.from_dict(data)
        logger.info(f"Loaded render state from {state_path}")
        return state
    except Exception as e:
        logger.error(f"Failed to load render state: {e}")
        return ChapterRenderState()


def save_render_state(state: ChapterRenderState, clips_dir: Path, chapter_stem: str) -> None:
    """Save render state to disk atomically."""
    state_path = get_state_file_path(clips_dir, chapter_stem)

    # Write to temp file first, then rename for atomicity
    temp_path = state_path.with_suffix(".json.tmp")

    try:
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(state.to_dict(), f, indent=2)
        temp_path.replace(state_path)
        logger.info(f"Saved render state to {state_path}")
    except Exception as e:
        logger.error(f"Failed to save render state: {e}")
        if temp_path.exists():
            temp_path.unlink()


def normalize_dialog_id(section: str, dlgseq: str) -> str:
    """Normalize dialog_id to consistent 'SSS_DDD' format (both zero-padded to 3 digits)."""
    sec = str(section or "0").zfill(3)
    dlg = str(dlgseq or "0").zfill(3)
    return f"{sec}_{dlg}"


def get_chapter_audio_timestamp(clips_dir: Path, chapter_stem: str) -> int:
    """
    Get the timestamp of the chapter audio file in story-audio/ directory.
    This is the definitive source for chapter_rendered_at per requirements.

    Returns the mtime of {chapter_stem}.wav in the parent directory of clips_dir,
    or 0 if the file doesn't exist.
    """
    chapter_audio_path = clips_dir.parent / f"{chapter_stem}.wav"
    if chapter_audio_path.exists():
        mtime = int(chapter_audio_path.stat().st_mtime * 1000)
        logger.debug(f"get_chapter_audio_timestamp: {chapter_audio_path.name} mtime={mtime}")
        return mtime
    else:
        logger.debug(f"get_chapter_audio_timestamp: chapter audio file not found at {chapter_audio_path}")
        return 0


def discover_existing_clips(clips_dir: Path, chapter_stem: str) -> Dict[str, Dict[str, Any]]:
    """
    Scan the clips directory for existing audio files and map them to dialog_ids.
    This helps initialize render state when audio files exist but render state is empty.
    """
    clip_map = {}
    chapter_clip_dir = clips_dir / chapter_stem

    if not chapter_clip_dir.exists():
        logger.debug(f"discover_existing_clips: directory not found {chapter_clip_dir}")
        return clip_map

    logger.info(f"discover_existing_clips: scanning {chapter_clip_dir} for existing clips")

    for clip_file in chapter_clip_dir.glob("*.wav"):
        # Try to parse dialog_id from filename: chapter_001_001_001_Narrator.wav
        match = __import__("re").search(r"chapter_(\d+)_(\d+)_(\d+)_", clip_file.name)
        if match:
            section = match.group(2)  # The middle number is usually section
            dlgseq = match.group(3)
            dialog_id = normalize_dialog_id(section, dlgseq)

            try:
                mtime = int(clip_file.stat().st_mtime * 1000)
                clip_map[dialog_id] = {
                    "clip_file": clip_file.name,
                    "rendered_at": mtime,
                    "clip_exists": True
                }
                logger.debug(f"discover_existing_clips: mapped {dialog_id} -> {clip_file.name} (mtime={mtime})")
            except Exception as e:
                logger.warning(f"discover_existing_clips: error processing {clip_file.name}: {e}")

    logger.info(f"discover_existing_clips: found {len(clip_map)} existing clips")
    return clip_map


def parse_dialog_states_from_xml(xml_path: Path) -> Dict[str, Dict[str, Any]]:
    """
    Parse XML, computing the current content hash of every dialog and reading any
    render bookkeeping (render_hash / rendered_at) stored directly on the element.

    Returns:
        {dialog_id: {"hash": <current content md5>,
                     "stored_hash": <render_hash attr or "">,
                     "rendered_at": <rendered_at attr (ms) or 0>}}
    """
    result: Dict[str, Dict[str, Any]] = {}
    if not xml_path.exists():
        logger.error(f"XML file not found: {xml_path}")
        return result

    tree = ET.parse(xml_path)
    root = tree.getroot()

    def process_nodes(nodes, section_num: str):
        for node in nodes:
            if node.tag in ("dialog", "narration"):
                legacy_id = node.attrib.get("id")
                dlgseq = node.attrib.get("dlgseq") or legacy_id or "000"
                dialog_id = normalize_dialog_id(section_num, dlgseq)
                try:
                    rendered_at = int(node.attrib.get("rendered_at", "0") or 0)
                except ValueError:
                    rendered_at = 0
                result[dialog_id] = {
                    "hash": compute_dialog_hash(node),
                    "stored_hash": node.attrib.get("render_hash", ""),
                    "rendered_at": rendered_at,
                }

    sections = root.findall("section")
    if sections:
        for section in sections:
            section_num = section.attrib.get("seq", "000").zfill(3)
            process_nodes(section, section_num)
    else:
        process_nodes(root, "000")

    return result


def parse_xml_dialogs(xml_path: Path) -> Dict[str, str]:
    """
    Parse XML and compute MD5 hashes for each dialog.
    Returns: {dialog_id: md5_hash}
    """
    states = parse_dialog_states_from_xml(xml_path)
    return {dialog_id: s["hash"] for dialog_id, s in states.items()}


def write_render_signatures_to_xml(xml_path: Path, updates: Dict[str, Dict[str, Any]]) -> None:
    """
    Persist render bookkeeping (render_hash / rendered_at) directly onto the
    matching <dialog>/<narration> elements in the chapter XML. This makes the XML
    the single source of truth for content signatures, replacing the sidecar
    .chapter_rendered.json.

    The file is edited *surgically*: we locate the specific dialog's start tag via
    regex and only add/replace its render_hash/rendered_at attributes. We
    deliberately avoid reserializing the whole document with ElementTree, because
    ElementTree normalizes attribute order and whitespace, which would change the
    on-disk attribute ordering and thus the content hash of OTHER dialogs each
    time a single dialog is updated.
    """
    import re

    if not xml_path.exists():
        logger.error(f"write_render_signatures_to_xml: XML not found: {xml_path}")
        return

    # Determine each target dialog's identifying attributes (tag + dlgseq/id) via
    # ElementTree, so we match the precise elements ET sees.
    tree = ET.parse(xml_path)
    root = tree.getroot()
    targets: Dict[str, Dict[str, Any]] = {}

    def collect(nodes, section_num: str):
        for node in nodes:
            if node.tag in ("dialog", "narration"):
                legacy_id = node.attrib.get("id")
                dlgseq = node.attrib.get("dlgseq") or legacy_id or "000"
                dialog_id = normalize_dialog_id(section_num, dlgseq)
                if dialog_id in updates:
                    targets[dialog_id] = {
                        "tag": node.tag,
                        "dlgseq": dlgseq,
                        "use_id": "id" in node.attrib and "dlgseq" not in node.attrib,
                    }

    sections = root.findall("section")
    if sections:
        for section in sections:
            section_num = section.attrib.get("seq", "000").zfill(3)
            collect(section, section_num)
    else:
        collect(root, "000")

    if not targets:
        return

    text = xml_path.read_text(encoding="utf-8")

    # Walk dialog/narration start tags in document order once, matching each to a
    # target by tag + exact dlgseq/id attribute value. Because we scan in order and
    # match on the exact attribute string, we unambiguously locate the correct tag
    # even when multiple sections reuse the same dlgseq numbering.
    tag_re = re.compile(r"<(dialog|narration)\b[^>]*>")
    attr_re = re.compile(r'(\S+?)="([^"]*)"')

    # Build a mutable map from (tag, dlgseq) -> list of dialog_ids needing updates,
    # in the order ET will encounter them (document order == ET iteration order).
    pending: Dict[Any, list] = {}
    for dialog_id, info in targets.items():
        key = (info["tag"], str(info["dlgseq"]))
        pending.setdefault(key, []).append(dialog_id)

    out = []
    last = 0
    for m in tag_re.finditer(text):
        tag_text = m.group(0)
        tag_name = m.group(1)
        attrs = dict(attr_re.findall(tag_text))
        dlgseq = attrs.get("dlgseq") or attrs.get("id") or ""
        key = (tag_name, dlgseq)

        out.append(text[last:m.start()])

        if key in pending and pending[key]:
            dialog_id = pending[key].pop(0)
            u = updates[dialog_id]
            hash_val = u.get("hash")
            rendered_at = u.get("rendered_at")
            inner = tag_text[:-1] if tag_text.endswith(">") else tag_text
            inner = re.sub(r'\s+render_hash="[^"]*"', "", inner)
            inner = re.sub(r'\s+rendered_at="[^"]*"', "", inner)
            if hash_val:
                inner += f' render_hash="{hash_val}"'
            if rendered_at is not None:
                inner += f' rendered_at="{int(rendered_at or 0)}"'
            out.append(inner + ">")
        else:
            out.append(tag_text)

        last = m.end()

    # Warn about any targets we never matched.
    for key, ids in pending.items():
        for dialog_id in ids:
            logger.warning(f"write_render_signatures_to_xml: no matching tag for {dialog_id} {key}")

    out.append(text[last:])
    new_text = "".join(out)

    temp_path = xml_path.with_suffix(xml_path.suffix + ".tmp")
    try:
        temp_path.write_text(new_text, encoding="utf-8")
        temp_path.replace(xml_path)
        logger.info(
            f"write_render_signatures_to_xml: wrote {len(targets)} signature(s) to {xml_path.name}"
        )
    except Exception as e:
        logger.error(f"write_render_signatures_to_xml: failed to replace {xml_path}: {e}")
        if temp_path.exists():
            temp_path.unlink()


def is_timestamp_stale(
    stored_rendered_at: int, clip_path: Path
) -> bool:
    """
    Check if a stored timestamp is stale compared to the actual file.

    Returns True if:
    - The file doesn't exist, OR
    - The stored timestamp is older than the file's modification time
      (within the given tolerance)
    """
    logger.debug(f"is_timestamp_stale: checking {clip_path.name}, stored={stored_rendered_at}")

    if not clip_path.exists():
        logger.info(f"is_timestamp_stale: file missing - {clip_path.name} -> stale")
        return True

    if stored_rendered_at == 0:
        logger.info(f"is_timestamp_stale: never rendered - {clip_path.name} -> stale")
        return True

    try:
        file_mtime = int(clip_path.stat().st_mtime * 1000)  # Convert to milliseconds
        is_stale = file_mtime > stored_rendered_at
        age_diff = file_mtime - stored_rendered_at

        logger.debug(
            f"is_timestamp_stale: {clip_path.name} - "
            f"file_mtime={file_mtime}, stored={stored_rendered_at}, "
            f"diff={age_diff}ms, stale={is_stale}"
        )

        if is_stale:
            logger.info(f"is_timestamp_stale: timestamp out of sync - {clip_path.name} (diff={age_diff}ms)")

        return is_stale
    except Exception:
        logger.error(f"is_timestamp_stale: error checking {clip_path.name}", exc_info=True)
        return True  # Error checking file -> treat as stale


def get_comprehensive_render_state(
    xml_path: Path,
    clips_dir: Path,
    chapter_stem: str,
    story_name: str,
    refresh_dialog_hashes: bool = False,
) -> Dict[str, Any]:
    """
    SINGLE FUNCTION that encapsulates all render state logic.

    This addresses both issues:
    1. Properly initializes timestamps on first creation
    2. Checks chapter-level staleness (any dialog newer than chapter_rendered_at)

    Args:
        xml_path: Path to chapter XML
        clips_dir: Base clips directory
        chapter_stem: Chapter stem name (e.g. '01-Hendrix')
        story_name: Story name for logging
        refresh_dialog_hashes: If True, update all signatures (full render)

    Returns:
        Structured result with:
        - status: "good" or "needs_render"
        - chapter: Chapter-level state
        - dialogs: Categorized dialog states
        - summary: Counts and metadata
    """
    logger.info(
        f"get_comprehensive_render_state: starting for {chapter_stem}, "
        f"refresh={refresh_dialog_hashes}, xml={xml_path.name}"
    )

    # Load legacy signature cache (only used as a one-time backfill for XMLs that
    # predate storing render hashes inline). We no longer treat it as authoritative.
    state = load_render_state(clips_dir, chapter_stem)
    state.story = story_name
    state.chapter = chapter_stem[:3].lstrip("0") or "001"
    state.xml_path = str(xml_path)
    state.clips_dir = str(clips_dir / chapter_stem)

    # Parse current XML: current content hash + any render bookkeeping stored inline.
    dialog_states = parse_dialog_states_from_xml(xml_path)
    current_dialogs = {d: s["hash"] for d, s in dialog_states.items()}
    current_xml_hash = compute_file_md5(xml_path)

    now = int(time.time() * 1000)

    # Discover existing clips (used both for first-time timestamps and analysis).
    existing_clips = discover_existing_clips(clips_dir, chapter_stem)

    # One-time backfill: if a dialog has no inline render_hash but the legacy
    # sidecar has a signature, seed the in-memory state from the sidecar and write
    # it into the XML so subsequent reads are self-contained.
    sidecar_updates: Dict[str, Dict[str, Any]] = {}
    for dialog_id, s in dialog_states.items():
        if not s["stored_hash"] and dialog_id in state.dialogs:
            legacy = state.dialogs[dialog_id]
            s["stored_hash"] = legacy.hash
            if s["rendered_at"] == 0:
                s["rendered_at"] = legacy.rendered_at
            sidecar_updates[dialog_id] = {"hash": legacy.hash, "rendered_at": s["rendered_at"]}
    if sidecar_updates:
        logger.info(f"Backfilling {len(sidecar_updates)} render signatures from sidecar into XML")
        write_render_signatures_to_xml(xml_path, sidecar_updates)

    # First-time initialization of inline signatures. This runs ONLY when there is
    # no signature source at all (no inline render_hash, no legacy sidecar). Any
    # dialog that already has a clip but no stored hash is assumed in-sync with the
    # current content (legacy behavior) so it shows green rather than falsely stale.
    # Gating on "no signature anywhere" prevents incorrectly re-seeding an edited
    # dialog's hash (which would mask real edits as in-sync).
    any_signature = bool(state.dialogs) or any(s["stored_hash"] for s in dialog_states.values())
    updates: Dict[str, Dict[str, Any]] = {}
    if not any_signature:
        for dialog_id, s in dialog_states.items():
            if dialog_id in existing_clips:
                # Assume the discovered clip corresponds to the current content.
                rendered_at = existing_clips[dialog_id].get("rendered_at", now)
                s["stored_hash"] = s["hash"]
                s["rendered_at"] = rendered_at
                updates[dialog_id] = {"hash": s["hash"], "rendered_at": rendered_at}
            # Dialogs with no clip simply get no signature; they are missing.
        if updates:
            logger.info(f"First-time inline signature init for {len(updates)} dialogs")
            write_render_signatures_to_xml(xml_path, updates)

    # chapter_rendered_at derives from the chapter audio file (definitive source),
    # falling back to the newest clip timestamp.
    chapter_audio_mtime = get_chapter_audio_timestamp(clips_dir, chapter_stem)
    if chapter_audio_mtime > 0:
        state.chapter_rendered_at = chapter_audio_mtime
    elif existing_clips:
        state.chapter_rendered_at = max(
            (c.get("rendered_at", 0) for c in existing_clips.values()), default=now
        )

    if refresh_dialog_hashes:
        # Full render: refresh ALL signatures and timestamps, written into XML.
        logger.info(f"get_comprehensive_render_state: refreshing all signatures for {chapter_stem}")
        refresh_updates: Dict[str, Dict[str, Any]] = {}
        for dialog_id, s in dialog_states.items():
            clip_path = None
            for pattern in [f"chapter_{dialog_id}_*.wav", f"chapter_{dialog_id}.wav", f"{dialog_id}.wav"]:
                potential_paths = list((clips_dir / chapter_stem).glob(pattern))
                if potential_paths:
                    clip_path = potential_paths[0]
                    break
            rendered_at = int(clip_path.stat().st_mtime * 1000) if clip_path and clip_path.exists() else now
            s["stored_hash"] = s["hash"]
            s["rendered_at"] = rendered_at
            refresh_updates[dialog_id] = {"hash": s["hash"], "rendered_at": rendered_at}
        write_render_signatures_to_xml(xml_path, refresh_updates)
        if chapter_audio_mtime > 0:
            state.chapter_rendered_at = chapter_audio_mtime
        else:
            state.chapter_rendered_at = now

    # Observation loop uses the inline signatures. Build a `state.dialogs`-compatible
    # view so the existing analysis below is unchanged.
    state.dialogs = {
        d: DialogRenderState(dialog_id=d, hash=s["stored_hash"] or "", rendered_at=s["rendered_at"])
        for d, s in dialog_states.items()
    }
    state._is_initialized = bool(updates)  # treat freshly-initialized clip dialogs as good
    state.xml_hash = current_xml_hash

    # Now perform comprehensive observation and analysis
    missing_dialogs = []
    needs_render_dialogs = []
    good_dialogs = []
    timestamp_stale_dialogs = []

    chapter_clip_dir = clips_dir / chapter_stem
    chapter_has_any_clips = False
    chapter_newest_clip_time = 0

    for dialog_id, current_hash in current_dialogs.items():
        stored_state = state.dialogs.get(dialog_id)

        if stored_state is None:
            # Should not happen after initialization above, but handle gracefully
            logger.warning(f"get_comprehensive_render_state: dialog {dialog_id} not in signature cache")
            missing_dialogs.append(dialog_id)
            continue

        # Check if dialog has any clip at all
        # Files are named: chapter_{chapter_num}_{section_num}_{dlgseq}_{speaker}.wav
        # But dialog_id is just {section_num}_{dlgseq}, so we need broader patterns
        clip_path = None
        for pattern in [
            f"chapter_*_{dialog_id}_*.wav",  # Match any chapter prefix
            f"chapter_{dialog_id}_*.wav",    # Legacy format
            f"chapter_{dialog_id}.wav",
            f"{dialog_id}.wav"
        ]:
            potential_paths = list(chapter_clip_dir.glob(pattern))
            if potential_paths:
                clip_path = potential_paths[0]
                chapter_has_any_clips = True
                file_mtime = int(clip_path.stat().st_mtime * 1000)
                chapter_newest_clip_time = max(chapter_newest_clip_time, file_mtime)
                break

        if not clip_path or not clip_path.exists():
            missing_dialogs.append(dialog_id)
            continue

        # Check for content changes
        if stored_state.hash != current_hash:
            logger.debug(f"get_comprehensive_render_state: content changed for {dialog_id}")
            needs_render_dialogs.append(dialog_id)
            continue

        # Check timestamp staleness - use actual file mtime for comparison
        file_mtime = int(clip_path.stat().st_mtime * 1000)

        # Special case for first-time initialization: if we just discovered this dialog
        # and it has a clip, treat it as good (the clip is assumed to match current XML)
        if stored_state.rendered_at == 0 and not getattr(state, "_is_initialized", False):
            logger.debug(f"get_comprehensive_render_state: first-time dialog with clip {dialog_id} -> good")
            good_dialogs.append(dialog_id)
        else:
            # Check if dialog clip is newer than CHAPTER rendered_at (for blue button)
            # This is the key requirement: dialog should be blue if dialog_clip_time > chapter_rendered_at
            # Exact comparison - no tolerance as timing differences should not occur in proper render flow
            is_newer_than_chapter = file_mtime > state.chapter_rendered_at

            if is_newer_than_chapter:
                logger.debug(f"get_comprehensive_render_state: dialog {dialog_id} is timestamp stale vs chapter (file_mtime={file_mtime}, chapter_rendered_at={state.chapter_rendered_at})")
                timestamp_stale_dialogs.append(dialog_id)
                needs_render_dialogs.append(dialog_id)
            elif stored_state.rendered_at == 0 or file_mtime > stored_state.rendered_at:
                # Also check individual dialog staleness as fallback
                logger.debug(f"get_comprehensive_render_state: dialog {dialog_id} has individual timestamp staleness (file_mtime={file_mtime}, stored={stored_state.rendered_at})")
                timestamp_stale_dialogs.append(dialog_id)
                needs_render_dialogs.append(dialog_id)
            else:
                good_dialogs.append(dialog_id)

    # ALWAYS use chapter audio file timestamp for chapter_rendered_at (per requirements)
    chapter_audio_mtime = get_chapter_audio_timestamp(clips_dir, chapter_stem)
    if chapter_audio_mtime > 0:
        chapter_newest_clip_time = max(chapter_newest_clip_time, chapter_audio_mtime)
        chapter_has_any_clips = True
        logger.debug(f"Using chapter audio file timestamp as definitive chapter_rendered_at reference: {chapter_audio_mtime}")

    # Chapter-level staleness: if ANY dialog is newer than chapter_rendered_at
    chapter_stale = False
    chapter_reason = "good"

    if not chapter_has_any_clips:
        chapter_stale = True
        chapter_reason = "no_clips"
    elif state.chapter_rendered_at == 0 and chapter_newest_clip_time > 0:
        # First time seeing clips - use chapter audio timestamp
        state.chapter_rendered_at = chapter_audio_mtime if chapter_audio_mtime > 0 else chapter_newest_clip_time
        chapter_reason = "initialized"
    elif chapter_newest_clip_time > state.chapter_rendered_at + 1000:  # 1 second tolerance
        chapter_stale = True
        chapter_reason = "newer_clips"
        logger.info(
            f"Chapter {chapter_stem} needs render: clips newer ({chapter_newest_clip_time}) "
            f"than chapter_rendered_at ({state.chapter_rendered_at})"
        )

    # Overall status
    needs_render = len(missing_dialogs) > 0 or len(needs_render_dialogs) > 0 or chapter_stale
    status = "needs_render" if needs_render else "good"

    # Build comprehensive result with legacy compatibility fields for UI
    all_stale = missing_dialogs + needs_render_dialogs + timestamp_stale_dialogs

    result = {
        "status": status,
        "chapter": {
            "chapter_rendered_at": state.chapter_rendered_at,
            "needs_render": chapter_stale or needs_render,
            "reason": chapter_reason,
            "has_any_clips": chapter_has_any_clips,
            "newest_clip_time": chapter_newest_clip_time,
        },
        "dialogs": {
            "missing": missing_dialogs,
            "needs_render": needs_render_dialogs,
            "timestamp_stale": timestamp_stale_dialogs,
            "good": good_dialogs,
        },
        "summary": {
            "total_dialogs": len(current_dialogs),
            "missing_count": len(missing_dialogs),
            "needs_render_count": len(needs_render_dialogs),
            "timestamp_stale_count": len(timestamp_stale_dialogs),
            "good_count": len(good_dialogs),
        },
        "metadata": {
            "xml_hash": current_xml_hash,
            "xml_changed": bool(state.xml_hash and state.xml_hash != current_xml_hash),
            "chapter_stem": chapter_stem,
            "story": story_name,
        },
        # Legacy compatibility fields expected by TypeScript UI code
        "needs_render": chapter_stale or needs_render,
        "is_fully_rendered": status == "good",
        "stale_dialogs": all_stale,
        "stale_count": len(all_stale),
        "chapter_rendered_at": state.chapter_rendered_at,
        "has_timestamp_stale": len(timestamp_stale_dialogs) > 0,
        "hasTimestampStale": len(timestamp_stale_dialogs) > 0,
        "timestamp_stale_dialogs": timestamp_stale_dialogs,
        "timestampStaleDialogs": timestamp_stale_dialogs,
        # Per-dialog signatures + timestamps, so the UI can merge the freshly
        # rendered hashes into its in-memory model and flip buttons to green
        # without re-reading the XML from disk.
        "dialog_hashes": {d: s["hash"] for d, s in dialog_states.items()},
        "rendered_at": {d: s["rendered_at"] for d, s in dialog_states.items()},
    }

    # Signatures are stored inline in the XML; no sidecar persistence is needed.
    # (render_hash / rendered_at were written above only when they changed.)

    logger.info(
        f"get_comprehensive_render_state: COMPLETE - status={status}, "
        f"missing={len(missing_dialogs)}, needs_render={len(needs_render_dialogs)}, "
        f"timestamp_stale={len(timestamp_stale_dialogs)}"
    )

    return result


def check_render_state(
    xml_path: Path,
    clips_dir: Path,
    chapter_stem: str,
    story_name: str,
    refresh_dialog_hashes: bool = False,
) -> ChapterRenderState:
    """
    Legacy wrapper that now delegates to get_comprehensive_render_state().

    This ensures get_comprehensive_render_state() is the SINGLE authoritative
    function for all render state determination, per the architecture requirements.
    """
    logger.info(
        f"check_render_state: delegating to comprehensive function for {chapter_stem}, "
        f"refresh={refresh_dialog_hashes}"
    )

    # Use the single authoritative function
    comprehensive = get_comprehensive_render_state(
        xml_path, clips_dir, chapter_stem, story_name, refresh_dialog_hashes
    )

    # Convert comprehensive result back to ChapterRenderState for backward compatibility
    state = load_render_state(clips_dir, chapter_stem)
    state.story = story_name
    state.chapter = chapter_stem[:3].lstrip("0") or "001"
    state.xml_path = str(xml_path)
    state.clips_dir = str(clips_dir / chapter_stem)

    # Update from comprehensive result
    state.needs_render = comprehensive.get("chapter", {}).get("needs_render", False)
    state.chapter_rendered_at = comprehensive.get("chapter", {}).get("chapter_rendered_at", 0)
    state.is_fully_rendered = comprehensive.get("status") == "good"

    # Update dialog signatures if we did a full refresh
    if refresh_dialog_hashes:
        dialogs_data = comprehensive.get("dialogs", {})
        for dialog_id, dialog_state in state.dialogs.items():
            if dialog_id in dialogs_data.get("good", []) or dialog_id in dialogs_data.get("timestamp_stale", []):
                # The comprehensive function already updated the state
                pass

    logger.info(
        f"check_render_state: COMPLETE via comprehensive - "
        f"needs_render={state.needs_render}, "
        f"status={comprehensive.get('status')}"
    )

    return state


def update_render_state_with_new_clips(
    state: ChapterRenderState,
    generated_clips: List[tuple],
    clips_dir: Path,
    chapter_stem: str,
    is_full_render: bool = True,
) -> ChapterRenderState:
    """
    Legacy function for backward compatibility with chapter_xml_to_audio.py.

    Now delegates to get_comprehensive_render_state() as the SINGLE
    authoritative function for all render state logic.
    """
    logger.info(f"update_render_state_with_new_clips: updating {len(generated_clips)} clips")

    # Update timestamps for the specific dialogs that were just rendered
    now = int(time.time() * 1000)
    updated_dialog_ids = []
    xml_updates: Dict[str, Dict[str, Any]] = {}

    for utt, clip_path, _ in generated_clips:
        dialog_id = normalize_dialog_id(utt.section_num, utt.dlgseq)
        updated_dialog_ids.append(dialog_id)

        # Use single canonical hash function (per docs)
        hash_val = compute_dialog_hash(utt)

        # Get the actual clip file mtime for the timestamp
        # BUGFIX: previously referenced an undefined `path_str`, raising NameError.
        cp = Path(clip_path) if clip_path else None
        if cp is not None and cp.exists():
            file_mtime = int(cp.stat().st_mtime * 1000)
        else:
            file_mtime = now

        # Update the in-memory signature cache
        state.dialogs[dialog_id] = DialogRenderState(
            dialog_id=dialog_id,
            hash=hash_val,
            rendered_at=file_mtime,
        )
        xml_updates[dialog_id] = {"hash": hash_val, "rendered_at": file_mtime}
        logger.debug(f"Updated render state for dialog {dialog_id} (rendered_at={file_mtime})")

    # chapter_rendered_at should reflect the actual chapter audio file timestamp
    chapter_audio_mtime = get_chapter_audio_timestamp(clips_dir, chapter_stem)
    if chapter_audio_mtime > 0:
        state.chapter_rendered_at = chapter_audio_mtime

    # Persist the updated signatures inline into the chapter XML (source of truth).
    xml_path_for_updates = Path(getattr(state, "xml_path", f"{chapter_stem}.xml"))
    try:
        write_render_signatures_to_xml(xml_path_for_updates, xml_updates)
    except Exception as e:
        logger.warning(f"Failed to write render signatures to XML: {e}")

    # Use the single authoritative function to get updated state
    story_name = getattr(state, "story", "Unknown")
    xml_path = Path(getattr(state, "xml_path", f"{chapter_stem}.xml"))

    comprehensive_result = get_comprehensive_render_state(
        xml_path, clips_dir, chapter_stem, story_name, refresh_dialog_hashes=is_full_render
    )

    logger.info(
        f"update_render_state_with_new_clips: COMPLETE - updated {len(updated_dialog_ids)} dialog(s), "
        f"status={comprehensive_result.get('status')}, missing={len(comprehensive_result.get('dialogs', {}).get('missing', []))}"
    )

    # Return minimal ChapterRenderState for backward compatibility
    # get_comprehensive_render_state() is the single source of truth
    chapter_rendered_at = comprehensive_result.get("chapter", {}).get("chapter_rendered_at", 0)
    return ChapterRenderState(
        story=story_name,
        chapter=chapter_stem[:3].lstrip("0") or "001",
        xml_path=str(xml_path),
        clips_dir=str(clips_dir / chapter_stem),
        chapter_rendered_at=chapter_rendered_at,
        needs_render=comprehensive_result.get("chapter", {}).get("needs_render", False),
        is_fully_rendered=comprehensive_result.get("status") == "good",
    )


def update_dialog_timestamp(
    xml_path: Path,
    clips_dir: Path,
    chapter_stem: str,
    story_name: str,
    dialog_id: str,
    new_timestamp: int = None
) -> Dict[str, Any]:
    """
    Update timestamp for a specific dialog after it has been re-rendered.
    This ensures the dialog turns from blue (timestamp stale) to green.
    """
    logger.info(f"update_dialog_timestamp: updating {dialog_id} in {chapter_stem}")

    # Determine the clip mtime from the actual file (avoids races with callers
    # passing Date.now()); fall back to the provided timestamp or now.
    chapter_clip_dir = clips_dir / chapter_stem
    clip_path = None
    for pattern in [
        f"chapter_*_{dialog_id}_*.wav",
        f"chapter_{dialog_id}_*.wav",
        f"{dialog_id}.wav",
    ]:
        potential_paths = list(chapter_clip_dir.glob(pattern))
        if potential_paths:
            clip_path = potential_paths[0]
            break

    if clip_path and clip_path.exists():
        ts = int(clip_path.stat().st_mtime * 1000)
    elif new_timestamp is not None:
        ts = int(new_timestamp)
    else:
        ts = int(time.time() * 1000)

    # Persist the current content hash + timestamp inline in the XML so the dialog
    # reflects the fresh render (turns green) and future edits compare against it.
    try:
        states = parse_dialog_states_from_xml(xml_path)
        if dialog_id in states:
            write_render_signatures_to_xml(
                xml_path, {dialog_id: {"hash": states[dialog_id]["hash"], "rendered_at": ts}}
            )
            logger.info(
                f"update_dialog_timestamp: wrote render_hash + rendered_at={ts} for {dialog_id} into XML"
            )
        else:
            logger.warning(f"update_dialog_timestamp: dialog {dialog_id} not found in XML")
    except Exception as e:
        logger.warning(f"update_dialog_timestamp: failed to write XML signature: {e}")

    # Do NOT update chapter_rendered_at here: bumping it for a single dialog render
    # would make OTHER dialogs appear timestamp-stale (they'd be older than the
    # chapter). chapter_rendered_at is owned by full chapter renders only.
    return get_comprehensive_render_state(
        xml_path, clips_dir, chapter_stem, story_name, refresh_dialog_hashes=False
    )


def update_xml_hash_after_render(
    xml_path: Path, clips_dir: Path, chapter_stem: str, story_name: str
) -> ChapterRenderState:
    """
    After a successful full "Render Chapter", refresh all dialog signatures so the
    stored hashes match the current XML. Signatures are stored inline in the XML
    (render_hash / rendered_at). chapter_rendered_at comes from the chapter audio
    file timestamp.

    Returns the comprehensive result for the UI.
    """
    logger.info(f"update_xml_hash_after_render: refreshing render signatures for {chapter_stem}")
    return get_comprehensive_render_state(
        xml_path, clips_dir, chapter_stem, story_name, refresh_dialog_hashes=True
    )


def refresh_all_dialog_hashes_after_render(
    xml_path: Path, clips_dir: Path, chapter_stem: str, story_name: str
) -> ChapterRenderState:
    """
    After a full chapter render, recalculate and update ALL dialog MD5 signatures,
    stored inline in the XML (render_hash / rendered_at). This ensures the stored
    hashes match the current XML so all rendered dialogs read as in-sync.
    """
    logger.info(f"refresh_all_dialog_hashes_after_render: refreshing signatures for {chapter_stem}")
    return get_comprehensive_render_state(
        xml_path, clips_dir, chapter_stem, story_name, refresh_dialog_hashes=True
    )


def _unused_refresh_all_dialog_hashes_after_render_legacy(
    xml_path: Path, clips_dir: Path, chapter_stem: str, story_name: str
) -> ChapterRenderState:
    """Legacy implementation retained for reference. Superseded by the inline-XML
    signature storage above. (Not used.)"""
    state = load_render_state(clips_dir, chapter_stem)

    # Set basic info
    state.story = story_name
    state.chapter = chapter_stem[:3].lstrip("0") or "001"
    state.xml_path = str(xml_path)
    state.clips_dir = str(clips_dir / chapter_stem)

    # Update XML hash as well
    state.xml_hash = compute_file_md5(xml_path)
    state.xml_changed = False
    state.current_xml_hash = state.xml_hash

    # Parse current dialogs from XML (source of truth)
    current_dialogs = parse_xml_dialogs(xml_path)

    now = int(time.time() * 1000)

    # Update ALL dialog hashes from current XML
    for dialog_id, dialog_hash in current_dialogs.items():
        # Find the corresponding clip file (if it exists)
        clip_file = ""
        clip_path = clips_dir / chapter_stem / f"chapter_{dialog_id}.wav"

        if clip_path.exists():
            clip_file = f"chapter_{dialog_id}.wav"
        else:
            # Try alternative naming patterns
            alt_clip_path = clips_dir / chapter_stem / f"{dialog_id}.wav"
            if alt_clip_path.exists():
                clip_file = f"{dialog_id}.wav"

        state.dialogs[dialog_id] = DialogRenderState(
            dialog_id=dialog_id,
            hash=dialog_hash,
            clip_file=clip_file,
            rendered_at=now,
            clip_exists=bool(clip_file),
        )

    # Use chapter audio file timestamp for chapter_rendered_at (per requirements)
    chapter_audio_mtime = get_chapter_audio_timestamp(clips_dir, chapter_stem)
    state.chapter_rendered_at = chapter_audio_mtime if chapter_audio_mtime > 0 else now
    # Note: We do NOT set computed fields (stale_dialogs, needs_render, etc.) on state.
    # These are DERIVED AT RUNTIME from observation in get_comprehensive_render_state().

    # Save updated state
    save_render_state(state, clips_dir, chapter_stem)

    logger.info(
        f"Refreshed all dialog hashes after full render for {chapter_stem} "
        f"({len(current_dialogs)} dialogs updated)"
    )

    # Return comprehensive state so UI gets the correct computed values
    # Force a full refresh to get proper staleness calculations
    comprehensive = get_comprehensive_render_state(
        xml_path, clips_dir, chapter_stem, story_name, refresh_dialog_hashes=True
    )

    # Ensure we always return a dict for the UI layer
    if not isinstance(comprehensive, dict):
        comprehensive = {
            "status": "good",
            "needs_render": False,
            "has_timestamp_stale": False,
            "timestamp_stale_dialogs": [],
            "stale_count": 0,
            "xml_changed": False,
            "message": "Render completed successfully"
        }

    logger.info(f"update_xml_hash_after_render: completed with status={comprehensive.get('status')}")
    return comprehensive
    # Force a full refresh to get proper staleness calculations
    comprehensive = get_comprehensive_render_state(
        xml_path, clips_dir, chapter_stem, story_name, refresh_dialog_hashes=True
    )
    logger.info(f"update_xml_hash_after_render: completed with status={comprehensive.get('status')}")
    return comprehensive


def remove_stale_clip_files(
    state: ChapterRenderState, stale_dialogs: List[str], clips_dir: Path, chapter_stem: str
) -> List[str]:
    """
    Remove clip files for stale dialogs to force re-rendering.
    
    Args:
        state: The render state containing dialog info
        stale_dialogs: List of dialog IDs that are stale (passed separately since
                      this is derived at runtime, not stored in state)
        clips_dir: Base clips directory
        chapter_stem: Chapter stem name
    
    Returns:
        List of removed file paths.
    """
    removed = []

    for dialog_id in stale_dialogs:
        dialog_state = state.dialogs.get(dialog_id)
        if not dialog_state or not dialog_state.clip_file:
            continue

        clip_path = clips_dir / chapter_stem / dialog_state.clip_file

        if clip_path.exists():
            try:
                clip_path.unlink()
                removed.append(str(clip_path))
                logger.info(f"Removed stale clip: {clip_path.name}")
            except Exception as e:
                logger.error(f"Failed to remove stale clip {clip_path}: {e}")

    return removed


def get_render_state_json(
    xml_path: str, story_dir: str, chapter_stem: str, story_name: str
) -> Dict[str, Any]:
    """
    Legacy compatibility wrapper. ALWAYS uses get_comprehensive_render_state()
    as the single authoritative function.
    """
    xml = Path(xml_path)
    story_path = Path("Stories") / story_dir
    clips_dir = story_path / "story-audio" / "clips"

    # Use the single authoritative function (per architecture requirements)
    comprehensive = get_comprehensive_render_state(
        xml, clips_dir, chapter_stem, story_name, refresh_dialog_hashes=False
    )

    # Convert comprehensive result to legacy format expected by UI
    dialogs = comprehensive.get("dialogs", {})
    missing = dialogs.get("missing", [])
    needs_render = dialogs.get("needs_render", [])
    timestamp_stale = dialogs.get("timestamp_stale", [])
    good = dialogs.get("good", [])
    all_stale = missing + needs_render + timestamp_stale

    return {
        "needs_render": comprehensive.get("chapter", {}).get("needs_render", False),
        "is_fully_rendered": comprehensive.get("status") == "good",
        "stale_dialogs": all_stale,
        "stale_count": len(all_stale),
        "xml_hash": comprehensive.get("metadata", {}).get("xml_hash", ""),
        "xml_changed": comprehensive.get("metadata", {}).get("xml_changed", False),
        "current_xml_hash": comprehensive.get("metadata", {}).get("xml_hash", ""),
        "chapter_rendered_at": comprehensive.get("chapter", {}).get("chapter_rendered_at", 0),
        "dialog_count": comprehensive.get("summary", {}).get("total_dialogs", 0),
        "clips_dir": str(clips_dir / chapter_stem),
        # Timestamp staleness fields - ensure both formats for UI compatibility
        "has_timestamp_stale": len(timestamp_stale) > 0,
        "hasTimestampStale": len(timestamp_stale) > 0,
        "timestamp_stale_dialogs": timestamp_stale,
        "timestampStaleDialogs": timestamp_stale,
        # Include dialog data for UI compatibility
        "dialogs": {
            dialog_id: {
                "dialogId": dialog_id,
                "hash": "",  # Not stored in comprehensive result
                "renderedAt": 0,  # Not stored
                "clipFile": "",
                "clipExists": dialog_id not in missing,
                "needsRender": dialog_id in all_stale,
            }
            for dialog_id in set(missing + needs_render + timestamp_stale + good)
        },
        # Include the full comprehensive result for debugging
        "_comprehensive": comprehensive
    }


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 4:
        print("Usage: chapter_render_state.py <xml_path> <story_dir> <chapter_stem> [update_hash]")
        sys.exit(1)

    xml_path = sys.argv[1]
    story_dir = sys.argv[2]
    chapter_stem = sys.argv[3]
    story_name = story_dir.replace("Story-", "")

    # Check command type
    story_path = Path("Stories") / story_dir
    clips_dir = story_path / "story-audio" / "clips"

    if len(sys.argv) > 4 and sys.argv[4] == "update_hash":
        # Update only XML hash after successful render (UI-driven)
        comprehensive = update_xml_hash_after_render(Path(xml_path), clips_dir, chapter_stem, story_name)
        # Ensure we have a dict result for the UI
        if isinstance(comprehensive, dict):
            result = comprehensive
        else:
            # Convert ChapterRenderState object to dict
            result = {
                "success": True,
                "xml_hash": getattr(comprehensive, "xml_hash", ""),
                "xml_changed": False,
                "needs_render": False,
                "has_timestamp_stale": False,
                "stale_count": 0,
                "timestamp_stale_dialogs": [],
                "message": f"Updated XML hash for {chapter_stem}",
            }
    elif len(sys.argv) > 4 and sys.argv[4] == "refresh_dialogs":
        # Full render - update signatures and timestamps using comprehensive function
        result = get_comprehensive_render_state(
            Path(xml_path), clips_dir, chapter_stem, story_name, refresh_dialog_hashes=True
        )
        result["success"] = True
        result["message"] = f"Refreshed {result.get('summary', {}).get('total_dialogs', 0)} dialog signatures and timestamps"
    elif len(sys.argv) > 5 and sys.argv[4] == "update_dialog_timestamp":
        # Update timestamp for a specific dialog after individual render
        dialog_id = sys.argv[5]
        timestamp = int(sys.argv[6]) if len(sys.argv) > 6 else None
        result = update_dialog_timestamp(
            Path(xml_path), clips_dir, chapter_stem, story_name, dialog_id, timestamp
        )
        result["success"] = True
        result["message"] = f"Updated timestamp for dialog {dialog_id}"
        result["updated_dialog"] = dialog_id
    else:
        # Normal render state check (UI-driven) - use comprehensive function
        result = get_comprehensive_render_state(
            Path(xml_path), clips_dir, chapter_stem, story_name, refresh_dialog_hashes=False
        )

    print(json.dumps(result, indent=2))
