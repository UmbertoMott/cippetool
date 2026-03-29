"""
Google Cloud Storage client for the CIPP/E Legal SaaS.
Handles PDF retrieval, signed URL generation, and text extraction.
"""

import os
import datetime
from typing import Optional, List, Dict
import fitz  # PyMuPDF
from io import BytesIO
from google.cloud import storage
from google.oauth2 import service_account


class GCSLegalClient:
    """Client for interacting with GCS bucket containing legal documents."""

    def __init__(self, credentials_path: str, bucket_name: str):
        self.bucket_name = bucket_name
        self.credentials_path = credentials_path
        self._credentials = service_account.Credentials.from_service_account_file(
            credentials_path,
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        self._client = storage.Client(credentials=self._credentials)
        self._bucket = self._client.bucket(bucket_name)

    def list_pdfs(self, prefix: str = "", max_results: int = 200) -> List[Dict]:
        """List all PDF files in the bucket with metadata."""
        blobs = self._client.list_blobs(
            self._bucket,
            prefix=prefix,
            max_results=max_results
        )
        pdfs = []
        for blob in blobs:
            if blob.name.lower().endswith('.pdf'):
                pdfs.append({
                    "name": blob.name,
                    "display_name": os.path.splitext(os.path.basename(blob.name))[0],
                    "size_bytes": blob.size,
                    "size_mb": round(blob.size / (1024 * 1024), 2) if blob.size else 0,
                    "updated": blob.updated.isoformat() if blob.updated else None,
                    "content_type": blob.content_type,
                    "metadata": dict(blob.metadata) if blob.metadata else {},
                })
        return pdfs

    def generate_signed_url(self, blob_name: str, expiration_minutes: int = 60) -> str:
        """Generate a signed URL for private PDF access."""
        blob = self._bucket.blob(blob_name)
        if not blob.exists():
            raise FileNotFoundError(f"Blob '{blob_name}' not found in bucket '{self.bucket_name}'")

        url = blob.generate_signed_url(
            version="v4",
            expiration=datetime.timedelta(minutes=expiration_minutes),
            method="GET",
            credentials=self._credentials,
            response_type="application/pdf",
            response_disposition=f"inline; filename=\"{os.path.basename(blob_name)}\""
        )
        return url

    def download_pdf_bytes(self, blob_name: str) -> bytes:
        """Download PDF content as bytes."""
        blob = self._bucket.blob(blob_name)
        if not blob.exists():
            raise FileNotFoundError(f"Blob '{blob_name}' not found in bucket '{self.bucket_name}'")
        return blob.download_as_bytes()

    def extract_text(self, blob_name: str, page_start: int = 0, page_end: Optional[int] = None) -> dict:
        """
        Extract text from a PDF in GCS using PyMuPDF.
        Returns structured text with page-level granularity.
        """
        pdf_bytes = self.download_pdf_bytes(blob_name)
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")

        total_pages = doc.page_count
        end = min(page_end, total_pages) if page_end else total_pages

        pages = []
        full_text = []
        for page_num in range(page_start, end):
            page = doc[page_num]
            text = page.get_text("text")
            pages.append({
                "page": page_num + 1,  # 1-indexed
                "text": text,
                "char_count": len(text)
            })
            full_text.append(text)

        doc.close()
        combined = "\n\n--- Pagina ---\n\n".join(full_text)
        return {
            "blob_name": blob_name,
            "total_pages": total_pages,
            "extracted_pages": list(range(page_start + 1, end + 1)),
            "pages": pages,
            "full_text": combined,
            "total_chars": len(combined)
        }

    def extract_text_with_positions(self, blob_name: str, search_text: str = None,
                                     page_hint: int = None, strict_page: bool = False) -> dict:
        """
        Extract text with positional data for highlight mapping.
        If search_text is provided, returns positions of matching text blocks.
        page_hint: if given, search that page first; fall back to all pages if not found.
        strict_page: if True AND page_hint is set, only search the hinted page — no global fallback.
        """
        pdf_bytes = self.download_pdf_bytes(blob_name)
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")

        results = {
            "blob_name": blob_name,
            "total_pages": doc.page_count,
            "matches": []
        }

        def _search_page(page_num):
            page = doc[page_num]
            page_rect = page.rect
            # Try exact match first, then case-insensitive
            instances = page.search_for(search_text, quads=False)
            if not instances:
                instances = page.search_for(search_text.lower(), quads=False)
            for inst in instances:
                results["matches"].append({
                    "page": page_num + 1,
                    "exact_text": search_text,
                    "page_width": round(page_rect.width, 2),
                    "page_height": round(page_rect.height, 2),
                    "rect": {
                        "x0": round(inst.x0, 2),
                        "y0": round(inst.y0, 2),
                        "x1": round(inst.x1, 2),
                        "y1": round(inst.y1, 2)
                    }
                })

        if search_text:
            if page_hint and 1 <= page_hint <= doc.page_count:
                # Search hinted page first
                _search_page(page_hint - 1)
                if strict_page:
                    # strict mode: only the hinted page, no fallback
                    pass
                else:
                    # If not found on hinted page, search ±3 pages around it, then all
                    if not results["matches"]:
                        nearby = range(
                            max(0, page_hint - 4),
                            min(doc.page_count, page_hint + 3)
                        )
                        for pn in nearby:
                            if pn != page_hint - 1:
                                _search_page(pn)
                    if not results["matches"]:
                        for pn in range(doc.page_count):
                            if pn != page_hint - 1:
                                _search_page(pn)
            else:
                for pn in range(doc.page_count):
                    _search_page(pn)

        doc.close()
        return results

    def generate_upload_signed_url(
        self,
        blob_name: str,
        content_type: str = "application/pdf",
        expiration_minutes: int = 10,
    ) -> str:
        """
        Genera una Signed URL per upload diretto dal browser verso GCS (PUT).
        Il file non transita dal server: browser → GCS direttamente.
        blob_name esempio: 'uploads/utente_A/2024-01-15_contratto.pdf'
        """
        blob = self._bucket.blob(blob_name)
        url = blob.generate_signed_url(
            version="v4",
            expiration=datetime.timedelta(minutes=expiration_minutes),
            method="PUT",
            content_type=content_type,
            credentials=self._credentials,
        )
        return url

    def delete_blob(self, blob_name: str) -> bool:
        """Elimina un blob dal bucket. Restituisce True se eliminato, False se non esiste."""
        blob = self._bucket.blob(blob_name)
        if blob.exists():
            blob.delete()
            return True
        return False

    def get_pdf_metadata(self, blob_name: str) -> dict:
        """Get PDF metadata (title, author, pages, etc.)."""
        pdf_bytes = self.download_pdf_bytes(blob_name)
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        meta = doc.metadata
        info = {
            "blob_name": blob_name,
            "total_pages": doc.page_count,
            "title": meta.get("title", ""),
            "author": meta.get("author", ""),
            "subject": meta.get("subject", ""),
            "creator": meta.get("creator", ""),
            "producer": meta.get("producer", ""),
            "creation_date": meta.get("creationDate", ""),
            "mod_date": meta.get("modDate", ""),
        }
        doc.close()
        return info
