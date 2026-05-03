// Vercel Serverless Function — Google Cloud Speech-to-Text proxy
// Stessa GOOGLE_TTS_API_KEY di api/tts.js (abilita "Cloud Speech-to-Text API" in GCP)

export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  if (req.method === 'OPTIONS') return res.status(200).end();
  if (req.method !== 'POST') return res.status(405).json({ error: 'Method not allowed' });

  const { audio, encoding = 'WEBM_OPUS', lang = 'it' } = req.body || {};
  if (!audio || typeof audio !== 'string') return res.status(400).json({ error: 'audio required' });

  const KEY = process.env.GOOGLE_TTS_API_KEY;
  if (!KEY) return res.status(503).json({ error: 'GOOGLE_TTS_API_KEY not configured' });

  const langCode = lang === 'en' ? 'en-US' : 'it-IT';
  const altLang  = lang === 'en' ? 'it-IT' : 'en-US';

  // WEBM_OPUS and OGG_OPUS don't need sampleRateHertz (embedded in container)
  const config = {
    encoding,
    languageCode: langCode,
    alternativeLanguageCodes: [altLang],
    enableAutomaticPunctuation: true,
    model: 'latest_short',
  };

  try {
    const gRes = await fetch('https://speech.googleapis.com/v1/speech:recognize', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'x-goog-api-key': KEY },
      body: JSON.stringify({ config, audio: { content: audio } }),
    });

    const data = await gRes.json();
    if (!gRes.ok) {
      const detail = data?.error?.message || 'unknown';
      console.error('Google STT error', gRes.status, detail);
      return res.status(502).json({ error: 'Google STT error', detail });
    }

    const transcript = (data.results || [])
      .flatMap(r => r.alternatives || [])
      .map(a => a.transcript)
      .join(' ')
      .trim();

    return res.status(200).json({ transcript });

  } catch (e) {
    console.error('Google STT exception:', e.message);
    return res.status(500).json({ error: e.message });
  }
}
