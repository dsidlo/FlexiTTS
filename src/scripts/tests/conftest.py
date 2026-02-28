"""Pytest configuration for TTS tests.

Sets up global mocks for heavy dependencies before any test imports.
Includes JSON report generation for dashboard.
"""

import sys
from pathlib import Path
from unittest.mock import Mock, MagicMock
import numpy as np
import pytest

# Store original modules to restore later
_original_modules = {}

def _setup_mocks():
    """Set up module-level mocks before any imports."""
    # Mock litellm first (before it's imported by chapter_to_xml)
    litellm_mock = Mock()
    litellm_mock.completion = Mock()
    sys.modules['litellm'] = litellm_mock
    
    # Mock torch and related modules
    torch_mock = Mock()
    torch_mock.cuda = Mock()
    torch_mock.cuda.is_available = Mock(return_value=False)
    torch_mock.cuda.empty_cache = Mock()
    torch_mock.cuda.get_device_properties = Mock(return_value=Mock(
        total_memory=8 * (1024**3)  # 8GB
    ))
    torch_mock.bfloat16 = Mock()
    torch_mock.float32 = Mock()
    torch_mock.device = Mock()
    sys.modules['torch'] = torch_mock
    
    # Make numpy available
    sys.modules['numpy'] = np
    
    # Mock soundfile
    sf_mock = Mock()
    sf_mock.read = Mock(return_value=(np.zeros(1000), 24000))
    sf_mock.write = Mock()
    sys.modules['soundfile'] = sf_mock
    
    # Mock qwen_tts
    qwen_tts_mock = Mock()
    qwen_tts_mock.Qwen3TTSModel = Mock()
    mock_model_instance = Mock()
    mock_model_instance.create_voice_clone_prompt = Mock(return_value="mock_prompt")
    mock_model_instance.generate_voice_clone = Mock(return_value=([np.zeros(1000)], 24000))
    mock_model_instance.generate_custom_voice = Mock(return_value=([np.zeros(1000)], 24000))
    qwen_tts_mock.Qwen3TTSModel.from_pretrained = Mock(return_value=mock_model_instance)
    sys.modules['qwen_tts'] = qwen_tts_mock
    sys.modules['qwen_tts'].Qwen3TTSModel = qwen_tts_mock.Qwen3TTSModel
    
    # Mock websockets  
    websockets_mock = Mock()
    websockets_mock.connect = Mock()
    mock_websocket = Mock()
    mock_websocket.send = Mock()
    mock_websocket.recv = Mock()
    mock_websocket.close = Mock()
    websockets_mock.connect = Mock(return_value=mock_websocket)
    sys.modules['websockets'] = websockets_mock
    
    # Mock asyncio for sync testing
    asyncio_mock = Mock()
    asyncio_mock.run = Mock(return_value=([np.zeros(1000)], 24000))
    asyncio_mock.sleep = Mock()
    asyncio_mock.wait_for = Mock(return_value=mock_websocket)
    asyncio_mock.TimeoutError = TimeoutError
    sys.modules['asyncio'] = asyncio_mock

# Set up mocks at module load time
_setup_mocks()


# =============================================================================
# Pytest Fixtures
# =============================================================================

@pytest.fixture(autouse=True)
def reset_tts_modules():
    """Reset tts modules before each test to ensure clean imports."""
    # Remove cached tts modules
    tts_modules = [k for k in list(sys.modules.keys()) if k.startswith('tts_')]
    for mod in tts_modules:
        del sys.modules[mod]
    yield


@pytest.fixture
def mock_base_model():
    """Create mocked base Qwen3TTSModel."""
    model = Mock()
    model.create_voice_clone_prompt = Mock(return_value="mock_prompt")
    model.generate_voice_clone = Mock(return_value=([np.zeros(1000)], 24000))
    return model


@pytest.fixture
def mock_custom_model():
    """Create mocked custom Qwen3TTSModel."""
    model = Mock()
    model.generate_custom_voice = Mock(return_value=([np.zeros(1000)], 24000))
    return model


