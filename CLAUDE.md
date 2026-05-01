# CLAUDE.md — CIPP/E Legal SaaS

Progetto: **privacyaitool.vercel.app**
Repo: `cipp_legal_saas/`
File principale frontend: `public/index.html` (tutto il codice UI/logica è qui)
API serverless: `api/` (Vercel Functions, ESM)

---

## Regola fondamentale — deploy target

**Le modifiche vanno sempre su `cipp_legal_saas/public/index.html`.**
Non toccare mai il file standalone `CIPPETOOL/cipp_e_IAPP_UmbertoMottolaSaas_v5_*.html` come target di deploy — è un export/backup, non la sorgente attiva.

---

## TTS — Google Cloud TTS Chirp3-HD (voce canonica)

**Skill di riferimento:** `~/.claude/skills/google-tts-chirp3hd/SKILL.md`

### Priorità provider (api/tts.js)

1. **Google Cloud TTS Chirp3-HD** — provider principale (`GOOGLE_TTS_API_KEY`)
   - Voce italiana: `it-IT-Chirp3-HD-Aoede`
   - Voce inglese: `en-US-Chirp3-HD-Aoede`
2. Gemini TTS (`GEMINI_API_KEY`) — fallback
3. OpenAI TTS (`OPENAI_API_KEY`) — ultimo fallback

**Non invertire questa priorità.** Se Chirp3-HD non risponde, il fallback è automatico — non spostare Gemini al primo posto.

### Architettura gapless (public/index.html)

Il playback usa `sentences.map(fetch + decodeAudioData in parallelo)` — tutti i segmenti vengono fetchati **e decodificati** in parallelo prima che `scheduleNext` li consumi. Questo elimina i gap di 4-5s tra segmenti.

**Non tornare al decode sequenziale dentro `scheduleNext`** — causerebbe di nuovo i gap.

Pattern critico:
```js
var bufPromises = sentences.map(function(sent, idx) {
  return abPromise.then(function(ab) {
    return new Promise(function(res, rej) { ctx.decodeAudioData(ab, res, rej); });
  }).catch(function() { return null; });
});
```

### Variabili di stato TTS (non rimuovere)

- `_wbCbtts` — stato globale AudioContext + sources + cancelled flag
- `_wbPF` — prefetch del primo segmento (scatta a mouseup sulla selezione)
- `_wbWordHL` — word highlight sincronizzato con l'audio
- `_wbSelRect` — rect della selezione salvato a mouseup (coordinate certe per il popup nota)

---

## AI Document Workbench — invarianti

### Nota a margine

`wbInsertMarginNote()` usa `_wbSelRect` (salvato al mouseup in `wbDocPageMouseUp`) per posizionare il popup:
- **Destra** del testo selezionato: `left = _wbSelRect.right + 14`
- **Altezza del primo rigo**: `top = _wbSelRect.top`

**Non ricalcolare `getBoundingClientRect()` dopo lo scroll** — restituirebbe coordinate errate. Usare sempre `_wbSelRect`.

### Auto-save — trigger obbligatori

`_wbAutoSave()` deve essere chiamata in questi punti (aggiunta dopo regressions):

- Dopo conferma nota (`wbMarginNoteConfirm`)
- Dopo invio messaggio chat (dopo `messagesEl.appendChild(userBubble)`)
- Dopo caricamento documento (`wbPostRender`)
- Dopo completamento tool AI
- Dopo risposta AI chat

### done() guard in _wbCbttsPlay

`_doneCalled` guard è obbligatorio per evitare che il mini-player sparisca prima della fine audio:
```js
var _doneCalled = false;
function done() {
  if (_doneCalled || _wbCbtts.cancelled) return;
  _doneCalled = true;
  setStatus(''); _wbWordHLStop(); if (onDone) onDone();
}
```
`done()` si chiama **solo** da `src.onended` (ultimo segmento) — mai da `scheduleNext` quando `idx >= n`.

---

## Vercel — ambiente

- Cold start: 3-5s → mitigato con warm-up a mousedown e caricamento documento
- Keep-warm: ping `/api/tts` ogni 3 minuti da `_wbTTSScheduleKeepWarm()`
- Env vars necessarie: `GOOGLE_TTS_API_KEY`, `GEMINI_API_KEY` (già presente), opzionale `OPENAI_API_KEY`

---

## Commit

Branch principale: `main` → deploy automatico su Vercel.
Prefissi commit: `fix:`, `feat:`, `perf:`, `design:`.
