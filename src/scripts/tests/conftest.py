"""Pytest configuration for TTS tests.

Sets up global mocks for heavy dependencies before any test imports.
Includes JSON report generation for dashboard.
"""

import sys
import asyncio
from pathlib import Path
from unittest.mock import Mock, MagicMock
import numpy as np
import pytest

# Add src/scripts to path for importing GenerateResult
sys.path.insert(0, str(Path(__file__).parent))

# Import GenerateResult before mocking
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from tts_models.base import GenerateResult

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
    mock_model_instance.generate_voice_clone = Mock(return_value=GenerateResult(
        audio_segments=[np.zeros(1000)], sample_rate=24000, duration_ms=500, model_name="mock"
    ))
    mock_model_instance.generate_custom_voice = Mock(return_value=GenerateResult(
        audio_segments=[np.zeros(1000)], sample_rate=24000, duration_ms=500, model_name="mock"
    ))
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
    
    # Note: We do NOT mock the asyncio module as it breaks async tests
    # that use asyncio.run(). Tests that need asyncio fixtures should
    # use pytest-asyncio's event_loop fixture instead.

# Set up mocks at module load time
_setup_mocks()


# =============================================================================
# Pytest Fixtures
# =============================================================================

@pytest.fixture
def event_loop():
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


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
    model.generate_voice_clone = Mock(return_value=GenerateResult(
        audio_segments=[np.zeros(1000)], sample_rate=24000, duration_ms=500, model_name="mock"
    ))
    return model


@pytest.fixture
def mock_custom_model():
    """Create mocked custom Qwen3TTSModel."""
    model = Mock()
    model.generate_custom_voice = Mock(return_value=GenerateResult(
        audio_segments=[np.zeros(1000)], sample_rate=24000, duration_ms=500, model_name="mock"
    ))
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
    provider.generate = Mock(return_value=GenerateResult(
        audio_segments=[np.zeros(1000)], sample_rate=24000, duration_ms=500, model_name="mock"
    ))
    provider.supports_character = Mock(return_value=True)
    provider.close = Mock()
    return provider


@pytest.fixture(autouse=True, scope="module")
def cleanup_threading_between_modules():
    """Clean up threading state between test modules to prevent isolation issues.
    
    Voice cache threading tests create threads and barriers that can leave
    Python's threading state corrupted for subsequent async tests. This 
    fixture ensures proper cleanup between modules.
    """
    yield
    import gc
    import time
    # Allow threads to terminate and cleanup
    time.sleep(0.05)
    # Force garbage collection to clean up thread objects
    gc.collect()


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
    all_test_reports_dir = "all-test-reports"
    dashboard_script = project_root / all_test_reports_dir / "generate-dashboard.py"
    if dashboard_script.exists():
        print(f"\n  Running generate-dashboard.py...")
        try:
            result = subprocess.run(
                ["python3", str(dashboard_script)],
                cwd=str(project_root / all_test_reports_dir),
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
