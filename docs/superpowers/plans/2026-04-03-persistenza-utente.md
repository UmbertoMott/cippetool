# Persistenza Utente — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rendere persistenti cross-device chat, flashcard, progressi quiz e file caricati usando Supabase come unica fonte di verità, con login Google obbligatorio.

**Architecture:** Il frontend JS in `public/index.html` scrive direttamente su Supabase (client già caricato) per tutti i dati utente. Il backend Render non cambia — resta responsabile solo delle operazioni AI. `localStorage` viene usato solo per preferenze UI non critiche (tema).

**Tech Stack:** Supabase JS v2 (già caricato in pagina), Supabase Postgres, Row Level Security, Supabase Realtime, Vanilla JS

---

## File coinvolti

| File | Operazione | Responsabilità |
|------|-----------|---------------|
| `supabase/schema.sql` | Modifica | Aggiunge 4 nuove tabelle + RLS |
| `public/index.html` | Modifica | Auth gate, sync Supabase, migrazione, Realtime |

Il backend Python **non viene toccato**.

---

## Task 1: Schema Supabase — 4 nuove tabelle

**Files:**
- Modify: `supabase/schema.sql`

- [ ] **Step 1: Aggiungi le 4 tabelle in fondo a `supabase/schema.sql`**

Apri `supabase/schema.sql` e aggiungi in fondo:

```sql
-- ── Chat sessions (Legal Lab LLC + ESB + EAP) ────────────────────────
CREATE TABLE IF NOT EXISTS public.chat_sessions (
  id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id     UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
  module      TEXT NOT NULL,                    -- 'llc' | 'esb' | 'eap'
  title       TEXT,                             -- primo messaggio troncato 60 chars
  messages    JSONB NOT NULL DEFAULT '[]',      -- [{role, content, ts}]
  blob_name   TEXT,                             -- documento GCS collegato (opzionale)
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Flashcard ────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.flashcards (
  id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id     UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
  front       TEXT NOT NULL,
  back        TEXT NOT NULL,
  domain      TEXT,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Progressi quiz (un record per utente, aggiornato in-place) ───────
CREATE TABLE IF NOT EXISTS public.quiz_progress (
  user_id       UUID PRIMARY KEY REFERENCES public.profiles(id) ON DELETE CASCADE,
  answers       JSONB NOT NULL DEFAULT '{}',    -- { "q_id": { correct: bool, ts: iso } }
  score_total   INTEGER NOT NULL DEFAULT 0,
  score_correct INTEGER NOT NULL DEFAULT 0,
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── File uploads (sostituisce SQLite su Render) ───────────────────────
CREATE TABLE IF NOT EXISTS public.file_uploads (
  id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id           UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
  blob_name         TEXT NOT NULL UNIQUE,
  original_filename TEXT NOT NULL,
  file_size_bytes   BIGINT,
  mime_type         TEXT,
  status            TEXT NOT NULL DEFAULT 'in_attesa',
  notes             TEXT,
  uploaded_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── RLS ──────────────────────────────────────────────────────────────
ALTER TABLE public.chat_sessions  ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.flashcards     ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.quiz_progress  ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.file_uploads   ENABLE ROW LEVEL SECURITY;

CREATE POLICY "own" ON public.chat_sessions  FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "own" ON public.flashcards     FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "own" ON public.quiz_progress  FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "own" ON public.file_uploads   FOR ALL USING (auth.uid() = user_id);
```

- [ ] **Step 2: Esegui lo schema sul progetto Supabase**

1. Vai su https://supabase.com → tuo progetto → SQL Editor
2. Incolla il contenuto aggiunto al file
3. Clicca **Run**
4. Verifica: Table Editor → vedi le 4 nuove tabelle

- [ ] **Step 3: Abilita Realtime per `chat_sessions`**

In Supabase → Database → Replication → abilita `chat_sessions` nella lista delle tabelle con Realtime.

- [ ] **Step 4: Commit**

```bash
cd /Users/umbertomottola/Downloads/cipp_legal_saas
git add supabase/schema.sql
git commit -m "feat: schema Supabase - chat_sessions, flashcards, quiz_progress, file_uploads"
```

---

## Task 2: Auth gate — login obbligatorio all'avvio

**Files:**
- Modify: `public/index.html` (vicino a riga 3559, `DOMContentLoaded`)

Il flusso attuale mostra la landing page agli utenti anonimi. Va modificato per controllare la sessione Supabase prima di tutto.

- [ ] **Step 1: Localizza `DOMContentLoaded` in `index.html`**

Cerca la riga:
```js
document.addEventListener('DOMContentLoaded', function() {
```
(circa riga 3559)

- [ ] **Step 2: Localizza `initSupabase` e `_supaShowApp`**

Cerca (circa riga 3419):
```js
(async function initSupabase() {
```
e (circa riga 3470):
```js
function _supaShowApp() {
```

- [ ] **Step 3: Aggiungi auth gate in `initSupabase`**

