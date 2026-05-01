// Vercel Serverless Function — TTS proxy
// Provider unico: Google Cloud TTS Chirp3-HD (GOOGLE_TTS_API_KEY)

// Wraps text in SSML with <mark> before each word for timepoint sync
function buildSSML(text) {
  const words = text.trim().split(/\s+/);
  return '<speak>' + words.map((w, i) => `<mark name="w${i}"/>${w}`).join(' ') + '</speak>';
}

const GOOGLE_VOICES_CHIRP = {
  'it': { languageCode: 'it-IT', name: 'it-IT-Chirp3-HD-Aoede' },
  'en': { languageCode: 'en-US', name: 'en-US-Chirp3-HD-Aoede' },
};

export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  if (req.method === 'OPTIONS') return res.status(200).end();
  if (req.method !== 'POST') return res.status(405).json({ error: 'Method not allowed' });

  const { text, lang = 'it', speed = 1.0 } = req.body || {};
  if (!text || typeof text !== 'string') return res.status(400).json({ error: 'text required' });

  const GOOGLE_KEY = process.env.GOOGLE_TTS_API_KEY;
  if (!GOOGLE_KEY) return res.status(503).json({ error: 'GOOGLE_TTS_API_KEY not configured' });

  const voiceCfg = GOOGLE_VOICES_CHIRP[lang] || GOOGLE_VOICES_CHIRP['it'];
  const ssml = buildSSML(text.substring(0, 5000));

  try {
    const gRes = await fetch('https://texttospeech.googleapis.com/v1/text:synthesize', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'x-goog-api-key': GOOGLE_KEY },
      body: JSON.stringify({
        input: { ssml },
        voice: voiceCfg,
        audioConfig: { audioEncoding: 'MP3', speakingRate: Math.min(Math.max(speed, 0.25), 4.0) },
        timepointTypes: ['SSML_MARK'],
      }),
    });

    if (!gRes.ok) {
      const err = await gRes.json().catch(() => ({}));
      console.error('Google Cloud TTS error', gRes.status, err?.error?.code);
      return res.status(502).json({ error: 'Google TTS error', code: gRes.status });
    }

    const data = await gRes.json();
    if (!data.audioContent) return res.status(502).json({ error: 'No audio from Google TTS' });

    if (data.timepoints && data.timepoints.length > 0) {
      res.setHeader('Content-Type', 'application/json');
      res.setHeader('Cache-Control', 'no-store');
      return res.status(200).json({
        audio: data.audioContent,
        mimeType: 'audio/mpeg',
        timepoints: data.timepoints,
      });
    }

    const buf = Buffer.from(data.audioContent, 'base64');
    res.setHeader('Content-Type', 'audio/mpeg');
    res.setHeader('Cache-Control', 'no-store');
    return res.status(200).send(buf);

  } catch (e) {
    console.error('Google Cloud TTS exception:', e.message);
    return res.status(500).json({ error: e.message });
  }
}
