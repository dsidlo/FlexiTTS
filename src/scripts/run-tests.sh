#!/bin/bash
# FlexiTTS Python Test Runner with HTML Reports
# Usage: ./run-tests.sh [test_pattern]
# Examples:
#   ./run-tests.sh                    # Run all tests
#   ./run-tests.sh test_tts_          # Run tests matching pattern
#   ./run-tests.sh tests/test_tts_local.py  # Run specific file

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Create reports directory
mkdir -p test-reports

# Determine test pattern
TEST_PATTERN="${1:-tests/}"

echo "=========================================="
echo "  FlexiTTS Python Test Runner"
echo "=========================================="
echo ""
echo "Test Pattern: $TEST_PATTERN"
echo "Working Directory: $(pwd)"
echo ""

# Check if pytest-html and pytest-cov are installed
echo "Checking dependencies..."
python -c "import pytest_html" 2>/dev/null || {
    echo "Installing pytest-html..."
    pip install pytest-html
}

python -c "import pytest_cov" 2>/dev/null || {
    echo "Installing pytest-cov..."
    pip install pytest-cov
}

echo ""
echo "=========================================="
echo "  Running Tests with Coverage"
echo "=========================================="
echo ""

# Run tests with HTML report and coveragesrc/scripts/test-reports
python -m pytest "$TEST_PATTERN" -v \
    --html=test-reports/pytest-report.html \
    --self-contained-html \
    --cov=../scripts/ \
    --cov-report=html:test-reports/pytest-coverage \
    --cov-report=xml:test-reports/coverage.xml \
    --cov-report=term-missing

TEST_EXIT_CODE=$?

echo ""
echo "=========================================="
echo "  Adding Coverage Link to Test Report"
echo "=========================================="
echo ""

# Add coverage link banner to the HTML report
python3 << 'EOF'
import re

html_file = "test-reports/pytest-report.html"

with open(html_file, 'r') as f:
    content = f.read()

# Dark theme CSS
dark_theme_css = '''
<style id="dark-theme">
  body {
    background: #1a1a2e !important;
    color: #eaeaea !important;
  }
  .container {
    background: #1a1a2e !important;
  }
  table {
    background: #16213e !important;
    border-color: #0f3460 !important;
  }
  th {
    background: #0f3460 !important;
    color: #eaeaea !important;
    border-color: #e94560 !important;
  }
  td {
    background: #16213e !important;
    color: #eaeaea !important;
    border-color: #0f3460 !important;
  }
  tr:hover td {
    background: #1a1a2e !important;
  }
  .passed .col-result {
    color: #22c55e !important;
  }
  .failed .col-result, .error .col-result {
    color: #ef4444 !important;
  }
  .skipped .col-result {
    color: #f59e0b !important;
  }
  .log {
    background: #0f0f23 !important;
    color: #eaeaea !important;
    border: 1px solid #0f3460 !important;
  }
  .header {
    background: #16213e !important;
    border-bottom: 2px solid #e94560 !important;
    color: #eaeaea !important;
  }
  .header h1, .header h2 {
    color: #eaeaea !important;
  }
  .summary {
    background: #16213e !important;
    border: 1px solid #0f3460 !important;
  }
  .summary p {
    color: #eaeaea !important;
  }
  .env {
    background: #16213e !important;
    border: 1px solid #0f3460 !important;
    color: #eaeaea !important;
  }
  h1, h2, h3, h4, h5, h6 {
    color: #eaeaea !important;
  }
  a {
    color: #4fc3f7 !important;
  }
  a:hover {
    color: #80d8ff !important;
  }
  .toggle, .collapsible {
    background: #0f3460 !important;
    color: #eaeaea !important;
  }
  .hidden {
    background: #1a1a2e !important;
  }
  .filtered {
    background: #2d1f3d !important;
  }
  /* Pytest HTML report specific classes */
  .results-table {
    background: #16213e !important;
  }
  .results-table-row {
    background: #16213e !important;
  }
  .results-table-row:hover {
    background: #1a1a2e !important;
  }
  .extrahtml {
    background: #0f0f23 !important;
    color: #eaeaea !important;
  }
  div.results-table-row[onclick] {
    background: #16213e !important;
  }
  div.results-table-row[onclick]:hover {
    background: #1a1a2e !important;
  }
  span.sortable {
    color: #eaeaea !important;
  }
  span.sortable:hover {
    background: #0f3460 !important;
  }
  div.spacer {
    background: #16213e !important;
  }
  /* Footer and metadata text - Light background for report generated text */
  .footer, footer {
    background: #16213e !important;
    color: #a0a0a0 !important;
    border-top: 1px solid #0f3460 !important;
  }
  .footer p, .footer span, .footer div,
  footer p, footer span, footer div {
    color: #1a1a1a !important;
  }
  /* Report generated text - light background box */
  p[class*="generated"], div[class*="generated"], span[class*="generated"],
  .generated-on, .report-time, .meta,
  [class*="report-meta"], [id*="generated"] {
    background: #d1d5db !important;
    color: #1a1a1a !important;
  }
  /* Target the plain p tag containing Report generated */
  body > p:last-of-type,
  body > p,
  .container > p:last-child,
  main > p:last-of-type,
  p:only-of-type,
  html > body > p,
  p:not([class]):not([id]),
  h1 + p,
  #title + p {
    background: #d1d5db !important;
    color: #1a1a1a !important;
    padding: 8px 12px !important;
    border-radius: 4px !important;
    margin: 10px 0 !important;
    display: inline-block !important;
  }
  /* Metadata rows */
  .metadata, table.metadata, tr.metadata {
    background: #16213e !important;
    color: #a0a0a0 !important;
  }
  .metadata td, .metadata th,
  table.metadata td, table.metadata th {
    color: #a0a0a0 !important;
  }
</style>
'''

