"""Core (non-GUI) logic for SplitPayPDF.

Config/appdata handling, filename/folder naming patterns, schema storage,
and the PDF operations (split, extract, merge). No tkinter imports here.
"""

import csv
import json
import os
import re
import subprocess
import sys
from datetime import datetime

import fitz  # PyMuPDF

# -------------------- App metadata --------------------

APP_NAME = "SplitPayPDF"
APP_VERSION = "1.1.0"
APP_DESCRIPTION = (
    "Split payroll PDFs into per-employee files and run everyday PDF tools "
    "(extract, merge) — fully local, no installation required."
)


class PdfError(Exception):
    """A PDF problem with a message that is safe to show a business user."""


# -------------------- App dirs / config --------------------


def get_appdata_folder():
    if os.name == "nt":
        base = os.getenv("APPDATA") or os.path.expanduser("~")
    else:
        base = os.getenv("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    folder = os.path.join(base, "SplitPayPDF")
    os.makedirs(folder, exist_ok=True)
    return folder


APPDATA_DIR = get_appdata_folder()
CONFIG_FILE = os.path.join(APPDATA_DIR, "splitpay_config.json")
APP_LOG_PATH = os.path.join(APPDATA_DIR, "app_log.txt")


def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_config(cfg):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def write_app_log(line: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with open(APP_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {line}\n")
    except Exception:
        pass


# -------------------- Utilities --------------------


def sanitize_filename(name: str) -> str:
    return re.sub(r"[^\w\s-]", "", name).strip().replace(" ", "_")


def normalize_folder_name(name: str) -> str:
    repl = {
        "č": "c",
        "ć": "c",
        "ž": "z",
        "š": "s",
        "đ": "d",
        "Č": "c",
        "Ć": "c",
        "Ž": "z",
        "Š": "s",
        "Đ": "d",
    }
    for k, v in repl.items():
        name = name.replace(k, v)
    name = re.sub(r"[^\w]", "", name)
    return name.lower()


def get_schema_folder():
    schema_dir = os.path.join(APPDATA_DIR, "Schemas")
    os.makedirs(schema_dir, exist_ok=True)
    return schema_dir


def list_schemas():
    schema_dir = get_schema_folder()
    return [f[:-5] for f in os.listdir(schema_dir) if f.endswith(".json")]


def _read_schema_file(path):
    """Read a schema JSON file, returning a dict or None on any failure.

    Never raises — a corrupt or unreadable schema logs the technical detail
    and returns None so callers can degrade gracefully instead of crashing.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            write_app_log(f"[schema-read-error] {path}: not a JSON object")
            return None
        return data
    except Exception as e:
        write_app_log(f"[schema-read-error] {path}: {e!r}")
        return None


def load_schema(name):
    path = os.path.join(get_schema_folder(), f"{name}.json")
    if not os.path.exists(path):
        return None
    return _read_schema_file(path)


def save_schema(name, file_pattern, folder_pattern):
    if not name:
        return
    schema_dir = get_schema_folder()
    path = os.path.join(schema_dir, f"{name}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "schema_name": name,
                "file_pattern": file_pattern,
                "folder_pattern": folder_pattern,
            },
            f,
            indent=2,
            ensure_ascii=False,
        )


def delete_schema(name):
    if not name or name == "None":
        return
    path = os.path.join(get_schema_folder(), f"{name}.json")
    if os.path.exists(path):
        os.remove(path)


def get_unique_auditlog_path(outdir: str) -> str:
    date_str = datetime.now().strftime("%Y-%m-%d")
    base = os.path.join(outdir, f"audit_log_{date_str}.csv")
    if not os.path.exists(base):
        return base
    counter = 1
    while True:
        candidate = os.path.join(outdir, f"audit_log_{date_str}_{counter}.csv")
        if not os.path.exists(candidate):
            return candidate
        counter += 1


def get_unique_path(base_path: str) -> str:
    """Return a unique filesystem path by adding _1, _2,... if needed."""
    if not os.path.exists(base_path):
        return base_path
    root, ext = os.path.splitext(base_path)
    counter = 1
    while True:
        candidate = f"{root}_{counter}{ext}"
        if not os.path.exists(candidate):
            return candidate
        counter += 1


AUDIT_FIELDS = ["Page", "Status", "Filename", "FolderRaw", "FolderName", "Note"]


def write_audit_csv(path: str, rows):
    """Write audit rows to CSV (utf-8 with BOM so Excel opens it correctly)."""
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=AUDIT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def open_folder(path: str, log=None):
    try:
        if os.name == "nt":
            subprocess.Popen(["explorer", os.path.realpath(path)])
        else:
            opener = "open" if sys.platform == "darwin" else "xdg-open"
            subprocess.Popen([opener, path])
    except Exception as e:
        if log:
            log(f"⚠ Failed to auto-open folder: {e}")


# -------------------- Pattern builder --------------------
# Supports:
#   [LINE 5]
#   [LINE 5(3)]
#   [LINE 5(3/8)]
# Line numbers are 0-based (matching the SAFE-mode debug output);
# character positions are 1-based.


LINE_TOKEN_RE = re.compile(r"\[LINE\s+(\d+)(?:\((\d+)(?:/(\d+))?\))?\]")


def _resolve_line_pattern(lines, pattern: str):
    """Substitute [LINE ...] tokens in ``pattern``.

    Returns ``(text, resolved_count)`` where ``resolved_count`` is the number
    of tokens that produced a non-empty value. Literal characters in the
    pattern (underscores, spaces, brackets, etc.) are preserved as-is; they do
    not count as resolved values. This lets callers tell the difference between
    "a real value was extracted" and "only literal separators remain".
    """
    resolved = 0

    def replace_token(match):
        nonlocal resolved
        line_no = int(match.group(1))
        start_pos = match.group(2)
        end_pos = match.group(3)

        if line_no < 0 or line_no >= len(lines):
            return ""

        text = lines[line_no]
        if start_pos:
            start = max(int(start_pos) - 1, 0)
            if end_pos:
                stop = int(end_pos)
                text = text[start:stop]
            else:
                text = text[start:]
        text = text.strip()
        if text:
            resolved += 1
        return text

    return LINE_TOKEN_RE.sub(replace_token, pattern or ""), resolved


def build_value_from_line_pattern(lines, pattern: str) -> str:
    value, _ = _resolve_line_pattern(lines, pattern)
    return value


def build_filename_from_line_pattern(lines, pattern: str) -> str:
    raw, resolved = _resolve_line_pattern(lines, pattern)

    # If the pattern relies on tokens but none of them produced a real value,
    # treat the page as unresolved — even if literal separators (e.g. "_",
    # spaces, brackets) would otherwise leave a non-empty string like "_.pdf".
    # Such pages must go to !manual_review, not be saved under a junk name.
    if LINE_TOKEN_RE.search(pattern or "") and resolved == 0:
        return ""

    if not raw:
        return ""
    if not raw.lower().endswith(".pdf"):
        raw += ".pdf"
    base, ext = os.path.splitext(raw)
    safe = sanitize_filename(base)
    if not safe:
        return ""
    return safe + ext


def get_page_lines(pdf_path: str, page_no: int):
    """Return the text lines of a single page (1-based page number)."""
    with fitz.open(pdf_path) as doc:
        if page_no < 1 or page_no > len(doc):
            raise ValueError(f"Page {page_no} out of range (1–{len(doc)}).")
        return doc.load_page(page_no - 1).get_text().splitlines()


# -------------------- PDF Tools naming (pure, testable) --------------------


def extraction_basename(inp_path: str) -> str:
    """Sanitized base name of the source PDF, used for extracted files."""
    base = os.path.splitext(os.path.basename(inp_path))[0]
    return sanitize_filename(base) or "document"


def extraction_filename(inp_path: str, page=None, page_from=None, page_to=None) -> str:
    """Operation-specific name for an extracted PDF.

    Single page  -> ``<source>_page_5.pdf``
    Page range   -> ``<source>_pages_5-10.pdf``
    """
    base = extraction_basename(inp_path)
    if page is not None:
        return f"{base}_page_{page}.pdf"
    return f"{base}_pages_{page_from}-{page_to}.pdf"


def merge_default_filename() -> str:
    """Default name for a merged PDF (merge-specific, dated)."""
    return f"merged_{datetime.now().strftime('%Y-%m-%d')}.pdf"


# -------------------- List ordering helper (pure) --------------------


def move_item(items, index, delta):
    """Return (new_list, new_index) after moving items[index] by delta (±1).

    Used by the merge list's Move up / Move down. No-op (returns the same list
    and index) if the move would fall outside the list.
    """
    n = len(items)
    if index is None or index < 0 or index >= n:
        return list(items), index
    target = index + delta
    if target < 0 or target >= n:
        return list(items), index
    out = list(items)
    out[index], out[target] = out[target], out[index]
    return out, target


# -------------------- PDF open / inspection (safety) --------------------


def _friendly_open_error(exc) -> str:
    """Map a low-level PDF open/read failure to a user-facing message."""
    msg = str(exc).lower()
    if "password" in msg or "encrypt" in msg:
        return (
            "This PDF is password-protected. Please provide an unlocked PDF "
            "and try again."
        )
    if any(k in msg for k in ("no such file", "not found", "does not exist")):
        return "The PDF file could not be found. Check the path and try again."
    return (
        "This file could not be opened as a PDF. It may be corrupted, "
        "incomplete, or not a PDF file."
    )


def open_pdf_checked(path: str):
    """Open a PDF, raising PdfError(friendly message) for common problems.

    Returns an open fitz document (caller must close it). Password-protected,
    corrupt, missing and non-PDF files all raise PdfError with a message that
    is safe to show a user; the technical detail is written to the app log.
    """
    try:
        doc = fitz.open(path)
    except Exception as e:
        write_app_log(f"[pdf-open-error] {path}: {e!r}")
        raise PdfError(_friendly_open_error(e)) from e

    if getattr(doc, "needs_pass", False):
        try:
            doc.close()
        except Exception:
            pass
        write_app_log(f"[pdf-open-error] {path}: password-protected")
        raise PdfError(
            "This PDF is password-protected. Please provide an unlocked PDF "
            "and try again."
        )
    return doc


def text_is_effectively_empty(samples) -> bool:
    """True if none of the sampled page texts contain any selectable text."""
    return not any((s or "").strip() for s in samples)


def sample_pdf_text(doc, pages: int = 3):
    """Return the text of the first `pages` pages (or fewer) of an open doc."""
    out = []
    for i in range(min(pages, len(doc))):
        out.append(doc.load_page(i).get_text())
    return out


def preflight_pdf(path: str, sample_pages: int = 3):
    """Inspect a PDF for GUI pre-checks.

    Returns {"page_count": int, "has_text": bool}. Raises PdfError for
    password-protected / corrupt / missing files (friendly message).
    """
    doc = open_pdf_checked(path)
    try:
        page_count = len(doc)
        samples = sample_pdf_text(doc, sample_pages)
        return {
            "page_count": page_count,
            "has_text": not text_is_effectively_empty(samples),
        }
    finally:
        try:
            doc.close()
        except Exception:
            pass


# -------------------- Full payroll engine --------------------


def split_pdf_full(
    inp_path: str,
    out_dir: str,
    file_pattern: str,
    folder_pattern: str,
    save_to_folders: bool,
    safe_mode: bool,
    auto_open: bool,
    log_callback=None,
    progress_callback=None,
    cancel_event=None,
):
    def log(msg: str):
        write_app_log(msg)
        if log_callback:
            log_callback(msg)

    log(f"🕒 Split started: {inp_path}")

    doc = open_pdf_checked(inp_path)
    total_pages = len(doc)
    if total_pages == 0:
        log("⚠ PDF has no pages.")
        doc.close()
        return {
            "total": 0,
            "success": 0,
            "failed": 0,
            "audit_path": None,
            "rows": [],
            "cancelled": False,
        }

    if not safe_mode:
        os.makedirs(out_dir, exist_ok=True)
        review_dir = os.path.join(out_dir, "!manual_review")
        os.makedirs(review_dir, exist_ok=True)
    else:
        review_dir = None

    audit_rows = []
    success = 0
    failed = 0
    cancelled = False

    for page_index in range(total_pages):
        if cancel_event is not None and cancel_event.is_set():
            cancelled = True
            log("⛔ Cancelled by user — stopping before next page.")
            break

        page_no = page_index + 1
        if progress_callback:
            progress_callback(page_no, total_pages)

        page = doc.load_page(page_index)
        text = page.get_text()
        lines = text.splitlines()

        if safe_mode and page_no == 1:
            log(f"[DEBUG] --- PAGE {page_no} ---")
            for idx, line in enumerate(lines):
                log(f"  LINE {idx}: {line}")
            log("–––––––––––––––––––––––––––––––––––––––")

        filename = build_filename_from_line_pattern(lines, file_pattern)
        raw_folder = build_value_from_line_pattern(lines, folder_pattern)
        foldername = normalize_folder_name(raw_folder) if raw_folder else ""

        if not filename or filename == ".pdf":
            failed += 1
            excerpt = text.replace("\n", " ")[:300]
            log(f"⚠ Page {page_no}: no valid filename → manual review needed")
            write_app_log(f"[manual_review] Page {page_no} excerpt: {excerpt}")

            if safe_mode:
                audit_rows.append(
                    {
                        "Page": page_no,
                        "Status": "Failed (SAFE mode)",
                        "Filename": "",
                        "FolderRaw": raw_folder or "",
                        "FolderName": foldername or "",
                        "Note": "Would be sent to !manual_review",
                    }
                )
                continue

            new_doc = fitz.open()
            new_doc.insert_pdf(doc, from_page=page_index, to_page=page_index)
            review_name = f"Unmatched_Page_{page_no}.pdf"
            review_path = os.path.join(review_dir, review_name)
            new_doc.save(review_path)
            new_doc.close()

            audit_rows.append(
                {
                    "Page": page_no,
                    "Status": "Failed",
                    "Filename": "",
                    "FolderRaw": raw_folder or "",
                    "FolderName": foldername or "",
                    "Note": f"Sent to {review_name}",
                }
            )
            continue

        if save_to_folders:
            if foldername:
                target_dir = os.path.join(out_dir, foldername)
            else:
                target_dir = os.path.join(out_dir, "unknown")
        else:
            target_dir = out_dir

        if safe_mode:
            final_name = filename
            audit_rows.append(
                {
                    "Page": page_no,
                    "Status": "OK (SAFE mode)",
                    "Filename": final_name,
                    "FolderRaw": raw_folder or "",
                    "FolderName": foldername or "",
                    "Note": "Would be saved",
                }
            )
            log(
                f"🔎 [SAFE] Page {page_no}: would save as "
                f"{os.path.join(target_dir, final_name)}"
            )
            continue

        os.makedirs(target_dir, exist_ok=True)

        final_name = filename
        base, ext = os.path.splitext(final_name)
        counter = 1
        while os.path.exists(os.path.join(target_dir, final_name)):
            final_name = f"{base}_{counter}{ext}"
            counter += 1

        out_path = os.path.join(target_dir, final_name)
        new_doc = fitz.open()
        new_doc.insert_pdf(doc, from_page=page_index, to_page=page_index)
        new_doc.save(out_path)
        new_doc.close()

        success += 1
        log(f"✅ Page {page_no}: saved as {out_path}")
        audit_rows.append(
            {
                "Page": page_no,
                "Status": "OK",
                "Filename": final_name,
                "FolderRaw": raw_folder or "",
                "FolderName": foldername or "",
                "Note": "",
            }
        )

    doc.close()

    audit_path = None
    if not safe_mode and audit_rows:
        audit_path = get_unique_auditlog_path(out_dir)
        try:
            write_audit_csv(audit_path, audit_rows)
            log(f"🧾 Audit log saved: {audit_path}")
        except Exception as e:
            log(f"❌ Failed to write audit log: {e}")
            audit_path = None
    elif safe_mode:
        log("SAFE MODE: no audit CSV written.")

    log(
        f"🏁 Split finished. Pages={total_pages}, Success={success}, "
        f"Manual review={failed}" + (", CANCELLED" if cancelled else "")
    )

    if (not safe_mode) and auto_open and not cancelled:
        open_folder(out_dir, log)

    return {
        "total": total_pages,
        "success": success,
        "failed": failed,
        "audit_path": audit_path,
        "rows": audit_rows,
        "cancelled": cancelled,
    }


# -------------------- PDF Tools core functions --------------------


def extract_pages(
    inp_path: str,
    out_dir: str,
    single_page: str,
    range_from: str,
    range_to: str,
    per_page: bool,
    auto_open: bool,
    log_callback=None,
    progress_callback=None,
    cancel_event=None,
):
    def log(msg: str):
        write_app_log(msg)
        if log_callback:
            log_callback(msg)

    log(f"🕒 Extract started: {inp_path}")
    doc = open_pdf_checked(inp_path)
    total = len(doc)
    if total == 0:
        log("⚠ PDF has no pages.")
        doc.close()
        return

    os.makedirs(out_dir, exist_ok=True)

    try:
        if single_page:
            p = int(single_page)
            if p < 1 or p > total:
                raise ValueError("Page number out of range.")
            if progress_callback:
                progress_callback(1, 1)
            new_doc = fitz.open()
            new_doc.insert_pdf(doc, from_page=p - 1, to_page=p - 1)
            out_name = extraction_filename(inp_path, page=p)
            final_path = get_unique_path(os.path.join(out_dir, out_name))
            new_doc.save(final_path)
            new_doc.close()
            log(f"✅ Extracted single page {p} → {final_path}")

        elif range_from and range_to:
            a = int(range_from)
            b = int(range_to)
            if a < 1 or b > total or a > b:
                raise ValueError("Invalid page range.")

            if per_page:
                count = b - a + 1
                for done, p in enumerate(range(a, b + 1), start=1):
                    if cancel_event is not None and cancel_event.is_set():
                        log("⛔ Extract cancelled by user.")
                        break
                    if progress_callback:
                        progress_callback(done, count)
                    new_doc = fitz.open()
                    new_doc.insert_pdf(doc, from_page=p - 1, to_page=p - 1)
                    out_name = extraction_filename(inp_path, page=p)
                    final_path = get_unique_path(os.path.join(out_dir, out_name))
                    new_doc.save(final_path)
                    new_doc.close()
                    log(f"✅ Extracted page {p} → {final_path}")
            else:
                if progress_callback:
                    progress_callback(1, 1)
                new_doc = fitz.open()
                new_doc.insert_pdf(doc, from_page=a - 1, to_page=b - 1)
                out_name = extraction_filename(inp_path, page_from=a, page_to=b)
                final_path = get_unique_path(os.path.join(out_dir, out_name))
                new_doc.save(final_path)
                new_doc.close()
                log(f"✅ Extracted pages {a}-{b} → {final_path}")
        else:
            raise ValueError("Specify single page or a page range.")
    finally:
        doc.close()

    if auto_open:
        open_folder(out_dir, log)


def merge_pdfs(
    files,
    out_dir: str,
    filename: str,
    auto_open: bool,
    log_callback=None,
    progress_callback=None,
    cancel_event=None,
):
    def log(msg: str):
        write_app_log(msg)
        if log_callback:
            log_callback(msg)

    if not files:
        return

    log(f"🕒 Merge started: {len(files)} files.")
    os.makedirs(out_dir, exist_ok=True)

    if filename:
        if not filename.lower().endswith(".pdf"):
            filename += ".pdf"
        base_out = os.path.join(out_dir, filename)
    else:
        base_out = os.path.join(out_dir, merge_default_filename())

    final_out = get_unique_path(base_out)

    total = len(files)
    merged = fitz.open()
    cancelled = False
    try:
        for i, p in enumerate(files, start=1):
            if cancel_event is not None and cancel_event.is_set():
                cancelled = True
                log("⛔ Merge cancelled by user.")
                break
            if progress_callback:
                progress_callback(i, total)
            log(f"  + {p}")
            src = open_pdf_checked(p)
            try:
                merged.insert_pdf(src)
            finally:
                try:
                    src.close()
                except Exception:
                    pass
        if not cancelled:
            merged.save(final_out)
            log(f"✅ Merged PDF saved: {final_out}")
    finally:
        merged.close()

    if auto_open and not cancelled:
        open_folder(out_dir, log)
