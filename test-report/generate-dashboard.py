#!/usr/bin/env python3
"""
FlexiTTS Unified Test Report Dashboard Generator
Generates test-report/index.html with links and summaries from:
  - src/ui/test-reports/
  - src/scripts/test-reports/
"""

import json
import os
from datetime import datetime
from pathlib import Path

# Configuration
UI_REPORTS = "../src/ui/test-reports"
SCRIPTS_REPORTS = "../src/scripts/test-reports"
OUTPUT_FILE = "index.html"

def read_json_report(path):
    """Read and parse JSON test report if it exists."""
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None

def get_coverage_stats(report_dir):
    """Extract coverage percentage from coverage report if available."""
    # Check for coverage JSON (if available)
    coverage_json = os.path.join(report_dir, "coverage", "coverage-summary.json")
    if os.path.exists(coverage_json):
        try:
            with open(coverage_json, 'r') as f:
                data = json.load(f)
                return data.get("total", {}).get("statements", {}).get("pct", 0)
        except:
            pass
    
    # Check for coverage XML
    coverage_xml = os.path.join(report_dir, "coverage.xml")
    if os.path.exists(coverage_xml):
        return "Available"
    
    return None

def check_file_exists(path):
    """Check if a file exists and return relative path."""
    full_path = os.path.join(os.path.dirname(__file__), path)
    return os.path.exists(full_path)

def format_duration(seconds):
    """Format duration in human readable form."""
    # Handle millisecond timestamps (Vitest uses ms, pytest uses s)
    if seconds is None or seconds > 1000000000:  # Likely timestamp in ms since epoch, not duration
        return "N/A"
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = int(seconds / 60)
        secs = int(seconds % 60)
        return f"{minutes}m {secs}s"
    else:
        hours = int(seconds / 3600)
        minutes = int((seconds % 3600) / 60)
        return f"{hours}h {minutes}m"

def get_duration_from_data(data):
    """Calculate duration from test data, handling different formats."""
    if not data:
        return None
    
    # Try to get duration from endTime - startTime (both in milliseconds)
    start_time = data.get('startTime')
    end_time = data.get('endTime')
    
    if start_time and end_time:
        return (end_time - start_time) / 1000  # Convert ms to seconds
    
    # If no global endTime, try to calculate from individual test results (Vitest format)
    test_results = data.get('testResults', [])
    if test_results:
        # Get the earliest start and latest end from test files
        starts = [tr.get('startTime') for tr in test_results if tr.get('startTime')]
        ends = [tr.get('endTime') for tr in test_results if tr.get('endTime')]
        if starts and ends:
            min_start = min(starts)
            max_end = max(ends)
            return (max_end - min_start) / 1000
    
    return None

