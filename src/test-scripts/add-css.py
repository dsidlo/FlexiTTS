#!/usr/bin/env python3
"""
Add CSS to pytest HTML report.

Usage:
    python add-css.py
    
Reads from: src/scripts/test-reports/pytest-report.html
Outputs to: src/scripts/test-results/unit-tests-report.html

This script is designed to work regardless of the current working directory.
"""

import sys
from pathlib import Path


def get_project_root():
    """Find the project root based on this script's location."""
    # This script is at src/test-scripts/add-css.py
    # Project root is 2 levels up
    return Path(__file__).parent.parent.parent


def add_dark_theme_css():
    """Add dark theme CSS to HTML report."""
    project_root = get_project_root()
    
    # Define paths
    scripts_dir = project_root / "src" / "scripts"
    input_file = scripts_dir / "test-reports" / "pytest-report.html"
    output_file = scripts_dir / "test-results" / "unit-tests-report.html"
    
    # Dark theme CSS
    dark_theme_css = '''
<style id="dark-theme">
  body { background: #0f172a !important; color: #e2e8f0 !important; }
  body * { color: inherit !important; }
  .container { background: #0f172a !important; }
  table { background: #0b1120 !important; border-color: #1d2a44 !important; }
  th { background: #172554 !important; color: #e2e8f0 !important; border-color: #1d4ed8 !important; }
  td { background: #111827 !important; color: #e2e8f0 !important; border-color: #1d2a44 !important; }
  tr:hover td { background: #1e293b !important; }
  .passed .col-result { color: #22c55e !important; }
  .failed .col-result, .error .col-result { color: #ef4444 !important; }
  .skipped .col-result { color: #f59e0b !important; }
  #environment { background: #0b1120 !important; }
  #environment td { color: #e2e8f0 !important; border-color: #1d2a44 !important; }
  .logwrapper { background: #0b1120 !important; border-color: #1d2a44 !important; }
  .logwrapper .log { background: #020617 !important; color: #94a3b8 !important; border-color: #1d2a44 !important; }
  .summary, .results-table-row { background: transparent !important; }
  .controls button { color: #60a5fa !important; }
  a { color: #93c5fd !important; }
</style>
'''
    
    print(f"Input:  {input_file}")
    print(f"Output: {output_file}")
    
    if not input_file.exists():
        print(f"❌ Input not found: {input_file}")
        return False
    
    try:
        with open(input_file, 'r') as f:
            content = f.read()
        
        if 'id="dark-theme"' in content:
            print("⚠️ CSS already present, copying anyway")
        else:
            if '</head>' in content:
                content = content.replace('</head>', dark_theme_css + '</head>', 1)
            else:
                content = content.replace('<html>', '<html><head>' + dark_theme_css + '</head>', 1)
            print("✅ CSS injected")
        
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w') as f:
            f.write(content)
        print(f"✅ Written: {output_file}")
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


if __name__ == "__main__":
    print("="*50)
    print("  Adding CSS to Unit Test Report")
    print("="*50)
    success = add_dark_theme_css()
    sys.exit(0 if success else 1)
