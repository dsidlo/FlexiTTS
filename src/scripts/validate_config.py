#!/usr/bin/env python3

import yaml
import json
import sys
import os
import re
from pathlib import Path
from jsonschema import validate, ValidationError

import tomllib

def get_project_version():
    """Get the project name and version from pyproject.toml."""
    try:
        with open('pyproject.toml', 'rb') as f:
            data = tomllib.load(f)
        project = data['project']
        name = project.get('name', 'flexitts')
        version = project.get('version', 'unknown')
        return f"{name} {version}"
    except (FileNotFoundError, tomllib.TOMLDecodeError, KeyError):
        return "flexitts unknown"


def get_schema():
    # [SCHEMA_MARKER_START]
    # Define the schema based on the current story-config.yml
    #
    # Keys are OPTIONAL unless noted in "required". The user-facing schema is
    # deliberately permissive: optional documentation/behavior keys such as
    # "description", "custom-voice", "dialog-effects", "sox-effects",
    # "tts-device", "max_voice_cache_size", "api_key", "temperature", ...
    # must not fail validation for configs that omit them.
    return {
        "type": "object",
        "properties": {
                "characters": {
                        "type": "array",
                        "minItems": 1,
                        "items": {
                                "type": "object",
                                "properties": {
                                        "name": {
                                                "type": "string"
                                        },
                                        "description": {
                                                "type": "string"
                                        },
                                        "voice-sample": {
                                                "type": "string"
                                        },
                                        "custom-voice": {
                                                "type": "object",
                                                "properties": {
                                                        "language": {"type": "string"},
                                                        "speaker": {"type": "string"},
                                                        "instruct": {"type": "string"},
                                                        "emotions": {
                                                                "type": "array",
                                                                "items": {
                                                                        "type": "object",
                                                                        "properties": {
                                                                                "emotion": {"type": "string"},
                                                                                "name": {"type": "string"},
                                                                                "instruct": {"type": "string"},
                                                                                "voice-sample": {"type": "string"},
                                                                                "sox-effects": {
                                                                                        "type": "array",
                                                                                        "items": {"type": "string"}
                                                                                }
                                                                        },
                                                                        "additionalProperties": False
                                                                }
                                                        }
                                                },
                                                "additionalProperties": False
                                        },
                                        "cloned-emotion": {
                                                "type": "array",
                                                "items": {
                                                        "type": "object",
                                                        "properties": {
                                                                "emotion": {"type": "string"},
                                                                "voice-sample": {"type": "string"},
                                                                "sox-effects": {
                                                                        "type": "array",
                                                                        "items": {"type": "string"}
                                                                },
                                                                "dialog-effects": {
                                                                        "type": "array",
                                                                        "items": {"type": "string"}
                                                                }
                                                        },
                                                        "additionalProperties": False
                                                }
                                        },
                                        "sox-effects": {
                                                "type": "array",
                                                "items": {"type": "string"}
                                        },
                                        "dialog-effects": {
                                                "type": "array",
                                                "items": {"type": "string"}
                                        }
                                },
                                "additionalProperties": False,
                                "required": [
                                        "name"
                                ]
                        }
                },
                "dialog-effects": {
                        "type": "array",
                        "items": {
                                "type": "object",
                                "properties": {
                                        "name": {
                                                "type": "string"
                                        },
                                        "sox-effects": {
                                                "type": "array",
                                                "items": {
                                                        "type": "string"
                                                }
                                        }
                                },
                                "additionalProperties": False,
                                "required": [
                                        "name",
                                        "sox-effects"
                                ]
                        }
                },
                "global": {
                        "type": "object",
                        "properties": {
                                "chapters": {
                                        "type": "string"
                                },
                                "clip-separation": {
                                        "type": "number"
                                },
                                "clips": {
                                        "type": "string"
                                },
                                "logs": {
                                        "type": "string"
                                },
                                "max_voice_cache_size": {
                                        "type": "integer"
                                },
                                "story-audio": {
                                        "type": "string"
                                },
                                "story-dir": {
                                        "type": "string"
                                },
                                "story-xml": {
                                        "type": "string"
                                },
                                "tts-device": {
                                        "type": "string"
                                },
                                "voices": {
                                        "type": "string"
                                }
                        },
                        "additionalProperties": False,
                        "required": [
                                "chapters",
                                "clips",
                                "logs",
                                "story-audio",
                                "story-dir",
                                "story-xml",
                                "voices"
                        ]
                },
                "llm-xml-generator": {
                        "type": "array",
                        "items": {
                                "type": "object",
                                "properties": {
                                        "api_base": {
                                                "type": "string"
                                        },
                                        "api_key": {
                                                "type": "string"
                                        },
                                        "default-llm": {
                                                "type": "string"
                                        },
                                        "llm": {
                                                "type": "string"
                                        },
                                        "model": {
                                                "type": "string"
                                        },
                                        "temperature": {
                                                "type": "number"
                                        }
                                },
                                "additionalProperties": False,
                                "required": [
                                        "model"
                                ]
                        }
                },
                "story-audio-post-process": {
                        "type": "object",
                        "properties": {
                                "sox-effects": {
                                        "type": "array",
                                        "items": {
                                                "type": "string"
                                        }
                                }
                        },
                        "additionalProperties": False
                }
        },
        "additionalProperties": False,
        "required": [
                "characters",
                "global"
        ]
}
    # [SCHEMA_MARKER_END]

