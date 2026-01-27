import yaml
import json
import sys
import os
import re
from jsonschema import validate, ValidationError

def get_schema():
    # Define the schema based on the current story-config.yml
    return {
        "type": "object",
        "properties": {
            "global": {
                "type": "object",
                "properties": {
                    "story-dir": {"type": "string"},
                    "voices": {"type": "string"},
                    "chapters": {"type": "string"},
                    "story-xml": {"type": "string"},
                    "logs": {"type": "string"},
                    "story-audio": {"type": "string"},
                    "clips": {"type": "string"}
                },
                "additionalProperties": False,
                "required": ["story-dir", "voices", "chapters", "story-xml", "logs", "story-audio", "clips"]
            },
            "llm-xml-generator": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "properties": {
                        "default-llm": {"type": "string"},
                        "llm": {"type": "string"},
                        "model": {"type": "string"},
                        "api_key": {"type": "string"},
                        "api_base": {"type": "string"},
                        "temperature": {"type": "number"},
                        "max_tokens": {"type": "integer"},
                        "rpm": {"type": "integer"},
                        "timeout": {"type": "integer"}
                    },
                    "additionalProperties": False
                }
            },
            "dialog-effects": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "sox-effects": {
                            "type": "array",
                            "minItems": 1,
                            "items": {"type": "string"}
                        }
                    },
                    "additionalProperties": False,
                    "required": ["name", "sox-effects"]
                }
            },
            "story-audio-post-process": {
                "type": "object",
                "properties": {
                    "sox-effects": {
                        "type": "array",
                        "minItems": 1,
                        "items": {"type": "string"}
                    }
                },
                "additionalProperties": False,
                "required": ["sox-effects"]
            },
            "characters": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "voice-sample": {"type": "string"},
                        "dialog-effects": {
                            "type": "array",
                            "minItems": 1,
                            "items": {"type": "string"}
                        },
                        "sox-effects": {
                            "type": "array",
                            "minItems": 1,
                            "items": {"type": "string"}
                        },
                        "custom-voice": {
                            "type": "object",
                            "properties": {
                                "language": {"type": "string"},
                                "speaker": {"type": "string"},
                                "instruct": {"type": "string"}
                            },
                            "additionalProperties": False,
                            "required": ["language", "speaker", "instruct"]
                        }
                    },
                    "additionalProperties": False,
                    "required": ["name"]
                }
            }
        },
        "additionalProperties": False,
        "required": ["global", "llm-xml-generator", "dialog-effects", "story-audio-post-process", "characters"]
    }

def find_line_number(path, data_lines):
    # path is a list of keys/indices, e.g., ['characters', 10, 'custom-voice']
    # If the validation failed because of a mis-indented key, that key
    # might appear multiple times in the file. We want to find the one
    # that matches the actual structure as closely as possible.
    
    # Let's try to match the WHOLE path at once if possible, or piece by piece
    # but starting from the end of the file or something?
    
    # Actually, the problem is that 'dialog-effects' IS at column 0 at line 29.
    # When it's also at column 0 at line 75, we have two 'dialog-effects' at column 0.
    # yaml.safe_load will only keep the LAST one for the same key at the same level.
    
    # If the error is "'cave' is not of type 'array'", it means the data['dialog-effects'] 
    # is the string 'cave' (from line 75) instead of the list (from line 29).
    
    # So we should be looking for the occurrence that actually matches the value 
    # that caused the error, or just the last occurrence if it's a duplicate key.

    current_line = 0
    current_indent = -1
    
    for idx, key in enumerate(path):
        found = False
        if isinstance(key, int):
            # We are looking for the n-th item in an array
            # Array items start with "- " at some indentation level
            count = -1
            # We need to find the start of the array first to know the indentation
            # But usually it starts right after the parent key or on the next line
            for i in range(current_line, len(data_lines)):
                line = data_lines[i]
                stripped = line.lstrip()
                if not stripped or stripped.startswith('#'):
                    continue
                
                indent = len(line) - len(stripped)
                
                # If we just started, we look for the first "- "
                if stripped.startswith('- '):
                    if count == -1:
                        item_indent = indent
                    
                    if indent == item_indent:
                        count += 1
                        if count == key:
                            current_line = i
                            current_indent = indent
                            found = True
                            break
                
                # If we hit a line with less or equal indentation than the parent (and it's not a list item),
                # we might have left the array, but this is tricky without a real parser.
                # For now, just keep going until we find the n-th item.
            
        else:
            # Search for "key:" at an indentation greater than current_indent
            # AND if we just came from an array index, it must be the key WITHIN that array item
            
            # Start search from current_line
            # We want to find the LAST occurrence of the key that matches the indentation constraints
            # but wait, YAML usually defines keys once.
            # If we mis-indented a key to column 0, it might be found EARLIER than where we expect it
            # if we only search forward from current_line.
            
            # Actually, the problem is that we find the FIRST occurrence of "dialog-effects:"
            # which happens to be at line 29.
            
            # If we are looking for a key that is part of a validation error, 
            # and that key is NOT found at the expected indentation level, 
            # we might want to search the WHOLE file but favor the one that is closest 
            # to the current_line or matches the structure better.
            
            # However, for mis-indentation to column 0, the key effectively becomes a global key.
            # The current logic finds it at line 29 because it's the first 'dialog-effects:' it sees.
            
            best_line = -1
            for i in range(len(data_lines)):
                line = data_lines[i]
                stripped = line.lstrip()
                if not stripped or stripped.startswith('#'):
                    continue
                
                indent = len(line) - len(stripped)
                
                # Look for "key:" or "- key:"
                if re.search(rf"^-?\s*{re.escape(str(key))}\s*:", stripped):
                    # If this is the FIRST key in the path, it must be at indent 0
                    if idx == 0:
                        if indent == 0:
                            # Favor the LAST occurrence for top-level keys
                            current_line = i
                            current_indent = indent
                            found = True
                            # Don't break, keep looking for later ones
                            continue
                        else:
                            # Not a top-level key, but might be what we are looking for if nothing else matches
                            if not found:
                                best_line = i
                            continue

                    # Check if it's in a plausible location
                    # If we have a current_line, it should probably be after it
                    if i >= current_line:
                        # Favor the first one we find after current_line that matches indentation if possible
                        if indent >= current_indent:
                            current_line = i
                            current_indent = indent
                            found = True
                            break
                        elif best_line == -1 or abs(i - current_line) < abs(best_line - current_line):
                            # Keep track of the occurrence closest to current_line
                            best_line = i
            
            if not found and best_line != -1:
                current_line = best_line
                current_indent = len(data_lines[best_line]) - len(data_lines[best_line].lstrip())
                found = True

        if not found:
            # If a level is not found, we stay at the last known line
            break
            
    return current_line + 1

