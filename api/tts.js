// Vercel Serverless Function — TTS proxy
// Priority 1: Gemini TTS (GEMINI_API_KEY — già configurata)
// Priority 2: Google Cloud TTS Chirp 3 HD (GOOGLE_TTS_API_KEY — richiede service account)
// Priority 3: OpenAI TTS (OPENAI_API_KEY — fallback)

// Wrap raw L16 PCM in a WAV container so browsers can decode it
function pcmToWav(pcmBuf, sampleRate = 24000, channels = 1, bitsPerSample = 16) {
  const dataSize = pcmBuf.length;
  const wav = Buffer.alloc(44 + dataSize);
  // RIFF header
  wav.write('RIFF', 0);
  wav.writeUInt32LE(36 + dataSize, 4);
  wav.write('WAVE', 8);
  // fmt chunk
  wav.write('fmt ', 12);
  wav.writeUInt32LE(16, 16);           // chunk size
  wav.writeUInt16LE(1, 20);            // PCM format
  wav.writeUInt16LE(channels, 22);
  wav.writeUInt32LE(sampleRate, 24);
  wav.writeUInt32LE(sampleRate * channels * bitsPerSample / 8, 28); // byte rate
  wav.writeUInt16LE(channels * bitsPerSample / 8, 32);              // block align
  wav.writeUInt16LE(bitsPerSample, 34);
  // data chunk
  wav.write('data', 36);
  wav.writeUInt32LE(dataSize, 40);
  pcmBuf.copy(wav, 44);
  return wav;
}

const GEMINI_TTS_MODEL = 'gemini-2.5-flash-preview-tts';
const GEMINI_BASE = 'https://generativelanguage.googleapis.com/v1beta';

const GOOGLE_VOICES_CHIRP = {
  'it': { languageCode: 'it-IT', name: 'it-IT-Chirp3-HD-Orus' },
  'en': { languageCode: 'en-US', name: 'en-US-Chirp3-HD-Orus' },
};

// Gemini prebuilt voice — Charon: informative, clearly male, good for legal content
const GEMINI_VOICE = 'Charon';

export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  if (req.method === 'OPTIONS') return res.status(200).end();
  if (req.method !== 'POST') return res.status(405).json({ error: 'Method not allowed' });

  const { text, lang = 'it', speed = 1.0 } = req.body || {};
  if (!text || typeof text !== 'string') return res.status(400).json({ error: 'text required' });

  const GEMINI_KEY  = process.env.GEMINI_API_KEY;
  const GOOGLE_KEY  = process.env.GOOGLE_TTS_API_KEY;
  const OPENAI_KEY  = process.env.OPENAI_API_KEY;

  // ── 1. Gemini TTS (primary — uses existing GEMINI_API_KEY) ────────────
  if (GEMINI_KEY) {
    try {
      const url = `${GEMINI_BASE}/models/${GEMINI_TTS_MODEL}:generateContent?key=${GEMINI_KEY}`;
      const gRes = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          contents: [{ role: 'user', parts: [{ text }] }],
          generationConfig: {
            responseModalities: ['AUDIO'],
            speechConfig: {
              voiceConfig: {
                prebuiltVoiceConfig: { voiceName: GEMINI_VOICE },
              },
            },
          },
        }),
      });

      if (gRes.ok) {
        const data = await gRes.json();
        const inline = data?.candidates?.[0]?.content?.parts?.[0]?.inlineData;
        if (inline?.data) {
          let buf = Buffer.from(inline.data, 'base64');
          let mime = inline.mimeType || 'audio/wav';
          console.log('Gemini TTS ok — mime:', mime, 'bytes:', buf.length);
          // Gemini returns raw L16 PCM — wrap in WAV so browsers can decode it
          if (mime.includes('L16') || mime.includes('pcm') || mime.includes('raw')) {
            const rateMatch = mime.match(/rate=(\d+)/);
            const sampleRate = rateMatch ? parseInt(rateMatch[1]) : 24000;
            buf = pcmToWav(buf, sampleRate);
            mime = 'audio/wav';
          }
          res.setHeader('Content-Type', mime);
          res.setHeader('Cache-Control', 'no-store');
          return res.status(200).send(buf);
        } else {
          // Log full response so we can see what Gemini returned (no audio data)
          const finishReason = data?.candidates?.[0]?.finishReason;
          const errMsg = data?.error?.message;
          console.error('Gemini TTS: no inlineData. finishReason:', finishReason, 'error:', errMsg, 'keys:', JSON.stringify(Object.keys(data || {})));
        }
      } else {
        const err = await gRes.json().catch(() => ({}));
        console.error('Gemini TTS error', gRes.status, err?.error?.message);
      }
    } catch (e) {
      console.error('Gemini TTS exception:', e.message);
    }
  }

  // ── 2. Google Cloud TTS Chirp 3 HD (needs service account auth) ────────
  if (GOOGLE_KEY) {
    try {
      const voiceCfg = GOOGLE_VOICES_CHIRP[lang] || GOOGLE_VOICES_CHIRP['it'];
      const gRes = await fetch('https://texttospeech.googleapis.com/v1/text:synthesize', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'x-goog-api-key': GOOGLE_KEY },
        body: JSON.stringify({
          input: { text: text.substring(0, 5000) },
          voice: voiceCfg,
          audioConfig: { audioEncoding: 'MP3', speakingRate: Math.min(Math.max(speed, 0.25), 4.0) },
        }),
      });

      if (gRes.ok) {
        const data = await gRes.json();
        if (data.audioContent) {
          const buf = Buffer.from(data.audioContent, 'base64');
          res.setHeader('Content-Type', 'audio/mpeg');
          res.setHeader('Cache-Control', 'no-store');
          return res.status(200).send(buf);
        }
      } else {
        const err = await gRes.json().catch(() => ({}));
        console.error('Google Cloud TTS error', gRes.status, err?.error?.code);
      }
    } catch (e) {
      console.error('Google Cloud TTS exception:', e.message);
    }
  }

  // ── 3. OpenAI TTS (fallback) ───────────────────────────────────────────
  if (!OPENAI_KEY) {
    return res.status(503).json({ error: 'No TTS provider available' });
  }

  try {
    const oRes = await fetch('https://api.openai.com/v1/audio/speech', {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${OPENAI_KEY}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model: 'tts-1',
        input: text.substring(0, 4096),
        voice: 'onyx',
        speed: Math.min(Math.max(speed, 0.25), 4.0),
        response_format: 'mp3',
      }),
    });

    if (!oRes.ok) {
      const err = await oRes.text();
      return res.status(oRes.status).json({ error: err });
    }

    const buf = await oRes.arrayBuffer();
    res.setHeader('Content-Type', 'audio/mpeg');
    res.setHeader('Cache-Control', 'no-store');
    return res.status(200).send(Buffer.from(buf));
  } catch (e) {
    return res.status(500).json({ error: e.message });
  }
}
