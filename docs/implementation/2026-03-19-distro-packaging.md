# FlexiTTS Distribution Packaging Plan

**Date:** 2026-03-19  
**Approach:** Embedded Python with electron-builder (Quick Start Recommendation)  
**PyTorch Variant:** CUDA-enabled (GPU acceleration support)

---

## Executive Summary

This document outlines the plan for creating an installable distribution package for FlexiTTS that includes:
- Electron frontend (UI)
- Embedded Python environment with all dependencies
- CUDA-enabled PyTorch for GPU-accelerated TTS inference
- Local Qwen3-TTS package integration
- Cross-platform support (Linux AppImage, Windows NSIS, macOS DMG)

---

## Architecture Overview

```
FlexiTTS Distribution Package
├── Electron Application (Frontend)
│   ├── React + Vite UI
│   └── IPC bridge to Python backend
│
└── Embedded Python Environment (Backend)
    ├── Python 3.11 (standalone)
    ├── CUDA-enabled PyTorch + torchaudio
    ├── Transformers, Qwen3-TTS, and dependencies
    └── FlexiTTS scripts (chapter_render_state.py, tts_ws_server.py, etc.)
```

---

## Key Design Decisions

### 1. Why Embedded Python vs. PyInstaller?

| Aspect | Embedded Python | PyInstaller |
|--------|----------------|-------------|
| Startup Time | Faster (no extraction) | Slower (self-extracting) |
| Debuggability | Easier (direct file access) | Harder (bundled) |
| Size | ~3-4GB (with CUDA) | ~2-3GB (with CUDA) |
| Update Mechanism | Replace Python files | Replace entire executable |
| Complexity | Lower | Higher |

**Decision:** Embedded Python for easier debugging and updates.

### 2. CUDA vs. CPU-Only PyTorch

**Decision:** Include CUDA-enabled PyTorch by default.

**Rationale:**
- TTS inference benefits significantly from GPU acceleration
- Users without CUDA will fall back to CPU automatically
- CPU-only package would require separate build pipeline
- Modern Linux distributions have CUDA drivers readily available

**Trade-offs:**
- Package size increases by ~1.5-2GB
- Requires CUDA runtime libraries on target system
- May need to bundle minimal CUDA libraries for portability

---

## Implementation Steps

### Phase 1: Python Environment Preparation

#### 1.1 Create Standalone Python Distribution

```bash
# Download python-build-standalone with shared library support
wget https://github.com/indygreg/python-build-standalone/releases/download/20240107/cpython-3.11.7+20240107-x86_64-unknown-linux-gnu-install_only.tar.gz

# Extract to project
tar xzf cpython-3.11.7+20240107-x86_64-unknown-linux-gnu-install_only.tar.gz
mv python build-python-standalone
```

**Note:** Use `install_only` variant, not `lto` or `pgo` variants, for compatibility with binary wheels.

#### 1.2 Create Virtual Environment with CUDA PyTorch

```bash
# Create bundle directory
mkdir -p .venv-bundled

# Use the standalone Python to create venv
build-python-standalone/bin/python3 -m venv .venv-bundled --copies

# Activate
source .venv-bundled/bin/activate

# Install CUDA-enabled PyTorch (CUDA 12.1)
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# Install remaining dependencies
pip install -r requirements.txt

# Install Qwen3-TTS from local path
pip install -e ./Qwen3-TTS

# Verify CUDA is available
python -c "import torch; print(f'CUDA available: {torch.cuda.is_available()}')"
```

#### 1.3 Bundle CUDA Runtime Libraries (Linux)

For AppImage distribution, we need to bundle minimal CUDA libraries:

```bash
# Create CUDA libs directory
mkdir -p .venv-bundled/lib/cuda

# Copy essential CUDA libraries from system
# (These will be used if system CUDA is not available)
cp /usr/local/cuda/lib64/libcudart.so* .venv-bundled/lib/cuda/ 2>/dev/null || true
cp /usr/local/cuda/lib64/libcudnn.so* .venv-bundled/lib/cuda/ 2>/dev/null || true

# Set RPATH for bundled libraries
# (Handled in electron-builder configuration)
```