Trova il blocco:
```js
  var { data: { session } } = await _supa.auth.getSession();
  if (session) {
    _supaUser = session.user;
    _supaShowApp();
  }
```

Sostituiscilo con:
```js
  var { data: { session } } = await _supa.auth.getSession();
  if (session) {
    _supaUser = session.user;
    _supaShowApp();
  } else {
    // Auth gate: nessun accesso anonimo — mostra sempre il login
    if (typeof showScreen === 'function') {
      showScreen('screenLogin');
    } else {
      // showScreen non ancora disponibile: aspetta DOMContentLoaded
      document.addEventListener('DOMContentLoaded', function() {
        if (typeof showScreen === 'function') showScreen('screenLogin');
      });
    }
  }
```

- [ ] **Step 4: Verifica manuale**
1. Apri `http://localhost:7890` in una finestra in incognito
2. Verifica che venga mostrata la schermata di login (non la landing page)
3. Fai login con Google
4. Verifica che dopo il login venga mostrata la dashboard

- [ ] **Step 5: Commit**

```bash
git add public/index.html
git commit -m "feat: auth gate - login Google obbligatorio all'avvio"
```

---

## Task 3: Helper `_supaSync` + `loadUserData()`

**Files:**
- Modify: `public/index.html` (dopo la definizione di `_supaUser`, circa riga 3412)

Aggiungi le funzioni di utilità Supabase usate da tutti i task successivi.

- [ ] **Step 1: Aggiungi `_supaLoadAll()` dopo la riga `var _supaUser = null;`**

Trova:
```js
var _supaUser = null;
```

Dopo quella riga aggiungi:

```js
// ── Supabase persistence helpers ─────────────────────────────────────

// Dati caricati in memoria dopo il login
var _supaChats      = [];   // chat_sessions rows
var _supaFlashcards = [];   // flashcards rows
var _supaQuizProgress = {}; // quiz_progress row
var _supaFiles      = [];   // file_uploads rows

async function _supaLoadAll() {
  if (!_supa || !_supaUser) return;
  try {
    var [chatsRes, flashRes, quizRes, filesRes] = await Promise.all([
      _supa.from('chat_sessions').select('*').order('updated_at', { ascending: false }),
      _supa.from('flashcards').select('*').order('created_at', { ascending: false }),
      _supa.from('quiz_progress').select('*').eq('user_id', _supaUser.id).maybeSingle(),
      _supa.from('file_uploads').select('*').order('uploaded_at', { ascending: false })
    ]);
    _supaChats        = chatsRes.data  || [];
    _supaFlashcards   = flashRes.data  || [];
    _supaQuizProgress = quizRes.data   || {};
    _supaFiles        = filesRes.data  || [];
  } catch(e) {
    console.warn('[Supabase] loadAll error:', e);
  }
}

// Salva o aggiorna una chat session
async function _supaSaveChatSession(module, sessionId, title, messages, blobName) {
  if (!_supa || !_supaUser) return null;
  try {
    var existing = _supaChats.find(function(c) { return c.id === sessionId; });
    if (existing) {
      var { data } = await _supa.from('chat_sessions')
        .update({ title: title, messages: messages, updated_at: new Date().toISOString() })
        .eq('id', sessionId).select().single();
      // aggiorna cache locale
      var idx = _supaChats.findIndex(function(c) { return c.id === sessionId; });
      if (idx >= 0) _supaChats[idx] = data;
      return data;
    } else {
      var { data } = await _supa.from('chat_sessions')
        .insert({ id: sessionId, user_id: _supaUser.id, module: module,
                  title: title, messages: messages, blob_name: blobName || null })
        .select().single();
      _supaChats.unshift(data);
      return data;
    }
  } catch(e) {
    console.warn('[Supabase] saveChatSession error:', e);
    return null;
  }
}

// Elimina una chat session
async function _supaDeleteChatSession(sessionId) {
  if (!_supa || !_supaUser) return;
  try {
    await _supa.from('chat_sessions').delete().eq('id', sessionId);
    _supaChats = _supaChats.filter(function(c) { return c.id !== sessionId; });
  } catch(e) {
    console.warn('[Supabase] deleteChatSession error:', e);
  }
}
```

- [ ] **Step 2: Aggiungi la chiamata `_supaLoadAll()` in `_supaShowApp()`**

Trova la funzione:
```js
function _supaShowApp() {
```

All'interno, trova la chiamata asincrona interna (il blocco `(async function() {`). Aggiungi `await _supaLoadAll();` come **prima** istruzione dentro quell'IIFE:

```js
    (async function() {
      await _supaLoadAll();   // <-- AGGIUNGI QUESTA RIGA
      try {
        if (typeof getUsers === 'function') {
```

- [ ] **Step 3: Verifica console**

Dopo il login, apri DevTools → Console e verifica che non ci siano errori rossi relativi a `_supaLoadAll`.

- [ ] **Step 4: Commit**

```bash
git add public/index.html
git commit -m "feat: helper _supaLoadAll + cache in-memory dati utente"
```

