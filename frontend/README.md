# CIPP/E Legal SaaS — React Frontend

Professional two-column Legal Research Lab interface for CIPP/E training and document analysis.

## Overview

This React TypeScript application provides:

- **Left Column**: Document library with GCS integration (22 legal PDFs)
- **Right Column**:
  - 📄 Document viewer with text extraction
  - 🔍 AI-powered legal analysis with Gemini
  - ①②③ Numbered highlights system
  - Structured analysis with tables, schemas, and diagrams

## Technology Stack

- **React 18** — UI framework
- **TypeScript** — Type safety
- **Vite** — Build tool & dev server
- **FastAPI Backend** — `/api/*` endpoints for PDF management & AI
- **Tailwind CSS** (optional) — Styling framework

## Setup

### Prerequisites

```bash
# Node.js 18+ and npm/yarn
node --version  # v18.0.0 or higher
npm --version   # 9.0.0 or higher
```

### Installation

```bash
cd /Users/umbertomottola/Downloads/cipp_legal_saas/frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

The app will open at `http://localhost:5173` with Vite's dev server.

### Backend Integration

The frontend proxies all `/api/*` requests to the FastAPI backend (port 8000):

```typescript
// vite.config.ts
proxy: {
  '/api': {
    target: 'http://127.0.0.1:8000',
    changeOrigin: true
  }
}
```

Ensure the FastAPI backend is running:

```bash
cd /Users/umbertomottola/Downloads/cipp_legal_saas/backend
python3 -m uvicorn main:app --host 127.0.0.1 --port 8000
```

## Project Structure

```
frontend/
├── index.html              # Entry HTML
├── main.tsx               # React entry point
├── App.tsx                # App wrapper
├── LegalResearchLab.tsx   # Main two-column component
├── LegalResearchLab.css   # Component styles
├── App.css                # App wrapper styles
├── index.css              # Global styles
├── package.json           # Dependencies
├── vite.config.ts         # Vite configuration
├── tsconfig.json          # TypeScript config
└── tsconfig.node.json     # Vite TypeScript config
```

## Components

### LegalResearchLab.tsx

Main component with:

- **Document Library** (left panel)
  - Lists all documents from `/api/documents`
  - Click to load document text via `/api/documents/ai-context`
  - Shows document size and GCS badge ☁️

- **Document Viewer** (right, tab 1)
  - Displays extracted text (first 5000 chars)
  - "Evidenzia" button finds highlights via `/api/documents/highlights`