def infer_schema(data):
    if isinstance(data, dict):
        properties = {}
        required = []
        for k, v in data.items():
            properties[k] = infer_schema(v)
            required.append(k)
        return {
            "type": "object",
            "properties": properties,
            "additionalProperties": False,
            "required": required
        }
    elif isinstance(data, list):
        if not data:
            return {"type": "array"}
        
        # Merge schemas of all items to handle optional fields
        merged_properties = {}
        merged_required = None
        item_types = set()
        
        for item in data:
            item_schema = infer_schema(item)
            item_types.add(item_schema["type"])
            
            if item_schema["type"] == "object":
                for k, v in item_schema["properties"].items():
                    if k not in merged_properties:
                        merged_properties[k] = v
                    # Optional: could merge v with existing if they differ
                
                if merged_required is None:
                    merged_required = set(item_schema["required"])
                else:
                    merged_required &= set(item_schema["required"])
            
        if len(item_types) == 1:
            item_type = item_types.pop()
            if item_type == "object":
                items_schema = {
                    "type": "object",
                    "properties": merged_properties,
                    "additionalProperties": False
                }
                if merged_required:
                    items_schema["required"] = sorted(list(merged_required))
            else:
                # Use the schema from the first item for non-objects
                items_schema = infer_schema(data[0])
        else:
            # Heterogeneous array, just use the first item's type or a generic item
            items_schema = infer_schema(data[0])
            
        return {
            "type": "array",
            "minItems": 1,
            "items": items_schema
        }
    elif isinstance(data, bool):
        return {"type": "boolean"}
    elif isinstance(data, int):
        return {"type": "integer"}
    elif isinstance(data, float):
        return {"type": "number"}
    elif isinstance(data, str):
        return {"type": "string"}
    elif data is None:
        return {"type": "null"}
    else:
        return {"type": "string"}

