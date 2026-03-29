"""
Database layer — CIPP/E Legal SaaS
Gestisce il tracciamento degli upload utente.
SQLite di default (file locale); si può passare a PostgreSQL/MySQL
cambiando DATABASE_URL nel .env — nessun cambio di codice necessario.
"""

import os
import datetime
from typing import Optional

import json as _json

from sqlalchemy import (
    create_engine, Column, Integer, String,
    BigInteger, DateTime, Text, Float, event
)
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from sqlalchemy.pool import StaticPool

# ── Config ────────────────────────────────────────────────────────────────────
_BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
_DEFAULT_DB   = f"sqlite:///{os.path.join(_BASE_DIR, 'uploads.db')}"
DATABASE_URL  = os.getenv("DATABASE_URL", _DEFAULT_DB)

# SQLite needs check_same_thread=False; other DB engines don't
_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    DATABASE_URL,
    connect_args=_connect_args,
    # StaticPool keeps a single connection for SQLite (fine for dev/single-process)
    poolclass=StaticPool if DATABASE_URL.startswith("sqlite") else None,
    echo=False,
)

# Enable WAL mode for SQLite (better concurrent read performance)
if DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def _set_wal(dbapi_conn, _):
        dbapi_conn.execute("PRAGMA journal_mode=WAL")
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ── Models ────────────────────────────────────────────────────────────────────

class Upload(Base):
    """Traccia ogni file caricato su GCS da un utente."""
    __tablename__ = "uploads"

    id                = Column(Integer,  primary_key=True, autoincrement=True)
    user_id           = Column(String(100), nullable=False, index=True)
    blob_name         = Column(String(600), nullable=False, unique=True)   # path GCS
    original_filename = Column(String(255), nullable=False)
    file_size         = Column(BigInteger,  nullable=True)                 # bytes
    mime_type         = Column(String(120), nullable=True)
    status            = Column(
        String(50),
        nullable=False,
        default="in_attesa"
    )                                                                       # in_attesa | approvato | rifiutato
    notes             = Column(Text,    nullable=True)                     # note admin
    uploaded_at       = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at        = Column(
        DateTime,
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow,
        nullable=False
    )

    def to_dict(self) -> dict:
        return {
            "id":                self.id,
            "user_id":           self.user_id,
            "blob_name":         self.blob_name,
            "original_filename": self.original_filename,
            "file_size":         self.file_size,
            "file_size_mb":      round(self.file_size / (1024 * 1024), 2) if self.file_size else None,
            "mime_type":         self.mime_type,
            "status":            self.status,
            "notes":             self.notes,
            "uploaded_at":       self.uploaded_at.isoformat() if self.uploaded_at else None,
            "updated_at":        self.updated_at.isoformat() if self.updated_at else None,
        }


# ── Embedding table ───────────────────────────────────────────────────────────

class DocEmbedding(Base):
    """
    Memorizza i chunk di documento con embedding semantici e metadati posizionali.
    Struttura ispirata a NotebookLM: ogni chunk sa esattamente dove si trova nel PDF.
    Un documento GCS → N record (uno per chunk/blocco).
    """
    __tablename__ = "doc_embeddings"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    blob_name   = Column(String(600), nullable=False, index=True)  # path GCS
    chunk_index = Column(Integer, nullable=False)                  # 0-based

    # ── Testo ────────────────────────────────────────────────────────
    text        = Column(Text, nullable=False)                     # testo del chunk
    char_start  = Column(Integer, nullable=True)                   # offset nel fulltext

    # ── Metadati posizionali (NotebookLM-style) ───────────────────────
    page_number = Column(Integer, nullable=True)                   # pagina PDF (1-indexed)
    article_ref = Column(String(120), nullable=True)               # es. "Art. 32", "Art. 5(1)(a)"
    x0          = Column(Float, nullable=True)                     # coordinata blocco PDF
    y0          = Column(Float, nullable=True)
    x1          = Column(Float, nullable=True)
    y1          = Column(Float, nullable=True)
    page_width  = Column(Float, nullable=True)                     # per normalizzare coordinate
    page_height = Column(Float, nullable=True)

    # ── Vettore ──────────────────────────────────────────────────────
    embedding   = Column(Text, nullable=False)                     # JSON array of floats
    indexed_at  = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    def to_dict(self) -> dict:
        return {
            "id":          self.id,
            "blob_name":   self.blob_name,
            "chunk_index": self.chunk_index,
            "text":        self.text,
            "char_start":  self.char_start,
            "page_number": self.page_number,
            "article_ref": self.article_ref,
            "coordinates": {
                "x0": self.x0, "y0": self.y0,
                "x1": self.x1, "y1": self.y1,
                "page_width":  self.page_width,
                "page_height": self.page_height,
            } if self.x0 is not None else None,
            "embedding":   _json.loads(self.embedding) if self.embedding else [],
        }


