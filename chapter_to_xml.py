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

def get_prompt_template(notes_path="dev-notes/FlexiTTS Dev Notes.md"):
    with open(notes_path, 'r') as f:
        content = f.read()
    
    # Extract the XML prompt section
    # Based on the file content, it's between ```xml and ```
    start_marker = "## Story to XML Generation (AI Prompt)\n\n```xml"
    end_marker = "```"
    
    start_index = content.find(start_marker)
    if start_index == -1:
        raise ValueError("Could not find prompt template in dev notes.")
    
    start_index += len(start_marker)
    end_index = content.find(end_marker, start_index)
    
    if end_index == -1:
        raise ValueError("Could not find end of prompt template in dev notes.")
        
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
    parser.add_argument("--lm-studio", type=str, help="Use local LM Studio with the specified model name.")
    args = parser.parse_args()

    chapter_files = []
    input_file = None

    if args.file_path:
        if '/' in args.file_path:
            input_file = Path(args.file_path)
        else:
            input_file =  chapters_dir / args.file_path
        if not input_file.exists():
            print(f"Input file {input_file} does not exist.")
            sys.exit(1)
    elif args.all_chapters:
        # If no file-path indicated, look for the file in the "chapters:" directory.
        if not chapters_dir.exists():
            print(f"Chapters directory {chapters_dir} does not exist.")
            sys.exit(1)
        
        # We look for markdown files in the chapters directory.
        # Since the requirement doesn't specify which one if multiple exist, 
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

        try:
            # Determine which model and base URL to use
            if args.lm_studio:
                model_name = f"openai/{args.lm_studio}"
                api_base = "http://localhost:1234/v1"
                print(f"  Using local LM Studio model: {args.lm_studio}")
                
                response = completion(
                    model=model_name,
                    messages=[{"role": "user", "content": prompt}],
                    api_base=api_base,
                    custom_llm_provider="openai"
                )
            else:
                # Use xAI grok-4-non-reasoning via LiteLLM
                response = completion(
                    model="xai/grok-4-1-fast-non-reasoning",
                    messages=[{"role": "user", "content": prompt}]
                )

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
