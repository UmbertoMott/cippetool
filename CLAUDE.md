# CLAUDE.md — CIPP/E Legal SaaS (cipp_legal_saas)

> Leggi anche `/Users/umbertomottola/Downloads/CIPPETOOL/CLAUDE.md` per il contesto completo.

---

## Regola fondamentale

**File deploy:** `public/index.html` → push su `main` → Vercel auto-deploya.
**NON modificare** il file standalone in `CIPPETOOL/`.

---

## TTS — api/tts.js

- Provider unico: **Google Cloud TTS Chirp3-HD** (`GOOGLE_TTS_API_KEY`)
- Endpoint: `https://texttospeech.googleapis.com/v1/text:synthesize`
- Input: `{ text: "..." }` — **NON ssml**, **NON timepointTypes** (causa 400 con Chirp3-HD)
- Risposta: MP3 binario diretto (`audio/mpeg`)
- Nessun fallback Gemini/OpenAI/WebSpeech

Skill: `~/.claude/skills/google-tts-chirp3hd/SKILL.md`

## TTS — frontend (public/index.html)

Skill completa: `~/.claude/skills/tts-selection-miniplayer/SKILL.md`

Bug critici risolti (NON reintrodurre):
1. `done()` in `_wbCbttsPlay` usa delay su `nextAt - ctx.currentTime` — senza questo il mini-player sparisce mentre l'audio suona
2. `_wbWordHLSchedule` usa sentence-level (NON word-by-word) — Chirp3-HD non ha timepoints
3. `topPx` in `wbInsertMarginNote` diviso per `_wbZoom`
4. Delete note su sessioni ripristinate: event delegation su `.doc-page`

## Vercel

- Env var modificate → **Redeploy manuale** obbligatorio
- `GOOGLE_TTS_API_KEY` deve avere spunta su **Production**
- Tutti i file in `vercel.json builds[]` devono essere committati (se mancano → build silenziosamente fallisce)
- Keep-warm: `_wbTTSScheduleKeepWarm()` ogni 3 min

## Commit

Branch: `main`. Prefissi: `fix:` `feat:` `perf:` `design:`.
