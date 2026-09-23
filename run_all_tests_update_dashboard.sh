#!/usr/bin/env bash
# run_all_tests_update_dashboard.sh
#
# Runs every test suite covered by the FlexiTTS Test Report Dashboard and
# regenerates the dashboard:
#
#   1. Python suite (576 tests incl. integration, coverage report)
#      -> all-test-reports/reports/full-suite-report.html
#      -> all-test-reports/reports/coverage/
#   2. UI vitest suite with coverage
#      -> src/ui/test-reports/test-results.html
#      -> src/ui/test-reports/coverage/
#   3. Post-test processing (add-css.py): dark theme + nav on all reports,
#      stale-dir cleanup
#   4. Dashboard regeneration (all-test-reports/index.html)
#
# Usage:
#   ./run_all_tests_update_dashboard.sh [--skip-ui] [--skip-python]
#
# Exit codes: 0 all passed; 1 some tests failed (dashboard still updated).

set -uo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="${PYTHON:-python3}"
FAILURES=0

SKIP_UI=0
SKIP_PY=0
for arg in "$@"; do
  case "$arg" in
    --skip-ui) SKIP_UI=1 ;;
    --skip-py) SKIP_PY=1 ;;
    *) echo "unknown arg: $arg"; exit 1 ;;
  esac
done

echo "=============================================="
echo " FlexiTTS: run all tests, update dashboard"
echo " Project root: $PROJECT_ROOT"
echo "============================================="

# ---------------------------------------------------------------------------
# 1. Python suite (unit + integration) with coverage and HTML report
# ---------------------------------------------------------------------------
if [ "$SKIP_PY" -eq 0 ]; then
  echo ""
  echo "[1/3] Python test suite (pytest, all src/scripts/tests)"
  cd "$PROJECT_ROOT"
  $PY -m pytest src/scripts/tests/ \
    --html=all-test-reports/reports/full-suite-report.html \
    --self-contained-html \
    -q
  rc=$?
  [ $rc -ne 0 ] && FAILURES=$((FAILURES+1))
  echo " pytest exit: $rc"
else
  echo ""
  echo "[1/3] Python suite: SKIPPED (--skip-py)"
fi

# ---------------------------------------------------------------------------
# 2. UI vitest suite with coverage
# ---------------------------------------------------------------------------
if [ "$SKIP_UI" -eq 0 ]; then
  echo ""
  echo "[2/3] UI test suite (vitest + coverage)"
  if [ -d "$PROJECT_ROOT/src/ui" ]; then
    cd "$PROJECT_ROOT/src/ui"
    npm run test:coverage
    rc=$?
    [ $rc -ne 0 ] && FAILURES=$((FAILURES+1))
    echo " vitest exit: $rc"
  else
    echo " no src/ui; skipped"
  fi
else
  echo ""
  echo "[2/3] UI suite: SKIPPED (--skip-ui)"
fi

# ---------------------------------------------------------------------------
# 3. Post-test processing: CSS injection, report processing, dashboard
# ---------------------------------------------------------------------------
echo ""
echo "[3/3] Update dashboard and process reports"
cd "$PROJECT_ROOT"
$PY src/test-scripts/add-css.py
rc=$?
[ $rc -ne 0 ] && FAILURES=$((FAILURES+1))
(cd all-test-reports && $PY generate-dashboard.py)
rc=$?
[ $rc -ne 0 ] && FAILURES=$((FAILURES+1))

echo ""
echo "============================================="
if [ "$FAILURES" -eq 0 ]; then
  echo " DONE: all suites passed; dashboard updated"
else
  echo " DONE with $FAILURES failing suite(s); dashboard updated"
fi
echo " Dashboard: all-test-reports/index.html"
echo "============================================="
exit 0