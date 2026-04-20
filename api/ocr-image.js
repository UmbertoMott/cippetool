// Vercel Serverless Function — OCR immagini tramite Gemini Vision
// Accetta POST { image_b64, mime_type, lang_hint } e restituisce { text, confidence }

export const config = {
  api: { bodyParser: { sizeLimit: '10mb' } },
};

const OCR_MODELS = [
  'gemini-flash-latest',   // alias stabile → sempre il miglior flash disponibile
  'gemini-2.5-flash',
  'gemini-2.5-flash-lite',
  'gemini-2.0-flash-001',  // versione pinned stabile
];

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
        { text: 'Estrai tutto il testo presente in questa immagine di documento esattamente come appare. Preserva gli a capo e la struttura originale. Restituisci solo il testo estratto, senza commenti o spiegazioni aggiuntive.' }
      ]
    }],
    generationConfig: { temperature: 0.1, maxOutputTokens: 8192 },
  };

  let lastErr = '';
  for (const model of OCR_MODELS) {
    try {
      const url = `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent?key=${GEMINI_API_KEY}`;
      const r = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });

      if (!r.ok) {
        const err = await r.json().catch(() => ({}));
        lastErr = err?.error?.message || r.statusText;
        // Try next model if this one is unavailable/deprecated
        if (r.status === 404 || r.status === 400 || (lastErr && (lastErr.includes('no longer') || lastErr.includes('not found') || lastErr.includes('deprecated')))) continue;
        return res.status(500).json({ error: lastErr, model });
      }

      const data = await r.json();
      const text = (data.candidates?.[0]?.content?.parts || []).map(p => p.text || '').join('').trim();
      return res.status(200).json({ text, confidence: 0.95, model });

    } catch (e) {
      lastErr = e.message;
    }
  }

  return res.status(500).json({ error: lastErr || 'Tutti i modelli Gemini Vision non disponibili' });
}
