#!/usr/bin/env python3

import sys
import os
import yaml
import re
from pathlib import Path
from lxml import etree
from log_utils import setup_script_logging

logger = setup_script_logging('chapter_validate_xml')

# Unified XSD schema for both supported XML root formats.
# Supports both <story> and <chapter> roots, with either flat dialog/narration
# content or section-based content.
XSD_SCHEMA = """<?xml version="1.0" encoding="UTF-8"?>
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
  <xs:complexType name="DialogType">
    <xs:simpleContent>
      <xs:extension base="xs:string">
        <xs:attribute name="character" type="xs:string" use="required"/>
        <xs:attribute name="dlgseq" type="xs:integer" use="required"/>
        <xs:attribute name="emotion" type="xs:string" use="optional"/>
      </xs:extension>
    </xs:simpleContent>
  </xs:complexType>

  <xs:complexType name="NarrationType">
    <xs:simpleContent>
      <xs:extension base="xs:string">
        <xs:attribute name="character" type="xs:string" use="optional"/>
        <xs:attribute name="dlgseq" type="xs:integer" use="required"/>
        <xs:attribute name="emotion" type="xs:string" use="optional"/>
      </xs:extension>
    </xs:simpleContent>
  </xs:complexType>

  <xs:complexType name="SectionContentType">
    <xs:choice minOccurs="0" maxOccurs="unbounded">
      <xs:element name="dialog" type="DialogType"/>
      <xs:element name="narration" type="NarrationType"/>
    </xs:choice>
  </xs:complexType>

  <xs:complexType name="SectionType">
    <xs:complexContent>
      <xs:extension base="SectionContentType">
        <xs:attribute name="seq" type="xs:integer" use="required"/>
      </xs:extension>
    </xs:complexContent>
  </xs:complexType>

  <xs:complexType name="ChapterContentType">
    <xs:choice minOccurs="0" maxOccurs="unbounded">
      <xs:element name="dialog" type="DialogType"/>
      <xs:element name="narration" type="NarrationType"/>
      <xs:element name="section" type="SectionType"/>
    </xs:choice>
  </xs:complexType>

  <xs:element name="chapter">
    <xs:complexType>
      <xs:complexContent>
        <xs:extension base="ChapterContentType">
          <xs:attribute name="name" type="xs:string" use="optional"/>
        </xs:extension>
      </xs:complexContent>
    </xs:complexType>
  </xs:element>

  <xs:element name="story">
    <xs:complexType>
      <xs:sequence>
        <xs:element name="section" type="SectionType" maxOccurs="unbounded"/>
      </xs:sequence>
    </xs:complexType>
  </xs:element>
</xs:schema>
"""

def _generate_unified_schema_from_xml(root):
    """Derive a schema payload from the provided XML tree.

    Currently returns the canonical unified schema which supports both <story>
    and <chapter> roots. This keeps the --update-xsd workflow functional while
    ensuring the schema remains consistent across regenerations.
    """
    # Strip leading/trailing whitespace to keep formatting predictable when
    # reinserted into scripts.
    return XSD_SCHEMA.strip()


def update_xsd(xml_path, script_path):
    print(f"[RESOURCE-ACCESS] Reading XML for XSD update", file=sys.stderr)
    print(f"  xml_path: {xml_path}", file=sys.stderr)
    print(f"  resourceType: xml", file=sys.stderr)
    print(f"  operation: read", file=sys.stderr)
    try:
        xml_path = Path(xml_path)
        script_path = Path(script_path)

        if not xml_path.exists():
            print(f"[RESOURCE-ACCESS] XML NOT found: {xml_path}", file=sys.stderr)
            return False

        parser = etree.XMLParser(remove_blank_text=True)
        xml_doc = etree.parse(str(xml_path), parser)
        root = xml_doc.getroot()
        new_xsd = _generate_unified_schema_from_xml(root)

        try:
            script_content = script_path.read_text()
        except FileNotFoundError:
            print(f"Error: Script file not found: {script_path}")
            return False

        pattern = r'XSD_SCHEMA\s*=\s*"""[\s\S]*?"""'
        replacement = f'XSD_SCHEMA = """{new_xsd}\n"""'
        updated_content, count = re.subn(pattern, replacement, script_content, count=1, flags=re.DOTALL)

        if count == 0:
            print("Error: Could not find XSD_SCHEMA block in the script to update.")
            return False

        script_path.write_text(updated_content)
        print(f"Successfully updated XSD_SCHEMA in {script_path} using {xml_path}")
        return True

    except etree.XMLSyntaxError as e:
        print(f"Error updating XSD: XML Syntax Error in {xml_path}: {e}")
        return False
    except Exception as e:
        print(f"Error updating XSD: {e}")
        return False

