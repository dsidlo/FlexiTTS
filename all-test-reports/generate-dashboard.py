#!/usr/bin/env python3
"""
FlexiTTS Unified Test Report Dashboard Generator
Generates all-test-reports/index.html with links and summaries from:
  - src/ui/test-reports/
  - src/scripts/test-results/
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

# Directories relative to this script (all-test-reports/)
ROOT = Path(__file__).resolve().parent
UI_REPORT_DIR = ROOT / "../src/ui/test-reports"
SCRIPTS_REPORT_DIR = ROOT / "../src/scripts/test-results"
OUTPUT_FILE = ROOT / "index.html"


def _read_json(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return None


def _duration_from(data: Optional[Dict[str, Any]]) -> Optional[float]:
    if not data:
        return None
    start = data.get("startTime")
    end = data.get("endTime")
    if isinstance(start, (int, float)) and isinstance(end, (int, float)):
        # Many runners use ms timestamps
        return max(0.0, (end - start) / 1000)
    # No global start/end. Vitest stores per-file start/end under testResults
    spans = [
        (tr.get("startTime"), tr.get("endTime"))
        for tr in data.get("testResults", [])
        if tr.get("startTime") and tr.get("endTime")
    ]
    if spans:
        min_start = min(s for s, _ in spans)
        max_end = max(e for _, e in spans)
        return max(0.0, (max_end - min_start) / 1000)
    return None


def _format_duration(seconds: Optional[float]) -> str:
    if seconds is None:
        return "N/A"
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = int(seconds // 60)
    remainder = int(seconds % 60)
    return f"{minutes}m {remainder}s"


def _status_badge(failed: int, missing: bool) -> str:
    if missing:
        return '<span class="status-badge status-missing">NO DATA</span>'
    if failed > 0:
        return '<span class="status-badge status-error">FAIL</span>'
    return '<span class="status-badge status-success">PASS</span>'


def _summary_card(icon: str, title: str, data: Optional[Dict[str, Any]], report_href: str, coverage_href: str) -> str:
    if not data:
        return f"""
            <div class="summary-card">
                <h2><span class="icon">{icon}</span> {title}
                    {_status_badge(0, True)}
                </h2>
                <p class="no-data">No test results found.</p>
                <p style=\"color: #6b7280; font-size: 0.9em; margin-top: 10px;\">
                    Run tests to generate reports.
                </p>
            </div>
        """
    total = data.get("numTotalTests", 0)
    passed = data.get("numPassedTests", 0)
    failed = data.get("numFailedTests", 0)
    duration = _format_duration(_duration_from(data))
    badge = _status_badge(failed, False)
    coverage_link = f'<a href="{coverage_href}" class="link-btn secondary">View Coverage</a>' if coverage_href else '<span class="link-btn disabled">Coverage Not Generated</span>'
    return f"""
        <div class="summary-card">
            <h2><span class="icon">{icon}</span> {title}
                {badge}
            </h2>
            <div class="stats">
                <div class="stat"><div class="stat-value">{total}</div><div class="stat-label">Total Tests</div></div>
                <div class="stat"><div class="stat-value" style=\"color: #22c55e;\">{passed}</div><div class="stat-label">Passed</div></div>
                <div class="stat{' failed' if failed else ''}"><div class="stat-value">{failed}</div><div class="stat-label">Failed</div></div>
                <div class="stat"><div class="stat-value">{duration}</div><div class="stat-label">Duration</div></div>
            </div>
            <div class="links">
                <a href="{report_href}" class="link-btn">View Test Report</a>
                {coverage_link}
            </div>
        </div>
    """


def generate_dashboard() -> None:
    ui_data = _read_json(UI_REPORT_DIR / "test-results.json")
    scripts_data = _read_json(SCRIPTS_REPORT_DIR / "test-results.json")

    ui_report = os.path.relpath(UI_REPORT_DIR / "test-results.html", ROOT)
    ui_cov_path = UI_REPORT_DIR / "coverage" / "index.html"
    ui_cov_rel = os.path.relpath(ui_cov_path, ROOT) if ui_cov_path.exists() else ""

    scripts_report = os.path.relpath(SCRIPTS_REPORT_DIR / "unit-tests-report.html", ROOT)
    scripts_cov_path = SCRIPTS_REPORT_DIR / "htmlcov" / "index.html"
    scripts_cov_rel = os.path.relpath(scripts_cov_path, ROOT) if scripts_cov_path.exists() else ""

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>FlexiTTS Test Report Dashboard</title>
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #1a1a2e; color: #eaeaea; line-height: 1.6; min-height: 100vh; }}
.container {{ max-width: 1200px; margin: 0 auto; padding: 20px; }}
header {{ background: linear-gradient(135deg, #16213e 0%, #0f3460 100%); padding: 40px; border-radius: 12px; margin-bottom: 30px; text-align: center; border: 1px solid #0f3460; }}
h1 {{ font-size: 2.5em; margin-bottom: 10px; color: #eaeaea; }}
.subtitle {{ color: #a0a0a0; font-size: 1.1em; }}
.timestamp {{ color: #6b7280; font-size: 0.9em; margin-top: 15px; }}
.summary-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 20px; margin-bottom: 30px; }}
.summary-card {{ background: #16213e; border-radius: 12px; padding: 25px; border: 1px solid #0f3460; transition: transform 0.2s, box-shadow 0.2s; }}
.summary-card:hover {{ transform: translateY(-2px); box-shadow: 0 8px 25px rgba(0, 0, 0, 0.3); }}
.summary-card h2 {{ font-size: 1.3em; margin-bottom: 15px; color: #4fc3f7; display: flex; align-items: center; gap: 10px; }}
.summary-card .icon {{ font-size: 1.5em; }}
.stats {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 15px; margin-top: 15px; }}
.stat {{ text-align: center; padding: 15px; background: #1a1a2e; border-radius: 8px; }}
.stat-value {{ font-size: 2em; font-weight: bold; color: #22c55e; }}
.stat.failed .stat-value {{ color: #ef4444; }}
.stat-label {{ font-size: 0.85em; color: #9ca3af; margin-top: 5px; }}
.links {{ margin-top: 20px; }}
.link-btn {{ display: inline-block; padding: 10px 20px; margin: 5px; background: #3b82f6; color: white; text-decoration: none; border-radius: 6px; font-weight: 500; transition: background 0.2s; }}
.link-btn:hover {{ background: #2563eb; }}
.link-btn.secondary {{ background: #10b981; }}
.link-btn.secondary:hover {{ background: #059669; }}
.link-btn.disabled {{ background: #4b5563; cursor: not-allowed; opacity: 0.6; }}
.status-badge {{ display: inline-block; padding: 4px 12px; border-radius: 20px; font-size: 0.85em; font-weight: 500; margin-left: 10px; }}
.status-success {{ background: #22c55e; color: white; }}
.status-error {{ background: #ef4444; color: white; }}
.status-missing {{ background: #6b7280; color: white; }}
.section {{ background: #16213e; border-radius: 12px; padding: 25px; margin-bottom: 20px; border: 1px solid #0f3460; }}
.section h2 {{ color: #4fc3f7; margin-bottom: 15px; font-size: 1.4em; }}
.footer {{ text-align: center; padding: 30px; color: #6b7280; border-top: 1px solid #0f3460; margin-top: 40px; }}
.no-data {{ color: #6b7280; font-style: italic; padding: 20px; text-align: center; }}
</style>
</head>
<body>
<div class="container">
  <header>
    <h1>🧪 FlexiTTS Test Report Dashboard</h1>
    <p class="subtitle">Unified Test & Coverage Reports</p>
    <p class="timestamp">Generated: {timestamp}</p>
  </header>
  <div class="summary-grid">
    {_summary_card('⚛️', 'UI Tests', ui_data, ui_report, ui_cov_rel)}
    {_summary_card('🐍', 'Python Tests', scripts_data, scripts_report, scripts_cov_rel)}
  </div>
  <div class="section">
    <h2>📁 Report Locations</h2>
    <table style="width: 100%; border-collapse: collapse; margin-top: 15px;">
      <tr style="border-bottom: 1px solid #0f3460;"><td style="padding: 12px; color: #4fc3f7;">UI Test Report</td><td style="padding: 12px; color: #9ca3af;"><code>src/ui/test-reports/test-results.html</code></td></tr>
      <tr style="border-bottom: 1px solid #0f3460;"><td style="padding: 12px; color: #4fc3f7;">UI Coverage</td><td style="padding: 12px; color: #9ca3af;"><code>src/ui/test-reports/coverage/index.html</code></td></tr>
      <tr style="border-bottom: 1px solid #0f3460;"><td style="padding: 12px; color: #4fc3f7;">Python Test Report</td><td style="padding: 12px; color: #9ca3af;"><code>src/scripts/test-results/unit-tests-report.html</code></td></tr>
      <tr><td style="padding: 12px; color: #4fc3f7;">Python Coverage</td><td style="padding: 12px; color: #9ca3af;"><code>src/scripts/test-results/htmlcov/index.html</code></td></tr>
    </table>
  </div>
  <footer class="footer">
    <p>FlexiTTS Test Dashboard • Generated by generate-dashboard.py</p>
  </footer>
</div>
</body>
</html>"""

    OUTPUT_FILE.write_text(html)
    print(f"✅ Dashboard generated: {OUTPUT_FILE}")


if __name__ == "__main__":
    generate_dashboard()