---

## Task 4: Sync chat ESB

**Files:**
- Modify: `public/index.html` (vicino a riga 7495, funzioni `esbSaveChats` / `esbLoadChats`)

- [ ] **Step 1: Localizza `esbSaveChats` e `esbLoadChats`**

Cerca:
```js
var _ESB_LS_KEY = 'cippe_esbChats_v3';
```
(circa riga 7495). Le funzioni `esbSaveChats()` e `esbLoadChats()` sono nelle righe successive.

- [ ] **Step 2: Modifica `esbSaveChats` per aggiungere sync Supabase**

Trova il corpo di `esbSaveChats` che contiene:
```js
    localStorage.setItem(_ESB_LS_KEY, JSON.stringify({
```

Aggiungi la chiamata Supabase **dopo** il salvataggio localStorage esistente. La funzione dopo la modifica deve avere questo aspetto:

```js
  function esbSaveChats() {
    try {
      var toSave = _esbChats.slice(0, 20).map(function(ch) {
        return { id: ch.id, name: ch.name, date: ch.date,
                 msgs: (ch.msgs || []).slice(-100) };
      });
      localStorage.setItem(_ESB_LS_KEY, JSON.stringify({
        chats: toSave, active: _esbActive
      }));
    } catch(e) {}
    // Supabase sync: salva la chat attiva
    if (_supa && _supaUser && _esbActive !== null) {
      var chat = _esbChats.find(function(ch) { return ch.id === _esbActive; });
      if (chat) {
        var sid = 'esb_' + _esbActive;
        var title = chat.name || 'Chat ESB';
        var messages = (chat.msgs || []).map(function(m) {
          return { role: m.role, content: m.html || m.text || '', ts: m.ts || new Date().toISOString() };
        });
        _supaSaveChatSession('esb', sid, title, messages, null).catch(function(){});
      }
    }
  }
```

- [ ] **Step 3: Modifica `esbLoadChats` per caricare da Supabase se disponibile**

Trova la funzione `esbLoadChats()`. Aggiungi il caricamento da `_supaChats` come sorgente primaria:

```js
  function esbLoadChats() {
    // Prima prova da Supabase (se disponibile)
    var supaEsb = _supaChats.filter(function(c) { return c.module === 'esb'; });
    if (supaEsb.length > 0) {
      _esbChats = supaEsb.map(function(c) {
        return {
          id:   c.id,
          name: c.title || 'Chat ESB',
          date: new Date(c.created_at).toLocaleDateString('it-IT'),
          msgs: (c.messages || []).map(function(m) {
            return { role: m.role, html: m.content, ts: m.ts };
          })
        };
      });
      if (_esbChats.length > 0) _esbActive = _esbChats[0].id;
      return;
    }
    // Fallback localStorage
    try {
      var raw = localStorage.getItem(_ESB_LS_KEY);
      if (!raw) return;
      var saved = JSON.parse(raw);
      if (!saved || !saved.chats) return;
      _esbChats = saved.chats;
      _esbActive = saved.active !== undefined ? Number(saved.active) : null;
      if (_esbActive === null && _esbChats.length > 0) _esbActive = _esbChats[0].id;
    } catch(e) {}
  }
```

- [ ] **Step 4: Localizza la funzione che elimina una chat ESB**

Cerca:
```js
_esbChats = _esbChats.filter(function(x){ return x.id !== id; });
```
(circa riga 7649). Dopo questa riga aggiungi:
```js
    _supaDeleteChatSession('esb_' + id).catch(function(){});
```

- [ ] **Step 5: Verifica manuale**

1. Avvia il combined server: `cd backend && python serve_combined.py`
2. Apri http://localhost:7890, fai login
3. Crea una nuova chat ESB, scrivi un messaggio
4. Vai su Supabase → Table Editor → `chat_sessions` → verifica che ci sia una riga con `module = 'esb'`
5. Ricarica la pagina → verifica che la chat sia ancora presente

- [ ] **Step 6: Commit**

```bash
git add public/index.html
git commit -m "feat: sync chat ESB su Supabase"
```

---

## Task 5: Sync chat LLC (Legal Lab)

**Files:**
- Modify: `public/index.html` (vicino a righe 9426 e 14067)

Il Legal Lab ha due strutture separate: `LLC._sessions` (lista sessioni) e `LLC._chatThreads` (messaggi per sessione).

- [ ] **Step 1: Localizza le funzioni di save/load sessioni LLC**

Cerca:
```js
var _LLC_SESSIONS_KEY = 'llc_chat_sessions_v2';
```
(circa riga 9426). Subito dopo ci sono le funzioni di save/load.

- [ ] **Step 2: Modifica save sessioni LLC**

Trova il blocco che contiene:
```js
    localStorage.setItem(_LLC_SESSIONS_KEY, JSON.stringify(LLC._sessions));
```