# ── Helpers ───────────────────────────────────────────────────────────────────

def init_db() -> None:
    """Crea le tabelle se non esistono (idempotente)."""
    Base.metadata.create_all(bind=engine)


def get_db() -> Session:
    """Dependency FastAPI — yield una sessione e chiude automaticamente."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# CRUD helpers

def create_upload(
    db: Session,
    user_id: str,
    blob_name: str,
    original_filename: str,
    file_size: Optional[int] = None,
    mime_type: Optional[str] = None,
) -> Upload:
    record = Upload(
        user_id=user_id,
        blob_name=blob_name,
        original_filename=original_filename,
        file_size=file_size,
        mime_type=mime_type,
        status="in_attesa",
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def list_uploads(
    db: Session,
    user_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 200,
) -> list:
    q = db.query(Upload)
    if user_id:
        q = q.filter(Upload.user_id == user_id)
    if status:
        q = q.filter(Upload.status == status)
    return q.order_by(Upload.uploaded_at.desc()).limit(limit).all()


def update_status(
    db: Session,
    upload_id: int,
    status: str,
    notes: Optional[str] = None,
) -> Optional[Upload]:
    record = db.query(Upload).filter(Upload.id == upload_id).first()
    if not record:
        return None
    record.status     = status
    record.updated_at = datetime.datetime.utcnow()
    if notes is not None:
        record.notes = notes
    db.commit()
    db.refresh(record)
    return record


def delete_upload(db: Session, upload_id: int) -> bool:
    record = db.query(Upload).filter(Upload.id == upload_id).first()
    if not record:
        return False
    db.delete(record)
    db.commit()
    return True


# ── Embedding CRUD ─────────────────────────────────────────────────────────────

def save_embeddings(db: Session, blob_name: str, chunks: list) -> int:
    """
    Salva i chunk con embedding e metadati posizionali per un documento.
    Elimina quelli precedenti (re-index idempotente).
    Ritorna il numero di chunk salvati.
    """
    db.query(DocEmbedding).filter(DocEmbedding.blob_name == blob_name).delete()
    for ch in chunks:
        emb_json = _json.dumps(ch["embedding"]) if ch.get("embedding") else "[]"
        coords = ch.get("coordinates") or {}
        db.add(DocEmbedding(
            blob_name   = blob_name,
            chunk_index = ch["chunk_index"],
            char_start  = ch.get("char_start"),
            text        = ch["text"],
            page_number = ch.get("page_number"),
            article_ref = ch.get("article_ref"),
            x0          = coords.get("x0"),
            y0          = coords.get("y0"),
            x1          = coords.get("x1"),
            y1          = coords.get("y1"),
            page_width  = coords.get("page_width"),
            page_height = coords.get("page_height"),
            embedding   = emb_json,
        ))
    db.commit()
    return len(chunks)


def load_embeddings(db: Session, blob_name: str) -> list:
    """
    Carica tutti i chunk di un documento con i loro embedding (già deserializzati).
    Ritorna lista di dict pronti per semantic_search().
    """
    rows = (
        db.query(DocEmbedding)
          .filter(DocEmbedding.blob_name == blob_name)
          .order_by(DocEmbedding.chunk_index)
          .all()
    )
    return [r.to_dict() for r in rows]


def is_indexed(db: Session, blob_name: str) -> bool:
    """Verifica se il documento ha già embedding nel DB."""
    return db.query(DocEmbedding).filter(
        DocEmbedding.blob_name == blob_name
    ).first() is not None
