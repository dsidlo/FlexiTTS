# Checks on Startup

**Date:** 2026-09-21
**Scope:** Resources FlexiTTS requires at startup and runtime across Linux, Windows, and macOS, the checks needed to verify each, and the setup required when a check fails. Derived from an audit of `src/ui/electron/main.ts`, `src/scripts/*.py`, `src/api/*.py`, and `pyproject.toml`.

---

## 1. Resource inventory (what the app actually needs)

| # | Resource | Where required | Why | Hard/Soft |
|---|---|---|---|---|
| 1 | **Node.js 20+** (Electron bundles its own runtime) | Packaged app: not needed. Dev mode: `npm`, `vite` | Dev-server + build tooling | Soft (packaged) |
| 2 | **Python >= 3.13** | TTS service, all Python scripts | TTS generation, config API | **Hard** |
| 3 | **`uv` package manager on PATH** | `main.ts` spawns `uv run python src/scripts/start_tts_service.py` and `uv run python <script>` for every bridge command | Python env orchestration | **Hard** (dev/current architecture) |
| 4 | **Python packages** (torch, torchaudio, transformers, accelerate, qwen-tts from local `Qwen3-TTS/`, litellm, soundfile, pyyaml, pandas, pydub, numpy, websockets, fastapi/uvicorn) | `uv sync --locked` env | Model inference, pipeline | **Hard** |
| 5 | **Qwen3-TTS model weights** (`Qwen/Qwen3-TTS-12Hz-1.7B-Base`, `Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice`) | `tts_local.py` `from_pretrained` | Local inference (~4-8 GB download on first run, cached by HuggingFace) | **Hard** for local mode |
| 6 | **`sox` binary on PATH** | `sox_service.py` (`shutil.which("sox")`), `chapter_xml_to_audio.py` effects | Effects processing | **Hard** when effects configured |
| 7 | **`ffprobe`/`ffmpeg` on PATH** | `sample_service.py` (duration probe), MP3 fixture/preview | Voice-sample integrity checks | **Soft** (WAV-only fallback) |
| 8 | **GPU + CUDA (torch.cuda.is_available())** | `tts_local.py`: `cuda:0` + bfloat16 if available, else `cpu` | Speed only; CPU fallback works | Soft |
| 9 | **Network: HuggingFace Hub** on first model load | Model download/cache | First-run model fetch | Soft (cached after) |
| 10 | **Network: LLM endpoint** (`api.x.ai` or local `localhost:1234` LM Studio) | `chapter_to_xml.py` via litellm | Chapter→XML breakdown | Soft (feature-optional) |
| 11 | **Filesystem: `~/.config/FlexiTTS/`** (main config), **stories-dir** (`<data>/FlexiTTS/stories` default), per-story subdirs (`story-voice-refs/`, `story-chapters/`, `story-xml/`, `story-audio/clips/`, `logs/`) | `base_config_manager.py` (creates on demand), bridge commands | All config/storage | **Hard** (auto-created) |
| 12 | **Free disk space** | Model cache (~8 GB), per-story audio, .venv (~6 GB dev) | Model + audio storage | Soft (warn) |
| 13 | **Free ports** (TTS WebSocket, config API) | `tts_ws_server.py`, `flexitts_api.py` | Runtime services | Soft (configurable) |
| 14 | **`redis` (>=7.2.0)** | Python dependency (litellm/optional caching) | Only if used at runtime | Soft |

---

## 2. Per-platform setup requirements

### Linux (primary dev platform — AppImage target)

- `sox` + `ffmpeg`: `sudo apt-get install sox ffmpeg` (also installs `libsndfile1` which `soundfile` needs)
- GPU: NVIDIA driver + CUDA userland matching the torch build; verify `nvidia-smi` works and `python -c "import torch; print(torch.cuda.is_available())"` is True
- AMD GPU (ROCm): install a ROCm torch build for Linux (different wheel index); detection works via the `torch.cuda` shim over HIP — see `GPU_Architectures_Linux_Windows_Mac.md`
- Audio system: PipeWire/PulseAudio present for any local playback paths (packaged Electron handles its own audio)
- Port availability: default ports free or reconfigured

### Windows (NSIS target)

- `sox`: no winget package parity — ship `sox.exe` via `extraResources` and prepend its dir to PATH in the main process, or require a manual install step documented in the installer's README
- `ffmpeg`: same approach — bundle a static `ffmpeg`/`ffprobe` build via `extraResources` (avoids users installing anything)
- CUDA: NVIDIA driver + matching CUDA runtime; torch wheels bundle the CUDA runtime on Windows, but the **driver** must be new enough — check `torch.cuda.is_available()` at startup and warn
- AMD GPU: `torch-directml` (separate package) on consumer RDNA cards, or CPU fallback; not a primary path (see `GPU_Architectures_Linux_Windows_Mac.md`)
- Long-path support: model cache paths can exceed 260 chars; enable long paths or keep cache under a short root
- Antivirus/SmartScreen: first-run blocking on unsigned binaries; document or sign
- `uv`: ship as sidecar or detect and instruct

### macOS (DMG target)

