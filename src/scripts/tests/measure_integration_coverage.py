#!/usr/bin/env python3
"""Measure coverage for subprocess-based integration tests."""

import sys
import subprocess
import json
from pathlib import Path
from coverage import Coverage

# Scripts to measure coverage for
SCRIPTS = [
    "chapter_seq_xml.py",
    "chapter_to_xml.py",
    "chapter_validate_xml.py",
    "chapter_xml_to_audio.py",
    "validate_config.py"
]

def measure_coverage():
    """Run coverage measurement on integration tests."""
    cov = Coverage(source=["src/scripts"])
    cov.start()
    
    # Import and run tests
    try:
        import pytest
        result = pytest.main([
            "src/scripts/tests/test_integration_*.py",
            "-v",
            "--tb=no",
            "-x"
        ])
    except Exception as e:
        print(f"Error running tests: {e}")
        result = 1
    
    cov.stop()
    cov.save()
    
    # Generate report
    print("\n" + "="*70)
    print("INTEGRATION TEST COVERAGE REPORT")
    print("="*70)
    
    for script in SCRIPTS:
        path = Path("src/scripts") / script
        analysis = cov.analysis2(str(path))
        if analysis[1]:
            total_lines = len(analysis[1])
            missing_lines = len(analysis[2])
            covered = total_lines - missing_lines
            coverage_pct = (covered / total_lines * 100) if total_lines else 0
            
            status = "✅ PASS" if coverage_pct >= 90 else f"⚠️  {coverage_pct:.1f}%"
            print(f"{script:40s} {status:10s} ({coverage_pct:.1f}%)")
        else:
            print(f"{script:40s} ⚠️  N/A")
    
    print("="*70)
    
    return result


if __name__ == "__main__":
    sys.exit(measure_coverage())
