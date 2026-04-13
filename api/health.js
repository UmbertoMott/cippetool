// Vercel serverless: health check per Legal Research Lab
export default function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.status(200).json({ status: 'ok', ts: Date.now() });
}
