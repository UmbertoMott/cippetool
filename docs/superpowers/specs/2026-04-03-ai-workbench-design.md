# AI Document Workbench — Design Spec
**Data:** 2026-04-03
**Approccio:** B — CSS custom `.wb-*` scoped a `#screenWorkbench`, zero conflitti con stili esistenti

---

## 1. Scopo

Aggiungere una terza modalità alla schermata di selezione (`screenMode`) che apre un workbench dedicato all'analisi AI di documenti PDF legati al contesto CIPP/E / GDPR. Il workbench offre 5 strumenti AI strutturati e un toggle tra due layout visivi (Split orizzontale / Stack verticale).

---

## 2. Modifiche a screenMode

- Griglia: `grid-template-columns: 1fr 1fr 1fr` su desktop (≥900px), `1fr 1fr` con terza card sotto su mobile
- Nuova card:
  - Icona: `🔬`
  - Titolo: "AI Document Workbench"
  - Descrizione: "Carica un PDF · Analisi AI strutturata · Visual Storytelling · Sintesi concetti · Domande di ripasso · Flashcard automatiche"
  - CTA: "Apri il workbench →" — colore `#d394ff`
  - Hover: `border-color: #d394ff`, `box-shadow: 0 12px 40px rgba(211,148,255,.2)`, `translateY(-3px)`
  - `onclick`: `showScreen('screenWorkbench')`

---

## 3. Tema Luminance Scholar (CSS scoped)

Blocco `<style id="wb-theme">` aggiunto nell'`<head>`. Tutte le regole prefissate `.wb-` o `#screenWorkbench` per zero conflitti.

```css
/* Variabili */
#screenWorkbench {
  --wb-bg:        #0e0e0e;
  --wb-sur-low:   #131313;
  --wb-sur:       #191919;
  --wb-sur-high:  #1f1f1f;
  --wb-sur-top:   #262626;
  --wb-primary:   #d394ff;
  --wb-primary-d: #aa30fa;
  --wb-primary-f: #cb80ff;
  --wb-tertiary:  #ff6d8d;
  --wb-cyan:      #06b6d4;
  --wb-outline:   #484848;
  --wb-txt:       #ffffff;
  --wb-muted:     #ababab;
  --wb-void:      #000000;
  font-family: 'Inter', sans-serif;
  background: var(--wb-bg);
  color: var(--wb-txt);
}
```

Font Space Grotesk caricato via `<link>` aggiuntivo (solo se non già presente).

---

## 4. Struttura screenWorkbench

```
#screenWorkbench
└── .wb-shell (display:flex; flex-direction:column; height:100vh)
    ├── .wb-header          ← barra fissa top
    │   ├── ← Torna (button)
    │   ├── 🔬 AI Document Workbench (titolo)
    │   └── .wb-toggle      ← pill A/B
    ├── .wb-upload-bar      ← Step 01, sempre visibile
    └── .wb-main            ← area principale, cambia layout
        ├── [Layout A] .wb-split  grid 2 colonne
        │   ├── .wb-doc-panel     ← Step 02 documento
        │   └── .wb-tools-panel  ← Step 03 tools
        └── [Layout B] .wb-stack  flex colonna
            ├── .wb-doc-panel
            └── .wb-tools-panel
```

---

## 5. Toggle Layout A / B

- Pill button nell'header: `[⬜⬛ Split | ⬛⬜ Stack]`
- Classe attiva: `.wb-main` riceve classe `wb-layout-split` o `wb-layout-stack`
- Persistenza: `localStorage.setItem('wb_layout_pref', 'split'|'stack')`
- Default: `split` (Layout A)
- Transizione: `transition: all 0.3s ease`

---

## 6. Step 01 — Upload Bar

- Sempre visibile sotto l'header, non scrolla
- Stato vuoto: zona dashed con `📎 Nessun documento — clicca per caricare PDF`
- Stato caricato: nome file + dimensione + pulsante "Cambia file"
- Usa il flusso upload esistente: `POST /api/upload/request-url` → PUT GCS → `POST /api/upload/confirm`
- Dopo conferma: salva `_wbCurrentBlob` (blob_name) e `_wbCurrentFile` (filename), abilita i 5 tool
- Supabase sync: chiama `_supa.from('file_uploads').insert(...)` (già implementato, riusa pattern Task 8)