def loose_review_xml(xml_path):
    """
    Performs a loose XML review of the input file:
    1. Checks for well-formedness (syntax).
    2. Checks basic structure (root tag is 'story' or 'chapter').
    3. Checks that tags are known ('story', 'chapter', 'section', 'narration', 'dialog').
    4. Checks for common attributes and provides hints.
    """
    print(f"[RESOURCE-ACCESS] Validating XML", file=sys.stderr)
    print(f"  xml_path: {xml_path}", file=sys.stderr)
    print(f"  resourceType: xml", file=sys.stderr)
    print(f"  operation: validate", file=sys.stderr)
    try:
        if not os.path.exists(xml_path):
            print(f"[RESOURCE-ACCESS] XML NOT found: {xml_path}", file=sys.stderr)
            return False
        print(f"[RESOURCE-ACCESS] Successfully read XML for validation", file=sys.stderr)
        print(f"  xml_path: {xml_path}", file=sys.stderr)
        parser = etree.XMLParser(remove_blank_text=True)
        xml_doc = etree.parse(xml_path, parser)
        root = xml_doc.getroot()
        
        success = True

        if root.tag not in ('story', 'chapter'):
            print(f"Loose Review Hint: Root tag is '{root.tag}', expected 'story' or 'chapter'.")
            success = False
        
        known_tags = {'story', 'chapter', 'section', 'narration', 'dialog'}
        
        for elem in root.iter():
            if elem.tag not in known_tags:
                print(f"Loose Review Hint: Unknown tag '{elem.tag}' found at line {elem.sourceline}.")
                success = False
            
            # Check for common attributes based on tag
            if elem.tag == 'section':
                if 'seq' not in elem.attrib:
                    print(f"Loose Review Hint: <section> at line {elem.sourceline} is missing 'seq' attribute.")
                    success = False
            elif elem.tag in ('narration', 'dialog'):
                if 'dlgseq' not in elem.attrib:
                    print(f"Loose Review Hint: <{elem.tag}> at line {elem.sourceline} is missing 'dlgseq' attribute.")
                    success = False
                if elem.tag == 'dialog' and 'character' not in elem.attrib:
                    print(f"Loose Review Hint: <dialog> at line {elem.sourceline} is missing 'character' attribute.")
                    success = False

        print(f"Loose review of {xml_path} completed.")
        return success

    except etree.XMLSyntaxError as e:
        print(f"Loose Review: XML Syntax Error in {xml_path}: {e}")
        return False
    except Exception as e:
        print(f"Loose Review: An unexpected error occurred: {e}")
        return False

