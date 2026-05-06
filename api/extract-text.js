// Serverless text extraction — DOCX via mammoth (Node.js)
// POST /api/extract-text
// Body: { fileBase64: "<base64>", fileName: "doc.docx" }
// Response: { text: "..." }

const mammoth = require('mammoth');

module.exports = async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  if (req.method === 'OPTIONS') { res.status(200).end(); return; }
  if (req.method !== 'POST') { res.status(405).json({ error: 'Method not allowed' }); return; }

  try {
    const { fileBase64, fileName } = req.body;
    if (!fileBase64 || !fileName) {
      return res.status(400).json({ error: 'fileBase64 and fileName required' });
    }

    const name = (fileName || '').toLowerCase();
    const buf = Buffer.from(fileBase64, 'base64');

    if (name.endsWith('.docx') || name.endsWith('.doc')) {
      const result = await mammoth.extractRawText({ buffer: buf });
      return res.status(200).json({ text: result.value || '' });
    }

    return res.status(200).json({ text: '' });
  } catch (err) {
    console.error('[extract-text] error:', err);
    return res.status(500).json({ error: err.message, text: '' });
  }
};