@pytest.fixture
def mock_websocket():
    """Create mocked WebSocket object."""
    ws = Mock()
    ws.send = Mock()
    ws.recv = Mock()
    ws.close = Mock()
    return ws


@pytest.fixture
def mock_fallback_provider():
    """Create mocked fallback TTS provider."""
    provider = Mock()
    provider.generate = Mock(return_value=([np.zeros(1000)], 24000))
    provider.supports_character = Mock(return_value=True)
    provider.close = Mock()
    return provider


# =============================================================================
# Dashboard hooks - JSON report generation for dashboard
# =============================================================================

@pytest.hookimpl(tryfirst=True)
def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """Capture test summary for JSON report."""
    import json
    import time
    from pathlib import Path
    from datetime import datetime
    
    # Get test counts from terminal reporter
    stats = terminalreporter.stats
    passed = len(stats.get('passed', []))
    failed = len(stats.get('failed', []))
    skipped = len(stats.get('skipped', []))
    error = len(stats.get('error', []))
    total = passed + failed + skipped + error
    
    # Find project root (3 levels up from src/scripts/tests/)
    script_dir = Path(__file__).parent  # src/scripts/tests/
    project_root = script_dir.parent.parent.parent
    test_results_dir = project_root / "src" / "scripts" / "test-results"
    test_results_dir.mkdir(parents=True, exist_ok=True)
    
    # Get start time from session
    starttime = getattr(terminalreporter._session, 'starttime', time.time())
    
    # Build JSON data matching Vitest format
    results = {
        "numTotalTests": total,
        "numPassedTests": passed,
        "numFailedTests": failed,
        "numPendingTests": skipped,
        "numTodoTests": 0,
        "startTime": int(starttime * 1000),
        "endTime": int(time.time() * 1000),
        "testResults": []
    }
    
    # Write JSON file
    json_path = test_results_dir / "test-results.json"
    with open(json_path, 'w') as f:
        json.dump(results, f, indent=2)


def pytest_sessionfinish(session, exitstatus):
    """Run post-test processing after pytest finishes."""
    import atexit
    
    # Register atexit handlers to run AFTER pytest-html finishes writing
    atexit.register(_run_post_test_processing)


def _run_post_test_processing():
    """Run CSS injection and dashboard generation after all plugins complete."""
    import subprocess
    import time
    from pathlib import Path
    
    print("\n" + "="*50)
    print("  Post-Test Processing")
    print("="*50)
    
    # Find project root (3 levels up from src/scripts/tests/)
    script_dir = Path(__file__).parent  # src/scripts/tests/
    project_root = script_dir.parent.parent.parent
    
    # Run add-css.py to inject CSS into test reports
    add_css_script = project_root / "src" / "test-scripts" / "add-css.py"
    if add_css_script.exists():
        print(f"\n  Running add-css.py...")
        try:
            # Small delay to ensure pytest-html has finished writing
            time.sleep(0.3)
            
            result = subprocess.run(
                ["python3", str(add_css_script)],
                cwd=str(project_root),
                capture_output=True,
                text=True
            )
            print(result.stdout)
            if result.returncode != 0:
                print(f"  ⚠️ add-css.py exited with code {result.returncode}")
        except Exception as e:
            print(f"  ⚠️ add-css.py error: {e}")
    else:
        print(f"\n  ⚠️ add-css.py not found at: {add_css_script}")
    
    # Generate dashboard
    dashboard_script = project_root / "test-report" / "generate-dashboard.py"
    if dashboard_script.exists():
        print(f"\n  Running generate-dashboard.py...")
        try:
            result = subprocess.run(
                ["python3", str(dashboard_script)],
                cwd=str(project_root / "test-report"),
                capture_output=True,
                text=True
            )
            print(result.stdout)
        except Exception as e:
            print(f"  ⚠️ Dashboard error: {e}")
    else:
        print(f"\n  ⚠️ generate-dashboard.py not found at: {dashboard_script}")
    
    print("\n" + "="*50)
    print("  Post-Test Processing Complete")
    print("="*50)