---

## 7. Step 02 — Document Panel

- Header: "STEP 02 · DOCUMENT VIEW" con controlli paginazione e zoom
- Body: area scrollabile `#000000` con testo estratto dal PDF (chiama `GET /api/upload/local/{blob}/extract-text` o l'endpoint LLC esistente)
- Layout A: colonna sinistra fissa ~45% larghezza
- Layout B: blocco collassabile (accordion) con altezza max `320px` prima dei tool

---

## 8. Step 03 — 5 Tool Cards

Ogni tool card: `background #1f1f1f`, `border-radius 12px`, glow bar sinistra `4px`, stato locked se nessun file caricato.

### TOOL 01 — Visual Storytelling `(glow: #d394ff)`
- Prompt AI: genera diagramma Mermaid (flowchart/sequenza) del concetto principale + metafora cognitiva quotidiana
- Render Mermaid: carica `mermaid.min.js` via CDN on-demand (lazy, solo se il tool viene aperto)
- Fallback se Mermaid non disponibile: ASCII art in `<pre>` monospace
- UI: blocco void `#000000` per il diagramma + box italic in `#262626` per la metafora

### TOOL 02 — Sintesi & Chunks `(glow: #cb80ff)`
- Prompt AI: 6-8 blocchi concettuali, ciascuno con titolo + 3 righe + tag articolo GDPR
- UI: cards `#262626` in griglia 2 colonne (layout A) o lista (layout B)

### TOOL 03 — Domande di Ripasso `(glow: #ff6d8d)`
- Prompt AI: 5 domande a risposta aperta dal documento
- UI: ogni domanda in "closed" state (background `#262626`, bordo tertiary ghost) → click → reveal risposta con animazione `scale(0.95)→scale(1)` + fade

### TOOL 04 — Flashcard Automatiche `(glow: #aa30fa)`
- Prompt AI: estrae 5-10 coppie termine/definizione GDPR
- UI: anteprima liste, pulsante "Salva X flashcard" → chiama `fcSave()` esistente con Supabase sync
- Badge: "✓ Salvate" dopo conferma

### TOOL 05 — Chat Contestuale `(glow: #06b6d4)`
- Campo input + lista messaggi (bubble style)
- Chiama il backend LLC esistente con `blob_name = _wbCurrentBlob`
- Riusa `llcChatSend()` o la chiamata diretta `POST /api/chat` con context del blob

---

## 9. Flusso Dati

```
[Utente carica PDF]
    → /api/upload/request-url (ottieni signed URL GCS)
    → PUT signed_url (upload diretto GCS)
    → /api/upload/confirm (registra nel DB)
    → Supabase file_uploads.insert (sync metadata)
    → _wbCurrentBlob = blob_name
    → Abilita 5 tool (rimuovi classe .wb-locked)

[Utente apre Tool 01-04]
    → POST /api/chat con {blob_name, prompt, tool_type}
    → Streaming response → renderizza nel tool card

[Utente salva Flashcard]
    → fcSave(cards) → localStorage + Supabase
```

---

## 10. Stato Locked / Abilitato

```css
.wb-tool-card.wb-locked {
  opacity: 0.4;
  pointer-events: none;
}
.wb-tool-card.wb-locked::after {
  content: '🔒 Carica un documento per attivare';
  /* overlay centrato */
}
```

---

## 11. File da modificare

- `public/index.html`:
  1. `<style id="wb-theme">` nell'`<head>`
  2. `<link>` Space Grotesk (se non già presente)
  3. Card terza su `#screenMode` (modifica griglia + nuovo button)
  4. Nuovo `<div id="screenWorkbench">` dopo `#screenMode`
  5. Funzioni JS: `wbInit()`, `wbToggleLayout()`, `wbUpload()`, `wbRunTool(toolId)`, `wbSaveFlashcards()`

---

## 12. Non incluso (YAGNI)

- Storico sessioni workbench (futura feature)
- Export PDF dei risultati (futura feature)
- Modalità confronto multi-documento (futura feature)