Aggiungi dopo:
```js
    // Supabase sync: aggiorna titoli sessioni attive
    if (_supa && _supaUser && LLC._sessions) {
      Object.keys(LLC._sessions).forEach(function(sid) {
        var sess = LLC._sessions[sid];
        var threads = LLC._chatThreads && LLC._chatThreads[sid];
        var messages = threads ? threads.map(function(m) {
          return { role: m.role, content: m.content || m.text || '', ts: m.ts || new Date().toISOString() };
        }) : [];
        _supaSaveChatSession('llc', sid, sess.title || 'Sessione LLC', messages, sess.blobName || null)
          .catch(function(){});
      });
    }
```

- [ ] **Step 3: Modifica load sessioni LLC**

Trova il blocco che contiene:
```js
    var raw = localStorage.getItem(_LLC_SESSIONS_KEY);
```

Aggiungi **prima** di quel blocco:
```js
    // Prima prova da Supabase
    var supaLlc = _supaChats.filter(function(c) { return c.module === 'llc'; });
    if (supaLlc.length > 0) {
      LLC._sessions = {};
      LLC._chatThreads = {};
      supaLlc.forEach(function(c) {
        LLC._sessions[c.id] = { title: c.title, blobName: c.blob_name, ts: c.updated_at };
        LLC._chatThreads[c.id] = (c.messages || []).map(function(m) {
          return { role: m.role, content: m.content, ts: m.ts };
        });
      });
      return;
    }
```

- [ ] **Step 4: Localizza le funzioni di save/load thread LLC**

Cerca:
```js
var _LLC_THREAD_KEY = 'llc_chat_thread_v2';
```
(circa riga 14067).

- [ ] **Step 5: Modifica save thread LLC**

Trova il blocco che contiene:
```js
  try { localStorage.setItem(_LLC_THREAD_KEY, JSON.stringify(LLC._chatThreads)); } catch(e) {}
```

Aggiungi dopo:
```js
  // Supabase sync: aggiorna messaggi della sessione corrente
  if (_supa && _supaUser && LLC._activeSession && LLC._chatThreads) {
    var sid = LLC._activeSession;
    var sess = LLC._sessions && LLC._sessions[sid];
    var threads = LLC._chatThreads[sid] || [];
    var messages = threads.map(function(m) {
      return { role: m.role, content: m.content || m.text || '', ts: m.ts || new Date().toISOString() };
    });
    _supaSaveChatSession('llc', sid, (sess && sess.title) || 'Sessione LLC', messages,
      (sess && sess.blobName) || null).catch(function(){});
  }
```

- [ ] **Step 6: Localizza `LLC._activeSession` o la variabile equivalente**

Cerca:
```js
LLC._activeSession
```
oppure come è chiamata (potrebbe essere `LLC.activeSession` o `LLC.currentSession`). Se non esiste come proprietà esplicita, cerca dove viene settata la sessione corrente nelle funzioni LLC.

- [ ] **Step 7: Verifica manuale**

1. Apri http://localhost:7890, fai login
2. Apri un documento PDF e avvia una sessione di chat Legal Lab
3. Invia un messaggio e aspetta la risposta
4. Vai su Supabase → `chat_sessions` → verifica riga con `module = 'llc'` e messages non vuoti
5. Ricarica la pagina → verifica che la conversazione sia ancora presente

- [ ] **Step 8: Commit**

```bash
git add public/index.html
git commit -m "feat: sync chat Legal Lab (LLC) su Supabase"
```

---

## Task 6: Sync flashcard

**Files:**
- Modify: `public/index.html` (vicino a riga 17019)

- [ ] **Step 1: Localizza `fcLoad` e `fcSave`**

Cerca:
```js
var _FC_KEY = 'cippe_flashcards_v1';
```
(circa riga 17017).

- [ ] **Step 2: Sostituisci `fcLoad`**

Trova:
```js
function fcLoad() {
  try { return JSON.parse(localStorage.getItem(_FC_KEY) || '[]'); }
```

Sostituisci l'intera funzione `fcLoad`:
```js
function fcLoad() {
  // Prima prova da cache Supabase in-memory
  if (_supaFlashcards && _supaFlashcards.length > 0) {
    return _supaFlashcards.map(function(f) {
      return { id: f.id, front: f.front, back: f.back, domain: f.domain || '' };
    });
  }
  // Fallback localStorage
  try { return JSON.parse(localStorage.getItem(_FC_KEY) || '[]'); }
  catch(e) { return []; }
}
```

- [ ] **Step 3: Sostituisci `fcSave`**

Trova:
```js
function fcSave(arr) {
  try { localStorage.setItem(_FC_KEY, JSON.stringify(arr)); } catch(e){}
```

