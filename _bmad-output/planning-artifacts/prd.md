---
stepsCompleted: [step-01-init, step-02-discovery, step-02b-vision, step-02c-executive-summary, step-03-success, step-04-journeys, step-09-data, step-10-technical, step-11-integration, step-12-deployment]
inputDocuments: ["_bmad-output/planning-artifacts/product-brief-FlexiTTS-2026-02-21.md"]
workflowType: 'prd'
date: 2026-02-21
author: Dsidlo
classification:
  projectType: "Desktop UI app (brownfield CLI to UI)"
  domain: "Generative AI / Audiobook Production"
  complexity: "Medium"
  projectContext: "brownfield"
---

# Product Requirements Document - FlexiTTS

**Author:** Dsidlo
**Date:** 2026-02-21

## Executive Summary

FlexiTTS is a brownfield Desktop UI application (evolving CLI workflows like chapter_to_xml.py → XML tagging → chapter_xml_to_audio.py → emotional TTS clips/effects) enabling indie authors, audiobook engineers, podcasters, contractors, and hobbyists to produce vision-true audiobooks affordably. Targets core problem: High costs ($200-500/hr talent) and robotic open-source TTS (Coqui/Piper monotony) block nuanced character delivery (e.g., Ayana whispers, Hendrix snarls). Delivers local-first pipeline: Doc import → LLM XML (character/emotion tags) → UI CRUD (drag-reorder timeline, live previews) → Hybrid Qwen3/Seed-VC gen (clips/tracks) → Reaper exports. Users achieve 70% time savings, 90% emotion fidelity; listeners gain distraction-free immersion boosting author income/satisfaction.

### What Makes This Special

Modular 'audio canvas' treats TTS as editable stems (not black box): Author-as-engineer control via intuitive timeline (overlaps, effects chaining), ethical local privacy (no cloud lock-in), V2V fallbacks for duress/laughs. Core insight: Brownfield CLI → UI evolution democratizes pro polish (SoX presets, arc-consistent AI tagging) amid $5B audiobook boom/gen-AI explosion. Users rave: "From raw MD to Reaper-ready in <1hr—no $500 fees." Unfair moat: Extensible APIs (Fish Audio swaps, Foley chaining) for multimodal without silos.

## Project Classification

**Project Type:** Desktop UI app (brownfield CLI to UI)  
**Domain:** Generative AI / Audiobook Production  
**Complexity:** Medium (GPU-local TTS, XML/audio batching, emotion fidelity risks)  
**Project Context:** Brownfield (existing chapter_to_xml.py, chapter_xml_to_audio.py, story-config.yml; expand UI CRUD/exports)

## Success Criteria

FlexiTTS succeeds when creators produce vision-true audio affordably (70% savings), community thrives (stars/discussions/bugs/features), and demos prove immersion (YT). Ties user behaviors to growth.

### Business Objectives

- **3 Months**: 1K stars, 50 discussions/bugs, 10 YT demos (>10K views).
- **12 Months**: 5K stars, 100 credits, 20% freemium, 5 partnerships.
- **Long-Term**: $50K ARR, 80% retention, indie standard.