# Create coverage link banner
coverage_banner = '''
<div style="background: #3b82f6; color: white; padding: 12px 20px; text-align: center; font-family: sans-serif;">
  <a href="pytest-coverage/index.html" style="color: white; text-decoration: none; font-weight: 500;">
    📊 View Coverage Report →
  </a>
</div>
'''

# Insert dark theme CSS after <head> tag
if '</head>' in content:
    content = content.replace('</head>', dark_theme_css + '</head>', 1)
else:
    # Fallback: insert after HTML tag
    content = content.replace('<html>', '<html><head>' + dark_theme_css + '</head>', 1)

# Insert coverage banner after <body> tag or after <body class="..."
if '<body>' in content:
    content = content.replace('<body>', '<body>' + coverage_banner, 1)
elif '<body class=' in content:
    # Match <body class="...">
    content = re.sub(r'(<body[^>]+>)', r'\1' + coverage_banner, content, count=1)
else:
    # Fallback: insert after </head>
    content = content.replace('</head>', '</head><body>' + coverage_banner + '</body><body>')

with open(html_file, 'w') as f:
    f.write(content)

print(f"✅ Dark theme & coverage link added to {html_file}")
print(f"   - Coverage link banner injected")
print(f"   - Dark theme CSS injected")

# Generate summary JSON for dashboard
try:
    import json
    import re
    from datetime import datetime
    
    # Look for the summary text in the HTML which shows test counts
    text = content.lower().replace('\n', ' ')
    
    passed = 0
    failed = 0
    skipped = 0
    
    passed_match = re.search(r'(\d+)\s+passed', text)
    if passed_match:
        passed = int(passed_match.group(1))
    
    failed_match = re.search(r'(\d+)\s+failed', text)
    if failed_match:
        failed = int(failed_match.group(1))
    
    skipped_match = re.search(r'(\d+)\s+skipped', text)
    if skipped_match:
        skipped = int(skipped_match.group(1))
    
    # Look for total in test count text like "1 test ran in 0.01s"
    total_match = re.search(r'(\d+)\s+tests?\s+ran', text)
    if total_match:
        total = int(total_match.group(1))
    else:
        total = passed + failed + skipped
    
    summary = {
        "numTotalTests": total,
        "numPassedTests": passed,
        "numFailedTests": failed,
        "numSkippedTests": skipped,
        "startTime": int(datetime.now().timestamp() * 1000) - 10000,
        "endTime": int(datetime.now().timestamp() * 1000),
        "testResults": [{"name": "Python Tests", "assertionResults": []}],
        "success": failed == 0
    }
    
    with open("test-reports/test-results.json", 'w') as f:
        json.dump(summary, f, indent=2)
    print(f"✅ Summary JSON generated: test-reports/test-results.json ({total} tests, {passed} passed, {failed} failed)")
except Exception as e:
    print(f"Warning: Could not generate summary JSON: {e}")

except Exception as e:
    print(f"Warning: Could not generate summary JSON: {e}")

EOF

echo ""
echo "=========================================="
echo "  Test Reports Generated"
echo "=========================================="
echo ""
echo "Location: $SCRIPT_DIR/test-reports/"
echo ""
echo "HTML Test Report:"
echo "  file://$SCRIPT_DIR/test-reports/pytest-report.html"
echo ""
echo "Coverage Report:"
echo "  file://$SCRIPT_DIR/test-reports/pytest-coverage/index.html"
echo ""
echo "Coverage XML (for CI):"
echo "  $SCRIPT_DIR/test-reports/coverage.xml"
echo ""
echo "=========================================="

exit $TEST_EXIT_CODE
