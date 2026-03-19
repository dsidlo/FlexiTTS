#!/usr/bin/env python3
"""Merge pytest reports into a single dark-themed HTML output.

This script:
1. Runs pytest to produce individual module reports under src/scripts/test-reports/modules.
2. Injects the dark theme CSS from add-css.py.
3. Builds an aggregate HTML that concatenates the module reports so all 360 tests are visible.
"""

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "src" / "scripts"
TEST_REPORTS_DIR = SCRIPTS_DIR / "test-reports"
MODULES_DIR = TEST_REPORTS_DIR / "modules"
OUTPUT_FILE = SCRIPTS_DIR / "test-results" / "unit-tests-report.html"
ADD_CSS_SCRIPT = PROJECT_ROOT / "src" / "test-scripts" / "add-css.py"

MODULES = [
    "chapter_seq_xml",
    "chapter_to_xml",
    "chapter_validate_xml",
    "chapter_xml_to_audio_preflight",
    "chapter_xml_to_audio",
    "config_manager_integration",
    "config_manager_unit",
    "cuda_context",
    "flexitts_bridge",
    "integration_chapter_seq_xml",
    "integration_chapter_to_xml",
    "integration_chapter_validate_xml",
    "integration_chapter_xml_to_audio",
    "integration_tts_service_management",
    "integration_validate_config",
    "model_concurrency",
    "sox_effects",
    "story_dropdown_config",
    "tts_factory",
    "tts_interface",
    "tts_local",
    "tts_service",
    "tts_service_health",
    "tts_service_retry",
    "tts_service_startup",
    "validate_config",
    "voice_cache_threading",
    "websocket_stress",
]

def run_module(module_name: str) -> Path:
    report_file = MODULES_DIR / f"{module_name}.html"
    cmd = [
        "pytest",
        f"tests/test_{module_name}.py",
        "--html",
        str(report_file),
        "--self-contained-html",
        "-q",
    ]
    print(f"Running {' '.join(cmd)}")
    subprocess.run(cmd, cwd=SCRIPTS_DIR, check=True)
    return report_file


def build_aggregate(reports):
    sections = []
    for report in reports:
        sections.append(f"<iframe src='../test-reports/modules/{report.name}' title='{report.name}'></iframe>")
    output_html = f"""
<!DOCTYPE html>
<html lang=\"en\">
<head>
<meta charset=\"UTF-8\" />
<title>Aggregated Pytest Report</title>
<style>
body {{ background: #0f172a; color: #e2e8f0; }}
iframe {{ width: 100%; height: 600px; border: 1px solid #1d4ed8; margin-bottom: 24px; }}
</style>
</head>
<body>
<h1>Aggregated Pytest Module Reports</h1>
{''.join(sections)}
</body>
</html>
    """
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(output_html)

def main():
    MODULES_DIR.mkdir(parents=True, exist_ok=True)
    reports = [run_module(module) for module in MODULES]
    # Inject CSS into each report
    subprocess.run(["python3", str(ADD_CSS_SCRIPT)], cwd=PROJECT_ROOT, check=True)
    build_aggregate(reports)

if __name__ == "__main__":
    main()
