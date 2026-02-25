#!/usr/bin/env python3

import sys
import os
import yaml
import re
from pathlib import Path
from lxml import etree

# Internal XSD Schema based on 01-Hendrix.xml
XSD_SCHEMA = """<?xml version="1.0" encoding="UTF-8"?>
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
  <xs:element name="story">
    <xs:complexType>
      <xs:sequence>
        <xs:element name="section" maxOccurs="unbounded">
          <xs:complexType>
            <xs:choice maxOccurs="unbounded">
              <xs:element name="dialog">
                <xs:complexType>
                  <xs:simpleContent>
                    <xs:extension base="xs:string">
                      <xs:attribute name="character" type="xs:string" use="required"/>
                      <xs:attribute name="dlgseq" type="xs:integer" use="required"/>
                      <xs:attribute name="emotion" type="xs:string" use="required"/>
                      <xs:attribute name="post-effects" type="xs:string" use="optional"/>
                    </xs:extension>
                  </xs:simpleContent>
                </xs:complexType>
              </xs:element>
              <xs:element name="narration">
                <xs:complexType>
                  <xs:simpleContent>
                    <xs:extension base="xs:string">
                      <xs:attribute name="dlgseq" type="xs:integer" use="required"/>
                      <xs:attribute name="emotion" type="xs:string" use="required"/>
                    </xs:extension>
                  </xs:simpleContent>
                </xs:complexType>
              </xs:element>
            </xs:choice>
            <xs:attribute name="seq" type="xs:integer" use="required"/>
          </xs:complexType>
        </xs:element>
      </xs:sequence>
    </xs:complexType>
  </xs:element>
</xs:schema>
"""

def update_xsd(xml_path, script_path):
    try:
        parser = etree.XMLParser(remove_blank_text=True)
        xml_doc = etree.parse(xml_path, parser)
        root = xml_doc.getroot()

        # Simple schema generation logic focused on the story structure
        # We'll build a schema that mirrors the elements and attributes found in the XML
        
        schema_lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">',
            '  <xs:element name="story">',
            '    <xs:complexType>',
            '      <xs:sequence>',
            '        <xs:element name="section" maxOccurs="unbounded">',
            '          <xs:complexType>',
            '            <xs:choice maxOccurs="unbounded">'
        ]

        # Gather all elements found in sections to build the choice block
        elements_in_sections = {}
        for section in root.findall("section"):
            for child in section:
                if child.tag not in elements_in_sections:
                    elements_in_sections[child.tag] = set(child.attrib.keys())
                else:
                    elements_in_sections[child.tag].update(child.attrib.keys())

        for tag, attrs in sorted(elements_in_sections.items()):
            schema_lines.append(f'              <xs:element name="{tag}">')
            schema_lines.append('                <xs:complexType>')
            schema_lines.append('                  <xs:simpleContent>')
            schema_lines.append('                    <xs:extension base="xs:string">')
            for attr in sorted(attrs):
                # Try to infer type for common attributes
                attr_type = "xs:integer" if attr in ("dlgseq", "seq") else "xs:string"
                use = "required" if attr in ("emotion", "character", "dlgseq") else "optional"
                schema_lines.append(f'                      <xs:attribute name="{attr}" type="{attr_type}" use="{use}"/>')
            schema_lines.append('                    </xs:extension>')
            schema_lines.append('                  </xs:simpleContent>')
            schema_lines.append('                </xs:complexType>')
            schema_lines.append('              </xs:element>')

        schema_lines.extend([
            '            </xs:choice>',
            '            <xs:attribute name="seq" type="xs:integer" use="required"/>',
            '          </xs:complexType>',
            '        </xs:element>',
            '      </xs:sequence>',
            '    </xs:complexType>',
            '  </xs:element>',
            '</xs:schema>'
        ])

        new_xsd = "\n".join(schema_lines)

        # Read the script and replace XSD_SCHEMA
        with open(script_path, 'r') as f:
            script_content = f.read()

        # Improved pattern to be more robust
        pattern = r'XSD_SCHEMA = """.*?"""'
        replacement = f'XSD_SCHEMA = """{new_xsd}\n"""'
        
        updated_content = re.sub(pattern, replacement, script_content, count=1, flags=re.DOTALL)
        
        if updated_content == script_content:
            print("Error: Could not find XSD_SCHEMA block in the script to update.")
            return False

        with open(script_path, 'w') as f:
            f.write(updated_content)
        
        print(f"Successfully updated XSD_SCHEMA in {script_path} using {xml_path}")
        return True

    except Exception as e:
        print(f"Error updating XSD: {e}")
        return False

def loose_review_xml(xml_path):
    """
    Performs a loose XML review of the input file:
    1. Checks for well-formedness (syntax).
    2. Checks basic structure (root tag is 'story').
    3. Checks that tags are known ('story', 'section', 'narration', 'dialog').
    4. Checks for common attributes and provides hints.
    """
    try:
        parser = etree.XMLParser(remove_blank_text=True)
        xml_doc = etree.parse(xml_path, parser)
        root = xml_doc.getroot()
        
        success = True

        if root.tag != 'story':
            print(f"Loose Review Hint: Root tag is '{root.tag}', expected 'story'.")
            success = False
        
        known_tags = {'story', 'section', 'narration', 'dialog'}
        
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
                if 'emotion' not in elem.attrib:
                    print(f"Loose Review Hint: <{elem.tag}> at line {elem.sourceline} is missing 'emotion' attribute.")
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
    in narrator and dialog tags are sequenced properly (starting from 1 and incrementing).
    """
    try:
        parser = etree.XMLParser(remove_blank_text=True)
        xml_doc = etree.parse(xml_path, parser)
        root = xml_doc.getroot()
        
        expected_section_seq = 1
        for section in root.findall("section"):
            actual_section_seq = int(section.attrib.get("seq", 0))
            if actual_section_seq != expected_section_seq:
                print(f"Sequence Error: <section> at line {section.sourceline} has seq='{actual_section_seq}', expected '{expected_section_seq}'.")
                return False
            
            expected_dlgseq = 1
            for child in section:
                if child.tag in ('narration', 'dialog'):
                    actual_dlgseq = int(child.attrib.get("dlgseq", 0))
                    if actual_dlgseq != expected_dlgseq:
                        print(f"Sequence Error: <{child.tag}> at line {child.sourceline} has dlgseq='{actual_dlgseq}', expected '{expected_dlgseq}'.")
                        return False
                    expected_dlgseq += 1
            
            expected_section_seq += 1
            
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
    try:
        # Load XSD
        schema_root = etree.XML(XSD_SCHEMA.encode('utf-8'))
        schema = etree.XMLSchema(schema_root)
        
        # Parse XML
        parser = etree.XMLParser(remove_blank_text=True)
        xml_doc = etree.parse(xml_path, parser)
        
        # Validate
        if schema.validate(xml_doc):
            print(f"Success: {xml_path} is valid against the schema.")
            return True
        else:
            print(f"Validation failed for {xml_path}:")
            for error in schema.error_log:
                print(f"  Line {error.line}: {error.message}")
            return False

    except etree.XMLSyntaxError as e:
        print(f"XML Syntax Error in {xml_path}: {e}")
        return False
    except Exception as e:
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

    # Load config (logic from chapter_seq_xml.py)
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