def print_context(lines, index):
    # surrounding 3 lines means 1 before and 1 after? 
    # Or "surrounding 3" usually means 3 before and 3 after?
    # "output the line number and the surrounding 3 lines" 
    # I'll output index-1, index, index+1 (total 3 lines) or maybe 3 lines including the error.
    # User said "surrounding 3 lines", I will show 3 lines around it.
    start = max(0, index - 1)
    end = min(len(lines), index + 2)
    for i in range(start, end):
        prefix = "-> " if i == index else "   "
        print(f"{i+1:4}{prefix}{lines[i].rstrip()}")

def validate_config(file_path):
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return False

    with open(file_path, 'r') as f:
        lines = f.readlines()
        content = "".join(lines)
    
    try:
        data = yaml.safe_load(content)
    except yaml.YAMLError as e:
        print(f"YAML parsing error in {file_path}:")
        if hasattr(e, 'problem_mark'):
            mark = e.problem_mark
            print(f"Error at line {mark.line + 1}, column {mark.column + 1}: {e.problem}")
            print_context(lines, mark.line)
        else:
            print(e)
        return False

    schema = get_schema()
    try:
        validate(instance=data, schema=schema)
        
        # Cross-reference validation for dialog-effects
        defined_effects = {eff["name"] for eff in data.get("dialog-effects", [])}
        success = True
        
        for i, char in enumerate(data.get("characters", [])):
            # Check top-level dialog-effects in character
            char_effects = char.get("dialog-effects", [])
            if isinstance(char_effects, str):
                char_effects = [char_effects]
            
            for j, effect_name in enumerate(char_effects):
                if effect_name not in defined_effects:
                    print(f"Validation error in {file_path}:")
                    print(f"Message: Named dialog-effect '{effect_name}' used by character '{char['name']}' is not defined.")
                    path = ["characters", i, "dialog-effects", j]
                    line_no = find_line_number(path, lines)
                    print(f"Location: {'.'.join(map(str, path))} (around line {line_no})")
                    print_context(lines, line_no - 1)
                    success = False

        if not success:
            return False

        print(f"Configuration file {file_path} is valid.")
        return True
    except ValidationError as e:
        print(f"Validation error in {file_path}:")
        print(f"Message: {e.message}")
        
        path = list(e.path)
        # For 'additionalProperties' errors, the path doesn't include the offending key
        # but it's in the message or the validator property.
        # e.message is "Additional properties are not allowed ('dialog-effects' was unexpected)"
        # e.validator == 'additionalProperties'
        # e.instance is the dictionary that has the additional property
        
        search_path = list(path)
        if e.validator == 'additionalProperties':
            # Try to extract the key from the message
            match = re.search(r"'(.*?)' was unexpected", e.message)
            if match:
                search_path.append(match.group(1))

        line_no = find_line_number(search_path, lines)
        print(f"Location: {'.'.join(map(str, search_path))} (around line {line_no})")
        print_context(lines, line_no - 1)

        # Check for mis-indented array entries if the array is empty or None
        is_empty_array = (e.validator == 'minItems' and e.instance == [])
        is_none = (e.validator == 'type' and e.instance is None and (isinstance(e.validator_value, str) and e.validator_value == 'array' or isinstance(e.validator_value, list) and 'array' in e.validator_value))
        
        if is_empty_array or is_none:
            # The next line after the empty/null array might contain a mis-indented item
            if line_no < len(lines):
                # Search forward for the next non-comment, non-empty line
                for i in range(line_no, len(lines)):
                    next_line = lines[i]
                    stripped = next_line.lstrip()
                    if not stripped or stripped.startswith('#'):
                        continue
                    if stripped.startswith('- '):
                        print("\nPossible mis-indented array entry found on next line:")
                        print(f"{i+1:4} -> {next_line.rstrip()}")
                        print("Check the indentation of the above line.")
                    break
        
        return False


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Validate story-config.yml")
    parser.add_argument("file", nargs="?", default="story-config.yml", help="Path to the config file")
    parser.add_argument("--json", action="store_true", help="Output JSON equivalent of the config")
    args = parser.parse_args()

    if args.json:
        if os.path.exists(args.file):
            with open(args.file, 'r') as f:
                data = yaml.safe_load(f)
                print(json.dumps(data, indent=2))
        else:
            print(f"File not found: {args.file}")
            sys.exit(1)
    else:
        success = validate_config(args.file)
        if not success:
            sys.exit(1)
