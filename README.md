# CIPP/E Legal SaaS Platform

Professional legal research and analysis platform built with **FastAPI** backend + **React** frontend, integrating **Google Cloud Storage**, **Gemini AI**, **PDF.js**, and **Mermaid.js** for advanced legal document analysis.

## 🎯 Overview

The CIPP/E Legal SaaS is a comprehensive platform for:

- **Document Management**: 22 legal PDFs from GCS (GDPR, CJEU cases, EDPB guidelines, AI Act, CIPP/E manual)
- **AI-Powered Analysis**: Gemini-based deep academic analysis with ratio legis, jurisprudence, and normative diagrams
- **Visual Highlighting**: Numbered highlights (①②③) with position mapping
- **Structured Output**: Tables, schemas, and Mermaid.js diagrams
- **CIPP/E Integration**: Cross-reference analysis with CIPP/E exam domains

## 📦 Project Structure

```
cipp_legal_saas/
├── backend/                          # FastAPI backend server
│   ├── main.py                      # API endpoints (7 routes)
│   ├── gcs_client.py                # Google Cloud Storage client
│   ├── serve_combined.py            # Combined proxy server
│   ├── requirements.txt             # Python dependencies
│   ├── .env                         # Environment variables
│   ├── .gitignore                   # Git ignore rules
│   └── credentials/
│       └── service_account.json     # GCS service account (⚠️ ROTATE)
│
├── frontend/                         # React/TypeScript frontend
│   ├── src/
│   │   ├── main.tsx                # React entry point
│   │   ├── App.tsx                 # App wrapper
│   │   ├── LegalResearchLab.tsx    # Main two-column component
│   │   ├── App.css                 # App styles
│   │   ├── index.css               # Global styles
│   │   └── LegalResearchLab.css    # Component styles
│   ├── index.html                  # HTML template
│   ├── package.json                # Node dependencies
│   ├── vite.config.ts              # Vite config with API proxy
│   ├── tsconfig.json               # TypeScript config
│   ├── README.md                   # Frontend setup guide
│   └── .gitignore                  # Git ignore rules
│
└── README.md                        # This file
```

## 🚀 Quick Start

### Backend Setup

```bash
cd backend

# Install Python dependencies
pip install -r requirements.txt

# Set environment variables
export GOOGLE_APPLICATION_CREDENTIALS=credentials/service_account.json
export GCS_BUCKET_NAME=data-protection-archive
export CORS_ORIGINS=http://localhost:5173

# Run FastAPI server
python3 -m uvicorn main:app --host 127.0.0.1 --port 8000
```

Server starts at `http://127.0.0.1:8000` with:
- `/docs` — Swagger UI
- `/api/health` — Health check
- `/api/documents` — Document listing
- 7 additional endpoints for text extraction, highlights, metadata, AI context

### Frontend Setup

```bash
cd frontend

# Install Node dependencies
npm install

# Start development server
npm run dev
```

App opens at `http://localhost:5173` with Vite dev server proxying `/api/*` to backend.

### Combined Server (for Production)

```bash
cd backend
python3 serve_combined.py
```

This starts:
- FastAPI backend on port 8001
- HTTP proxy server on port 7890 (serves HTML + proxies `/api/*`)

## 🔌 API Endpoints

All endpoints require GCS bucket access and return JSON responses.

### Documents

| Endpoint | Method | Purpose | Response |
|----------|--------|---------|----------|
| `/api/documents` | GET | List all PDFs in bucket | `{ count, documents: [...] }` |
| `/api/documents/signed-url` | GET | Generate signed URL | `{ blob_name, signed_url, expires_in_minutes }` |
| `/api/documents/metadata` | GET | Get PDF metadata | `{ title, author, pages, ... }` |
| `/api/documents/pdf-proxy` | GET | Download PDF (same-origin) | Binary PDF content |

### Text Extraction

| Endpoint | Method | Purpose | Response |
|----------|--------|---------|----------|
| `/api/documents/extract-text` | POST | Extract text from pages | `{ full_text, pages: [...], total_pages, total_chars }` |
| `/api/documents/ai-context` | GET | Extract text for AI | `{ metadata, text, pages_extracted, truncated }` |

### Highlights

| Endpoint | Method | Purpose | Response |
|----------|--------|---------|----------|
| `/api/documents/highlights` | POST | Find highlight positions | `{ blob_name, total_matches, highlights: [...] }` |

### Health

| Endpoint | Method | Purpose | Response |
|----------|--------|---------|----------|
| `/api/health` | GET | Connection status | `{ status, gcs_connected, bucket }` |

## 🗄️ GCS Documents

The bucket `data-protection-archive` contains 22 legal PDFs:

