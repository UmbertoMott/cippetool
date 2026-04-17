"""
Embedding Service — CIPP/E Legal SaaS
Chunking NotebookLM-style: ogni chunk porta con sé pagina, article_ref e coordinate PDF.
Usa gemini-embedding-2-preview (MRL 768 dims) per i vettori semantici.
"""

import re
import math
import logging
from io import BytesIO
from typing import List, Optional

import fitz  # PyMuPDF — già installato
import google.generativeai as genai

logger = logging.getLogger("cipp-legal-api")

# ── Config ─────────────────────────────────────────────────────────────────────
EMBED_MODEL        = "models/gemini-embedding-2-preview"
EMBED_DIMS         = 768       # MRL — ridotto da 3072
MIN_BLOCK_CHARS    = 80        # scarta blocchi troppo corti (numeri di pagina, header)
MAX_BLOCK_CHARS    = 900       # blocchi > MAX vengono spezzati in sotto-chunk
BLOCK_OVERLAP_CHARS = 120      # overlap tra sotto-chunk dello stesso blocco
MAX_CHUNKS_PER_DOC = 400       # limite sicurezza

_genai_ready = False


def init_embedding(api_key: str) -> None:
    global _genai_ready
    if not api_key:
        logger.warning("[Embed] GEMINI_API_KEY mancante — embedding disabilitato")
        return
    genai.configure(api_key=api_key)
    _genai_ready = True
    logger.info(f"[Embed] Pronto — model={EMBED_MODEL}, dims={EMBED_DIMS}")


# ── Article reference extraction ───────────────────────────────────────────────

# Cattura: Art. 5, Art. 5(1)(a), Article 32, Artt. 13-14, § 3, Considerando 47, Recital 47
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
    """Ritorna il primo riferimento normativo trovato nel testo del chunk."""
    m = _ART_RE.search(text)
    if m:
        return m.group(0).strip()[:120]
    return None


# ── Block-level chunking with PyMuPDF ──────────────────────────────────────────

