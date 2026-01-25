import os
import sys
import yaml
import argparse
from pathlib import Path
from litellm import completion
from dotenv import load_dotenv

def load_config(config_path="story-config.yml"):
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

def get_prompt_template(notes_path="./FlexiTTS-AI-Prompt-Chapter-to-XML.md"):
    with open(notes_path, 'r') as f:
        content = f.read()
    
    # Extract the XML prompt section
    # Based on the file content, it's between ```xml and ```
    start_marker = "## Story to XML Generation (AI Prompt)\n\n```xml"
    end_marker = "```"
    
    start_index = content.find(start_marker)
    if start_index == -1:
        raise ValueError("Could not find prompt template.")
    
    start_index += len(start_marker)
    end_index = content.find(end_marker, start_index)
    
    if end_index == -1:
        raise ValueError("Could not find end of prompt template.")
        
    template = content[start_index:end_index].strip()
    return template

def main():
    # Load environment variables from ~/.env
    env_path = Path.home() / ".env"
    load_dotenv(dotenv_path=env_path)

    config = load_config()
    story_dir = Path(config['global']['story-dir'])
    chapters_dir = story_dir / config['global']['chapters']
    xml_dir = story_dir / config['global']['story-xml']

    parser = argparse.ArgumentParser(description="Convert story chapter markdown to XML using LLM.")
    parser.add_argument("file_path", nargs="?", help="Path to the markdown file.")
    # add a flag argument to process all file in config.global.chapters --all-chapters
    parser.add_argument("--all-chapters", action="store_true", help="Process all files in the chapters directory.")
    parser.add_argument("--llm", type=str, help="Name of the LLM configuration to use from story-config.yml.")
    args = parser.parse_args()

    chapter_files = []
    input_file = None

    if args.file_path:
        if '/' in args.file_path:
            input_file = Path(args.file_path)
        else:
            input_file = chapters_dir / args.file_path
        if not input_file.exists():
            print(f"Input file {input_file} does not exist.")
            sys.exit(1)
    elif args.all_chapters:
        # If no file-path indicated, look for the file in the "chapters:" directory.
        if not chapters_dir.exists():
            print(f"Chapters directory {chapters_dir} does not exist.")
            sys.exit(1)
        
        # We look for Markdown files in the chapters directory.
        # Since the requirement doesn't specify which one if multiple exists,
        # we'll list them and pick the first one, but inform the user.
        chapter_files = sorted([f for f in chapters_dir.glob("*.md") if not f.name.startswith("00")])
        if not chapter_files:
            # Try including 00 files if nothing else found
            chapter_files = sorted(list(chapters_dir.glob("*.md")))
            
        if not chapter_files:
            print(f"No markdown files found in {chapters_dir}")
            sys.exit(1)
    else:
        print(f"A <chapter>.md file or --all-chapters parameter is required.")
        sys.exit(1)

    if input_file is not None and not input_file.exists():
        print(f"Input file {input_file} does not exist.")
        sys.exit(1)

    if not chapter_files:
        chapter_files.append(input_file)

    for input_file in chapter_files:
        with open(input_file, 'r') as f:
            story_text = f.read()

        template = get_prompt_template()

        # The template has <text_input>...Paste Story Text Here...</text_input>
        # I should replace that part with the actual story text.
        prompt = template.replace("...Paste Story Text Here...", story_text)

        print(f"Sending {input_file.name} to LLM...")

        # Determine which LLM configuration to use
        llm_configs = config.get('llm-xml-generator', [])
        selected_config = None
        
        if args.llm:
            for cfg in llm_configs:
                if cfg.get('llm') == args.llm or cfg.get('default-llm') == args.llm:
                    selected_config = cfg
                    break
            if not selected_config:
                print(f"Error: LLM configuration '{args.llm}' not found in story-config.yml")
                sys.exit(1)
        else:
            # Look for the default-llm
            for cfg in llm_configs:
                if 'default-llm' in cfg:
                    selected_config = cfg
                    break
            if not selected_config and llm_configs:
                selected_config = llm_configs[0]
        
        if not selected_config:
            print("Error: No LLM configuration found in story-config.yml")
            sys.exit(1)

        model_name = selected_config.get('model')
        api_base = selected_config.get('api_base')
        api_key = selected_config.get('api_key')
        
        # Handle api_key if it references os.environ
        if api_key and api_key.startswith('os.environ/'):
            env_var = api_key.split('/', 1)[1]
            api_key = os.getenv(env_var)
        
        completion_kwargs = {
            "model": model_name,
            "messages": [{"role": "user", "content": prompt}]
        }
        
        if api_base:
            completion_kwargs["api_base"] = api_base
        if api_key:
            completion_kwargs["api_key"] = api_key
        if 'temperature' in selected_config:
            completion_kwargs["temperature"] = selected_config['temperature']
        if 'max_tokens' in selected_config:
            completion_kwargs["max_tokens"] = selected_config['max_tokens']
            
        print(f"  Using LLM: {selected_config.get('llm') or selected_config.get('default-llm')} ({model_name})")

        try:
            response = completion(**completion_kwargs)

            xml_output = response.choices[0].message.content

            # Clean up XML if LLM wrapped it in backticks
            if xml_output.startswith("```xml"):
                xml_output = xml_output[6:]
            if xml_output.endswith("```"):
                xml_output = xml_output[:-3]
            xml_output = xml_output.strip()

            # Output should be placed into "story-xml:" directory path
            # Use the same name as original .md but change suffix to .xml
            output_filename = input_file.stem + ".xml"
            output_path = xml_dir / output_filename

            xml_dir.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w') as f:
                f.write(xml_output)

            print(f"XML saved to {output_path}")

        except Exception as e:
            print(f"Error calling LLM: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()