def validate_sequence(xml_path):
    """
    Validates that the seq attribute in section tags and the dlgseq attribute
    in narration and dialog tags are sequenced properly (starting from 1 and incrementing).
    Supports both flat chapter/story roots and section-based content.
    """
    try:
        parser = etree.XMLParser(remove_blank_text=True)
        xml_doc = etree.parse(xml_path, parser)
        root = xml_doc.getroot()

        def validate_content_sequence(parent):
            expected_dlgseq = 1
            for child in parent:
                if child.tag in ('narration', 'dialog'):
                    actual_dlgseq = int(child.attrib.get('dlgseq', 0))
                    if actual_dlgseq != expected_dlgseq:
                        print(f"Sequence Error: <{child.tag}> at line {child.sourceline} has dlgseq='{actual_dlgseq}', expected '{expected_dlgseq}'.")
                        return False
                    expected_dlgseq += 1
            return True

        sections = root.findall('./section')
        if sections:
            expected_section_seq = 1
            for section in sections:
                actual_section_seq = int(section.attrib.get('seq', 0))
                if actual_section_seq != expected_section_seq:
                    print(f"Sequence Error: <section> at line {section.sourceline} has seq='{actual_section_seq}', expected '{expected_section_seq}'.")
                    return False

                if not validate_content_sequence(section):
                    return False

                expected_section_seq += 1
        else:
            if not validate_content_sequence(root):
                return False

        return True

    except Exception as e:
        print(f"Error during sequence validation: {e}")
        return False

def validate_and_fix_xml(xml_path):
    """
    Performs full validation: XSD schema validation and sequence validation.
    If sequencing is incorrect, it attempts to fix it using resequence_xml.
    Returns True if valid (or successfully fixed), False otherwise.
    """
    if not validate_xml(xml_path):
        return False
    
    if not validate_sequence(xml_path):
        print(f"Sequencing issue detected in {xml_path}. Running re-sequencing...")
        try:
            from chapter_seq_xml import resequence_xml
            resequence_xml(str(xml_path))
            print("Re-sequencing completed. Re-validating sequence...")
            if validate_sequence(xml_path):
                print("Sequence is now valid.")
                return True
            else:
                print("Error: Sequence still invalid after re-sequencing.")
                return False
        except ImportError:
            print("Error: chapter_seq_xml.py not found. Cannot automatically fix sequencing.")
            return False
        except Exception as e:
            print(f"Error during automatic re-sequencing: {e}")
            return False
    
    return True