def extract_blocks_from_pdf(pdf_bytes: bytes) -> List[dict]:
    """
    Estrae blocchi di testo da un PDF con metadati posizionali completi.
    Ritorna lista di dict con: text, page_number, coordinates, article_ref.

    Ogni blocco PyMuPDF = paragrafo/gruppo di righe semanticamente coeso.
    Se un blocco supera MAX_BLOCK_CHARS viene spezzato conservando le coordinate del blocco padre.
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    blocks_out = []
    char_offset = 0

    for page_idx in range(doc.page_count):
        page = doc[page_idx]
        page_rect = page.rect
        page_num  = page_idx + 1   # 1-indexed

        # get_text("blocks") → (x0, y0, x1, y1, text, block_no, block_type)
        raw_blocks = page.get_text("blocks", sort=True)  # sort=True → ordine lettura

        for blk in raw_blocks:
            x0, y0, x1, y1, text, _bno, btype = blk
            if btype != 0:          # 0=text, 1=image — saltiamo immagini
                continue
            text = text.strip()
            if len(text) < MIN_BLOCK_CHARS:
                continue

            coords = {
                "x0": round(x0, 2), "y0": round(y0, 2),
                "x1": round(x1, 2), "y1": round(y1, 2),
                "page_width":  round(page_rect.width, 2),
                "page_height": round(page_rect.height, 2),
            }
            art_ref = _extract_article_ref(text)

            if len(text) <= MAX_BLOCK_CHARS:
                # Blocco piccolo → un singolo chunk
                blocks_out.append({
                    "text":        text,
                    "page_number": page_num,
                    "article_ref": art_ref,
                    "coordinates": coords,
                    "char_start":  char_offset,
                })
                char_offset += len(text)
            else:
                # Blocco grande → sotto-chunk sovrapposti (stesse coordinate del blocco padre)
                start = 0
                while start < len(text):
                    end   = start + MAX_BLOCK_CHARS
                    sub   = text[start:end].strip()
                    if sub:
                        sub_art = _extract_article_ref(sub) or art_ref
                        blocks_out.append({
                            "text":        sub,
                            "page_number": page_num,
                            "article_ref": sub_art,
                            "coordinates": coords,   # coordinate del blocco padre
                            "char_start":  char_offset + start,
                        })
                    if end >= len(text):
                        break
                    start += MAX_BLOCK_CHARS - BLOCK_OVERLAP_CHARS
                char_offset += len(text)

        if len(blocks_out) >= MAX_CHUNKS_PER_DOC:
            logger.warning(f"[Embed] Limite {MAX_CHUNKS_PER_DOC} chunk raggiunto a pagina {page_num}")
            break

    total_pages = doc.page_count
    doc.close()
    logger.info(f"[Embed] Estratti {len(blocks_out)} blocchi da {total_pages} pagine")
    return blocks_out[:MAX_CHUNKS_PER_DOC]


# ── Embedding generation ────────────────────────────────────────────────────────

def embed_chunks(text_chunks: List[str]) -> List[List[float]]:
    """Genera embedding per una lista di testi (task: RETRIEVAL_DOCUMENT). Batch da 100."""
    if not _genai_ready:
        raise RuntimeError("Embedding service non inizializzato")

    embeddings = []
    for i in range(0, len(text_chunks), 100):
        batch = text_chunks[i:i + 100]
        result = genai.embed_content(
            model=EMBED_MODEL,
            content=batch,
            task_type="RETRIEVAL_DOCUMENT",
            output_dimensionality=EMBED_DIMS
        )
        vecs = result.get("embedding", [])
        if vecs and isinstance(vecs[0], float):
            vecs = [vecs]   # singolo elemento
        embeddings.extend(vecs)
    return embeddings


def embed_query(query: str) -> List[float]:
    """Genera embedding per una query (task: RETRIEVAL_QUERY)."""
    if not _genai_ready:
        raise RuntimeError("Embedding service non inizializzato")
    result = genai.embed_content(
        model=EMBED_MODEL,
        content=query,
        task_type="RETRIEVAL_QUERY",
        output_dimensionality=EMBED_DIMS
    )
    vec = result.get("embedding", [])
    return vec[0] if vec and isinstance(vec[0], list) else vec


# ── Cosine similarity ───────────────────────────────────────────────────────────

def _cosine(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na  = math.sqrt(sum(x * x for x in a))
    nb  = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def semantic_search(
    query: str,
    stored_chunks: List[dict],
    top_k: int = 5,
    min_score: float = 0.50,
) -> List[dict]:
    """
    Semantic search con restituzione di metadati posizionali completi.
    Ogni risultato include page_number, article_ref e coordinates per highlight PDF.
    """
    if not stored_chunks:
        return []
    q_vec = embed_query(query)
    scored = []
    for ch in stored_chunks:
        emb = ch.get("embedding")
        if not emb:
            continue
        score = _cosine(q_vec, emb)
        if score >= min_score:
            scored.append({
                "chunk_index": ch.get("chunk_index", 0),
                "text":        ch.get("text", ""),
                "score":       round(score, 4),
                "page_number": ch.get("page_number"),
                "article_ref": ch.get("article_ref"),
                "coordinates": ch.get("coordinates"),
                "char_start":  ch.get("char_start", 0),
            })
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]


# ── Main indexing entry point ───────────────────────────────────────────────────

def index_document(pdf_bytes: bytes) -> List[dict]:
    """
    Indicizza un PDF: estrae blocchi con metadati, genera embedding.
    Ritorna lista pronta per save_embeddings() nel DB.
    Accetta bytes del PDF direttamente (non testo grezzo).
    """
    blocks = extract_blocks_from_pdf(pdf_bytes)
    if not blocks:
        return []

    texts = [b["text"] for b in blocks]
    embeddings = embed_chunks(texts)

    result = []
    for i, (blk, emb) in enumerate(zip(blocks, embeddings)):
        result.append({
            "chunk_index": i,
            "text":        blk["text"],
            "char_start":  blk.get("char_start", 0),
            "page_number": blk.get("page_number"),
            "article_ref": blk.get("article_ref"),
            "coordinates": blk.get("coordinates"),
            "embedding":   emb,
        })
    return result
