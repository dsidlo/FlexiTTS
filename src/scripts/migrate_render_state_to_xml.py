#!/usr/bin/env python3
"""
One-time migration: copy per-dialog render signatures out of the legacy
.chapter_rendered.json sidecar files into the chapter XML as render_hash /
rendered_at attributes.

Usage:
    python src/scripts/migrate_render_state_to_xml.py [--story Story-Name]

Without --story it migrates every story under Stories/.
After a successful migration the sidecar files may be removed manually.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from chapter_render_state import write_render_signatures_to_xml  # noqa: E402


def migrate_chapter(xml_path: Path, sidecar_path: Path) -> int:
    """Copy hashes/timestamps from one sidecar into the matching XML. Returns count."""
    try:
        data = json.loads(sidecar_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"  !! could not read {sidecar_path}: {e}")
        return 0

    dialogs = data.get("dialogs", {})
    updates = {}
    for dialog_id, d in dialogs.items():
        hash_val = d.get("hash")
        if not hash_val:
            continue
        updates[dialog_id] = {"hash": hash_val, "rendered_at": d.get("rendered_at", 0)}

    if not updates:
        print(f"  -- no dialog signatures in {sidecar_path}")
        return 0

    if not xml_path.exists():
        print(f"  !! XML not found for sidecar {sidecar_path} (expected {xml_path})")
        return 0

    write_render_signatures_to_xml(xml_path, updates)
    print(f"  ok  {xml_path.name}: migrated {len(updates)} signatures from sidecar")
    return len(updates)


def migrate_story(story_dir: Path) -> int:
    clips_root = story_dir / "story-audio" / "clips"
    xml_root = story_dir / "story-xml"
    if not clips_root.exists():
        return 0

    total = 0
    for chapter_dir in sorted(clips_root.iterdir()):
        sidecar = chapter_dir / ".chapter_rendered.json"
        if not sidecar.exists():
            continue
        stem = chapter_dir.name
        xml_path = xml_root / f"{stem}.xml"
        total += migrate_chapter(xml_path, sidecar)
    return total


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--story", help="Story directory name (e.g. Story-Entanglement)")
    args = parser.parse_args()

    stories_root = Path("Stories")
    if not stories_root.exists():
        print("Stories/ directory not found (run from the project root)", file=sys.stderr)
        return 1

    if args.story:
        story_dirs = [stories_root / args.story]
    else:
        story_dirs = [d for d in sorted(stories_root.iterdir()) if d.is_dir()]

    grand_total = 0
    for story_dir in story_dirs:
        if not story_dir.exists():
            print(f"Story not found: {story_dir}", file=sys.stderr)
            continue
        print(f"Migrating {story_dir.name}")
        grand_total += migrate_story(story_dir)

    print(f"Done. Migrated {grand_total} dialog signatures into XML.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
