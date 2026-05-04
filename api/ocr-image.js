// Vercel Serverless Function — OCR immagini tramite Gemini Vision
// Accetta POST { image_b64, mime_type, lang_hint } e restituisce { text, confidence }

export const config = {
  api: { bodyParser: { sizeLimit: '10mb' } },
  maxDuration: 60,
};

// Solo versioni stabili esplicite — no alias, no preview (hanno quota limitata)
const OCR_MODELS = [
  'gemini-2.5-flash',
  'gemini-2.0-flash-001',
  'gemini-2.5-flash-lite',
  'gemini-2.0-flash-lite-001',
];

const MODEL_TIMEOUT_MS = 20000; // 20s per model, then try next

function fetchWithTimeout(url, options, ms) {
  const ctrl = new AbortController();
  const tid = setTimeout(() => ctrl.abort(), ms);
  return fetch(url, { ...options, signal: ctrl.signal })
    .finally(() => clearTimeout(tid));
}

export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  if (req.method === 'OPTIONS') return res.status(200).end();
  if (req.method !== 'POST') return res.status(405).json({ error: 'Method not allowed' });

  const GEMINI_API_KEY = process.env.GEMINI_API_KEY;
  if (!GEMINI_API_KEY) return res.status(503).json({ error: 'GEMINI_API_KEY non configurata' });

  const { image_b64, mime_type = 'image/jpeg' } = req.body || {};
  if (!image_b64) return res.status(400).json({ error: 'image_b64 mancante' });

  const body = {
    contents: [{
      role: 'user',
      parts: [
        { inlineData: { mimeType: mime_type, data: image_b64 } },
        { text: 'Estrai il testo di questo documento in formato Markdown, preservando la struttura visiva:\n- Usa # per titoli principali (font grande, intestazione di sezione, testo centrato o in maiuscolo enfatico)\n- Usa ## per sottotitoli o intestazioni secondarie\n- Usa ### per intestazioni di terzo livello\n- Usa **testo** per parole in grassetto o comunque enfatizzate visivamente\n- Testo normale per il corpo del documento\n- Preserva a capo e separazione tra paragrafi\nRestituisci solo il Markdown, senza spiegazioni o commenti aggiuntivi.' }
      ]
    }],
    generationConfig: { temperature: 0.1, maxOutputTokens: 32768 },
  };

  let lastErr = '';
  for (const model of OCR_MODELS) {
    try {
      const url = `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent?key=${GEMINI_API_KEY}`;
      const r = await fetchWithTimeout(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      }, MODEL_TIMEOUT_MS);

      if (!r.ok) {
        const err = await r.json().catch(() => ({}));
        lastErr = err?.error?.message || r.statusText;
        // Try next model on deprecation / not found / overloaded
        if (r.status === 404 || r.status === 429 || r.status === 503 ||
            (lastErr && /no longer|not found|deprecated|overload|unavailable|quota/i.test(lastErr))) continue;
        return res.status(500).json({ error: lastErr, model });
      }

      const data = await r.json();
      const text = (data.candidates?.[0]?.content?.parts || []).map(p => p.text || '').join('').trim();
      return res.status(200).json({ text, confidence: 0.95, model });

    } catch (e) {
      lastErr = e.name === 'AbortError' ? `Timeout modello ${model} (>${MODEL_TIMEOUT_MS}ms)` : e.message;
      // AbortError = timeout → try next model
    }
  }

  return res.status(500).json({ error: lastErr || 'Tutti i modelli Gemini Vision non disponibili' });
}