#### 1.4 Optimization: Remove Unnecessary Files

```bash
# Create optimization script: scripts/optimize-python-bundle.sh
#!/bin/bash
set -e

VENV_PATH=".venv-bundled"

echo "Optimizing Python bundle..."

# Remove cache files
find "$VENV_PATH" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "$VENV_PATH" -name "*.pyc" -delete
find "$VENV_PATH" -name "*.pyo" -delete

# Remove test files
find "$VENV_PATH" -type d -name "tests" -exec rm -rf {} + 2>/dev/null || true
find "$VENV_PATH" -type d -name "test" -exec rm -rf {} + 2>/dev/null || true

# Remove documentation
find "$VENV_PATH" -name "*.md" -delete
find "$VENV_PATH" -name "*.rst" -delete
find "$VENV_PATH" -type d -name "docs" -exec rm -rf {} + 2>/dev/null || true

# Remove development files
find "$VENV_PATH" -name "*.h" -delete
find "$VENV_PATH" -name "*.c" -delete
find "$VENV_PATH" -name "*.cpp" -delete

# Remove unused torch backends (keep CUDA, remove others)
TORCH_PATH="$VENV_PATH/lib/python3.11/site-packages/torch"
rm -rf "$TORCH_PATH/backends/mps" 2>/dev/null || true  # Apple Metal
# Keep CUDA, CPU backends

# Remove unused transformers architectures (optional)
# Only if size is critical - can break model loading

# Strip binaries (Linux only)
find "$VENV_PATH/bin" -type f -executable -exec strip {} \; 2>/dev/null || true

echo "Bundle optimized. Size: $(du -sh "$VENV_PATH" | cut -f1)"
```

**Expected Final Size:**
- Base Python: ~50MB
- PyTorch + CUDA: ~2.5-3GB
- Other dependencies: ~500MB
- Qwen3-TTS: ~100MB
- **Total: ~3-4GB**

---

### Phase 2: Electron Integration

#### 2.1 Update Main Process for Bundled Python

Modify `src/ui/electron/main.ts`:

```typescript
// Configuration for bundled Python
const isDev = !app.isPackaged;

function getPythonExecutable(): string {
  if (isDev) {
    return 'uv'; // Development mode
  }
  
  // Production: use bundled Python
  const platform = process.platform;
  const pythonDir = path.join(process.resourcesPath, 'python');
  
  if (platform === 'win32') {
    return path.join(pythonDir, 'python.exe');
  }
  return path.join(pythonDir, 'bin', 'python3');
}

function getPythonEnv(): NodeJS.ProcessEnv {
  const env = { ...process.env };
  
  if (!isDev) {
    const pythonDir = path.join(process.resourcesPath, 'python');
    
    // Set Python path
    env.PYTHONHOME = pythonDir;
    env.PYTHONPATH = path.join(pythonDir, 'lib', 'python3.11', 'site-packages');
    
    // Set library path for CUDA (Linux)
    if (process.platform === 'linux') {
      const libPath = path.join(pythonDir, 'lib');
      const cudaLibPath = path.join(pythonDir, 'lib', 'cuda');
      env.LD_LIBRARY_PATH = `${cudaLibPath}:${libPath}:${env.LD_LIBRARY_PATH || ''}`;
    }
    
    // Windows DLL path
    if (process.platform === 'win32') {
      const dllPath = path.join(pythonDir, 'DLLs');
      const libPath = path.join(pythonDir, 'Lib');
      env.PATH = `${dllPath};${libPath};${env.PATH || ''}`;
    }
  }
  
  return env;
}

// Modified executePythonScript
async function executePythonScript(
  scriptPath: string, 
  args: string[]
): Promise<{ stdout: string; stderr: string; code: number | null }> {
  
  const pythonExe = getPythonExecutable();
  const env = getPythonEnv();
  
  // Resolve script path
  let fullScriptPath: string;
  if (isDev) {
    fullScriptPath = path.join(projectRoot, scriptPath);
  } else {
    fullScriptPath = path.join(process.resourcesPath, 'scripts', path.basename(scriptPath));
  }
  
  // Validate security
  if (!isPathWithinParent(fullScriptPath, isDev ? projectRoot : process.resourcesPath)) {
    throw new Error('Security: Script path outside allowed directories');
  }
  
  return new Promise((resolve, reject) => {
    const proc = spawn(pythonExe, [fullScriptPath, ...args], {
      cwd: isDev ? projectRoot : path.join(process.resourcesPath, 'app'),
      env,
      stdio: ['ignore', 'pipe', 'pipe']
    });
    
    // ... rest of implementation
  });
}
```