Sostituisci l'intera funzione `fcSave`:
```js
function fcSave(arr) {
  try { localStorage.setItem(_FC_KEY, JSON.stringify(arr)); } catch(e){}
  // Supabase sync: elimina tutto e reinserisci (array piccolo, max ~200 cards)
  if (_supa && _supaUser) {
    (async function() {
      try {
        // Elimina cards non più presenti
        var incomingIds = arr.filter(function(c) { return c.id && String(c.id).length === 36; })
                             .map(function(c) { return c.id; });
        var existingIds = _supaFlashcards.map(function(f) { return f.id; });
        var toDelete = existingIds.filter(function(id) { return incomingIds.indexOf(id) === -1; });
        if (toDelete.length > 0) {
          await _supa.from('flashcards').delete().in('id', toDelete);
        }
        // Inserisci nuove (quelle senza UUID Supabase)
        var toInsert = arr.filter(function(c) {
          return !c.id || String(c.id).length !== 36;
        }).map(function(c) {
          return { user_id: _supaUser.id, front: c.front, back: c.back, domain: c.domain || null };
        });
        if (toInsert.length > 0) {
          var { data } = await _supa.from('flashcards').insert(toInsert).select();
          if (data) _supaFlashcards = _supaFlashcards.concat(data);
        }
      } catch(e) { console.warn('[Supabase] fcSave error:', e); }
    })();
  }
}
```

- [ ] **Step 4: Verifica manuale**

1. Vai nella sezione Flashcard dell'app
2. Crea una nuova flashcard
3. Vai su Supabase → `flashcards` → verifica che la riga sia presente
4. Ricarica la pagina → verifica che la flashcard sia ancora visibile

- [ ] **Step 5: Commit**

```bash
git add public/index.html
git commit -m "feat: sync flashcard su Supabase"
```

---

## Task 7: Sync progressi quiz (heatmap)

**Files:**
- Modify: `public/index.html` (vicino a riga 17275)

- [ ] **Step 1: Localizza le funzioni heatmap**

Cerca:
```js
var _HM_KEY = 'cippe_heatmap_v1';
```
(circa riga 17275). Subito dopo ci sono le funzioni di load/save.

- [ ] **Step 2: Sostituisci la funzione di load heatmap**

Trova il blocco:
```js
  try { return JSON.parse(localStorage.getItem(_HM_KEY) || '{}'); } catch(e) { return {}; }
```

Sostituisci l'intera funzione (quella che contiene quella riga):
```js
function hmLoad() {
  // Prima prova da cache Supabase
  if (_supaQuizProgress && _supaQuizProgress.answers) {
    return _supaQuizProgress.answers;
  }
  try { return JSON.parse(localStorage.getItem(_HM_KEY) || '{}'); } catch(e) { return {}; }
}
```

- [ ] **Step 3: Sostituisci la funzione di save heatmap**

Trova il blocco:
```js
  try { localStorage.setItem(_HM_KEY, JSON.stringify(data)); } catch(e) {}
```

Sostituisci l'intera funzione (quella che contiene quella riga):
```js
function hmSave(data) {
  try { localStorage.setItem(_HM_KEY, JSON.stringify(data)); } catch(e) {}
  // Supabase sync: upsert del record quiz_progress
  if (_supa && _supaUser) {
    (async function() {
      try {
        var total   = Object.keys(data).length;
        var correct = Object.values(data).filter(function(v) { return v && v.correct; }).length;
        var { data: row } = await _supa.from('quiz_progress')
          .upsert({
            user_id:       _supaUser.id,
            answers:       data,
            score_total:   total,
            score_correct: correct,
            updated_at:    new Date().toISOString()
          }, { onConflict: 'user_id' })
          .select().single();
        if (row) _supaQuizProgress = row;
      } catch(e) { console.warn('[Supabase] hmSave error:', e); }
    })();
  }
}
```

- [ ] **Step 4: Verifica manuale**

1. Vai nella sezione Quiz/Esame
2. Rispondi a una domanda
3. Vai su Supabase → `quiz_progress` → verifica che il record sia presente con `answers` non vuoto
4. Ricarica la pagina → verifica che la heatmap mostri ancora le risposte precedenti

- [ ] **Step 5: Commit**

```bash
git add public/index.html
git commit -m "feat: sync progressi quiz (heatmap) su Supabase"
```

---

## Task 8: Sync file uploads

**Files:**
- Modify: `public/index.html` (la funzione che gestisce la conferma upload)

- [ ] **Step 1: Localizza la funzione di conferma upload nel frontend**

Cerca nel file la chiamata a `/api/upload/confirm` oppure `/api/upload/direct`:
```js
/api/upload/confirm
```
oppure:
```js
/api/upload/direct
```

- [ ] **Step 2: Aggiungi sync Supabase dopo upload confermato**

Trova il blocco dove viene gestita la risposta di successo dell'upload (il `.then()` o `await` che segue la chiamata fetch a `/api/upload/confirm` o `/api/upload/direct`). Aggiungi dopo la gestione del successo:

```js
// Supabase sync: salva metadati file
if (_supa && _supaUser) {
  _supa.from('file_uploads').insert({
    user_id:           _supaUser.id,
    blob_name:         uploadedBlobName,       // variabile del contesto locale
    original_filename: originalFilename,        // variabile del contesto locale
    file_size_bytes:   fileSize || null,        // variabile del contesto locale
    mime_type:         mimeType || null,        // variabile del contesto locale
    status:            'in_attesa'
  }).then(function(res) {
    if (res.data) _supaFiles.unshift(res.data[0]);
  }).catch(function(e) { console.warn('[Supabase] file_uploads insert error:', e); });
}
```