def update_script_schema(new_schema):
    script_path = os.path.abspath(__file__)
    with open(script_path, 'r') as f:
        lines = f.readlines()

    schema_json = json.dumps(new_schema, indent=8)
    schema_python = schema_json.replace(": true", ": True").replace(": false", ": False").replace(": null", ": None")
    
    start_idx = -1
    end_idx = -1
    for i, line in enumerate(lines):
        if "[SCHEMA_MARKER_START]" in line:
            start_idx = i
        if "[SCHEMA_MARKER_END]" in line:
            end_idx = i
            break
    
    if start_idx == -1 or end_idx == -1:
        print("Error: Could not find schema markers in the script.")
        return False

    new_lines = lines[:start_idx + 1]
    new_lines.append("    # Define the schema based on the current story-config.yml\n")
    new_lines.append(f"    return {schema_python}\n")
    new_lines.extend(lines[end_idx:])

    with open(script_path, 'w') as f:
        f.writelines(new_lines)
    
    print(f"Successfully updated internal schema in {script_path}")
    return True

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

        # Cross-reference validation for voice-sample files against global.voices
        voices_dir_name = str((data.get("global") or {}).get("voices", "")).strip()

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

            # Emotion name uniqueness per character (across all emotion lists)
            emotion_entries = []
            for key, entry in (("emotions", char.get("custom-voice", {}).get("emotions", [])),
                               ("cloned-emotion", char.get("cloned-emotion", [])),
                               ("emotions", char.get("emotions", []))):
                if isinstance(entry, list):
                    emotion_entries.extend((key, k, e) for k, e in enumerate(entry))

            seen_emotions = {}
            for key, k, em in emotion_entries:
                if not isinstance(em, dict):
                    continue
                emotion_name = str(em.get("emotion") or em.get("name") or "").strip()
                if not emotion_name:
                    continue
                norm = emotion_name.lower()
                if norm in seen_emotions:
                    prev_key, prev_k = seen_emotions[norm]
                    print(f"Validation error in {file_path}:")
                    print(f"Message: Duplicate emotion '{emotion_name}' in character '{char['name']}' (first defined in {prev_key}[{prev_k}], duplicated in {key}[{k}]).")
                    path = ["characters", i, key, k]
                    line_no = find_line_number(path, lines)
                    print(f"Location: {'.'.join(map(str, path))} (around line {line_no})")
                    print_context(lines, line_no - 1)
                    success = False
                else:
                    seen_emotions[norm] = (key, k)

            # cloned-emotion entries require a voice-sample value
            for k, em in enumerate(char.get("cloned-emotion", []) or []):
                if isinstance(em, dict) and not str(em.get("voice-sample", "")).strip():
                    print(f"Validation error in {file_path}:")
                    print(f"Message: cloned-emotion[{k}] of character '{char['name']}' is missing 'voice-sample'.")
                    path = ["characters", i, "cloned-emotion", k]
                    line_no = find_line_number(path, lines)
                    print(f"Location: {'.'.join(map(str, path))} (around line {line_no})")
                    print_context(lines, line_no - 1)
                    success = False

            # Per-emotion dialog-effects references (cloned-emotion level)
            for k, em in enumerate(char.get("cloned-emotion", []) or []):
                if not isinstance(em, dict):
                    continue
                em_effects = em.get("dialog-effects", [])
                if isinstance(em_effects, str):
                    em_effects = [em_effects]
                for j, effect_name in enumerate(em_effects):
                    if effect_name not in defined_effects:
                        print(f"Validation error in {file_path}:")
                        print(f"Message: Named dialog-effect '{effect_name}' used by emotion '{em.get('emotion', '?')}' of character '{char['name']}' is not defined.")
                        path = ["characters", i, "cloned-emotion", k, "dialog-effects", j]
                        line_no = find_line_number(path, lines)
                        print(f"Location: {'.'.join(map(str, path))} (around line {line_no})")
                        print_context(lines, line_no - 1)
                        success = False

            # Per-emotion voice-sample values must be non-empty strings when
            # present (custom-voice emotions + cloned-emotion entries). These
            # enable the emotion-sample clone dispatch for expressiveness.
            emotion_sample_lists = []
            cv = char.get("custom-voice")
            if isinstance(cv, dict) and isinstance(cv.get("emotions"), list):
                emotion_sample_lists.append(("custom-voice", "emotions", cv["emotions"]))
            if isinstance(char.get("cloned-emotion"), list):
                emotion_sample_lists.append(("characters", "cloned-emotion", char["cloned-emotion"]))
            for parent_key, list_key, emotions in emotion_sample_lists:
                for k, em in enumerate(emotions):
                    if not isinstance(em, dict):
                        continue
                    if "voice-sample" not in em:
                        continue
                    sample = str(em.get("voice-sample", "") or "").strip()
                    if not sample:
                        em_name = str(em.get("emotion") or em.get("name") or k)
                        print(f"Validation error in {file_path}:")
                        print(f"Message: Emotion '{em_name}' of character '{char['name']}' has an empty 'voice-sample'.")
                        path = [parent_key if parent_key != "characters" else i, "custom-voice" if list_key == "emotions" and parent_key != "characters" else list_key, k, "voice-sample"]
                        line_no = find_line_number(path, lines)
                        print(f"Location: {'.'.join(map(str, path))} (around line {line_no})")
                        print_context(lines, line_no - 1)
                        success = False

            # voice-sample file existence (relative to global.voices), when the
            # story directory is reachable from the config location.
            sample = str(char.get("voice-sample", "") or "").strip()
            if sample and voices_dir_name:
                config_dir = Path(file_path).resolve().parent
                candidate = Path(sample)
                if not candidate.is_absolute():
                    voices_path = config_dir / voices_dir_name
                    if voices_path.is_dir():
                        resolved = (voices_path / sample).resolve()
                        if not resolved.exists():
                            print(f"Validation warning in {file_path}:")
                            print(f"Message: voice-sample '{sample}' of character '{char['name']}' not found at {resolved}.")
                            path = ["characters", i, "voice-sample"]
                            line_no = find_line_number(path, lines)
                            print(f"Location: {'.'.join(map(str, path))} (around line {line_no})")
                            # Warning only: file may be provisioned later; render
                            # preflight hard-fails on missing samples.

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
    parser.add_argument("--update-schema", help="Update the internal schema using the specified well-formed YAML file")
    parser.add_argument('--version', '-V', action='version', version=get_project_version(), help='Show FlexiTTS version and exit')
    args = parser.parse_args()

    if args.update_schema:
        if not os.path.exists(args.update_schema):
            print(f"File not found: {args.update_schema}")
            sys.exit(1)
        
        with open(args.update_schema, 'r') as f:
            try:
                data = yaml.safe_load(f)
            except yaml.YAMLError as e:
                print(f"Error parsing YAML file {args.update_schema}: {e}")
                sys.exit(1)
        
        if not data:
            print(f"YAML file {args.update_schema} is empty.")
            sys.exit(1)
            
        new_schema = infer_schema(data)
        if update_script_schema(new_schema):
            sys.exit(0)
        else:
            sys.exit(1)

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