#### 2.2 Create Entry Point Script

Create `src/scripts/entry_point.py`:

```python
#!/usr/bin/env python3
"""
FlexiTTS Python Backend Entry Point
Routes to appropriate script based on command.
"""
import sys
import os

# Determine base directory
def get_base_dir():
    """Get the base directory for resources."""
    if getattr(sys, 'frozen', False):
        # Running in bundled mode
        return os.path.dirname(sys.executable)
    # Development mode
    return os.path.dirname(os.path.abspath(__file__))

BASE_DIR = get_base_dir()

# Add paths for imports
sys.path.insert(0, BASE_DIR)
sys.path.insert(0, os.path.join(BASE_DIR, 'Qwen3-TTS'))

# Import handlers
SCRIPT_MAP = {
    'tts_ws_server': 'tts_ws_server',
    'chapter_render_state': 'chapter_render_state',
    'start_tts_service': 'start_tts_service',
    'stop_tts_service': 'stop_tts_service',
    'tts_service': 'tts_service',
}

def main():
    if len(sys.argv) < 2:
        print("Usage: python entry_point.py <script_name> [args...]")
        print(f"Available scripts: {', '.join(SCRIPT_MAP.keys())}")
        sys.exit(1)
    
    script_name = sys.argv[1]
    script_args = sys.argv[2:]
    
    if script_name not in SCRIPT_MAP:
        print(f"Unknown script: {script_name}")
        print(f"Available: {', '.join(SCRIPT_MAP.keys())}")
        sys.exit(1)
    
    # Import and run the module
    module_name = SCRIPT_MAP[script_name]
    
    try:
        if module_name == 'tts_ws_server':
            import tts_ws_server
            sys.argv = [sys.argv[0]] + script_args
            tts_ws_server.main()
        elif module_name == 'chapter_render_state':
            import chapter_render_state
            sys.argv = [sys.argv[0]] + script_args
            chapter_render_state.main()
        elif module_name == 'start_tts_service':
            import start_tts_service
            sys.argv = [sys.argv[0]] + script_args
            start_tts_service.main()
        elif module_name == 'stop_tts_service':
            import stop_tts_service
            sys.argv = [sys.argv[0]] + script_args
            stop_tts_service.main()
        elif module_name == 'tts_service':
            import tts_service
            sys.argv = [sys.argv[0]] + script_args
            tts_service.main()
    except ImportError as e:
        print(f"Failed to import {module_name}: {e}")
        print(f"Python path: {sys.path}")
        sys.exit(1)
    except Exception as e:
        print(f"Error running {script_name}: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()
```

---

### Phase 3: electron-builder Configuration

#### 3.1 Create electron-builder.yml

Create `src/ui/electron-builder.yml`:

