#!/usr/bin/env python3

import sys
import os
import yaml
from pathlib import Path
from xml.etree import ElementTree as ET
from log_utils import setup_script_logging

logger = setup_script_logging('chapter_seq_xml')

def indent(elem, level=0):
    i = "\n" + level*"  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
        for elem in elem:
            indent(elem, level+1)
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i

def resequence_xml(input_path, output_path=None):
    logger.info(f"resequence_xml input_path={input_path} output_path={output_path}")
    print(f"[RESOURCE-ACCESS] Reading XML for resequencing", file=sys.stderr)
    print(f"  input_path: {input_path}", file=sys.stderr)
    print(f"  resourceType: xml", file=sys.stderr)
    print(f"  operation: read", file=sys.stderr)
    if not os.path.exists(input_path):
        print(f"[RESOURCE-ACCESS] XML NOT found: {input_path}", file=sys.stderr)
        return

    try:
        print(f"[RESOURCE-ACCESS] Successfully read XML for resequencing", file=sys.stderr)
        print(f"  input_path: {input_path}", file=sys.stderr)
        # Standard ET parse
        tree = ET.parse(input_path)
        root = tree.getroot()

        section_count = 1
        for section in root.findall('.//section'):
            section.set('seq', str(section_count))

            dlgseq_count = 1
            # We want to iterate over all children of section in order
            for child in section:
                if child.tag in ('narration', 'dialog'):
                    child.set('dlgseq', str(dlgseq_count))
                    dlgseq_count += 1
            
            section_count += 1
        
        if output_path is None:
            output_path = input_path

        print(f"[RESOURCE-ACCESS] Writing XML output", file=sys.stderr)
        print(f"  output_path: {output_path}", file=sys.stderr)
        print(f"  resourceType: xml", file=sys.stderr)
        print(f"  operation: write", file=sys.stderr)
        
        # ET.write
        tree.write(output_path, encoding='utf-8', xml_declaration=False)
        print(f"[RESOURCE-ACCESS] Successfully wrote XML output", file=sys.stderr)
        print(f"  output_path: {output_path}", file=sys.stderr)
        print(f"Successfully re-sequenced XML and saved to {output_path}")

    except Exception as e:
        print(f"An error occurred: {e}")

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Re-sequence XML chapters")
    parser.add_argument("xml_file", nargs="?", help="Path to the chapter XML file")
    parser.add_argument("--output", help="Optional output path. If not provided, overwrites the input file.")
    args = parser.parse_args()

    # Determine story directory from XML file path if provided
    story_config_dir = Path(".")
    if args.xml_file and ("/" in args.xml_file or os.path.sep in args.xml_file):
        xml_path_input = Path(args.xml_file)
        # Navigate up from story-xml/ to find story-config.yml
        for parent in xml_path_input.parents:
            potential_config = parent / "story-config.yml"
            if potential_config.exists():
                story_config_dir = parent
                break
            # Stop at Stories level
            if parent.name == "Stories" or (len(parent.parts) > 1 and parent.parent.name == "Stories"):
                break
    
    # Load config
    config_file = story_config_dir / "story-config.yml"
    if not config_file.exists():
        # Fallback to current directory
        config_file = Path("story-config.yml")
        if not config_file.exists():
            print(f"Error: story-config.yml not found.")
            sys.exit(1)

    with open(config_file, "r") as f:
        config = yaml.safe_load(f)
    
    global_cfg = config.get("global", {})
    config_base_dir = config_file.parent.resolve()

    configured_story_dir = Path(global_cfg.get("story-dir", "."))
    story_dir = configured_story_dir if configured_story_dir.is_absolute() else (config_base_dir / configured_story_dir).resolve()
    if not story_dir.exists():
        story_dir = config_base_dir

    story_xml_cfg = Path(global_cfg.get("story-xml", "story-xml"))
    story_xml_dir = story_xml_cfg if story_xml_cfg.is_absolute() else (story_dir / story_xml_cfg).resolve()
    logger.info(f"resolved resources config_file={config_file} story_dir={story_dir} story_xml_dir={story_xml_dir} xml_arg={args.xml_file}")

    if args.xml_file:
        if "/" in args.xml_file or os.path.sep in args.xml_file:
            xml_path = Path(args.xml_file)
        else:
            # Check if it exists in current dir
            xml_path = Path(args.xml_file)
            if not xml_path.exists():
                # Try in story-xml directory
                xml_path = story_xml_dir / args.xml_file
    else:
        # Look in story-xml directory
        if not story_xml_dir.exists():
            print(f"Error: Story XML directory {story_xml_dir} not found.")
            sys.exit(1)
        xml_files = list(story_xml_dir.glob("*.xml"))
        if not xml_files:
            print(f"No XML files found in {story_xml_dir}")
            return
        xml_path = xml_files[0]
        print(f"No file path indicated, using {xml_path}")

    if not xml_path.exists():
        print(f"File not found: {xml_path}")
        sys.exit(1)

    resequence_xml(str(xml_path), args.output)

if __name__ == "__main__":
    main()
