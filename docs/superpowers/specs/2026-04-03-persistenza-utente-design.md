# Design Spec: Persistenza Dati Utente — Approccio Ibrido

**Data:** 2026-04-03
**Stato:** Approvato
**URL produzione:** https://privacyaitool.vercel.app

---

## Problema

I dati della zona utente (chat, flashcard, progressi quiz, file caricati) non persistono tra sessioni e dispositivi perché:

1. Tutto è salvato in `localStorage` — per-browser, per-device
2. Il DB `uploads.db` è SQLite su filesystem effimero di Render — si azzera ad ogni deploy
3. Non esiste una tabella per le chat complete su Supabase

---

## Approccio scelto: Ibrido (Frontend → Supabase per dati utente, Render per AI)

### Responsabilità per sistema

| Sistema | Responsabilità |
|---------|---------------|
| **Supabase** | Auth, dati utente, persistenza cross-device, RLS |
| **Render backend** | Solo AI: Gemini, OCR, embedding — nessuna modifica |
| **GCS** | Storage file fisici — invariato |
| **localStorage** | Solo cache UI: tema, preferenze visive non critiche |

---

## Architettura

```
Browser (index.html)
    │
    ├─ Auth gate (login Google obbligatorio)
    │       └─ Supabase OAuth → getSession() all'avvio
    │
    ├─ Dati utente ──────────────────────→ Supabase DB (Postgres)
    │   ├─ chat_sessions
    │   ├─ flashcards
    │   ├─ quiz_progress
    │   └─ file_uploads
    │
    └─ AI Operations ────────────────────→ Render backend
        ├─ /api/gemini
        ├─ /api/documents/embed
        ├─ /api/documents/ocr
        └─ /api/documents/vertex-analyze
                                └─ file bytes → GCS
```

---

## Schema database Supabase (nuove tabelle)

Le tabelle esistenti (`profiles`, `login_sessions`, `query_history`, `document_history`) restano invariate.

### `chat_sessions`
```sql
CREATE TABLE public.chat_sessions (
  id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id     UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
  module      TEXT NOT NULL,          -- 'llc' | 'esb' | 'eap'
  title       TEXT,                   -- primo messaggio troncato a 60 chars
  messages    JSONB NOT NULL DEFAULT '[]',  -- [{role, content, ts}]
  blob_name   TEXT,                   -- documento GCS collegato (opzionale)
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### `flashcards`
```sql
CREATE TABLE public.flashcards (
  id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id     UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
  front       TEXT NOT NULL,
  back        TEXT NOT NULL,
  domain      TEXT,                   -- area GDPR es. "Art. 5", "DPIA"
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### `quiz_progress`
```sql
CREATE TABLE public.quiz_progress (
  user_id       UUID PRIMARY KEY REFERENCES public.profiles(id) ON DELETE CASCADE,
  answers       JSONB NOT NULL DEFAULT '{}',  -- { question_id: {correct, ts} }
  score_total   INTEGER NOT NULL DEFAULT 0,
  score_correct INTEGER NOT NULL DEFAULT 0,
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### `file_uploads`
```sql
CREATE TABLE public.file_uploads (
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
```

### RLS (tutte le nuove tabelle)
```sql
ALTER TABLE public.chat_sessions  ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.flashcards     ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.quiz_progress  ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.file_uploads   ENABLE ROW LEVEL SECURITY;

CREATE POLICY "own" ON public.chat_sessions  FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "own" ON public.flashcards     FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "own" ON public.quiz_progress  FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "own" ON public.file_uploads   FOR ALL USING (auth.uid() = user_id);
```

---

## Logica frontend

### Auth gate (login obbligatorio)
- All'avvio: `getSession()` → se nessuna sessione attiva, mostra schermata login
- Nessun accesso anonimo
- Dopo login: `loadUserData()` carica tutto in parallelo

```js
const [chats, flashcards, quizProgress, files] = await Promise.all([
  _supa.from('chat_sessions').select('*').order('updated_at', { ascending: false }),
  _supa.from('flashcards').select('*'),
  _supa.from('quiz_progress').select('*').single(),
  _supa.from('file_uploads').select('*').order('uploaded_at', { ascending: false })
])
```

### Migrazione localStorage al primo login
1. Rileva dati `cippe_*` esistenti nel localStorage
2. Dialog utente: "Vuoi importare i tuoi dati locali sul tuo account?"
3. Se sì → migra su Supabase → svuota localStorage
4. Se no → svuota localStorage senza migrare

### Timing di salvataggio

| Dato | Trigger salvataggio |
|------|-------------------|
| Chat message | Immediatamente dopo ogni risposta AI |
| Nuovo chat thread | Al primo messaggio |
| Nuova flashcard | Al momento della creazione |
| Risposta quiz | Immediatamente dopo ogni risposta (upsert) |
| File caricato | Dopo conferma upload su GCS |

### Sync cross-device (Supabase Realtime)
```js
_supa.channel('chat_sessions')
  .on('postgres_changes', { event: 'UPDATE', schema: 'public', table: 'chat_sessions' },
    payload => { /* aggiorna UI */ })
  .subscribe()
```

---

## Gestione errori

- Ogni scrittura Supabase in try/catch silenzioso
- Fallback offline: dati restano in memoria per la sessione corrente
- Indicatore visivo discreto se salvataggio fallisce
- Strategia conflitti cross-device: **last-write-wins** (sufficiente per uso studio personale)
- Logout: sessione terminata, memoria svuotata, niente su localStorage

---

## Piano di rollout

| Step | Cosa | Impatto utenti |
|------|------|---------------|
| 1 | Schema Supabase (4 nuove tabelle) | Nessuno |
| 2 | Auth gate obbligatorio | Blocca accesso anonimo |
| 3 | Sync chat (LLC + ESB) | Nuove chat persistono |
| 4 | Sync flashcard + quiz | Dati studio persistono |
| 5 | File uploads su Supabase | Elimina SQLite su Render |
| 6 | Pulizia localStorage | Rimuove dipendenza da localStorage per dati utente |

---

## Modifiche per sistema

| File/Sistema | Cambia? | Dettaglio |
|---|---|---|
| `public/index.html` | ✅ Sì | Auth gate, sync Supabase, migrazione localStorage |
| `supabase/schema.sql` | ✅ Sì | 4 nuove tabelle + RLS |
| `backend/main.py` | ❌ No | Invariato |
| `backend/database.py` | ❌ No | SQLite ignorato (non rimosso per sicurezza) |
| `render.yaml` | ❌ No | Invariato |
| `vercel.json` | ❌ No | Invariato |

---

## Fix sicurezza inclusi (da fare in parallelo)

- **CSP `connect-src`**: aggiunto `https://cipp-legal-api.onrender.com` ✅ (già fatto)
- **Supabase anon key**: spostare da hardcoded HTML a Vercel Environment Variable
- **`unsafe-inline` CSP**: richiede refactoring JS separato (fuori scope di questo sprint)
