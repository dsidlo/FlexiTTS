#!/bin/bash
# FlexiTTS Python Test Runner with HTML Reports
# Run from: project root OR src/scripts/
#
# Usage: ./run-tests.sh [test_pattern]
# Examples:
#   ./run-tests.sh                    # Run all tests
#   ./run-tests.sh test_tts_          # Run tests matching pattern
#   ./run-tests.sh tests/test_tts_local.py  # Run specific file

set -e

# Determine script location and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${SCRIPT_DIR}"

# Navigate to script directory for output paths
cd "$SCRIPT_DIR"

echo "=========================================="
echo "  FlexiTTS Python Test Runner"
echo "=========================================="
echo ""
echo "Script Dir: $SCRIPT_DIR"
echo "Test Directory: tests/"
echo ""

# Create reports directories
mkdir -p test-reports test-results

# Determine test pattern (relative to src/scripts/)
TEST_PATTERN="${1:-tests/}"

echo "Test Pattern: $TEST_PATTERN"
echo ""

# Check dependencies
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

# Run tests - paths are relative to current directory
python -m pytest "$TEST_PATTERN" -v \
    --html=test-reports/pytest-report.html \
    --self-contained-html \
    --cov=. \
    --cov-report=html:test-results/htmlcov \
    --cov-report=xml:test-results/coverage.xml \
    --cov-report=term-missing

TEST_EXIT_CODE=$?

echo ""
echo "=========================================="
echo "  Test Reports Generated"
echo "=========================================="
echo ""
echo "Raw Report:"
echo "  $SCRIPT_DIR/test-reports/pytest-report.html"
echo ""
echo "Styled Report:"
echo "  $SCRIPT_DIR/test-results/unit-tests-report.html"
echo ""
echo "Coverage Report:"
echo "  file://$SCRIPT_DIR/test-results/htmlcov/index.html"
echo ""
echo "Dashboard:"
echo "  $PROJECT_ROOT/test-report/index.html"
echo ""
echo "=========================================="

exit $TEST_EXIT_CODE
