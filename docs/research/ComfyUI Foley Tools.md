# ComfyUI Foley Tools

**The best local (offline, self-hosted) tools for Foley generation** focus on AI models that create realistic sound effects—either synchronized to video (true Foley workflow) or from text prompts. These run entirely on your hardware (typically NVIDIA GPU) after downloading models/weights—no internet or subscriptions needed post-setup.

Non-AI options like manual recording in Audacity/Reaper or royalty-free libraries exist but don't "generate" novel sounds. The top recommendations below are open-source, actively used in local video/AI workflows (e.g., via **ComfyUI** for easiest integration), and current as of early 2026.

### Top for Video-to-Foley (Synchronized SFX to Video)
These analyze video frames + optional text prompts to generate perfectly timed effects (footsteps, impacts, ambiences, etc.).

1. **HunyuanVideo-Foley** (Tencent, 2025) – **Best overall for high-quality, professional Foley**  
   State-of-the-art multimodal diffusion model for 48kHz Foley audio synced to video. Outperforms others (including MMAudio) on benchmarks for fidelity, timing, and semantics. Excellent for films, shorts, games, ads.  
   - **Local run**: Fully offline after model download. Gradio UI or ComfyUI custom nodes (e.g., Vantage Hunyuan Foley or if-ai).  
   - **Hardware**: 8–20GB VRAM (XL model ~8GB with offload; XXL for max quality). CUDA 11.8/12.4, Linux/Windows supported.  
   - **Pros**: Crystal-clear output, batch processing, strong text control.  
   - **Cons**: Higher VRAM for best model.  
   - GitHub: https://github.com/Tencent-Hunyuan/HunyuanVideo-Foley  
   - HF models: tencent/HunyuanVideo-Foley  
   - Tutorials: Search "HunyuanVideo-Foley ComfyUI" or Windows install videos.

2. **MMAudio** (CVPR 2025) – **Best lightweight/fast option**  
   Multimodal model for high-quality synced audio from video (± text). Handles Foley-style effects (impacts, ambiences, events) extremely well and integrates seamlessly into local video gen pipelines.  
   - **Local run**: Gradio demo, ComfyUI nodes (popular kijai or custom), CLI. Auto-downloads models.  
   - **Hardware**: Very efficient (~6GB VRAM in FP16), fast inference (~1–2s for 8s clip). Works on mid-range GPUs.  
   - **Pros**: Low resources, great sync, versatile (also pure text-to-audio).  
   - **Cons**: Slightly below Hunyuan in raw fidelity on some benchmarks.  
   - GitHub: https://github.com/hkchengrex/MMAudio  
   - HF: hkchengrex/MMAudio

3. **FoleyCrafter** (open-mmlab, 2024) – Solid research-grade alternative  
   Text-guided video-to-audio framework built for lifelike, temporally synced Foley. Uses diffusion + temporal adapter.  
   - **Local run**: Conda setup + Gradio. Fully offline.  
   - **Hardware**: GPU recommended (exact VRAM not strict, but similar to other diffusion models).  
   - GitHub: https://github.com/open-mmlab/FoleyCrafter

### Top for Text-to-Foley/Sound Effects (Prompt-Based Generation)
Great for creating individual elements (e.g., "creaky wooden door closing, 2 seconds") or layering into videos manually.

1. **MOSS-SoundEffect** (OpenMOSS Team / MOSI.AI, Feb 2026) – **Best modern text-to-SFX**  
   Specialized high-fidelity model for environment sounds, urban scenes, biological/human actions, musical fragments, etc. Controllable duration and broad category coverage—perfect Foley building blocks. Part of the MOSS-TTS family.  
   - **Local run**: Hugging Face inference or their GitHub scripts (autoregressive token-based). ComfyUI-compatible workflows emerging.  
   - **Hardware**: 8B model—standard consumer GPU (exact VRAM depends on setup but designed for local).  
   - GitHub: https://github.com/OpenMOSS/MOSS-TTS  
   - HF: OpenMOSS-Team/MOSS-SoundEffect

2. **Stable Audio Open** (Stability AI, 2024—still excellent in 2026) – **Most established & easy text-to-SFX**  
   Generates up to ~47s stereo clips (44.1kHz) of sound effects, ambiences, short production elements from text. Trained heavily on Freesound-style data—ideal for custom Foley.  
   - **Local run**: Official stable-audio-tools repo, Gradio, or ComfyUI nodes. One-click via Pinokio launcher often.  
   - **Hardware**: Runs on modest GPUs (optimized variants even lighter).  
   - **Pros**: Simple prompts, great quality for effects/field recordings.  
   - HF: stabilityai/stable-audio-open-1.0  
   - Repo/tools: https://github.com/Stability-AI/stable-audio-tools

### Setup Recommendations for All Tools
- **Easiest UX**: Install **ComfyUI** (or Pinokio for one-click app launcher) → search/install custom nodes for Hunyuan, MMAudio, Stable Audio, etc. Workflows let you pipe video directly into generation.
- **Requirements**: NVIDIA GPU (8GB+ VRAM recommended for best results; lower with quantization/offloading). Python/PyTorch environment. Windows/Linux both supported (Linux often smoother).
- **Tips**: Start with Gradio UIs for quick testing. Combine tools (e.g., generate elements in Stable Audio/MOSS then sync in DAW). All are free/open-source (Apache/MIT-style licenses—check for commercial use).

These cover 95% of local Foley needs in 2026. HunyuanVideo-Foley or MMAudio will feel like "AI Foley artists" for video projects; pair with MOSS/Stable Audio for custom elements. If your hardware is limited (<8GB VRAM), start with MMAudio + Stable Audio Open. Search YouTube for "[tool name] ComfyUI local install" for 5–10 min setup guides.
