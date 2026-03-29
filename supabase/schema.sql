-- ============================================================
-- Privacy & AI Tool — Supabase Schema
-- Esegui questo SQL nel SQL Editor di Supabase
-- ============================================================

-- ── Estensioni ──────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ── Profili utente ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.profiles (
  id            UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  email         TEXT,
  full_name     TEXT,
  avatar_url    TEXT,
  plan          TEXT NOT NULL DEFAULT 'free',   -- free | pro | enterprise
  query_count   INTEGER NOT NULL DEFAULT 0,
  doc_count     INTEGER NOT NULL DEFAULT 0,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  last_seen_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Sessioni di login ────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.login_sessions (
  id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id     UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
  login_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  user_agent  TEXT,
  ip_address  TEXT
);

-- ── Storico query AI ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.query_history (
  id             UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id        UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
  query_text     TEXT NOT NULL,
  document_name  TEXT,
  document_type  TEXT,           -- pdf | docx | gcs
  answer_summary TEXT,           -- primi 500 chars della risposta
  points_count   INTEGER DEFAULT 0,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Documenti caricati/aperti ────────────────────────────────
CREATE TABLE IF NOT EXISTS public.document_history (
  id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id       UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
  filename      TEXT NOT NULL,
  file_type     TEXT,            -- pdf | docx | gcs
  file_size_kb  INTEGER,
  source        TEXT,            -- local_upload | gcs | url
  opened_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Row Level Security ───────────────────────────────────────
ALTER TABLE public.profiles         ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.login_sessions   ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.query_history    ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.document_history ENABLE ROW LEVEL SECURITY;

-- Ogni utente vede solo i propri dati
CREATE POLICY "own_profile"   ON public.profiles         FOR ALL USING (auth.uid() = id);
CREATE POLICY "own_sessions"  ON public.login_sessions   FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "own_queries"   ON public.query_history    FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "own_docs"      ON public.document_history FOR ALL USING (auth.uid() = user_id);

-- ── Trigger: crea profilo automaticamente dopo signup ────────
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER LANGUAGE plpgsql SECURITY DEFINER AS $$
BEGIN
  INSERT INTO public.profiles (id, email, full_name, avatar_url)
  VALUES (
    NEW.id,
    NEW.email,
    COALESCE(NEW.raw_user_meta_data->>'full_name', NEW.raw_user_meta_data->>'name'),
    NEW.raw_user_meta_data->>'avatar_url'
  )
  ON CONFLICT (id) DO NOTHING;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- ── Trigger: aggiorna last_seen_at e query_count ─────────────
CREATE OR REPLACE FUNCTION public.increment_query_count()
RETURNS TRIGGER LANGUAGE plpgsql SECURITY DEFINER AS $$
BEGIN
  UPDATE public.profiles
  SET query_count  = query_count + 1,
      last_seen_at = NOW()
  WHERE id = NEW.user_id;
  RETURN NEW;
END;
$$;

CREATE TRIGGER on_query_insert
  AFTER INSERT ON public.query_history
  FOR EACH ROW EXECUTE FUNCTION public.increment_query_count();

-- Trigger: aggiorna doc_count
CREATE OR REPLACE FUNCTION public.increment_doc_count()
RETURNS TRIGGER LANGUAGE plpgsql SECURITY DEFINER AS $$
BEGIN
  UPDATE public.profiles
  SET doc_count    = doc_count + 1,
      last_seen_at = NOW()
  WHERE id = NEW.user_id;
  RETURN NEW;
END;
$$;

CREATE TRIGGER on_doc_insert
  AFTER INSERT ON public.document_history
  FOR EACH ROW EXECUTE FUNCTION public.increment_doc_count();
