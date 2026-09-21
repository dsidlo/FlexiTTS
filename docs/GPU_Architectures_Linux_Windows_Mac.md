# GPU / Accelerator Architectures: Linux, Windows, macOS

**Date:** 2026-09-21
**Question:** Can the CUDA-dependent components of FlexiTTS run on Apple M1-M5 Silicon or AMD-based architectures?
**Basis:** Code-level audit of device selection in `src/scripts/tts_local.py`, torch 2.13.0+cu130 capability checks in the locked environment, and `qwen_tts` inference dtype requirements.

---

## 1. Executive summary

**Yes, all pipeline components can run on Apple Silicon and AMD — with different accelerators and different levels of effort.** Nothing is CUDA-locked at the algorithm level. The lock is entirely in device selection, which today lives in exactly one place: `src/scripts/tts_local.py` lines 71-72.

Everything *around* the models is already architecture-independent: `sox`/`ffmpeg` (native binaries on all three OSes), config pipeline, chapter-to-XML (cloud LLM), voice-sample management/preview, the Electron UI, and voice-clone prompt caching.

Model footprint matters: the two Qwen3-TTS models are 1.7B each (~4-8 GB total). That small size is what makes CPU and MPS viable in ways that larger models would not be.

---

## 2. Current state (verified)

```python
# src/scripts/tts_local.py lines 71-72 — the only device decision in the app
self.device = "cuda:0" if torch.cuda.is_available() else "cpu"
self.dtype = torch.bfloat16 if torch.cuda.is_available() else torch.float32
```

Verified in the locked dev environment (`torch 2.13.0+cu130`):

| Backend | Available in current env |
|---|---|
| CUDA (NVIDIA) | Yes (A5000 Mobile) |
| MPS (Apple) | Attribute exists, unavailable — CUDA wheel ships no MPS runtime |
| ROCm/HIP (AMD Linux) | Not in this wheel (`torch.version.hip` is None) |
| DirectML (AMD Windows) | `torch-directml` not installed |
| XPU (Intel/AMD NPU) | `torch.xpu` exists, no hardware → False |
| CPU | Universal fallback, already implemented |

Additional constraints from the model side: `qwen_tts` documents `dtype=torch.bfloat16` and `attn_implementation="eager"` (flash-attention not used — good, since it is unavailable outside CUDA).

---

## 3. Apple M1-M5 Silicon — yes, via MPS (small effort)

### What works today, zero changes

Everything except acceleration: `sox`/`ffmpeg`, config pipeline, chapter-to-XML (cloud LLM), sample management, and CPU torch inference. Models run on CPU — correct but slow for autoregressive audio-token decode.

### To accelerate on Apple Silicon (MPS backend)

1. **Install an MPS-capable torch wheel.** macOS arm64 torch builds include MPS out of the box. The CUDA wheel used on the dev machine simply does not ship it. `uv add torch` on an M-series Mac gives `torch.backends.mps.is_available() == True`.
2. **Three-way device selection** (the patch):

```python
if torch.cuda.is_available():              # NVIDIA (existing path)
    device, dtype = "cuda:0", torch.bfloat16
elif getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
    device, dtype = "mps", torch.float16   # bf16 unreliable on MPS; fp16 safe
else:
    device, dtype = "cpu", torch.float32
```

3. **Caveats to handle:**
   - bf16 MPS support is limited/version-dependent; use float16 on MPS
   - Some ops in `qwen_tts` custom modeling code may not have MPS kernels: set `PYTORCH_ENABLE_MPS_FALLBACK=1` so unsupported ops transparently run on CPU
   - Guard `torch.cuda.empty_cache()` (`tts_local.py` line 294) — it must only run on the CUDA path (already conditioned, verify)
   - MPS memory is unified with system RAM: a 16 GB Mac yields roughly 10 GB usable for GPU — sufficient for 2 x 1.7B models
   - Keep `attn_implementation="eager"` (flash-attention is unavailable on MPS; the code already uses eager)

4. **CI/packaging:** macOS arm64 hosted runners also unlock the DMG packaging target; a torch arm64 index entry for `uv` per-platform is needed.

**Effort: small** (roughly the patch above plus per-platform torch index and CI validation).
**Expected performance:** ~2-4x slower than the RTX A5000 reference GPU, dramatically faster than CPU-only. M3/M4/M5 handle 2 x 1.7B comfortably.

---

## 4. AMD architectures — two distinct paths

### AMD on Linux (ROCm/HIP) — yes, different torch build

- PyTorch ships ROCm wheels exposing a CUDA-like surface (`torch.cuda` shim over HIP) on supported Radeon cards (MI-series, RX 7000-series)
- Code changes are minimal — `cuda:0` maps to HIP; bf16 works on modern CDNA/RDNA cards
- Constraints: Linux only, version-sensitive (kernel/driver combos), varying support across gfx generations
- **Effort: moderate** — add a ROCm torch index to `uv` for Linux (per-platform index selection), verify detection (works unchanged), test on the target Radeon generation

### AMD on Windows (DirectML) — possible, less mature

- `torch-directml` (Microsoft's DirectX 12 backend) runs on consumer RDNA cards
- Separate package, some ops fall back to CPU, performance below ROCm
- Treat as a stretch goal, not the primary AMD path

### AMD Ryzen AI / NPUs (XPU)

- `torch.xpu` exists in torch 2.13 (no hardware locally to verify). Realistic only on Windows with recent Ryzen AI hardware; not a primary target.

### Pure CPU on any architecture

- Always works today with zero changes. 1.7B TTS on a modern 8-16 core CPU generates audio at roughly real-time-to-slow (minutes per chapter vs seconds per clip on the reference GPU). Viable for light use.

---

## 5. What is portable with zero effort (already done)

| Component | Portability |
|---|---|
| `sox` / `ffmpeg` effects | Native binaries all three OSes |
| Config pipeline / bridge | Pure Python |
| Chapter-to-XML breakdown | Cloud LLM (works anywhere with network) |
| Sample upload/preview | Electron + native binaries |
| Electron UI | Cross-platform |
| Voice-clone prompt caching | Filesystem, portable |

---

## 6. Recommendation

1. **Now:** no change — the existing `cuda-or-cpu` fallback already covers Apple (CPU) and AMD-without-ROCm (CPU). CI validates the CPU path on Linux.
2. **Next:** add the three-way device selector (CUDA / MPS / CPU) — about 10 lines in `tts_local.py`, opens real acceleration on every M-series Mac, zero cost elsewhere.
3. **Later (if AMD matters):** add a ROCm torch index option for Linux AMD users; DirectML for Windows AMD as a stretch goal.
4. **Keep:** the packaging doc's "CUDA by default, CPU fallback" decision stands. MPS is the cheap addition that widens hardware coverage to all Apple Silicon.

---

## 7. Device-selection decision table

| Hardware | Backend | Status today | Effort to enable | Expected performance vs RTX A5000 reference |
|---|---|---|---|---|
| NVIDIA (Linux/Windows) | CUDA | Working (current default) | None | Baseline |
| Apple M1-M5 | MPS | CPU fallback only | Small patch + macOS torch index + macOS CI | ~2-4x slower |
| AMD Linux (ROCm) | HIP via CUDA shim | CPU fallback only | Moderate (wheel index + testing) | Varies by card; MI-series comparable |
| AMD Windows | DirectML | CPU fallback only | Larger effort (separate package) | Slower than ROCm |
| Any, CPU | CPU | Working | None | Minutes per chapter |
| Intel/AMD NPU (XPU) | torch.xpu | Not applicable (no hardware in dev fleet) | Larger effort | Unverified |