def validate_xml(xml_path):
    logger.info(f"validate_xml xml_path={xml_path}")
    print(f"[RESOURCE-ACCESS] Validating XML against XSD schema", file=sys.stderr)
    print(f"  xml_path: {xml_path}", file=sys.stderr)
    print(f"  resourceType: xml", file=sys.stderr)
    print(f"  operation: validate", file=sys.stderr)
    try:
        if not os.path.exists(xml_path):
            print(f"[RESOURCE-ACCESS] XML NOT found: {xml_path}", file=sys.stderr)
            return False
        print(f"[RESOURCE-ACCESS] Successfully read XML for XSD validation", file=sys.stderr)
        print(f"  xml_path: {xml_path}", file=sys.stderr)

        # Parse XML first so we can choose the proper schema for the root format
        parser = etree.XMLParser(remove_blank_text=True)
        xml_doc = etree.parse(xml_path, parser)
        root = xml_doc.getroot()
        root_tag = root.tag

        if root_tag not in ('story', 'chapter'):
            print(f"[RESOURCE-ACCESS] XML validation failed", file=sys.stderr)
            print(f"  xml_path: {xml_path}", file=sys.stderr)
            print(f"Validation failed for {xml_path}:")
            print(f"  Unknown root element '{root_tag}'. Expected 'story' or 'chapter'.")
            return False

        schema_name = 'unified'
        print(f"[RESOURCE-ACCESS] Using XML schema", file=sys.stderr)
        print(f"  xml_path: {xml_path}", file=sys.stderr)
        print(f"  schema: {schema_name}", file=sys.stderr)
        print(f"  root: {root_tag}", file=sys.stderr)

        schema_root = etree.XML(XSD_SCHEMA.encode('utf-8'))
        schema = etree.XMLSchema(schema_root)
        
        if schema.validate(xml_doc):
            print(f"[RESOURCE-ACCESS] XML validation successful", file=sys.stderr)
            print(f"  xml_path: {xml_path}", file=sys.stderr)
            print(f"  schema: {schema_name}", file=sys.stderr)
            print(f"Success: {xml_path} is valid against the {schema_name} schema.")
            return True
        else:
            print(f"[RESOURCE-ACCESS] XML validation failed", file=sys.stderr)
            print(f"  xml_path: {xml_path}", file=sys.stderr)
            print(f"  schema: {schema_name}", file=sys.stderr)
            print(f"Validation failed for {xml_path}:")
            for error in schema.error_log:
                print(f"  Line {error.line}: {error.message}")
            return False

    except etree.XMLSyntaxError as e:
        print(f"[RESOURCE-ACCESS] XML syntax error", file=sys.stderr)
        print(f"  xml_path: {xml_path}", file=sys.stderr)
        print(f"XML Syntax Error in {xml_path}: {e}")
        return False
    except Exception as e:
        print(f"[RESOURCE-ACCESS] XML validation error", file=sys.stderr)
        print(f"  xml_path: {xml_path}", file=sys.stderr)
        print(f"An unexpected error occurred: {e}")
        return False

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Validate Chapter XML files against XSD")
    parser.add_argument("xml_file", nargs="?", help="Path to the chapter XML file")
    parser.add_argument("--update-xsd", help="Update the internal XSD schema using the specified XML file as a template")
    parser.add_argument("--output-xsd", action="store_true", help="Print the current XSD schema in a structured human readable format")
    args = parser.parse_args()

    # If --output-xsd is provided, print the schema and exit
    if args.output_xsd:
        print(XSD_SCHEMA)
        sys.exit(0)

    # If --update-xsd is provided, we perform the update and exit
    if args.update_xsd:
        # We need to find the update source file first using similar logic
        # Load config to resolve directories
        config_file = "story-config.yml"
        if not os.path.exists(config_file):
            print(f"Error: {config_file} not found.")
            sys.exit(1)

        with open(config_file, "r") as f:
            config = yaml.safe_load(f)
        
        global_cfg = config.get("global", {})
        story_dir = Path(global_cfg.get("story-dir", "."))
        story_xml_dir = story_dir / global_cfg.get("story-xml", "story-xml")

        update_source = args.update_xsd
        if "/" in update_source or os.path.sep in update_source:
            update_path = Path(update_source)
        else:
            update_path = Path(update_source)
            if not update_path.exists():
                update_path = story_xml_dir / update_source
        
        if not update_path.exists():
            print(f"Update source file not found: {update_path}")
            sys.exit(1)
        
        script_path = os.path.abspath(__file__)
        # Perform loose review before updating XSD
        if not loose_review_xml(str(update_path)):
            print("Aborting XSD update due to loose review failure.")
            sys.exit(1)
        
        if update_xsd(str(update_path), script_path):
            sys.exit(0)
        else:
            sys.exit(1)

    # Determine story directory from XML file path if provided
    story_config_dir = Path(".")
    if args.xml_file and ("/" in args.xml_file or os.path.sep in args.xml_file):
        xml_path_input = Path(args.xml_file)
        # Navigate up from story-xml/ to find story-config.yml
        # path like: Stories/Story-Name/story-xml/file.xml
        # story-config.yml should be at: Stories/Story-Name/story-config.yml
        if xml_path_input.parts[0] == "Stories" or "story-xml" in xml_path_input.parts:
            # Find the story root (parent of story-xml or similar)
            for parent in xml_path_input.parents:
                potential_config = parent / "story-config.yml"
                if potential_config.exists():
                    story_config_dir = parent
                    break
                # Stop at Stories level
                if parent.name == "Stories" or parent.parent.name == "Stories":
                    break
    
    # Load config (logic from chapter_seq_xml.py)
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
        xml_files = sorted(list(story_xml_dir.glob("*.xml")))
        if not xml_files:
            print(f"No XML files found in {story_xml_dir}")
            return
        xml_path = xml_files[0]
        print(f"No file path indicated, using {xml_path}")

    if not xml_path.exists():
        print(f"File not found: {xml_path}")
        sys.exit(1)

    if validate_and_fix_xml(str(xml_path)):
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()