**Nota:** adatta i nomi delle variabili (`uploadedBlobName`, `originalFilename`, ecc.) a quelli effettivamente usati nel contesto locale della funzione.

- [ ] **Step 3: Aggiorna la lista file nella zona utente per leggerla da `_supaFiles`**

Cerca la funzione che renderizza la lista dei file caricati dall'utente. Se chiama `/api/upload/files`, aggiungi un check preliminare:
```js
// Prima mostra i file dalla cache Supabase (più veloce, no round-trip)
if (_supaFiles && _supaFiles.length > 0) {
  renderFileList(_supaFiles);   // adatta al nome della funzione di render esistente
} else {
  // Fallback: chiama il backend
  fetch('/api/upload/files?user_id=' + encodeURIComponent(_supaUser.id))
    // ... logica esistente
}
```

- [ ] **Step 4: Verifica manuale**

1. Carica un file PDF nella zona utente
2. Vai su Supabase → `file_uploads` → verifica la riga
3. Ricarica la pagina → verifica che il file appaia nella lista

- [ ] **Step 5: Commit**

```bash
git add public/index.html
git commit -m "feat: sync metadati file uploads su Supabase"
```

---

## Task 9: Dialog migrazione localStorage

**Files:**
- Modify: `public/index.html` (dentro `_supaShowApp`, dopo `_supaLoadAll`)

- [ ] **Step 1: Aggiungi funzione di migrazione**

Dopo il blocco degli helper Supabase (Task 3), aggiungi:

```js
async function _supaCheckMigration() {
  // Esegui migrazione solo una volta per utente
  var migKey = 'cippe_migrated_' + _supaUser.id;
  if (localStorage.getItem(migKey)) return;

  // Controlla se ci sono dati locali da migrare
  var hasLocal = localStorage.getItem('cippe_esbChats_v3') ||
                 localStorage.getItem('llc_chat_sessions_v2') ||
                 localStorage.getItem('cippe_flashcards_v1') ||
                 localStorage.getItem('cippe_heatmap_v1');
  if (!hasLocal) {
    localStorage.setItem(migKey, '1');
    return;
  }

  // Mostra dialog
  var choice = await new Promise(function(resolve) {
    var overlay = document.createElement('div');
    overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.7);z-index:99999;display:flex;align-items:center;justify-content:center';
    overlay.innerHTML = '<div style="background:#1e1e2e;border:1px solid rgba(255,255,255,.15);border-radius:16px;padding:32px;max-width:420px;text-align:center;font-family:Inter,sans-serif;color:#e0e0f0">'
      + '<div style="font-size:32px;margin-bottom:12px">📂</div>'
      + '<h3 style="margin:0 0 8px;font-size:18px">Dati locali trovati</h3>'
      + '<p style="color:#aaa;font-size:14px;margin:0 0 24px">Hai chat, flashcard e progressi salvati su questo browser. Vuoi importarli nel tuo account?</p>'
      + '<div style="display:flex;gap:12px;justify-content:center">'
      + '<button id="_migYes" style="padding:10px 24px;background:#7c3aed;color:white;border:none;border-radius:8px;cursor:pointer;font-weight:600">Sì, importa</button>'
      + '<button id="_migNo" style="padding:10px 24px;background:rgba(255,255,255,.08);color:#ccc;border:1px solid rgba(255,255,255,.15);border-radius:8px;cursor:pointer">No, ignora</button>'
      + '</div></div>';
    document.body.appendChild(overlay);
    document.getElementById('_migYes').onclick = function() { document.body.removeChild(overlay); resolve(true); };
    document.getElementById('_migNo').onclick  = function() { document.body.removeChild(overlay); resolve(false); };
  });

  if (choice) {
    // Migra ESB chats
    var esbRaw = localStorage.getItem('cippe_esbChats_v3');
    if (esbRaw) {
      try {
        var esbData = JSON.parse(esbRaw);
        var chats = esbData.chats || [];
        for (var i = 0; i < chats.length; i++) {
          var ch = chats[i];
          var msgs = (ch.msgs || []).map(function(m) {
            return { role: m.role, content: m.html || m.text || '', ts: m.ts || new Date().toISOString() };
          });
          await _supa.from('chat_sessions').insert({
            user_id: _supaUser.id, module: 'esb',
            title: ch.name || 'Chat ESB', messages: msgs
          });
        }
      } catch(e) { console.warn('[Migration] ESB error:', e); }
    }
    // Migra LLC sessions
    var llcRaw = localStorage.getItem('llc_chat_sessions_v2');
    if (llcRaw) {
      try {
        var llcSessions = JSON.parse(llcRaw);
        var threadsRaw = localStorage.getItem('llc_chat_thread_v2');
        var threads = threadsRaw ? JSON.parse(threadsRaw) : {};
        for (var sid in llcSessions) {
          var sess = llcSessions[sid];
          var msgs = (threads[sid] || []).map(function(m) {
            return { role: m.role, content: m.content || '', ts: m.ts || new Date().toISOString() };
          });
          await _supa.from('chat_sessions').insert({
            user_id: _supaUser.id, module: 'llc',
            title: sess.title || 'Sessione LLC', messages: msgs,
            blob_name: sess.blobName || null
          });
        }
      } catch(e) { console.warn('[Migration] LLC error:', e); }
    }
    // Migra flashcard
    var fcRaw = localStorage.getItem('cippe_flashcards_v1');
    if (fcRaw) {
      try {
        var cards = JSON.parse(fcRaw);
        var toInsert = cards.map(function(c) {
          return { user_id: _supaUser.id, front: c.front, back: c.back, domain: c.domain || null };
        });
        if (toInsert.length > 0) await _supa.from('flashcards').insert(toInsert);
      } catch(e) { console.warn('[Migration] flashcards error:', e); }
    }
    // Migra quiz progress
    var hmRaw = localStorage.getItem('cippe_heatmap_v1');
    if (hmRaw) {
      try {
        var hmData = JSON.parse(hmRaw);
        var total   = Object.keys(hmData).length;
        var correct = Object.values(hmData).filter(function(v) { return v && v.correct; }).length;
        await _supa.from('quiz_progress').upsert({
          user_id: _supaUser.id, answers: hmData,
          score_total: total, score_correct: correct
        }, { onConflict: 'user_id' });
      } catch(e) { console.warn('[Migration] heatmap error:', e); }
    }
    // Ricarica dati da Supabase
    await _supaLoadAll();
  }

  // Segna come completata
  localStorage.setItem(migKey, '1');
  // Pulisci localStorage dati utente
  ['cippe_esbChats_v3','cippe_esbChats_v2','llc_chat_sessions_v2',
   'llc_chat_thread_v2','cippe_flashcards_v1','cippe_heatmap_v1'].forEach(function(k) {
    try { localStorage.removeItem(k); } catch(e) {}
  });
}
```

