"""
Document AI OCR Service — CIPP/E Legal SaaS
Usa Google Cloud Document AI per OCR di PDF scansionati/immagini.

Produce lo stesso formato di blocchi di embedding_service.extract_blocks_from_pdf,
permettendo feed diretto nella pipeline di embedding esistente senza modifiche.

Processore configurato:
  project_id   : 135860130899
  location     : eu
  processor_id : 84052fa43f976f74
"""

import logging
import os
import re
from typing import List, Optional

logger = logging.getLogger("cipp-legal-api")

# ── Document AI config (dal tuo processore OCR) ────────────────────────────────
DOCAI_PROJECT   = os.getenv("DOCAI_PROJECT_ID",   "135860130899")
DOCAI_LOCATION  = os.getenv("DOCAI_LOCATION",     "eu")
DOCAI_PROCESSOR = os.getenv("DOCAI_PROCESSOR_ID", "84052fa43f976f74")

# ── Soglie chunking (identiche a embedding_service) ────────────────────────────
MIN_PARA_CHARS  = 60    # scarta paragrafi troppo corti
MAX_PARA_CHARS  = 900   # spezza paragrafi lunghi
PARA_OVERLAP    = 120   # overlap tra sotto-chunk dello stesso paragrafo

# ── Soglia auto-detect scansione ───────────────────────────────────────────────
OCR_THRESHOLD_CHARS_PER_PAGE = 80  # sotto questa media → PDF scansionato

_docai_client = None  # DocumentProcessorServiceClient

# ── Regex riferimenti normativi (identica a embedding_service) ─────────────────
_ART_RE = re.compile(
    r'\b(?:Art(?:t?|icle|icolo)s?\.?\s*\d+(?:\s*\(\d+\)\s*\([a-z]\))?'
    r'|Considerand[oi]\s+\d+'
    r'|Recital\s+\d+'
    r'|§\s*\d+'
    r'|Clause\s+\d+'
    r'|Section\s+\d+(?:\.\d+)*)',
    re.IGNORECASE
)


def _extract_article_ref(text: str) -> Optional[str]:
    """Ritorna il primo riferimento normativo trovato nel testo."""
    m = _ART_RE.search(text)
    return m.group(0).strip()[:120] if m else None


# ── Init ───────────────────────────────────────────────────────────────────────

def init_docai(credentials_path: Optional[str] = None) -> bool:
    """
    Inizializza il client Document AI.
    Ritorna True se ok, False se la libreria non è installata (graceful fallback).
    """
    global _docai_client
    try:
        from google.cloud import documentai  # noqa: F401
    except ImportError:
        logger.warning(
            "[DocAI] google-cloud-documentai non installato — OCR disabilitato. "
            "Esegui: pip install google-cloud-documentai"
        )
        return False

    try:
        from google.cloud import documentai
        from google.api_core.client_options import ClientOptions

        if credentials_path and os.path.exists(credentials_path):
            os.environ.setdefault("GOOGLE_APPLICATION_CREDENTIALS", credentials_path)

        opts = ClientOptions(
            api_endpoint=f"{DOCAI_LOCATION}-documentai.googleapis.com"
        )
        _docai_client = documentai.DocumentProcessorServiceClient(client_options=opts)
        logger.info(
            f"[DocAI] ✅ Client inizializzato — "
            f"project={DOCAI_PROJECT}, location={DOCAI_LOCATION}, "
            f"processor={DOCAI_PROCESSOR}"
        )
        return True
    except Exception as e:
        logger.error(f"[DocAI] ❌ Errore init: {e}")
        return False


def is_ready() -> bool:
    """Ritorna True se il client Document AI è inizializzato."""
    return _docai_client is not None


# ── Auto-detect PDF scansionato ────────────────────────────────────────────────

def needs_ocr(pdf_bytes: bytes) -> bool:
    """
    Rileva automaticamente se un PDF è scansionato (testo non selezionabile).
    Legge le prime 5 pagine con PyMuPDF: se la media è sotto OCR_THRESHOLD_CHARS_PER_PAGE
    il PDF è considerato immagine e viene inviato a Document AI.
    """
    try:
        import fitz
        doc       = fitz.open(stream=pdf_bytes, filetype="pdf")
        n_sample  = min(doc.page_count, 5)
        total_txt = sum(len(doc[i].get_text("text").strip()) for i in range(n_sample))
        doc.close()
        avg   = total_txt / max(1, n_sample)
        result = avg < OCR_THRESHOLD_CHARS_PER_PAGE
        logger.info(
            f"[DocAI] needs_ocr={result} "
            f"(media {avg:.0f} chars/pagina, soglia={OCR_THRESHOLD_CHARS_PER_PAGE})"
        )
        return result
    except Exception as e:
        logger.warning(f"[DocAI] needs_ocr check fallito: {e} — assumo OCR non necessario")
        return False


