"""
Piper TTS — Italian voice synthesis for the CIPP/E Legal SaaS backend.
Auto-downloads the piper binary and it_IT-riccardo-medium voice model to /tmp.
"""

import os
import re
import stat
import tarfile
import logging
import tempfile
import subprocess
import urllib.request

logger = logging.getLogger("cipp-legal-api")

# ── Paths ────────────────────────────────────────────────────────────
_EXTRACT_DIR  = "/tmp/piper_release"
_PIPER_BIN    = "/tmp/piper_release/piper/piper"
_ESPEAK_DATA  = "/tmp/piper_release/piper/espeak-ng-data"
_MODEL_DIR    = "/tmp/piper_models"
_MODEL_NAME   = "it_IT-riccardo-x_low"
_MODEL_ONNX   = os.path.join(_MODEL_DIR, f"{_MODEL_NAME}.onnx")
_MODEL_JSON   = os.path.join(_MODEL_DIR, f"{_MODEL_NAME}.onnx.json")

_PIPER_TAR_URL = (
    "https://github.com/rhasspy/piper/releases/download/"
    "2023.11.14-2/piper_linux_x86_64.tar.gz"
)
_MODEL_BASE_URL = (
    "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/"
    "it/it_IT/riccardo/x_low"
)

_ready = False


