# Checks on Setup (Accelerator / GPU Architecture Detection)

**Date:** 2026-09-21
**Companion to:** `Checks_on_Startup.md` (startup check list) and `GPU_Architectures_Linux_Windows_Mac.md` (full backend analysis).

---

## 1. Detection probes (in priority order)

The device-selection code lives in `src/scripts/tts_local.py` (`_select_device` semantics at lines 71-72; today a two-way CUDA/CPU branch). The recommended expansion is a four-way probe executed at setup time, cached, and re-validated at startup (check #7 in `Checks_on_Startup.md`):

| Priority | Probe | True means | Device / dtype | Setup required |
|---|---|---|---|---|
| 1 | `torch.cuda.is_available()` | NVIDIA CUDA, or AMD ROCm via the `torch.cuda` shim over HIP | `cuda:0` (or `hip:0`) + bfloat16 | NVIDIA: driver + CUDA userland. AMD Linux: ROCm torch wheel (different index) + ROCm userland |
| 2 | `torch.backends.mps.is_available()` | Apple M1-M5 unified memory GPU | `mps` + float16 (bf16 unreliable on MPS) | arm64 macOS torch wheel (CUDA wheels ship no MPS runtime); `PYTORCH_ENABLE_MPS_FALLBACK=1` |
| 3 | `torch.xpu.is_available()` | Intel / AMD NPU (Windows) | `xpu` + float16 | torch XPU-enabled build; recent Ryzen AI hardware |
| 4 | (none of the above) | No accelerator | `cpu` + float32 | Nothing; warn "generation will be slow" |

## 2. Setup matrix per OS

### Linux (NVIDIA / AMD)

| Accelerator | Torch wheel | System requirements | Verification |
|---|---|---|---|
| NVIDIA CUDA | `+cu130` (current default) | Driver + CUDA userland | `nvidia-smi`; `torch.cuda.is_available()` |
| AMD ROCm | `+rocm6.x` index (Linux only) | ROCm userland + compatible kernel/driver; supported gfx (MI-series, RX 7000) | `rocm-smi`; `torch.cuda.is_available()` returns True via HIP shim; check `torch.version.hip` |

### Windows

| Accelerator | Torch wheel | System requirements | Verification |
|---|---|---|---|
| NVIDIA CUDA | `+cu130` | Driver new enough (wheel bundles CUDA runtime) + VC++ redistributable | `torch.cuda.is_available()` |
| AMD DirectML | `torch-directml` (separate package) | DirectX 12, RDNA consumer cards | `torch_directml.device_count()` |

### macOS

| Accelerator | Torch wheel | System requirements | Verification |
|---|---|---|---|
| Apple MPS | Standard arm64 torch (default on macOS) | Apple Silicon M1-M5; macOS version with MPS kernels for needed ops | `torch.backends.mps.is_available()` |

Notes:
- The dev machine's CUDA wheel does **not** ship the MPS runtime or ROCm — per-OS torch index selection in `uv` is required
- `attn_implementation="eager"` must be kept on MPS (flash-attention is CUDA-only); the code already uses eager
- Guard `torch.cuda.empty_cache()` to the CUDA/HIP path only

## 3. Setup commands per platform

```bash
# Linux NVIDIA (current default)
uv sync --locked

# Linux AMD (ROCm) - select the rocm index for torch
uv sync --locked --index-url https://download.pytorch.org/whl/rocm6.4  # example; match torch/rocm versions

# Apple Silicon (macOS)
uv sync --locked  # standard arm64 torch wheel includes MPS

# Windows AMD (DirectML) - after base sync
uv pip install torch-directml
```

## 4. Cross-references

- `GPU_Architectures_Linux_Windows_Mac.md` - full backend analysis, effort estimates, device-selection decision table
- `Checks_on_Startup.md` - the ordered 13-check startup list; check #7 is the accelerator probe
- `docs/implementation/2026-03-19-distro-packaging.md` - packaging plan (CUDA default, CPU fallback)
