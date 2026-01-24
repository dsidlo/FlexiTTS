#!/usr/bin/env bash

python ./gen_story_tts.py \
  --xml Chapter-03-Yamamoto.xml \
  --out ch-001-dlgseq.json \
  --chapter 001 \
  --base-url http://0.0.0.0:8004 \
  --narrator-ref refs/dgs-voice.wav \
  --char-ref Hendricks=./refs/hendricks.wav \
  --char-ref Yamo=./refs/yamo.wav \
  --char-ref Anyana=./refs/anyana.wav \
  --char-ref Yamato=./refs/yamato.wav \
  --char-ref Juko=./refs/juko.wav \
  --char-ref Hayden=./refs/hayden.wav