**Core Regulations:**
- GDPR (2016/679)
- AI Act (2024/1689)
- eIDAS Regulation
- NIS 2 Directive

**CIPP/E Materials:**
- CIPP/E Manual (3rd ed., IAPP)
- CIPP/E Exam Questions

**Case Law:**
- CJEU (Court of Justice of the European Union) decisions
- EDPB (European Data Protection Board) guidelines
- EFSA (European Food Safety Authority) opinions

**Additional:**
- GDPR Recitals & Annexes
- Standard Contractual Clauses
- Data Processing Agreements

## 🔐 Security Considerations

### ⚠️ Service Account Private Key Rotation

The `credentials/service_account.json` private key has been **exposed** in this repository. **Immediate action required:**

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Navigate to **IAM & Admin** → **Service Accounts**
3. Select your service account
4. **Delete** the exposed key
5. **Create a new key** and update `credentials/service_account.json`
6. Commit the new credentials (they will be ignored by `.gitignore`)

```bash
# Do NOT commit credentials
git add -A
git commit -m "Rotate compromised service account key"
```

### Environment Variables

Store sensitive config in `.env`:

```bash
# .env
GOOGLE_APPLICATION_CREDENTIALS=credentials/service_account.json
GCS_BUCKET_NAME=data-protection-archive
CORS_ORIGINS=http://localhost:5173,https://yourdomain.com
```

**Never commit `.env` to git.**

## 🛠️ Technology Stack

### Backend

| Technology | Version | Purpose |
|-----------|---------|---------|
| Python | 3.9.6 | Runtime |
| FastAPI | Latest | Web framework |
| uvicorn | Latest | ASGI server |
| google-cloud-storage | Latest | GCS SDK |
| google-auth | Latest | Authentication |
| PyMuPDF (fitz) | Latest | PDF text extraction |
| pydantic | Latest | Data validation |
| python-dotenv | Latest | Environment config |

**Install all:**
```bash
pip install -r backend/requirements.txt
```

### Frontend

| Technology | Version | Purpose |
|-----------|---------|---------|
| React | 18.2 | UI framework |
| TypeScript | 5.3 | Type safety |
| Vite | 5.0 | Build tool |
| PDF.js | 3.11 | PDF rendering |
| Mermaid.js | 10.9 | Diagram rendering |
| CSS3 | Latest | Styling |

**Install all:**
```bash
cd frontend && npm install
```

### External Services

| Service | Purpose | Config |
|---------|---------|--------|
| Google Cloud Storage | Document storage | Bucket: `data-protection-archive` |
| Gemini AI | Legal analysis | Backend system prompt |
| PDF.js CDN | PDF rendering | Frontend library |
| Mermaid.js CDN | Diagrams | Frontend library |