- **Analysis Panel** (right, tab 2)
  - Text input for legal questions
  - "Analizza" button calls backend AI analysis
  - Renders structured output with:
    - Headers (# ## ###)
    - Numbered comments (①②③)
    - Paragraphs with formatting

## API Endpoints Used

All calls are proxied through vite dev server to `http://127.0.0.1:8000`:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/documents` | GET | List all documents |
| `/api/documents/ai-context?blob_name=...` | GET | Get document text + metadata |
| `/api/documents/highlights` | POST | Find highlight positions in document |
| `/api/analyze` | POST | Run Gemini analysis on document + query |

### Optional Backend Endpoints

The FastAPI backend also provides:

- `/api/health` — Connection status
- `/api/documents/signed-url` — Generate signed URL
- `/api/documents/extract-text` — Extract text from range
- `/api/documents/metadata` — Get PDF metadata
- `/api/documents/pdf-proxy` — Proxy PDF bytes (CORS workaround)

## Build & Deploy

```bash
# Development
npm run dev          # Runs Vite dev server on :5173

# Production Build
npm run build        # Generates dist/ folder

# Preview built version locally
npm run preview      # Serves dist/ on :4173

# Type checking
npm run type-check   # Run tsc --noEmit
```

### Production Deployment

For production, build and serve the static `dist/` folder:

```bash
npm run build

# Then serve dist/ with your web server (nginx, Apache, etc.)
# and ensure the same-origin `/api/*` proxy points to FastAPI backend
```

## Styling

The component uses CSS custom properties (CSS variables) for theming:

```css
--primary: #7c3aed      /* Purple accent */
--accent: #f59e0b       /* Amber highlight */
--success: #10b981      /* Green */
--danger: #ef4444       /* Red */
--bg-dark: #0f172a      /* Dark background */
--bg-card: #1e293b      /* Card background */
--txt: #e2e8f0          /* Text color */
--txt-muted: #94a3b8    /* Muted text */
--border: #334155       /* Border color */
```

To customize, edit `LegalResearchLab.css` `:root` section.

### Responsive Design

- **Desktop** (1280px+) — Two-column layout
- **Tablet** (768–1024px) — Reduced left panel width
- **Mobile** (<768px) — Stacked layout with tabs

## Features

### 1. Document Library Integration

```typescript
// Load documents from GCS via FastAPI
const response = await fetch('/api/documents?limit=50');
const data = await response.json();
setDocuments(data.documents);
```

Each document shows:
- Title (display name)
- Size (MB)
- GCS badge ☁️ for cloud documents

### 2. AI-Powered Analysis

```typescript
// Query Gemini with document context
const response = await fetch('/api/analyze', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    document_text: documentText,
    query: analysisQuery,
    blob_name: selectedDoc.name,
  }),
});
```

Backend system prompt (FastAPI) returns:
- 🔍 Ratio Legis e Motivazione
- ⚖️ Leggi di Riferimento (table)
- 📚 Giurisprudenza Rilevante (table)
- 📊 Diagramma Normativo (Mermaid)
- 🗺️ Schema Esplicativo
- 🎓 Rilevanza CIPP/E

### 3. Numbered Highlights

Analysis responses use `[HL:N: text]` syntax:

```
[HL:1: Il GDPR protegge i dati personali di individui]
[HL:2: L'interessato ha diritti di accesso, rettifica e cancellazione]
```

Frontend extracts and renders:

```typescript
① Il GDPR protegge i dati personali di individui
② L'interessato ha diritti di accesso, rettifica e cancellazione
```

### 4. Structured Output Rendering

```typescript
// Render headers, numbered comments, paragraphs
const renderAnalysis = (text: string) => {
  return text.split('\n').map((line, idx) => {
    if (/^[①②③...]/.test(line)) {
      return <div className="lrl-num-comment">{line}</div>;
    }
    if (line.startsWith('##')) {
      return <h2>{line.replace(/^#+\s*/, '')}</h2>;
    }
    return <p>{line}</p>;
  });
};
```

## TypeScript Types

```typescript
interface PDFDocument {
  name: string;
  display_name: string;
  size_bytes: number;
  size_mb: number;
  updated: string;
  content_type: string;
  metadata?: Record<string, unknown>;
  isGCS?: boolean;
  gcs_blob?: string;
}

interface Highlight {
  num: number;
  text: string;
}
```

## Environment Variables

Create a `.env.local` file for environment-specific config:

```bash
# Backend API base (if not using same-origin proxy)
VITE_API_BASE=http://127.0.0.1:8000

# Max tokens for AI analysis
VITE_MAX_TOKENS=4000
```

In component:

```typescript
const apiBase = import.meta.env.VITE_API_BASE || '';
```

## Troubleshooting

### CORS Errors on `/api/*` calls

**Issue**: `Failed to fetch from http://127.0.0.1:8000/api/...`

**Solution**: Ensure Vite dev server proxy is configured:

```typescript
// vite.config.ts
proxy: {
  '/api': {
    target: 'http://127.0.0.1:8000',
    changeOrigin: true
  }
}
```

### Backend not responding

```bash
# Check FastAPI is running
lsof -i :8000

# Restart backend
cd ../backend
python3 -m uvicorn main:app --host 127.0.0.1 --port 8000
```

### Vite dev server not starting

```bash
# Clear node_modules and reinstall
rm -rf node_modules
npm install

# Restart dev server
npm run dev
```

## Performance Optimization

- **Code splitting**: Vite automatically splits bundles
- **Lazy loading**: Load documents on demand
- **Text truncation**: Only show first 5000 chars (configurable)
- **CSS-in-JS avoided**: Pure CSS for faster rendering

## Future Enhancements

- [ ] PDF.js viewer in document panel (client-side rendering)
- [ ] Real-time highlight sync between viewer and analysis
- [ ] Document export (PDF with annotations)
- [ ] Multi-document comparative analysis
- [ ] Custom system prompt editor
- [ ] Analysis history & saved queries
- [ ] Dark/light theme toggle
- [ ] Keyboard shortcuts
- [ ] Search within document library

## License

Proprietary — CIPP/E Legal SaaS Platform

## Support

For issues or questions, contact the development team.
