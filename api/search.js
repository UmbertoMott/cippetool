// Vercel Serverless Function — Semantic search via Gemini embeddings + cosine similarity
// POST body: {query: "...", chunks: [{id:"c1", text:"...", page:1, docId:"d1"}, ...]}
// Returns: {results: [{chunkId, score, text, page, docId}]} — top 5

const EMBEDDING_MODEL = 'text-embedding-004';

export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  if (req.method === 'OPTIONS') return res.status(200).end();
  if (req.method !== 'POST') return res.status(405).json({ error: 'Method not allowed' });

  const GEMINI_API_KEY = process.env.GEMINI_API_KEY;
  if (!GEMINI_API_KEY) return res.status(503).json({ error: 'GEMINI_API_KEY not configured' });

  const body = req.body || {};
  const query = (body.query || '').trim();
  const chunks = Array.isArray(body.chunks) ? body.chunks : [];

  if (!query) return res.status(400).json({ error: 'query is required' });
  if (!chunks.length) return res.json({ results: [] });

  try {
    // Embed query + all chunks in parallel
    const texts = [query, ...chunks.map(c => c.text || '')];
    const embeddings = await Promise.all(texts.map(t => embedText(t, GEMINI_API_KEY)));

    const queryVec = embeddings[0];
    const chunkVecs = embeddings.slice(1);

    // Cosine similarity
    const scored = chunks.map((chunk, i) => ({
      chunkId: chunk.id,
      score: cosine(queryVec, chunkVecs[i]),
      text: chunk.text || '',
      page: chunk.page || 1,
      docId: chunk.docId || '',
    }));

    scored.sort((a, b) => b.score - a.score);
    const top5 = scored.slice(0, 5);

    return res.status(200).json({ results: top5 });
  } catch (e) {
    console.error('search.js error:', e);
    return res.status(500).json({ error: e.message || 'Embedding failed' });
  }
}

async function embedText(text, apiKey) {
  const url = `https://generativelanguage.googleapis.com/v1beta/models/${EMBEDDING_MODEL}:embedContent?key=${apiKey}`;
  const resp = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      model: `models/${EMBEDDING_MODEL}`,
      content: { parts: [{ text: text.substring(0, 2048) }] },
    }),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(err?.error?.message || `Embedding HTTP ${resp.status}`);
  }
  const data = await resp.json();
  return data.embedding?.values || [];
}

function cosine(a, b) {
  if (!a.length || !b.length || a.length !== b.length) return 0;
  let dot = 0, na = 0, nb = 0;
  for (let i = 0; i < a.length; i++) {
    dot += a[i] * b[i];
    na += a[i] * a[i];
    nb += b[i] * b[i];
  }
  const denom = Math.sqrt(na) * Math.sqrt(nb);
  return denom === 0 ? 0 : dot / denom;
}