- `sox` + `ffmpeg`: `brew install sox ffmpeg` (brew is the least-surprise path; or bundle static binaries via `extraResources`)
- Gatekeeper/notarization: unsigned DMGs are blocked; sign + notarize before distributing, or document right-click bypass
- Case-sensitivity: default APFS is case-insensitive (fine); if a user opts into case-sensitive APFS, path checks still work (code resolves paths case-sensitively via `Path.resolve()`)
- GPU: Apple Silicon has no CUDA. With the three-way selector, MPS acceleration is available on M1-M5 (`torch.backends.mps.is_available()` → `mps` device, float16). Requires an arm64 macOS torch wheel (the dev CUDA wheel ships no MPS runtime). Set `PYTORCH_ENABLE_MPS_FALLBACK=1` for unsupported ops. See `GPU_Architectures_Linux_Windows_Mac.md`
- Xcode Command Line Tools: needed if any wheel must compile (avoid by using prebuilt wheels)

---

## 3. Recommended startup checks (ordered, with failure actions)

Add a `StartupChecks` module invoked from `main.ts` before warmup and from `start_tts_service.py` before loading models. Each check is cheap (<100ms) except model-cache probe (stat-only).

| Order | Check | Command/probe | On failure |
|---|---|---|---|
| 1 | Python interpreter >= 3.13 | `uv run python -c "import sys; assert sys.version_info >= (3,13)"` | Show setup link; refuse to start service |
| 2 | `uv` on PATH | `shutil.which("uv")` | Instruct install (`pipx install uv` / installer bundle) |
| 3 | Python env synced | marker: `.venv/lib/python*/site-packages/qwen_tts` exists, or `uv sync --locked --frozen` fast no-op | Auto-run `uv sync --locked` with progress UI |
| 4 | `sox` on PATH | `shutil.which("sox")` | Disable effects + warn (non-fatal) |
| 5 | `ffprobe` on PATH | `shutil.which("ffprobe")` | Restrict uploads to WAV (non-fatal) |
| 6 | Model cache present | stat `~/.cache/huggingface/hub/models--Qwen--Qwen3-TTS-12Hz-1.7B-{Base,CustomVoice}` (Linux/macOS), `%USERPROFILE%\.cache\huggingface\hub` (Windows) | Show "Downloading models (~8GB, one-time)" progress; require HF reachable |
| 7 | Accelerator detection + device/dtype selection (see `GPU_Architectures_Linux_Windows_Mac.md`) | Probe in priority order: `torch.cuda.is_available()` (NVIDIA CUDA / AMD ROCm via HIP shim) → `torch.backends.mps.is_available()` (Apple M1-M5) → `torch.xpu.is_available()` (Intel/AMD NPU) → CPU | Log selected backend + dtype (CUDA/bf16, MPS/fp16, XPU/fp16, CPU/fp32); warn "CPU mode: generation will be slow" when falling to CPU; never fatal |
| 8 | Disk space | `shutil.disk_usage` on cache dir and stories dir; warn < 10 GB free | Warn (non-fatal) |
| 9 | Stories dir exists/writable | `base_config_manager` bootstrap; test-write a temp file | Auto-create; fail only if permission denied |
| 10 | Main config valid | `load_main_config()` returns dict with `FlexiTTS` key | Auto-create default config |
| 11 | Port bindable | try-bind test socket | Fall back to next port; surface final URLs |
| 12 | TTS service health | existing `check_tts_service.py` WebSocket health check | Retry with backoff (existing logic), then error modal |
| 13 | LLM endpoint reachable (optional) | HEAD ping of configured `api_base` | Mark breakdown offline; app still opens |

### Windows-specific checks

- `sox`/`ffmpeg` resolution: check `extraResources\bin` first, then PATH (bundle-once approach avoids user setup)
- Long-path registry or short-cache paths for HuggingFace cache
- Visual C++ redistributable present (torch/onnxruntime wheels need it)

### macOS-specific checks

- Confirm notarization/signature validity at first run (or document bypass)
- No CUDA → force `cpu` device and show expected-latency warning

### Linux-specific checks

- `libsndfile1` present (soundfile dependency); Debian/Ubuntu pull it via the `sox`/`ffmpeg` package chain
- AppImage: FUSE available (`fusermount`) or extract-run instructions

---

## 4. CI alignment (already in place)

The GitHub Actions workflow (`.github/workflows/ci.yml`) already validates the Linux-side of these requirements on every push:

- Python 3.13 via setup-uv + `uv sync --locked` (checks 1-3)
- `sox` + `ffmpeg` installed (checks 4-5)
- Repo-anchored FlexiTTS config written (check 9/10)
- Full pytest suite proves the pipeline works with all of the above

What CI does **not** yet cover: Windows/macOS binaries resolution, model-download path, GPU paths, and Electron packaging on those OSes (act is Linux-only). These are covered by the packaging doc (`docs/implementation/2026-03-19-distro-packaging.md`) phase plan and require hosted runners per target OS.

---

## 5. Implementation checklist

- [ ] `StartupChecks` module in the Electron main process (or a Python preflight script invoked via `uv run`) running checks 1-13 with structured results
- [ ] Startup report surfaced in-app: pass/warn/fail per check with the exact fix command shown
- [ ] Auto-heal where safe: `uv sync --locked` on missing env; mkdir on missing dirs
- [ ] Bundle `sox`/`ffmpeg` via `extraResources` for Windows/macOS targets
- [ ] First-run model download UX with progress and resume
- [ ] Non-fatal degradation paths: CPU-mode warning, effects-disabled warning, offline-breakdown mode
- [ ] Log every check result to `logs/startup-checks-<ts>.log` for support