def _download(url: str, dest: str, label: str) -> None:
    logger.info("[Piper] Downloading %s → %s", label, dest)
    tmp = dest + ".part"
    try:
        urllib.request.urlretrieve(url, tmp)
        os.replace(tmp, dest)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def ensure_piper() -> bool:
    """Download piper binary + Italian voice model if not already in /tmp. Thread-safe via module-level flag."""
    global _ready
    if _ready:
        return True

    os.makedirs(_EXTRACT_DIR, exist_ok=True)
    os.makedirs(_MODEL_DIR, exist_ok=True)

    # ── Binary ────────────────────────────────────────────────────────
    if not os.path.isfile(_PIPER_BIN):
        tgz = os.path.join(_EXTRACT_DIR, "piper.tar.gz")
        _download(_PIPER_TAR_URL, tgz, "piper binary")
        logger.info("[Piper] Extracting archive…")
        with tarfile.open(tgz, "r:gz") as tf:
            tf.extractall(_EXTRACT_DIR)
        os.unlink(tgz)
        # Ensure executable bit
        if os.path.isfile(_PIPER_BIN):
            st = os.stat(_PIPER_BIN)
            os.chmod(_PIPER_BIN, st.st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
            logger.info("[Piper] Binary ready: %s", _PIPER_BIN)
        else:
            raise RuntimeError(f"Piper binary not found after extraction at {_PIPER_BIN}")

    # ── Voice model ───────────────────────────────────────────────────
    if not os.path.isfile(_MODEL_ONNX):
        _download(f"{_MODEL_BASE_URL}/{_MODEL_NAME}.onnx", _MODEL_ONNX, "ONNX model")
    if not os.path.isfile(_MODEL_JSON):
        _download(f"{_MODEL_BASE_URL}/{_MODEL_NAME}.onnx.json", _MODEL_JSON, "model config")

    logger.info("[Piper] Ready — binary=%s model=%s", _PIPER_BIN, _MODEL_ONNX)
    _ready = True
    return True


# ── Legal Italian text normalisation ────────────────────────────────

# Roman numeral → Italian ordinal
_ROMAN_MAP = {
    "I": "primo", "II": "secondo", "III": "terzo", "IV": "quarto",
    "V": "quinto", "VI": "sesto", "VII": "settimo", "VIII": "ottavo",
    "IX": "nono", "X": "decimo", "XI": "undicesimo", "XII": "dodicesimo",
    "XIII": "tredicesimo", "XIV": "quattordicesimo", "XV": "quindicesimo",
    "XVI": "sedicesimo", "XVII": "diciassettesimo", "XVIII": "diciottesimo",
    "XIX": "diciannovesimo", "XX": "ventesimo",
    "XXI": "ventunesimo", "XXII": "ventiduesimo", "XXIII": "ventitreesimo",
    "XXIV": "ventiquattresimo", "XXV": "venticinquesimo",
    "XXX": "trentesimo", "XL": "quarantesimo", "L": "cinquantesimo",
    "LX": "sessantesimo", "LXX": "settantesimo", "LXXX": "ottantesimo",
    "XC": "novantesimo", "C": "centesimo",
}

_ROMAN_PATTERN = re.compile(
    r'\b(M{0,4}(?:CM|CD|D?C{0,3})(?:XC|XL|L?X{0,3})(?:IX|IV|V?I{0,3}))\b',
    re.IGNORECASE,
)
_STRUCT_WORDS = re.compile(
    r'\b(Libro|Titolo|Capo|Capitolo|Sezione|Parte|Allegato|Volume|Paragrafo)\s+',
    re.IGNORECASE,
)

_ABBR = [
    # Codici e fonti
    (r'\bGDPR\b',                      'Gi Di Pi Erre'),
    (r'\bD\.?Lgs\.?\b',                'Decreto Legislativo'),
    (r'\bD\.?L\.?\b',                  'Decreto Legge'),
    (r'\bD\.?P\.?R\.?\b',              'Decreto del Presidente della Repubblica'),
    (r'\bL\.?\s+n\.\s*',              'Legge numero '),
    (r'\bArt\.\s*',                    'Articolo '),
    (r'\bart\.\s*',                    'articolo '),
    (r'\bArtt\.\s*',                   'Articoli '),
    (r'\bco\.\s*',                     'comma '),
    (r'\bcomma\s+(\d+)',               r'comma \1'),
    (r'\bpar\.\s*',                    'paragrafo '),
    (r'\bc\.p\.c\.',                   'codice di procedura civile'),
    (r'\bc\.p\.p\.',                   'codice di procedura penale'),
    (r'\bc\.c\.',                      'codice civile'),
    (r'\bc\.p\.',                      'codice penale'),
    (r'\bt\.u\.',                      'testo unico'),
    (r'\bT\.U\.',                      'Testo Unico'),
    (r'\bGU\b',                        'Gazzetta Ufficiale'),
    (r'\bGUUE\b',                      'Gazzetta Ufficiale dell\'Unione Europea'),
    (r'\bUE\b',                        'Unione Europea'),
    (r'\bCE\b',                        'Comunità Europea'),
    (r'\bCEDU\b',                      'Convenzione Europea dei Diritti dell\'Uomo'),
    # Garante e autorità
    (r'\bGarant[ei]\b',                'Garante per la protezione dei dati personali'),
    (r'\bEDPB\b',                      'Comitato Europeo per la Protezione dei Dati'),
    (r'\bEDPS\b',                      'Garante Europeo della Protezione dei Dati'),
    # Numeri e simboli
    (r'€\s*(\d)',                       r'euro \1'),
    (r'(\d)\s*€',                       r'\1 euro'),
    (r'(\d+)\s*%',                      r'\1 per cento'),
    # Trattini e slash
    (r'\s*—\s*',                        ', '),
    (r'\s*–\s*',                        ', '),
    (r'(\d{4})/(\d{4})',                r'\1 del \2'),   # anno/anno
    (r'(\d+)/(\d{4})',                  r'\1 del \2'),   # n/anno
    # Enumerazioni: a) b) 1) — aggiunge pausa
    (r'(?m)^([a-z])\)',                 r'\1, '),
    (r'(?m)^(\d+)\)',                   r'\1, '),
    # Puntini di sospensione
    (r'\.{2,}',                         '.'),
    # Acronimi spaziali
    (r'\bIA\b',                         'Intelligenza Artificiale'),
    (r'\bAI\s+Act\b',                   'AI Act'),
    (r'\bDPIA\b',                       'Valutazione d\'impatto sulla protezione dei dati'),
    (r'\bDPO\b',                        'Responsabile della protezione dei dati'),
    (r'\bRPD\b',                        'Responsabile della protezione dei dati'),
]

# Precompile abbreviation patterns
_ABBR_COMPILED = [(re.compile(pat), repl) for pat, repl in _ABBR]


def _expand_romans(text: str) -> str:
    """Replace Roman numerals preceded by structural words with Italian ordinals."""
    def _replace(m: re.Match) -> str:
        roman = m.group(1).upper()
        return _ROMAN_MAP.get(roman, m.group(1))

    # After structural words: "Titolo III" → "Titolo terzo"
    def _struct_replace(m: re.Match) -> str:
        word = m.group(1)
        rest = text[m.end():]
        rm = _ROMAN_PATTERN.match(rest)
        if rm:
            roman = rm.group(1).upper()
            ordinal = _ROMAN_MAP.get(roman, rm.group(1))
            return f"{word} {ordinal} "
        return m.group(0)

    # Replace Romans after structural keywords
    result = []
    last = 0
    for sm in _STRUCT_WORDS.finditer(text):
        result.append(text[last:sm.end()])
        rest = text[sm.end():]
        rm = _ROMAN_PATTERN.match(rest)
        if rm:
            roman = rm.group(1).upper()
            result.append(_ROMAN_MAP.get(roman, rm.group(1)) + " ")
            last = sm.end() + rm.end()
        else:
            last = sm.end()
    result.append(text[last:])
    return "".join(result)


def normalize_legal_text(text: str) -> str:
    """Normalize Italian legal text for natural TTS pronunciation."""
    # Roman numerals in structural context
    text = _expand_romans(text)

    # Abbreviations
    for pat, repl in _ABBR_COMPILED:
        text = pat.sub(repl, text)

    # Collapse multiple spaces/newlines
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r' {2,}', ' ', text)

    return text.strip()


# ── Synthesis ────────────────────────────────────────────────────────

def synthesize(text: str, length_scale: float = 1.08) -> bytes:
    """
    Synthesize text to WAV bytes using Piper.
    length_scale > 1 slows speech slightly for clarity (1.08 ≈ natural legal pace).
    Raises RuntimeError if piper is unavailable.
    """
    ensure_piper()

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        out_path = tmp.name

    try:
        env = os.environ.copy()
        env["ESPEAK_DATA_PATH"] = _ESPEAK_DATA

        result = subprocess.run(
            [
                _PIPER_BIN,
                "--model", _MODEL_ONNX,
                "--output_file", out_path,
                "--length_scale", str(length_scale),
                "--sentence_silence", "0.3",
            ],
            input=text.encode("utf-8"),
            capture_output=True,
            timeout=60,
            env=env,
        )

        if result.returncode != 0:
            err = result.stderr.decode("utf-8", errors="replace")
            raise RuntimeError(f"Piper exited {result.returncode}: {err[:300]}")

        with open(out_path, "rb") as f:
            return f.read()

    finally:
        if os.path.exists(out_path):
            os.unlink(out_path)
