#!/usr/bin/env python3
"""
Process ALL pytest HTML reports in the repo:
- inject the dark theme CSS
- write standardized, linked copies into all-test-reports/reports/

Processed sources (existing files only, others skipped):
  - src/scripts/test-reports/pytest-report.html  (scripts unit runs)
  - src/test-reports/pytest-report.html          (src-root runs)
  - test-reports/pytest-report.html              (repo-root runs)
  - src/scripts/tests/test-reports/pytest-report.html (tests-dir runs)

Outputs:
  all-test-reports/reports/<source>-report.html
  (also keeps the original unit-tests-report.html for compatibility)

Usage:
    python add-css.py [--out-dir PATH]

Designed to work regardless of the current working directory.
"""

import shutil
import sys
from pathlib import Path

DARK_THEME_CSS = '''
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

NAV_CSS = '''
<style id="report-nav">
  .report-nav { background: #1e293b; padding: 12px 18px; border-radius: 8px;
                margin-bottom: 18px; border: 1px solid #1d4ed8; }
  .report-nav a { color: #93c5fd !important; text-decoration: none;
                  margin-right: 18px; font-weight: 600; }
  .report-nav a:hover { text-decoration: underline; }
  .report-nav .home { color: #fbbf24 !important; }
</style>
'''


def get_project_root():
    return Path(__file__).resolve().parent.parent.parent


def get_report_sources(project_root: Path):
    """(source_label, input_path, output_name) for every known report location."""
    return [
        ("full-suite", project_root / "all-test-reports/reports/full-suite-report.html"),
        ("scripts-unit", project_root / "src/scripts/test-reports/pytest-report.html"),
        ("src-root", project_root / "src/test-reports/pytest-report.html"),
        ("repo-root", project_root / "test-reports/pytest-report.html"),
        ("tests-dir", project_root / "src/scripts/tests/test-reports/pytest-report.html"),
    ]


def inject_css(content: str) -> str:
    import datetime
    stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    if 'id="dark-theme"' not in content:
        if "</head>" in content:
            content = content.replace("</head>", DARK_THEME_CSS + "</head>", 1)
        else:
            content = ("<html><head>" + DARK_THEME_CSS + "</head>" +
                       content.split("<html>", 1)[-1])
    if 'id="report-nav"' not in content:
        nav = (f'<div class="report-nav">'
               f'<a class="home" href="../index.html">&#8592; Test Dashboard</a>'
               f'<span style="color:#94a3b8; margin-left: 24px;">'
               f'Report generated: {stamp}</span>'
               f'</div>')
        if "<body>" in content:
            content = content.replace("<body>", "<body>" + nav, 1)
    return content


def process(source_label: str, input_file: Path, out_dir: Path) -> bool:
    out_file = out_dir / f"{source_label}-report.html"
    if not input_file.exists():
        print(f"  - {source_label}: no report at {input_file}, skipped")
        return False
    in_place = input_file.resolve() == out_file.resolve()
    if in_place:
        print(f"  = {source_label}: processing in place")
    try:
        content = input_file.read_text()
        content = inject_css(content)
        out_dir.mkdir(parents=True, exist_ok=True)
        if in_place:
            input_file.write_text(content)
            print(f"  + {source_label}: {input_file} (in place)")
        else:
            out_file.write_text(content)
            print(f"  + {source_label}: {input_file} -> {out_file}")
        return True
    except Exception as e:
        print(f"  x {source_label}: {e}")
        return False


def cleanup_stale_reports(project_root: Path) -> None:
    """Remove stale coverage/report dirs that no run refreshes, so the
    dashboard never links to outdated data:
    - src/scripts/test-results/htmlcov  (superseded by all-test-reports/coverage)
    - htmlcov at repo root (same)
    """
    stale = [
        project_root / "src/scripts/test-results/htmlcov",
        project_root / "htmlcov",
    ]
    for d in stale:
        if d.exists():
            import shutil
            shutil.rmtree(d)
            print(f"  - removed stale dir: {d}")


def main() -> int:
    project_root = get_project_root()
    out_dir = project_root / "all-test-reports" / "reports"
    print("=" * 60)
    print("  Processing pytest reports (dark CSS + nav + dashboard links)")
    print("=" * 60)
    cleanup_stale_reports(project_root)

    processed = 0
    for label, path in get_report_sources(project_root):
        if process(label, path, out_dir):
            processed += 1

    # Keep the legacy compatibility output updated as well.
    legacy_in = project_root / "src/scripts/test-reports/pytest-report.html"
    legacy_out = project_root / "src/scripts/test-results/unit-tests-report.html"
    if legacy_in.exists():
        content = inject_css(legacy_in.read_text())
        legacy_out.parent.mkdir(parents=True, exist_ok=True)
        legacy_out.write_text(content)
        print(f"  + legacy unit-tests-report.html refreshed")

    print(f"\n  {processed} report(s) processed into {out_dir}")
    print("=" * 60)
    return 0 if processed >= 0 else 1


if __name__ == "__main__":
    print("=" * 50)
    print("  Processing Test Reports")
    print("=" * 50)
    sys.exit(main())