# ── OCR principale ─────────────────────────────────────────────────────────────

def ocr_pdf_bytes(pdf_bytes: bytes) -> List[dict]:
    """
    Esegue OCR sul PDF via Google Cloud Document AI.

    Ritorna una lista di blocchi nel MEDESIMO formato di
    embedding_service.extract_blocks_from_pdf():
      {
        "text":        str,
        "page_number": int (1-indexed),
        "article_ref": str | None,
        "coordinates": { x0, y0, x1, y1, page_width, page_height },
        "char_start":  int,
        "source":      "docai_ocr"   # campo extra per tracciabilità
      }

    Il risultato può essere passato direttamente a embed_chunks() e save_embeddings().
    """
    if not _docai_client:
        raise RuntimeError(
            "[DocAI] Client non inizializzato. Chiamare init_docai() prima."
        )

    from google.cloud import documentai

    processor_name = _docai_client.processor_path(
        DOCAI_PROJECT, DOCAI_LOCATION, DOCAI_PROCESSOR
    )

    raw_doc = documentai.RawDocument(
        content=pdf_bytes,
        mime_type="application/pdf"
    )
    request = documentai.ProcessRequest(
        name=processor_name,
        raw_document=raw_doc
    )

    logger.info(f"[DocAI] Invio a Document AI ({len(pdf_bytes) // 1024} KB)...")
    response  = _docai_client.process_document(request=request)
    doc       = response.document
    full_text = doc.text

    blocks_out  = []
    char_offset = 0

    for page in doc.pages:
        page_num    = page.page_number        # già 1-indexed in Document AI
        page_width  = page.dimension.width  or 595.0   # fallback A4
        page_height = page.dimension.height or 842.0

        # paragraphs > blocks per testo legale strutturato
        # se il processore non produce paragraphs usa blocks
        items = page.paragraphs if page.paragraphs else page.blocks

        for item in items:
            text = _get_text(item.layout.text_anchor, full_text).strip()
            if len(text) < MIN_PARA_CHARS:
                continue

            # Bounding box normalizzato → coordinate assolute
            verts = item.layout.bounding_poly.normalized_vertices
            if verts:
                xs = [v.x * page_width  for v in verts]
                ys = [v.y * page_height for v in verts]
                coords = {
                    "x0": round(min(xs), 2),
                    "y0": round(min(ys), 2),
                    "x1": round(max(xs), 2),
                    "y1": round(max(ys), 2),
                    "page_width":  round(page_width,  2),
                    "page_height": round(page_height, 2),
                }
            else:
                coords = {
                    "x0": 0, "y0": 0,
                    "x1": round(page_width, 2), "y1": round(page_height, 2),
                    "page_width":  round(page_width, 2),
                    "page_height": round(page_height, 2),
                }

            art_ref = _extract_article_ref(text)

            if len(text) <= MAX_PARA_CHARS:
                blocks_out.append({
                    "text":        text,
                    "page_number": page_num,
                    "article_ref": art_ref,
                    "coordinates": coords,
                    "char_start":  char_offset,
                    "source":      "docai_ocr",
                })
                char_offset += len(text)
            else:
                # Paragrafo lungo → sotto-chunk sovrapposti
                start = 0
                while start < len(text):
                    end = start + MAX_PARA_CHARS
                    sub = text[start:end].strip()
                    if sub:
                        blocks_out.append({
                            "text":        sub,
                            "page_number": page_num,
                            "article_ref": _extract_article_ref(sub) or art_ref,
                            "coordinates": coords,
                            "char_start":  char_offset + start,
                            "source":      "docai_ocr",
                        })
                    if end >= len(text):
                        break
                    start += MAX_PARA_CHARS - PARA_OVERLAP
                char_offset += len(text)

    logger.info(
        f"[DocAI] ✅ OCR completato: {len(blocks_out)} blocchi "
        f"da {len(doc.pages)} pagine"
    )
    return blocks_out


# ── Utility ────────────────────────────────────────────────────────────────────

def _get_text(text_anchor, full_text: str) -> str:
    """
    Estrae il testo dal full_text del documento usando text_anchor.text_segments.
    Document AI non include il testo direttamente negli elementi layout —
    usa offset nel testo globale del documento.
    """
    if not text_anchor or not text_anchor.text_segments:
        return ""
    parts = []
    for seg in text_anchor.text_segments:
        s = int(seg.start_index) if seg.start_index else 0
        e = int(seg.end_index)   if seg.end_index   else 0
        parts.append(full_text[s:e])
    return "".join(parts)