```yaml
appId: com.flexitts.app
productName: FlexiTTS
copyright: Copyright © 2026

directories:
  output: dist-electron
  buildResources: build-resources

files:
  - dist/**/*
  - dist-electron/electron/**/*
  - package.json
  - "!**/*.map"
  - "!**/*.ts"
  - "!**/*.tsx"
  - "!node_modules/**/*.md"
  - "!node_modules/**/*.map"
  - "!node_modules/**/docs/**/*"
  - "!node_modules/**/test/**/*"
  - "!node_modules/**/tests/**/*"

# Extra resources bundled into app.asar.unpacked
extraResources:
  # Python environment
  - from: ../.venv-bundled
    to: python
    filter:
      - "**/*"
      - "!**/__pycache__/**"
      - "!**/*.pyc"
      - "!**/*.pyo"
      - "!**/tests/**"
      - "!**/test/**"
  
  # Python scripts
  - from: ../src/scripts
    to: scripts
    filter:
      - "**/*.py"
      - "**/*.json"
      - "!**/__pycache__/**"
      - "!**/tests/**"
  
  # Qwen3-TTS package
  - from: ../Qwen3-TTS
    to: Qwen3-TTS
    filter:
      - "**/*.py"
      - "**/*.json"
      - "**/*.txt"
      - "**/*.yaml"
      - "**/*.yml"
      - "**/*.md"
      - "!**/__pycache__/**"
      - "!**/tests/**"
      - "!**/.git/**"
  
  # Configuration
  - from: ../config
    to: config
    filter:
      - "**/*"

# macOS Configuration
mac:
  category: public.app-category.utilities
  target:
    - target: dmg
      arch:
        - x64
        - arm64
    - target: zip
      arch:
        - x64
        - arm64
  
  # macOS notarization (required for distribution)
  # identity: null  # Use for unsigned builds
  # hardenedRuntime: true
  # gatekeeperAssess: false
  # entitlements: build-resources/entitlements.mac.plist
  # entitlementsInherit: build-resources/entitlements.mac.plist

# Windows Configuration
win:
  target:
    - target: nsis
      arch:
        - x64
    - target: portable
      arch:
        - x64
  
  # Code signing (optional for distribution)
  # certificateFile: build-resources/certificate.p12
  # certificatePassword: process.env.WIN_CERT_PASSWORD

# Linux Configuration
linux:
  category: AudioVideo
  maintainer: FlexiTTS Team
  target:
    - target: AppImage
      arch:
        - x64
    - target: deb
      arch:
        - x64
    - target: tar.gz
      arch:
        - x64
  
  # Desktop integration
  desktop:
    Name: FlexiTTS
    Comment: AI-Powered Text-to-Speech for Storytelling
    Categories: AudioVideo;Audio;
    MimeType: application/x-flexitts;

# NSIS Installer (Windows)
nsis:
  oneClick: false
  allowToChangeInstallationDirectory: true
  createDesktopShortcut: true
  createStartMenuShortcut: true
  shortcutName: FlexiTTS
  uninstallDisplayName: FlexiTTS
  license: ../LICENSE

# AppImage Configuration
appImage:
  artifactName: "${name}-${version}-${arch}.${ext}"
  category: AudioVideo
  # Include update information for AppImageUpdate
  # updateInfo: "gh-releases-zsync|username|repo|latest|*.AppImage.zsync"

# Deb Configuration
deb:
  packageName: flexitts
  maintainer: FlexiTTS Team <team@flexitts.app>
  homepage: https://github.com/yourusername/flexitts
  description: |
    FlexiTTS - AI-Powered Text-to-Speech for Storytelling
    .
    Features:
    - GPU-accelerated TTS with CUDA support
    - Chapter-based audio generation
    - Real-time preview and editing
  depends:
    - libgtk-3-0
    - libnotify4
    - libnss3
    - libxss1
    - libxtst6
    - xdg-utils
    - libatspi2.0-0
    - libuuid1
    - libsecret-1-0
    # CUDA runtime (optional - can be installed separately)
    # - cuda-runtime-12-1
  
  # Recommend CUDA but don't require it
  recommends:
    - nvidia-driver-525  # Minimum driver for CUDA 12.1
```

#### 3.2 Create Build Scripts

Create `scripts/build-distribution.sh`:

