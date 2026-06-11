"""
core/memory/ingest.py

Knowledge ingestion pipeline — load external documents into the
company's knowledge system.

Supports:
    - Plain text files (.txt, .md)
    - JSON files (.json)
    - CSV files (.csv) — first row as headers, each row as an entry
    - PDF files (.pdf) — requires pdfplumber (optional dependency)

Ingested content goes into the SQLite `knowledge` table and is included
in the next knowledge indexer run, becoming part of the distilled
institutional memory.

Usage:
    python scripts/ingest.py --company janky_games --file path/to/doc.md
    python scripts/ingest.py --company janky_games --dir path/to/docs/
"""

import csv
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


SUPPORTED_EXTENSIONS = {".txt", ".md", ".json", ".csv", ".pdf"}


def ingest_file(company_id: str, file_path: str,
                category: str = "ingested") -> dict:
    """
    Ingest a single file into the company's knowledge table.

    Returns:
        {"success": bool, "entries": int, "message": str}
    """
    path = Path(file_path)

    if not path.exists():
        return {"success": False, "entries": 0,
                "message": f"File not found: {path}"}

    ext = path.suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        return {"success": False, "entries": 0,
                "message": f"Unsupported file type: {ext}. "
                           f"Supported: {', '.join(SUPPORTED_EXTENSIONS)}"}

    try:
        if ext in (".txt", ".md"):
            entries = _ingest_text(path, category)
        elif ext == ".json":
            entries = _ingest_json(path, category)
        elif ext == ".csv":
            entries = _ingest_csv(path, category)
        elif ext == ".pdf":
            entries = _ingest_pdf(path, category)
        else:
            return {"success": False, "entries": 0,
                    "message": f"No handler for {ext}"}

        _write_entries(company_id, entries)

        return {"success": True, "entries": len(entries),
                "message": f"Ingested {len(entries)} entries from {path.name}"}

    except Exception as e:
        return {"success": False, "entries": 0,
                "message": f"Ingestion failed: {e}"}


def ingest_directory(company_id: str, dir_path: str,
                      category: str = "ingested") -> dict:
    """
    Ingest all supported files from a directory.

    Returns:
        {"success": bool, "files": int, "entries": int, "errors": list}
    """
    path = Path(dir_path)
    if not path.is_dir():
        return {"success": False, "files": 0, "entries": 0,
                "errors": [f"Not a directory: {path}"]}

    total_entries = 0
    total_files = 0
    errors = []

    for f in sorted(path.iterdir()):
        if f.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue
        if f.is_file():
            result = ingest_file(company_id, str(f), category)
            if result["success"]:
                total_files += 1
                total_entries += result["entries"]
            else:
                errors.append(result["message"])

    return {
        "success": len(errors) == 0,
        "files":   total_files,
        "entries": total_entries,
        "errors":  errors,
    }


# ── File type handlers ───────────────────────────────────────────────────────

def _ingest_text(path: Path, category: str) -> list[dict]:
    """Ingest a text/markdown file as a single knowledge entry."""
    content = path.read_text(encoding="utf-8")
    return [{
        "category": category,
        "title":    path.stem,
        "content":  content,
        "source":   str(path),
    }]


def _ingest_json(path: Path, category: str) -> list[dict]:
    """
    Ingest a JSON file. If it's an array of objects, each becomes an entry.
    If it's a single object, it becomes one entry.
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    entries = []

    if isinstance(data, list):
        for i, item in enumerate(data):
            if isinstance(item, dict):
                title = item.get("title", item.get("name", f"{path.stem}_{i}"))
                content = json.dumps(item, indent=2)
            else:
                title = f"{path.stem}_{i}"
                content = str(item)
            entries.append({
                "category": category,
                "title":    str(title),
                "content":  content,
                "source":   str(path),
            })
    elif isinstance(data, dict):
        entries.append({
            "category": category,
            "title":    data.get("title", path.stem),
            "content":  json.dumps(data, indent=2),
            "source":   str(path),
        })
    else:
        entries.append({
            "category": category,
            "title":    path.stem,
            "content":  str(data),
            "source":   str(path),
        })

    return entries


def _ingest_csv(path: Path, category: str) -> list[dict]:
    """Ingest a CSV file — each row becomes a knowledge entry."""
    entries = []
    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            title = row.get("title", row.get("name", f"{path.stem}_row{i}"))
            content = "\n".join(f"{k}: {v}" for k, v in row.items())
            entries.append({
                "category": category,
                "title":    str(title),
                "content":  content,
                "source":   str(path),
            })
    return entries


def _ingest_pdf(path: Path, category: str) -> list[dict]:
    """Ingest a PDF file — each page becomes a knowledge entry."""
    try:
        import pdfplumber
    except ImportError:
        raise ImportError(
            "PDF ingestion requires pdfplumber. Install: pip install pdfplumber"
        )

    entries = []
    with pdfplumber.open(path) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text()
            if text and text.strip():
                entries.append({
                    "category": category,
                    "title":    f"{path.stem}_page{i+1}",
                    "content":  text,
                    "source":   str(path),
                })
    return entries


# ── SQLite writer ────────────────────────────────────────────────────────────

def _write_entries(company_id: str, entries: list[dict]) -> None:
    """Write knowledge entries to SQLite."""
    from core.memory.writer import _db_path, _ensure_db_exists

    _ensure_db_exists(company_id)
    db = _db_path(company_id)
    now = datetime.now(timezone.utc).isoformat()

    with sqlite3.connect(str(db)) as conn:
        for entry in entries:
            conn.execute(
                """
                INSERT INTO knowledge
                    (company_id, category, title, content, source, added_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    company_id,
                    entry.get("category", "ingested"),
                    entry.get("title", ""),
                    entry.get("content", ""),
                    entry.get("source", ""),
                    now,
                ),
            )