- [ ] **Step 2: Chiama `_supaCheckMigration()` in `_supaShowApp` dopo `_supaLoadAll()`**

Trova dentro l'IIFE in `_supaShowApp`:
```js
      await _supaLoadAll();
```

Aggiungi subito dopo:
```js
      await _supaCheckMigration();
```

- [ ] **Step 3: Verifica manuale**

1. Aggiungi manualmente dei dati in localStorage: `localStorage.setItem('cippe_flashcards_v1', JSON.stringify([{front:'test',back:'risposta',domain:'Art.5'}]))`
2. Ricarica la pagina → fai login
3. Verifica che appaia il dialog di migrazione
4. Clicca "Sì, importa"
5. Vai su Supabase → `flashcards` → verifica la riga importata
6. Ricarica di nuovo → verifica che il dialog NON appaia una seconda volta

- [ ] **Step 4: Commit**

```bash
git add public/index.html
git commit -m "feat: dialog migrazione dati localStorage → Supabase al primo login"
```

---

## Task 10: Supabase Realtime — sync cross-device chat

**Files:**
- Modify: `public/index.html` (dentro `_supaShowApp`, dopo la migrazione)

- [ ] **Step 1: Aggiungi subscription Realtime dopo `_supaCheckMigration()`**

Trova dentro l'IIFE in `_supaShowApp`:
```js
      await _supaCheckMigration();
```

Aggiungi subito dopo:
```js
      // Supabase Realtime: aggiorna chat se cambia su un altro dispositivo
      _supa.channel('user-chats-' + _supaUser.id)
        .on('postgres_changes', {
          event: 'UPDATE', schema: 'public', table: 'chat_sessions',
          filter: 'user_id=eq.' + _supaUser.id
        }, function(payload) {
          var updated = payload.new;
          var idx = _supaChats.findIndex(function(c) { return c.id === updated.id; });
          if (idx >= 0) {
            _supaChats[idx] = updated;
          } else {
            _supaChats.unshift(updated);
          }
          // Aggiorna UI ESB se la chat aggiornata è quella attiva
          if (updated.module === 'esb' && typeof esbLoadChats === 'function') {
            esbLoadChats();
            if (typeof esbRenderChatList === 'function') esbRenderChatList();
          }
        })
        .subscribe();
```

- [ ] **Step 2: Verifica manuale cross-device**

1. Apri l'app su due tab del browser diversi (o due browser)
2. Fai login con lo stesso account su entrambi
3. Crea un messaggio ESB su tab 1
4. Verifica che tab 2 riceva l'aggiornamento entro pochi secondi (controlla la console per errori Realtime)

- [ ] **Step 3: Commit**

```bash
git add public/index.html
git commit -m "feat: Supabase Realtime sync cross-device chat_sessions"
```