def generate_dashboard():
    """Generate the unified test report dashboard."""
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Read UI test reports
    ui_json_path = os.path.join(script_dir, UI_REPORTS, "test-results.json")
    ui_data = read_json_report(ui_json_path)
    
    ui_html_report = os.path.join(UI_REPORTS, "test-results.html")
    ui_coverage = os.path.join(UI_REPORTS, "coverage", "index.html")
    ui_coverage_exists = check_file_exists(ui_coverage)
    
    # Read Scripts test reports
    scripts_json_path = os.path.join(script_dir, SCRIPTS_REPORTS, "test-results.json")
    scripts_data = read_json_report(scripts_json_path)
    
    scripts_html_report = os.path.join(SCRIPTS_REPORTS, "pytest-report.html")
    scripts_coverage = os.path.join(SCRIPTS_REPORTS, "pytest-coverage", "index.html")
    scripts_coverage_exists = check_file_exists(scripts_coverage)
    
    # Get timestamps
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Build HTML
    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>FlexiTTS Test Report Dashboard</title>
    <style>
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #1a1a2e;
            color: #eaeaea;
            line-height: 1.6;
            min-height: 100vh;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }}
        header {{
            background: linear-gradient(135deg, #16213e 0%, #0f3460 100%);
            padding: 40px;
            border-radius: 12px;
            margin-bottom: 30px;
            text-align: center;
            border: 1px solid #0f3460;
        }}
        h1 {{
            font-size: 2.5em;
            margin-bottom: 10px;
            color: #eaeaea;
        }}
        .subtitle {{
            color: #a0a0a0;
            font-size: 1.1em;
        }}
        .timestamp {{
            color: #6b7280;
            font-size: 0.9em;
            margin-top: 15px;
        }}
        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        .summary-card {{
            background: #16213e;
            border-radius: 12px;
            padding: 25px;
            border: 1px solid #0f3460;
            transition: transform 0.2s, box-shadow 0.2s;
        }}
        .summary-card:hover {{
            transform: translateY(-2px);
            box-shadow: 0 8px 25px rgba(0, 0, 0, 0.3);
        }}
        .summary-card h2 {{
            font-size: 1.3em;
            margin-bottom: 15px;
            color: #4fc3f7;
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        .summary-card .icon {{
            font-size: 1.5em;
        }}
        .stats {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 15px;
            margin-top: 15px;
        }}
        .stat {{
            text-align: center;
            padding: 15px;
            background: #1a1a2e;
            border-radius: 8px;
        }}
        .stat-value {{
            font-size: 2em;
            font-weight: bold;
            color: #22c55e;
        }}
        .stat.failed .stat-value {{
            color: #ef4444;
        }}
        .stat-label {{
            font-size: 0.85em;
            color: #9ca3af;
            margin-top: 5px;
        }}
        .links {{
            margin-top: 20px;
        }}
        .link-btn {{
            display: inline-block;
            padding: 10px 20px;
            margin: 5px;
            background: #3b82f6;
            color: white;
            text-decoration: none;
            border-radius: 6px;
            font-weight: 500;
            transition: background 0.2s;
        }}
        .link-btn:hover {{
            background: #2563eb;
        }}
        .link-btn.secondary {{
            background: #10b981;
        }}
        .link-btn.secondary:hover {{
            background: #059669;
        }}
        .link-btn.disabled {{
            background: #4b5563;
            cursor: not-allowed;
            opacity: 0.6;
        }}
        .status-badge {{
            display: inline-block;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.85em;
            font-weight: 500;
            margin-left: 10px;
        }}
        .status-success {{
            background: #22c55e;
            color: white;
        }}
        .status-warning {{
            background: #f59e0b;
            color: #1a1a1a;
        }}
        .status-error {{
            background: #ef4444;
            color: white;
        }}
        .status-missing {{
            background: #6b7280;
            color: white;
        }}
        .section {{
            background: #16213e;
            border-radius: 12px;
            padding: 25px;
            margin-bottom: 20px;
            border: 1px solid #0f3460;
        }}
        .section h2 {{
            color: #4fc3f7;
            margin-bottom: 15px;
            font-size: 1.4em;
        }}
        .test-file-list {{
            list-style: none;
            margin-top: 15px;
        }}
        .test-file-list li {{
            padding: 10px;
            background: #1a1a2e;
            margin-bottom: 8px;
            border-radius: 6px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .test-file-list li:hover {{
            background: #1f2937;
        }}
        .pass-count {{
            color: #22c55e;
            font-weight: 500;
        }}
        .footer {{
            text-align: center;
            padding: 30px;
            color: #6b7280;
            border-top: 1px solid #0f3460;
            margin-top: 40px;
        }}
        .no-data {{
            color: #6b7280;
            font-style: italic;
            padding: 20px;
            text-align: center;
        }}
        @media (max-width: 768px) {{
            .stats {{
                grid-template-columns: 1fr;
            }}
            h1 {{
                font-size: 1.8em;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🧪 FlexiTTS Test Report Dashboard</h1>
            <p class="subtitle">Unified Test & Coverage Reports</p>
            <p class="timestamp">Generated: {now}</p>
        </header>

        <div class="summary-grid">
'''
    
    # UI Tests Card
    if ui_data:
        ui_total = ui_data.get('numTotalTests', 0)
        ui_passed = ui_data.get('numPassedTests', 0)
        ui_failed = ui_data.get('numFailedTests', 0)
        ui_duration = get_duration_from_data(ui_data)
        
        status_class = "status-success" if ui_failed == 0 else "status-error"
        status_text = "PASS" if ui_failed == 0 else "FAIL"
        
        html += f'''
            <div class="summary-card">
                <h2><span class="icon">⚛️</span> UI Tests
                    <span class="status-badge {status_class}">{status_text}</span>
                </h2>
                <div class="stats">
                    <div class="stat">
                        <div class="stat-value">{ui_total}</div>
                        <div class="stat-label">Total Tests</div>
                    </div>
                    <div class="stat">
                        <div class="stat-value" style="color: #22c55e;">{ui_passed}</div>
                        <div class="stat-label">Passed</div>
                    </div>
                    <div class="stat{'.failed' if ui_failed > 0 else ''}">
                        <div class="stat-value">{ui_failed}</div>
                        <div class="stat-label">Failed</div>
                    </div>
                    <div class="stat">
                        <div class="stat-value">{format_duration(ui_duration)}</div>
                        <div class="stat-label">Duration</div>
                    </div>
                </div>
                <div class="links">
                    <a href="{ui_html_report}" class="link-btn">View Test Report</a>
                    {f'<a href="{ui_coverage}" class="link-btn secondary">View Coverage</a>' if ui_coverage_exists else '<span class="link-btn disabled">Coverage Not Generated</span>'}
                </div>
            </div>
'''
    else:
        html += f'''
            <div class="summary-card">
                <h2><span class="icon">⚛️</span> UI Tests
                    <span class="status-badge status-missing">NO DATA</span>
                </h2>
                <p class="no-data">No test results found.</p>
                <p style="color: #6b7280; font-size: 0.9em; margin-top: 10px;">
                    Run tests in src/ui/ to generate reports<br>
                    <code>npm run test:report</code>
                </p>
            </div>
'''
    
    # Scripts Tests Card
    if scripts_data:
        scripts_total = scripts_data.get('numTotalTests', 0)
        scripts_passed = scripts_data.get('numPassedTests', 0)
        scripts_failed = scripts_data.get('numFailedTests', 0)
        scripts_duration = get_duration_from_data(scripts_data)
        
        status_class = "status-success" if scripts_failed == 0 else "status-error"
        status_text = "PASS" if scripts_failed == 0 else "FAIL"
        
        html += f'''
            <div class="summary-card">
                <h2><span class="icon">🐍</span> Python Tests
                    <span class="status-badge {status_class}">{status_text}</span>
                </h2>
                <div class="stats">
                    <div class="stat">
                        <div class="stat-value">{scripts_total}</div>
                        <div class="stat-label">Total Tests</div>
                    </div>
                    <div class="stat">
                        <div class="stat-value" style="color: #22c55e;">{scripts_passed}</div>
                        <div class="stat-label">Passed</div>
                    </div>
                    <div class="stat{'.failed' if scripts_failed > 0 else ''}">
                        <div class="stat-value">{scripts_failed}</div>
                        <div class="stat-label">Failed</div>
                    </div>
                    <div class="stat">
                        <div class="stat-value">{format_duration(scripts_duration)}</div>
                        <div class="stat-label">Duration</div>
                    </div>
                </div>
                <div class="links">
                    <a href="{scripts_html_report}" class="link-btn">View Test Report</a>
                    {f'<a href="{scripts_coverage}" class="link-btn secondary">View Coverage</a>' if scripts_coverage_exists else '<span class="link-btn disabled">Coverage Not Generated</span>'}
                </div>
            </div>
'''
    else:
        html += f'''
            <div class="summary-card">
                <h2><span class="icon">🐍</span> Python Tests
                    <span class="status-badge status-missing">NO DATA</span>
                </h2>
                <p class="no-data">No test results found.</p>
                <p style="color: #6b7280; font-size: 0.9em; margin-top: 10px;">
                    Run tests in src/scripts/ to generate reports<br>
                    <code>./run-tests.sh</code>
                </p>
            </div>
'''
    
    html += '''
        </div>

        <div class="section">
            <h2>📋 Quick Commands</h2>
            <p style="color: #9ca3af; margin-bottom: 15px;">Generate fresh test reports:</p>
            <div style="background: #1a1a2e; padding: 20px; border-radius: 8px; font-family: monospace; color: #4fc3f7; overflow-x: auto;">
                <p style="margin-bottom: 10px;"><strong># UI Tests</strong></p>
                <p style="color: #eaeaea;">cd src/ui && npm run test:report:html</p>
                <br>
                <p style="margin-bottom: 10px;"><strong># Python Tests</strong></p>
                <p style="color: #eaeaea;">cd src/scripts && ./run-tests.sh</p>
                <br>
                <p style="margin-bottom: 10px;"><strong># Update This Dashboard</strong></p>
                <p style="color: #eaeaea;">cd test-report && python3 generate-dashboard.py</p>
            </div>
        </div>

        <div class="section">
            <h2>📁 Report Locations</h2>
            <table style="width: 100%; border-collapse: collapse; margin-top: 15px;">
                <tr style="border-bottom: 1px solid #0f3460;">
                    <td style="padding: 12px; color: #4fc3f7;">UI Test Report</td>
                    <td style="padding: 12px; color: #9ca3af;"><code>src/ui/test-reports/test-results.html</code></td>
                </tr>
                <tr style="border-bottom: 1px solid #0f3460;">
                    <td style="padding: 12px; color: #4fc3f7;">UI Coverage</td>
                    <td style="padding: 12px; color: #9ca3af;"><code>src/ui/test-reports/coverage/index.html</code></td>
                </tr>
                <tr style="border-bottom: 1px solid #0f3460;">
                    <td style="padding: 12px; color: #4fc3f7;">Python Test Report</td>
                    <td style="padding: 12px; color: #9ca3af;"><code>src/scripts/test-reports/pytest-report.html</code></td>
                </tr>
                <tr>
                    <td style="padding: 12px; color: #4fc3f7;">Python Coverage</td>
                    <td style="padding: 12px; color: #9ca3af;"><code>src/scripts/test-reports/pytest-coverage/index.html</code></td>
                </tr>
            </table>
        </div>

        <footer class="footer">
            <p>FlexiTTS Test Dashboard • Generated by generate-dashboard.py</p>
        </footer>
    </div>
</body>
</html>
'''
    
    # Write the HTML file
    output_path = os.path.join(script_dir, OUTPUT_FILE)
    with open(output_path, 'w') as f:
        f.write(html)
    
    print(f"✅ Dashboard generated: {output_path}")
    
    # Print summary
    print("\n=== Summary ===")
    if ui_data:
        print(f"UI Tests: {ui_data.get('numTotalTests', 0)} total, {ui_data.get('numPassedTests', 0)} passed, {ui_data.get('numFailedTests', 0)} failed")
        print(f"  Coverage: {'✅' if ui_coverage_exists else '❌'} {'Available' if ui_coverage_exists else 'Not generated'}")
    else:
        print("UI Tests: ❌ No data")
    
    if scripts_data:
        print(f"Python Tests: {scripts_data.get('numTotalTests', 0)} total, {scripts_data.get('numPassedTests', 0)} passed, {scripts_data.get('numFailedTests', 0)} failed")
        print(f"  Coverage: {'✅' if scripts_coverage_exists else '❌'} {'Available' if scripts_coverage_exists else 'Not generated'}")
    else:
        print("Python Tests: ❌ No data")

if __name__ == "__main__":
    generate_dashboard()