```bash
#!/bin/bash
set -e

# FlexiTTS Distribution Build Script
# Usage: ./scripts/build-distribution.sh [platform]
# Platforms: linux, win, mac, all (default: current platform)

PLATFORM="${1:-$(uname -s | tr '[:upper:]' '[:lower:]')}"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UI_DIR="$PROJECT_ROOT/src/ui"

echo "=========================================="
echo "FlexiTTS Distribution Build"
echo "Platform: $PLATFORM"
echo "Project Root: $PROJECT_ROOT"
echo "=========================================="

# Step 1: Clean previous builds
echo ""
echo "[1/5] Cleaning previous builds..."
cd "$PROJECT_ROOT"
rm -rf .venv-bundled
rm -rf "$UI_DIR/dist"
rm -rf "$UI_DIR/dist-electron"

# Step 2: Create bundled Python environment
echo ""
echo "[2/5] Creating bundled Python environment..."
"$PROJECT_ROOT/scripts/bundle-python-cuda.sh"

# Step 3: Build Electron frontend
echo ""
echo "[3/5] Building Electron frontend..."
cd "$UI_DIR"
npm ci
npm run build

# Step 4: Compile Electron main process
echo ""
echo "[4/5] Compiling Electron main process..."
npm run electron:build

# Step 5: Package with electron-builder
echo ""
echo "[5/5] Packaging with electron-builder..."

# Determine target based on platform
case "$PLATFORM" in
  linux)
    npm run electron:dist -- --linux
    ;;
  win|windows|msys*)
    npm run electron:dist -- --win
    ;;
  mac|darwin)
    npm run electron:dist -- --mac
    ;;
  all)
    npm run electron:dist -- --linux --win --mac
    ;;
  *)
    echo "Unknown platform: $PLATFORM"
    echo "Usage: $0 [linux|win|mac|all]"
    exit 1
    ;;
esac

echo ""
echo "=========================================="
echo "Build Complete!"
echo "Output: $UI_DIR/dist-electron/"
echo "=========================================="
ls -lh "$UI_DIR/dist-electron/"
```

Create `scripts/bundle-python-cuda.sh`:

```bash
#!/bin/bash
set -e

# FlexiTTS Python Bundle Script with CUDA Support

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PATH="$PROJECT_ROOT/.venv-bundled"
PYTHON_VERSION="3.11.7"
CUDA_VERSION="12.1"

echo "=========================================="
echo "FlexiTTS Python Bundle (CUDA $CUDA_VERSION)"
echo "Python: $PYTHON_VERSION"
echo "Output: $VENV_PATH"
echo "=========================================="

# Download standalone Python if not present
STANDALONE_URL="https://github.com/indygreg/python-build-standalone/releases/download/20240107/cpython-${PYTHON_VERSION}+20240107-x86_64-unknown-linux-gnu-install_only.tar.gz"
STANDALONE_TAR="$PROJECT_ROOT/build-python-standalone.tar.gz"
STANDALONE_DIR="$PROJECT_ROOT/build-python-standalone"

if [ ! -d "$STANDALONE_DIR" ]; then
    echo ""
    echo "[1/6] Downloading standalone Python..."
    wget -O "$STANDALONE_TAR" "$STANDALONE_URL"
    tar xzf "$STANDALONE_TAR" -C "$PROJECT_ROOT"
    mv "$PROJECT_ROOT/python" "$STANDALONE_DIR"
    rm "$STANDALONE_TAR"
else
    echo ""
    echo "[1/6] Using existing standalone Python"
fi

# Create virtual environment
echo ""
echo "[2/6] Creating virtual environment..."
rm -rf "$VENV_PATH"
"$STANDALONE_DIR/bin/python3" -m venv "$VENV_PATH" --copies

# Activate
source "$VENV_PATH/bin/activate"

# Upgrade pip
echo ""
echo "[3/6] Upgrading pip..."
pip install --upgrade pip setuptools wheel

# Install CUDA-enabled PyTorch
echo ""
echo "[4/6] Installing CUDA-enabled PyTorch..."
pip install torch==2.2.0 torchvision torchaudio --index-url "https://download.pytorch.org/whl/cu${CUDA_VERSION//./}"

# Verify CUDA installation
echo ""
echo "Verifying CUDA installation..."
python -c "import torch; print(f'PyTorch: {torch.__version__}'); print(f'CUDA available: {torch.cuda.is_available()}'); print(f'CUDA version: {torch.version.cuda}')"

# Install other dependencies
echo ""
echo "[5/6] Installing dependencies..."
pip install -r "$PROJECT_ROOT/requirements.txt"

# Install Qwen3-TTS
echo ""
echo "Installing Qwen3-TTS..."
pip install -e "$PROJECT_ROOT/Qwen3-TTS"

# Install FlexiTTS scripts as package
echo ""
echo "Installing FlexiTTS scripts..."
pip install -e "$PROJECT_ROOT"

# Optimize bundle
echo ""
echo "[6/6] Optimizing bundle..."

# Remove cache
find "$VENV_PATH" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "$VENV_PATH" -name "*.pyc" -delete
find "$VENV_PATH" -name "*.pyo" -delete

# Remove test files
find "$VENV_PATH" -type d -name "tests" -exec rm -rf {} + 2>/dev/null || true
find "$VENV_PATH" -type d -name "test" -exec rm -rf {} + 2>/dev/null || true

# Remove documentation
find "$VENV_PATH" -name "*.md" -delete 2>/dev/null || true
find "$VENV_PATH" -type d -name "docs" -exec rm -rf {} + 2>/dev/null || true

# Strip binaries (Linux)
if [ "$(uname)" = "Linux" ]; then
    find "$VENV_PATH/bin" -type f -executable -exec strip {} \; 2>/dev/null || true
fi

# Report size
echo ""
echo "=========================================="
echo "Bundle Complete!"
echo "Size: $(du -sh "$VENV_PATH" | cut -f1)"
echo "Location: $VENV_PATH"
echo "=========================================="
```

