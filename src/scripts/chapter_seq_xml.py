#!/usr/bin/env python3

import sys
import os
import yaml
from pathlib import Path
from xml.etree import ElementTree as ET

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
    if not os.path.exists(input_path):
        print(f"Error: File {input_path} not found.")
        return

    try:
        # Using a custom parser to keep comments if any exist
        parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))
        tree = ET.parse(input_path, parser=parser)
        root = tree.getroot()

        section_count = 1
        for section in root.findall('.//section'):
            section.set('seq', str(section_count))
            section_count += 1

            dlgseq_count = 1
            # We want to iterate over all children of section in order
            for child in section:
                if child.tag in ('narration', 'dialog'):
                    child.set('dlgseq', str(dlgseq_count))
                    dlgseq_count += 1
        
        if output_path is None:
            output_path = input_path

        # To preserve some formatting, we might want to be careful.
        # But simple ET.write works.
        tree.write(output_path, encoding='utf-8', xml_declaration=False)
        print(f"Successfully re-sequenced XML and saved to {output_path}")

    except Exception as e:
        print(f"An error occurred: {e}")

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Re-sequence XML chapters")
    parser.add_argument("xml_file", nargs="?", help="Path to the chapter XML file")
    parser.add_argument("--output", help="Optional output path. If not provided, overwrites the input file.")
    args = parser.parse_args()

    # Load config
    config_file = "story-config.yml"
    if not os.path.exists(config_file):
        print(f"Error: {config_file} not found.")
        sys.exit(1)

    with open(config_file, "r") as f:
        config = yaml.safe_load(f)
    
    global_cfg = config.get("global", {})
    story_dir = Path(global_cfg.get("story-dir", "."))
    story_xml_dir = story_dir / global_cfg.get("story-xml", "story-xml")

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