---

## Task 11: Pulizia localStorage

**Files:**
- Modify: `public/index.html`

- [ ] **Step 1: Aggiungi pulizia chiavi legacy nel logout**

Cerca la funzione `logout` o il handler del pulsante logout (circa riga 3449-3453). Aggiungi prima della chiamata `_supa.auth.signOut()`:

```js
    // Pulisci dati utente da localStorage (la fonte di verità è Supabase)
    ['cippe_esbChats_v3','cippe_esbChats_v2','llc_chat_sessions_v2',
     'llc_chat_thread_v2','llc_panel_hist_v1','cippe_flashcards_v1',
     'cippe_heatmap_v1','cippe_reports_v1'].forEach(function(k) {
      try { localStorage.removeItem(k); } catch(e) {}
    });
    // Azzera cache in-memory
    _supaChats = []; _supaFlashcards = []; _supaQuizProgress = {}; _supaFiles = [];
```

- [ ] **Step 2: Verifica manuale**

1. Fai login, crea una flashcard
2. Fai logout
3. Apri DevTools → Application → localStorage
4. Verifica che le chiavi `cippe_esbChats_v3`, `cippe_flashcards_v1`, ecc. non siano presenti
5. Fai login di nuovo → verifica che la flashcard sia ancora presente (arriva da Supabase)

- [ ] **Step 3: Commit**

```bash
git add public/index.html
git commit -m "feat: pulizia localStorage al logout - dati utente solo su Supabase"
```

---

## Task 12: Supabase anon key → Vercel Environment Variable

**Files:**
- Modify: `public/index.html`
- Vercel project settings

La chiave `sb_publishable_v_Af3s9TBMAJGDZWvf8nIg_VIeP7uy9` è una chiave pubblica (anon) — è progettata per stare nel frontend con RLS. Tuttavia i security scanner la flaggano. La soluzione è iniettarla tramite Vercel.

- [ ] **Step 1: Configura le env var su Vercel**

1. Vai su https://vercel.com → tuo progetto `privacyaitool` → Settings → Environment Variables
2. Aggiungi:
   - `NEXT_PUBLIC_SUPABASE_URL` = `https://dahwdvttuvvaxijlobtj.supabase.co`
   - `NEXT_PUBLIC_SUPABASE_ANON_KEY` = `sb_publishable_v_Af3s9TBMAJGDZWvf8nIg_VIeP7uy9`

- [ ] **Step 2: Aggiungi `vercel.json` build con injection**

Aggiorna `vercel.json` per usare una Edge Function che sostituisce i placeholder:

```json
{
  "version": 2,
  "builds": [
    {
      "src": "public/index.html",
      "use": "@vercel/static"
    }
  ],
  "routes": [
    {
      "src": "/api/(.*)",
      "dest": "https://cipp-legal-api.onrender.com/api/$1"
    },
    {
      "src": "/(.*)",
      "dest": "/public/index.html"
    }
  ]
}
```

**Nota:** `@vercel/static` non supporta env var injection. Per iniettare env var in un file HTML statico occorre un build step (Vite/webpack) oppure una Vercel Edge Function. **Valuta se il guadagno giustifica la complessità**: la chiave anon è pubblica by design e protetta da RLS. Se RLS è configurato correttamente, la chiave hardcoded è accettabile. Considera questo task opzionale fino a quando non è necessario per compliance.

- [ ] **Step 3: Commit (solo se si implementa l'injection)**

```bash
git add vercel.json public/index.html
git commit -m "feat: Supabase keys via Vercel env vars"
```

---

## Self-Review

### Copertura spec
- ✅ Schema 4 tabelle + RLS → Task 1
- ✅ Auth gate obbligatorio → Task 2
- ✅ `loadUserData()` parallelo → Task 3
- ✅ Sync ESB chat → Task 4
- ✅ Sync LLC chat → Task 5
- ✅ Sync flashcard → Task 6
- ✅ Sync quiz progress → Task 7
- ✅ Sync file uploads → Task 8
- ✅ Migrazione localStorage → Task 9
- ✅ Realtime cross-device → Task 10
- ✅ Pulizia localStorage → Task 11
- ✅ Supabase anon key → Task 12 (opzionale)

### Dipendenze tra task
- Task 4-11 dipendono da Task 3 (`_supaLoadAll`, `_supaChats`, ecc.) → devono essere eseguiti in ordine
- Task 1 deve essere eseguito prima di qualsiasi test funzionale
- Task 2 può essere eseguito in parallelo con Task 3

### Variabili da adattare (Task 5 e 8)
- Task 5: il nome `LLC._activeSession` va verificato nel codice reale — potrebbe chiamarsi diversamente
- Task 8: i nomi `uploadedBlobName`, `originalFilename`, `fileSize`, `mimeType` vanno adattati al contesto della funzione di upload trovata

### Nessun placeholder
Ogni step ha il codice completo. Tasks marcati "adatta" hanno istruzioni esplicite su cosa adattare.
