// Vercel Serverless Function — proxy Gemini API
// GEMINI_API_KEY must be set in Vercel project environment variables

// Solo versioni stabili esplicite — no alias, no preview
const MODELS = [
  'gemini-2.5-flash',
  'gemini-2.0-flash-001',
  'gemini-2.5-flash-lite',
  'gemini-2.0-flash-lite-001',
  'gemini-2.5-pro',
];

export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  if (req.method === 'OPTIONS') return res.status(200).end();
  if (req.method !== 'POST') return res.status(405).json({ error: 'Method not allowed' });

  const GEMINI_API_KEY = process.env.GEMINI_API_KEY;
  if (!GEMINI_API_KEY) return res.status(503).json({ error: 'GEMINI_API_KEY not configured in Vercel environment' });

  const body = req.body || {};
  const requestedModel = body.model || MODELS[0];
  const modelsToTry = [requestedModel, ...MODELS.filter(m => m !== requestedModel)];

  const geminiBody = {
    contents: body.contents,
    generationConfig: body.generationConfig || { temperature: 0.4, maxOutputTokens: 2048 },
  };
  if (body.system_instruction) geminiBody.system_instruction = body.system_instruction;
  if (body.tools) geminiBody.tools = body.tools;

  let lastErr = '';
  for (const model of modelsToTry) {
    try {
      const url = `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent?key=${GEMINI_API_KEY}`;
      const geminiResp = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(geminiBody),
      });

      if (!geminiResp.ok) {
        const errData = await geminiResp.json().catch(() => ({}));
        lastErr = errData?.error?.message || geminiResp.statusText;
        const s = geminiResp.status;
        // Retry on: not found, quota, overload, server error, deprecation
        if (s === 404 || s === 429 || s === 500 || s === 503 ||
            /not found|deprecated|quota|overload|unavailable/i.test(lastErr)) continue;
        return res.status(500).json({ error: lastErr });
      }

      const data = await geminiResp.json();
      const text = (data.candidates?.[0]?.content?.parts || []).map(p => p.text || '').join('');
      return res.status(200).json({ text });

    } catch (e) {
      lastErr = e.message;
    }
  }

  return res.status(503).json({ error: lastErr || 'Tutti i modelli Gemini non disponibili' });
}