---

### Phase 4: Testing Strategy

#### 4.1 Pre-Build Tests

```bash
# Test Python environment
source .venv-bundled/bin/activate
python -c "import torch; assert torch.cuda.is_available(), 'CUDA not available'"
python -c "import qwen_tts; print('Qwen3-TTS OK')"
python src/scripts/entry_point.py tts_ws_server --help
```

#### 4.2 Post-Build Tests

```bash
# Test AppImage
./dist-electron/FlexiTTS-0.1.0.AppImage --appimage-extract-and-run &

# Verify Python works
./squashfs-root/resources/python/bin/python3 -c "import torch; print(torch.__version__)"

# Test TTS service starts
# (Manual testing via UI)
```

#### 4.3 Distribution Tests

| Platform | Test Item | Expected Result |
|----------|-----------|-----------------|
| Linux AppImage | Launch | App starts, TTS service initializes |
| Linux AppImage | GPU inference | Uses CUDA if available, falls back to CPU |
| Linux Deb | Install | `dpkg -i` succeeds |
| Linux Deb | Desktop entry | Appears in application menu |
| Windows NSIS | Install | Installer completes, shortcuts created |
| Windows | GPU inference | Uses CUDA if available |
| macOS DMG | Launch | App starts (CPU-only, no CUDA on macOS) |

---

### Phase 5: CI/CD Integration

#### 5.1 GitHub Actions Workflow

Create `.github/workflows/build-distribution.yml`:

```yaml
name: Build Distribution Packages

on:
  push:
    tags:
      - 'v*'
  workflow_dispatch:

jobs:
  build-linux:
    runs-on: ubuntu-22.04
    steps:
      - uses: actions/checkout@v4
        with:
          submodules: true  # For Qwen3-TTS
      
      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'
      
      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install system dependencies
        run: |
          sudo apt-get update
          sudo apt-get install -y wget libgtk-3-0 libnotify4
      
      - name: Build distribution
        run: |
          ./scripts/build-distribution.sh linux
      
      - name: Upload artifacts
        uses: actions/upload-artifact@v4
        with:
          name: linux-packages
          path: |
            src/ui/dist-electron/*.AppImage
            src/ui/dist-electron/*.deb
            src/ui/dist-electron/*.tar.gz

  build-windows:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'
      
      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install CUDA (Windows)
        uses: Jimver/cuda-toolkit@v0.2.14
        with:
          cuda: '12.1.0'
      
      - name: Build distribution
        run: |
          .\scripts\build-distribution.ps1 win
      
      - name: Upload artifacts
        uses: actions/upload-artifact@v4
        with:
          name: windows-packages
          path: |
            src/ui/dist-electron/*.exe
            src/ui/dist-electron/*.portable

  build-macos:
    runs-on: macos-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'
      
      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Build distribution
        run: |
          ./scripts/build-distribution.sh mac
      
      - name: Upload artifacts
        uses: actions/upload-artifact@v4
        with:
          name: macos-packages
          path: |
            src/ui/dist-electron/*.dmg
            src/ui/dist-electron/*.zip

  release:
    needs: [build-linux, build-windows, build-macos]
    runs-on: ubuntu-latest
    if: startsWith(github.ref, 'refs/tags/')
    steps:
      - name: Download all artifacts
        uses: actions/download-artifact@v4
      
      - name: Create Release
        uses: softprops/action-gh-release@v1
        with:
          files: |
            linux-packages/*
            windows-packages/*
            macos-packages/*
          draft: true
```