## 📊 System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Browser (React)                         │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ LegalResearchLab Component                           │   │
│  │ - Document Library (left panel)                      │   │
│  │ - Document Viewer (right, tab 1)                     │   │
│  │ - AI Analysis Panel (right, tab 2)                   │   │
│  └──────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────┘
                            │
                    /api/* requests
                            │
                            ▼
┌──────────────────────────────────────────────────────────────┐
│                   FastAPI Backend (Python)                    │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ API Routes:                                          │   │
│  │ - GET  /api/documents                               │   │
│  │ - GET  /api/documents/signed-url                    │   │
│  │ - POST /api/documents/extract-text                  │   │
│  │ - POST /api/documents/highlights                    │   │
│  │ - GET  /api/documents/metadata                      │   │
│  │ - GET  /api/documents/ai-context                    │   │
│  │ - GET  /api/documents/pdf-proxy                     │   │
│  └──────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ GCSLegalClient (google-cloud-storage SDK)           │   │
│  │ - list_pdfs()                                       │   │
│  │ - download_pdf_bytes()                              │   │
│  │ - extract_text()                                    │   │
│  │ - extract_text_with_positions()                     │   │
│  │ - get_pdf_metadata()                                │   │
│  │ - generate_signed_url()                             │   │
│  └──────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────┘
                            │
                    GCS API calls
                            │
                            ▼
┌──────────────────────────────────────────────────────────────┐
│         Google Cloud Storage (data-protection-archive)       │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ 22 Legal PDFs:                                       │   │
│  │ - GDPR, AI Act, eIDAS, NIS 2                        │   │
│  │ - CIPP/E Manual, Exam Questions                     │   │
│  │ - CJEU Cases, EDPB Guidelines                       │   │
│  │ - Standard Clauses, Annexes, etc.                   │   │
│  └──────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────┘
```

## 📝 System Prompt (AI Analysis)

The FastAPI backend's system prompt instructs Gemini to provide:

1. **Highlights** — Numbered `[HL:N: text]` tags for key passages
2. **Ratio Legis** — 5-6 lines explaining legislative motivation
3. **Laws** — Table with norm references and 5-6 line explanations
4. **Jurisprudence** — Table with cases and 5-6 line legal principles
5. **Diagram** — `[MERMAID]...[/MERMAID]` blocks for normative relationships
6. **Schema** — `[SCHEMA]...[/SCHEMA]` blocks for visual logic
7. **CIPP/E Relevance** — Cross-reference to exam domains

The frontend parses these blocks and renders:
- Numbered comments (①②③) with badges
- Structured tables
- Mermaid.js diagrams
- Schema boxes

## 🧪 Testing

### Backend Health Check

```bash
curl http://127.0.0.1:8000/api/health
# Response: {"status":"ok","gcs_connected":true,"bucket":"data-protection-archive"}
```

### List Documents

```bash
curl http://127.0.0.1:8000/api/documents?limit=5
# Response: {"count":22,"bucket":"data-protection-archive","documents":[...]}
```

### Extract Text

```bash
curl -X POST http://127.0.0.1:8000/api/documents/extract-text \
  -H "Content-Type: application/json" \
  -d '{"blob_name":"679 2016 gdpr.pdf","page_start":0,"page_end":5}'
```

### Frontend Development

```bash
# Terminal 1: Start backend
cd backend
python3 -m uvicorn main:app --host 127.0.0.1 --port 8000

# Terminal 2: Start frontend
cd frontend
npm run dev

# Open http://localhost:5173 in browser
```

## 🎓 CIPP/E Domains

The platform references the CIPP/E examination domains:

| Domain | Chapters | Topics |
|--------|----------|--------|
| **I** | 1-3 | Introduction to EU Data Protection |
| **II** | 4-8 | EU Data Protection Law & Regulation (GDPR, eIDAS, etc.) |
| **III** | 9-12 | Compliance (Privacy by design, DPA, impact assessments) |
| **IV** | 13-15 | International Data Transfers (SCCs, adequacy, mechanisms) |

Analysis output includes mappings to these domains for exam preparation.

## 📚 Documentation

- **Backend** → `backend/README.md` (FastAPI setup, dependencies, endpoints)
- **Frontend** → `frontend/README.md` (React setup, components, styling)
- **API** → FastAPI auto-docs at `/docs`

## 🔄 Workflow

### For End Users

1. Open app at `http://localhost:5173`
2. Select a document from the library (left panel)
3. Click the **📄 Documento** tab to read the text
4. Switch to **🔍 Analisi** tab
5. Type a legal question (e.g., "Quali sono gli obblighi del titolare?")
6. Click **🚀 Analizza** to get AI-powered response
7. Read structured analysis with:
   - Numbered highlights (①②③)
   - Tables with legal references
   - Mermaid.js diagrams
   - CIPP/E cross-reference

### For Developers

1. Start backend: `cd backend && python3 -m uvicorn main:app --host 127.0.0.1 --port 8000`
2. Start frontend: `cd frontend && npm run dev`
3. Edit component files in `frontend/src/`
4. Backend auto-reloads; frontend hot-reloads

## 🚀 Deployment

### Production Build

```bash
# Build frontend
cd frontend
npm run build
# Creates dist/ folder with optimized bundle

# Build backend
cd backend
pip install -r requirements.txt
```

### Server Configuration

Use a production ASGI server (e.g., **Gunicorn** + **Uvicorn**):

```bash
pip install gunicorn

gunicorn main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --access-logfile - \
  --error-logfile -
```

Serve frontend `dist/` with **Nginx**:

```nginx
server {
  listen 80;
  server_name yourdomain.com;

  # Frontend
  location / {
    root /path/to/cipp_legal_saas/frontend/dist;
    try_files $uri /index.html;
  }

  # Backend proxy
  location /api/ {
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
  }
}
```

## 🤝 Contributing

For changes:

1. Create a feature branch: `git checkout -b feature/my-feature`
2. Make changes
3. Test locally
4. Commit: `git commit -m "Add feature description"`
5. Push: `git push origin feature/my-feature`
6. Open a pull request

## 📄 License

Proprietary — CIPP/E Legal SaaS Platform

## 🆘 Support

For issues or questions:
- Check FastAPI docs at `/docs`
- Review frontend `README.md`
- Check backend logs: `python3 -m uvicorn main:app --log-level debug`
- Check browser console for frontend errors

---

**Last Updated**: March 11, 2026
**Status**: ✅ Fully Functional (Backend + Frontend integrated with GCS)
