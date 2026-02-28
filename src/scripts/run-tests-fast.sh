#!/bin/bash
# FlexiTTS Python Fast Test Runner (no coverage)
# Usage: ./run-tests-fast.sh [test_pattern]
#
# Examples:
#   ./run-tests-fast.sh                    # Run all tests
#   ./run-tests-fast.sh test_tts_          # Run tests matching pattern

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Create reports directories
mkdir -p test-reports test-results

echo "=========================================="
echo "  FlexiTTS Python Tests (Fast Mode)"
echo "=========================================="
echo ""

# Determine test pattern
TEST_PATTERN="${1:-tests/}"

echo "Running: pytest $TEST_PATTERN --html=test-reports/pytest-report.html"
echo ""

# Check if pytest-html is installed
python -c "import pytest_html" 2>/dev/null || {
    echo "Installing pytest-html..."
    pip install pytest-html
}

# Run tests with HTML report (no coverage)
python -m pytest "$TEST_PATTERN" -v \
    --html=test-reports/pytest-report.html \
    --self-contained-html

echo ""
echo "=========================================="
echo "  Test Report Generated"
echo "=========================================="
echo ""
echo "Raw Report:"
echo "  $SCRIPT_DIR/test-reports/pytest-report.html"
echo ""
echo "Styled Report (after add-css.py runs):"
echo "  $SCRIPT_DIR/test-results/unit-tests-report.html"
echo ""
echo "Note: Coverage not generated (fast mode)"
echo "      Run ./run-tests.sh for coverage"
echo "=========================================="