---

## Known Challenges & Mitigations

### Challenge 1: CUDA Library Dependencies

**Problem:** Target system may not have CUDA runtime installed.

**Mitigation:**
- Bundle minimal CUDA runtime libraries (libcudart, libcudnn)
- Set `LD_LIBRARY_PATH` in launcher
- Document CUDA driver requirements
- Provide CPU fallback (automatic via PyTorch)

### Challenge 2: Package Size

**Problem:** 3-4GB distribution is large for download.

**Mitigation:**
- Provide torrent/magnet links for large files
- Use delta updates (electron-updater)
- Split into "Core" and "Models" packages
- Compress with UPX where possible

### Challenge 3: GPU Memory Requirements

**Problem:** Qwen3-TTS may require significant VRAM.

**Mitigation:**
- Document minimum GPU requirements (4GB VRAM recommended)
- Provide model quantization options
- Support CPU fallback automatically

### Challenge 4: Platform-Specific Issues

**Problem:** macOS doesn't support CUDA.

**Mitigation:**
- macOS build uses CPU-only PyTorch
- Document platform limitations
- Consider Core ML conversion for macOS (future)

---

## Timeline Estimate

| Phase | Task | Estimated Time |
|-------|------|----------------|
| 1 | Python environment setup | 2-3 days |
| 2 | Electron integration | 2-3 days |
| 3 | electron-builder configuration | 1-2 days |
| 4 | Testing & debugging | 3-5 days |
| 5 | CI/CD setup | 1-2 days |
| **Total** | | **9-15 days** |

---

## Next Steps

1. **Immediate:** Create `scripts/bundle-python-cuda.sh` and test locally
2. **Day 2-3:** Update `electron/main.ts` for bundled Python
3. **Day 4-5:** Create and test `electron-builder.yml`
4. **Day 6-10:** Test on clean VMs (no dev dependencies)
5. **Day 11-15:** CI/CD integration and release automation

---

## Appendix: File Checklist

### New Files to Create
- [ ] `scripts/bundle-python-cuda.sh`
- [ ] `scripts/build-distribution.sh`
- [ ] `scripts/optimize-python-bundle.sh`
- [ ] `src/scripts/entry_point.py`
- [ ] `src/ui/electron-builder.yml`
- [ ] `.github/workflows/build-distribution.yml`
- [ ] `build-resources/entitlements.mac.plist` (for macOS)

### Files to Modify
- [ ] `src/ui/electron/main.ts` - Add bundled Python support
- [ ] `src/ui/package.json` - Add build scripts
- [ ] `pyproject.toml` - Add entry point configuration

### Documentation
- [ ] Update `README.md` with installation instructions
- [ ] Create `docs/user/installation.md`
- [ ] Create `docs/user/troubleshooting.md`

---

## References

- [python-build-standalone](https://github.com/indygreg/python-build-standalone)
- [electron-builder Documentation](https://www.electron.build/)
- [PyTorch CUDA Installation](https://pytorch.org/get-started/locally/)
- [AppImage Documentation](https://docs.appimage.org/)
- [GitHub Actions for Electron](https://www.electron.build/continuous-integration.html)
