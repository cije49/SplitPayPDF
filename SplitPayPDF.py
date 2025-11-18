import fitz
import re
import os
import json
import subprocess
from datetime import datetime
import sys
import tkinter as tk
from tkinter import (
    filedialog,
    messagebox,
    scrolledtext,
    ttk,
    simpledialog,
)
import pandas as pd
import threading

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


def load_schema(name):
    path = os.path.join(get_schema_folder(), f"{name}.json")
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


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


# -------------------- Pattern builder --------------------
# Supports:
#   [LINE 5]
#   [LINE 5(3)]
#   [LINE 5(3/8)]


LINE_TOKEN_RE = re.compile(r"\[LINE\s+(\d+)(?:\((\d+)(?:/(\d+))?\))?\]")


def build_value_from_line_pattern(lines, pattern: str) -> str:
    def replace_token(match):
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
        return text.strip()

    return LINE_TOKEN_RE.sub(replace_token, pattern or "")


def build_filename_from_line_pattern(lines, pattern: str) -> str:
    raw = build_value_from_line_pattern(lines, pattern)
    if not raw:
        return ""
    if not raw.lower().endswith(".pdf"):
        raw += ".pdf"
    base, ext = os.path.splitext(raw)
    safe = sanitize_filename(base)
    return safe + ext


# -------------------- Help dialog helper (auto sizing) --------------------


def show_help_dialog(parent, title: str, text: str):
    win = tk.Toplevel(parent)
    win.title(title)
    win.transient(parent)
    win.grab_set()

    frm = ttk.Frame(win, padding=10)
    frm.pack(fill="both", expand=True)

    lbl = tk.Label(
        frm,
        text=text,
        justify="left",
        anchor="nw",
        wraplength=420,
    )
    lbl.pack(fill="both", expand=True, pady=(0, 8))

    btn = ttk.Button(frm, text="OK", command=win.destroy)
    btn.pack(pady=(0, 4))

    win.update_idletasks()

    lw = lbl.winfo_reqwidth()
    lh = lbl.winfo_reqheight()
    w = min(max(lw + 40, 350), 600)
    h = min(max(lh + 80, 180), 500)

    try:
        px = parent.winfo_rootx()
        py = parent.winfo_rooty()
        pw = parent.winfo_width()
        ph = parent.winfo_height()
        if pw <= 1 or ph <= 1:
            pw, ph = 800, 600
    except Exception:
        px, py, pw, ph = 100, 100, 800, 600

    x = px + (pw - w) // 2
    y = py + (ph - h) // 2
    win.geometry(f"{w}x{h}+{x}+{y}")

    def on_escape(event=None):
        win.destroy()

    win.bind("<Escape>", on_escape)
    win.focus_set()


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
):
    def log(msg: str):
        write_app_log(msg)
        if log_callback:
            log_callback(msg)

    log(f"🕒 Split started: {inp_path}")

    doc = fitz.open(inp_path)
    total_pages = len(doc)
    if total_pages == 0:
        log("⚠ PDF has no pages.")
        doc.close()
        return {"total": 0, "success": 0, "failed": 0, "audit_path": None}

    if not safe_mode:
        os.makedirs(out_dir, exist_ok=True)
        review_dir = os.path.join(out_dir, "!manual_review")
        os.makedirs(review_dir, exist_ok=True)
    else:
        review_dir = None

    audit_rows = []
    success = 0
    failed = 0

    for page_index in range(total_pages):
        page_no = page_index + 1
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
    if not safe_mode:
        audit_path = get_unique_auditlog_path(out_dir)
        try:
            df = pd.DataFrame(audit_rows)
            df.to_csv(audit_path, index=False, encoding="utf-8-sig")
            log(f"🧾 Audit log saved: {audit_path}")
        except Exception as e:
            log(f"❌ Failed to write audit log: {e}")
            audit_path = None
    else:
        log("SAFE MODE: no audit CSV written.")

    log(
        f"🏁 Split finished. Pages={total_pages}, Success={success}, Manual review={failed}"
    )

    if (not safe_mode) and auto_open:
        try:
            if os.name == "nt":
                subprocess.Popen(["explorer", os.path.realpath(out_dir)])
            else:
                opener = "open" if sys.platform == "darwin" else "xdg-open"
                subprocess.Popen([opener, out_dir])
        except Exception as e:
            log(f"⚠ Failed to auto-open folder: {e}")

    return {
        "total": total_pages,
        "success": success,
        "failed": failed,
        "audit_path": audit_path,
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
):
    def log(msg: str):
        write_app_log(msg)
        if log_callback:
            log_callback(msg)

    log(f"🕒 Extract started: {inp_path}")
    doc = fitz.open(inp_path)
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
            new_doc = fitz.open()
            new_doc.insert_pdf(doc, from_page=p - 1, to_page=p - 1)
            base_name = os.path.splitext(os.path.basename(inp_path))[0]
            out_name = f"{base_name}_page_{p}.pdf"
            final_path = get_unique_path(os.path.join(out_dir, out_name))
            new_doc.save(final_path)
            new_doc.close()
            log(f"✅ Extracted single page {p} → {final_path}")

        elif range_from and range_to:
            a = int(range_from)
            b = int(range_to)
            if a < 1 or b > total or a > b:
                raise ValueError("Invalid page range.")
            base_name = os.path.splitext(os.path.basename(inp_path))[0]

            if per_page:
                for p in range(a, b + 1):
                    new_doc = fitz.open()
                    new_doc.insert_pdf(doc, from_page=p - 1, to_page=p - 1)
                    out_name = f"{base_name}_page_{p}.pdf"
                    final_path = get_unique_path(os.path.join(out_dir, out_name))
                    new_doc.save(final_path)
                    new_doc.close()
                    log(f"✅ Extracted page {p} → {final_path}")
            else:
                new_doc = fitz.open()
                new_doc.insert_pdf(doc, from_page=a - 1, to_page=b - 1)
                out_name = f"{base_name}_pages_{a}-{b}.pdf"
                final_path = get_unique_path(os.path.join(out_dir, out_name))
                new_doc.save(final_path)
                new_doc.close()
                log(f"✅ Extracted pages {a}-{b} → {final_path}")
        else:
            raise ValueError("Specify single page or a page range.")
    finally:
        doc.close()

    if auto_open:
        try:
            if os.name == "nt":
                subprocess.Popen(["explorer", os.path.realpath(out_dir)])
            else:
                opener = "open" if sys.platform == "darwin" else "xdg-open"
                subprocess.Popen([opener, out_dir])
        except Exception as e:
            log(f"⚠ Failed to auto-open folder: {e}")


def merge_pdfs(
    files,
    out_dir: str,
    filename: str,
    auto_open: bool,
    log_callback=None,
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
        date_str = datetime.now().strftime("%Y-%m-%d")
        base_out = os.path.join(out_dir, f"merged_{date_str}.pdf")

    final_out = get_unique_path(base_out)

    merged = fitz.open()
    try:
        for p in files:
            log(f"  + {p}")
            with fitz.open(p) as src:
                merged.insert_pdf(src)
        merged.save(final_out)
        log(f"✅ Merged PDF saved: {final_out}")
    finally:
        merged.close()

    if auto_open:
        try:
            if os.name == "nt":
                subprocess.Popen(["explorer", os.path.realpath(out_dir)])
            else:
                opener = "open" if sys.platform == "darwin" else "xdg-open"
                subprocess.Popen([opener, out_dir])
        except Exception as e:
            log(f"⚠ Failed to auto-open folder: {e}")


# -------------------- GUI --------------------


def run_gui():
    cfg = load_config()

    default_width = cfg.get("window_width", 1000)
    default_height = cfg.get("window_height", 800)

    root = tk.Tk()
    root.title("SplitPayPDF Engine + PDF Tools")

    root.update_idletasks()
    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()
    w = default_width
    h = default_height
    x = (sw - w) // 2
    y = (sh - h) // 2
    root.geometry(f"{w}x{h}+{x}+{y}")

    main = ttk.Frame(root)
    main.pack(fill="both", expand=True, padx=8, pady=8)
    main.rowconfigure(1, weight=1)
    main.columnconfigure(0, weight=1)

    notebook = ttk.Notebook(main)
    notebook.grid(row=0, column=0, sticky="nsew")

    # ---------------- Shared log box ----------------
    log_box = scrolledtext.ScrolledText(main, wrap=tk.WORD, height=12)
    log_box.grid(row=1, column=0, sticky="nsew", padx=4, pady=8)

    def append_log(msg: str):
        log_box.insert(tk.END, f"{datetime.now().strftime('%H:%M:%S')}  {msg}\n")
        log_box.see(tk.END)
        log_box.update_idletasks()
        write_app_log(msg)

    # ============ TAB 1: Payroll Splitter ============
    tab_pay = ttk.Frame(notebook)
    notebook.add(tab_pay, text="Payroll Splitter")

    for c in range(3):
        tab_pay.columnconfigure(c, weight=1 if c == 1 else 0)
    tab_pay.rowconfigure(7, weight=1)

    ttk.Label(tab_pay, text="Input PDF:").grid(
        row=0, column=0, sticky="w", padx=4, pady=4
    )
    pay_in = tk.StringVar(value=cfg.get("last_input", ""))
    ttk.Entry(tab_pay, textvariable=pay_in, width=70).grid(
        row=0, column=1, sticky="ew", padx=4, pady=4
    )
    ttk.Button(
        tab_pay,
        text="Browse",
        command=lambda: pay_in.set(
            filedialog.askopenfilename(filetypes=[("PDF files", "*.pdf")])
            or pay_in.get()
        ),
    ).grid(row=0, column=2, padx=4, pady=4)

    ttk.Label(tab_pay, text="Output folder:").grid(
        row=1, column=0, sticky="w", padx=4, pady=4
    )
    pay_out = tk.StringVar(value=cfg.get("last_output", ""))
    ttk.Entry(tab_pay, textvariable=pay_out, width=70).grid(
        row=1, column=1, sticky="ew", padx=4, pady=4
    )
    ttk.Button(
        tab_pay,
        text="Browse",
        command=lambda: pay_out.set(
            filedialog.askdirectory() or pay_out.get()
        ),
    ).grid(row=1, column=2, padx=4, pady=4)

    auto_open = tk.BooleanVar(value=cfg.get("auto_open", True))
    save_to_folders = tk.BooleanVar(value=cfg.get("save_to_folders", True))
    debug_safe = tk.BooleanVar(value=cfg.get("debug_safe", True))

    ttk.Checkbutton(
        tab_pay,
        text="Auto-open output folder when done",
        variable=auto_open,
    ).grid(row=2, column=0, columnspan=3, sticky="w", padx=4)

    ttk.Checkbutton(
        tab_pay,
        text="Save each PDF to employee folder (folder pattern)",
        variable=save_to_folders,
    ).grid(row=3, column=0, columnspan=3, sticky="w", padx=4)

    safe_cb = ttk.Checkbutton(
        tab_pay,
        text="SAFE debug mode (no folders / no PDFs / no audit CSV)",
        variable=debug_safe,
    )
    safe_cb.grid(row=4, column=0, columnspan=2, sticky="w", padx=4)

    def safe_help():
        text = (
            "Safe Mode Help\n\n"
            "In SAFE mode, the splitter simulates the entire process:\n"
            "- No folders are created\n"
            "- No PDFs are written\n"
            "- No audit CSV is saved\n\n"
            "You can review everything in the log before running for real."
        )
        show_help_dialog(root, "Safe Mode Help", text)

    ttk.Button(tab_pay, text="?", width=2, command=safe_help).grid(
        row=4, column=2, sticky="e", padx=4, pady=4
    )

    schema_frame = ttk.LabelFrame(tab_pay, text="Schema / Naming Patterns")
    schema_frame.grid(row=5, column=0, columnspan=3, sticky="ew", padx=4, pady=8)
    schema_frame.columnconfigure(1, weight=1)

    selected_schema = tk.StringVar(value=cfg.get("last_schema", "None"))
    existing_schemas = ["None"] + list_schemas()
    if selected_schema.get() not in existing_schemas:
        selected_schema.set("None")

    ttk.Label(schema_frame, text="Active schema:").grid(
        row=0, column=0, sticky="w", padx=4, pady=4
    )
    schema_combo = ttk.Combobox(
        schema_frame,
        textvariable=selected_schema,
        values=existing_schemas,
        state="readonly",
        width=25,
    )
    schema_combo.grid(row=0, column=1, sticky="w", padx=4, pady=4)

    default_pattern = "[LINE 1][LINE 2]_[LINE 3]_[LINE 43(17)].pdf"
    file_pattern_var = tk.StringVar(value=cfg.get("file_pattern", default_pattern))
    folder_pattern_var = tk.StringVar(
        value=cfg.get("folder_pattern", cfg.get("file_pattern", default_pattern))
    )
    lock_patterns = tk.BooleanVar(value=cfg.get("pattern_locked", False))

    def do_save_schema():
        name = simpledialog.askstring("Save Schema", "Enter schema name:")
        if not name:
            return
        save_schema(name, file_pattern_var.get(), folder_pattern_var.get())
        vals = ["None"] + list_schemas()
        schema_combo["values"] = vals
        selected_schema.set(name)
        schema_combo.set(name)
        cfg["last_schema"] = name
        save_config(cfg)
        messagebox.showinfo("Saved", f"Schema '{name}' saved.")

    def do_remove_schema():
        name = selected_schema.get()
        if not name or name == "None":
            messagebox.showinfo("Remove Schema", "No schema selected.")
            return
        if not messagebox.askyesno("Confirm", f"Delete schema '{name}'?"):
            return
        delete_schema(name)
        vals = ["None"] + list_schemas()
        schema_combo["values"] = vals
        selected_schema.set("None")
        schema_combo.set("None")
        cfg["last_schema"] = "None"
        save_config(cfg)
        messagebox.showinfo("Removed", f"Schema '{name}' removed.")

    save_btn = ttk.Button(schema_frame, text="💾 Save Schema", command=do_save_schema)
    save_btn.grid(row=0, column=2, sticky="w", padx=4, pady=4)

    def save_help():
        text = (
            "Save Schema Help\n\n"
            "When you adjust your file/folder naming patterns, click\n"
            "“Save Schema” to store them under a name for future use.\n\n"
            "Schemas are saved in your AppData folder under:\n"
            "  SplitPayPDF/Schemas\n\n"
            "You must save the schema to apply changes."
        )
        show_help_dialog(root, "Save Schema Help", text)

    ttk.Button(schema_frame, text="?", width=2, command=save_help).grid(
        row=0, column=3, sticky="e", padx=2, pady=4
    )

    remove_btn = ttk.Button(
        schema_frame, text="🗑 Remove Schema", command=do_remove_schema
    )
    remove_btn.grid(row=0, column=4, sticky="w", padx=4, pady=4)

    def remove_help():
        text = (
            "Remove Schema Help\n\n"
            "This deletes the selected schema file from your\n"
            "SplitPayPDF/Schemas folder in AppData.\n\n"
            "This action cannot be undone."
        )
        show_help_dialog(root, "Remove Schema Help", text)

    ttk.Button(schema_frame, text="?", width=2, command=remove_help).grid(
        row=0, column=5, sticky="e", padx=2, pady=4
    )

    adv_frame = ttk.LabelFrame(schema_frame, text="Patterns")
    adv_frame.grid(row=1, column=0, columnspan=6, sticky="ew", padx=4, pady=4)
    adv_frame.columnconfigure(1, weight=1)

    ttk.Label(adv_frame, text="File naming pattern:").grid(
        row=0, column=0, sticky="w", padx=4, pady=2
    )
    file_entry = ttk.Entry(adv_frame, textvariable=file_pattern_var, width=60)
    file_entry.grid(row=0, column=1, sticky="ew", padx=4, pady=2)

    def file_pattern_help():
        text = (
            "File Naming Pattern Help\n\n"
            "You can build file names using line-based tokens from the PDF:\n"
            "[LINE X]         → whole line X\n"
            "[LINE X(Y)]      → from character Y\n"
            "[LINE X(Y/Z)]    → characters Y–Z\n\n"
            "Examples:\n"
            "[LINE 1][LINE 2]_[LINE 3].pdf\n"
            "[LINE 43(17/26)]_neto.pdf\n\n"
            "You can mix tokens with text freely."
        )
        show_help_dialog(root, "File Naming Pattern Help", text)

    ttk.Button(adv_frame, text="?", width=2, command=file_pattern_help).grid(
        row=0, column=2, sticky="e", padx=4, pady=2
    )

    ttk.Label(adv_frame, text="Folder naming pattern:").grid(
        row=1, column=0, sticky="w", padx=4, pady=2
    )
    folder_entry = ttk.Entry(adv_frame, textvariable=folder_pattern_var, width=60)
    folder_entry.grid(row=1, column=1, sticky="ew", padx=4, pady=2)

    def folder_pattern_help():
        text = (
            "Folder Naming Pattern Help\n\n"
            "Folder patterns use the same [LINE X(Y/Z)] logic as files.\n"
            "Example:\n"
            "[LINE 3]_[LINE 1(1/3)] → Burton_228\n\n"
            "Folder names are normalized:\n"
            "- Special characters removed\n"
            "- Spaces removed\n"
            "- Lowercased (e.g. 'John Doe' → 'johndoe')."
        )
        show_help_dialog(root, "Folder Naming Pattern Help", text)

    ttk.Button(adv_frame, text="?", width=2, command=folder_pattern_help).grid(
        row=1, column=2, sticky="e", padx=4, pady=2
    )

    def apply_lock_state():
        state = "readonly" if lock_patterns.get() else "normal"
        file_entry.config(state=state)
        folder_entry.config(state=state)
        save_btn.config(state="disabled" if lock_patterns.get() else "normal")
        remove_btn.config(state="disabled" if lock_patterns.get() else "normal")
        cfg["pattern_locked"] = lock_patterns.get()
        save_config(cfg)

    lock_cb = ttk.Checkbutton(
        adv_frame,
        text="Lock naming patterns",
        variable=lock_patterns,
        command=apply_lock_state,
    )
    lock_cb.grid(row=2, column=0, columnspan=2, sticky="w", padx=4, pady=4)

    def lock_help():
        text = (
            "Lock Patterns Help\n\n"
            "When enabled, file and folder naming patterns\n"
            "are locked for editing, and schema save/remove\n"
            "is disabled.\n\n"
            "Use this to avoid accidental changes before a run."
        )
        show_help_dialog(root, "Lock Patterns Help", text)

    ttk.Button(adv_frame, text="?", width=2, command=lock_help).grid(
        row=2, column=2, sticky="e", padx=4, pady=4
    )

    apply_lock_state()

    def on_schema_selected(event=None):
        name = selected_schema.get()
        if not name or name == "None":
            return
        data = load_schema(name)
        if not data:
            return
        if not lock_patterns.get():
            fp = data.get("file_pattern")
            if fp:
                file_pattern_var.set(fp)
            fp2 = data.get("folder_pattern")
            if fp2 is not None:
                folder_pattern_var.set(fp2)

    schema_combo.bind("<<ComboboxSelected>>", on_schema_selected)

    def run_splitter():
        inp = pay_in.get().strip()
        if not inp or not os.path.isfile(inp):
            messagebox.showerror("Error", "Please select a valid payroll PDF.")
            return

        out_dir = pay_out.get().strip()
        if not out_dir:
            out_dir = os.path.join(os.path.dirname(inp), "output_pdfs")
            pay_out.set(out_dir)

        cfg["last_input"] = inp
        cfg["last_output"] = out_dir
        cfg["auto_open"] = auto_open.get()
        cfg["save_to_folders"] = save_to_folders.get()
        cfg["debug_safe"] = debug_safe.get()
        cfg["file_pattern"] = file_pattern_var.get()
        cfg["folder_pattern"] = folder_pattern_var.get()
        cfg["last_schema"] = selected_schema.get()
        save_config(cfg)

        file_pat = file_pattern_var.get()
        folder_pat = folder_pattern_var.get()
        schema_name = selected_schema.get()
        if schema_name and schema_name != "None":
            data = load_schema(schema_name)
            if data and not lock_patterns.get():
                if data.get("file_pattern"):
                    file_pat = data["file_pattern"]
                if "folder_pattern" in data:
                    folder_pat = data["folder_pattern"]

        append_log(f"▶ Run on: {inp}")
        append_log(f"Output: {out_dir}")
        append_log(f"Schema: {schema_name}")
        append_log(f"File pattern: {file_pat}")
        append_log(f"Folder pattern: {folder_pat}")
        append_log(f"SAFE mode: {debug_safe.get()}")

        def worker():
            try:
                res = split_pdf_full(
                    inp_path=inp,
                    out_dir=out_dir,
                    file_pattern=file_pat,
                    folder_pattern=folder_pat,
                    save_to_folders=save_to_folders.get(),
                    safe_mode=debug_safe.get(),
                    auto_open=auto_open.get(),
                    log_callback=append_log,
                )
                if res["total"] == 0:
                    messagebox.showwarning("Done", "PDF had no pages.")
                    return

                msg = (
                    f"Split completed.\n\n"
                    f"Pages: {res['total']}\n"
                    f"Success: {res['success']}\n"
                    f"Manual review: {res['failed']}\n"
                )
                if not debug_safe.get() and res["audit_path"]:
                    msg += f"\nAudit log:\n{res['audit_path']}"

                messagebox.showinfo("Done", msg)
            except Exception as e:
                append_log(f"❌ ERROR during split: {e}")
                messagebox.showerror("Error", f"An error occurred:\n{e}")

        threading.Thread(target=worker, daemon=True).start()

    ttk.Button(
        tab_pay, text="Run Payroll Splitter", command=run_splitter
    ).grid(row=6, column=0, columnspan=3, sticky="ew", padx=4, pady=4)

    # ============ TAB 2: PDF Tools ============
    tab_tools = ttk.Frame(notebook)
    notebook.add(tab_tools, text="PDF Tools")

    for c in range(4):
        tab_tools.columnconfigure(c, weight=1 if c in (1, 3) else 0)

    # Left: Extract
    extract_frame = ttk.LabelFrame(tab_tools, text="Extract Pages")
    extract_frame.grid(row=0, column=0, columnspan=2, sticky="nsew", padx=4, pady=4)
    extract_frame.columnconfigure(1, weight=1)

    tools_ext_in = tk.StringVar(value=cfg.get("tools_ext_in", ""))
    tools_ext_out = tk.StringVar(value=cfg.get("tools_ext_out", ""))
    ext_single_page = tk.StringVar()
    ext_range_from = tk.StringVar()
    ext_range_to = tk.StringVar()
    ext_per_page = tk.BooleanVar(value=cfg.get("ext_per_page", False))
    tools_auto_open = tk.BooleanVar(value=cfg.get("tools_auto_open", True))

    ttk.Label(extract_frame, text="Input PDF:").grid(
        row=0, column=0, sticky="w", padx=4, pady=2
    )
    ttk.Entry(extract_frame, textvariable=tools_ext_in).grid(
        row=0, column=1, sticky="ew", padx=4, pady=2
    )
    ttk.Button(
        extract_frame,
        text="Browse",
        command=lambda: tools_ext_in.set(
            filedialog.askopenfilename(filetypes=[("PDF files", "*.pdf")])
            or tools_ext_in.get()
        ),
    ).grid(row=0, column=2, padx=4, pady=2)

    ttk.Label(extract_frame, text="Output folder:").grid(
        row=1, column=0, sticky="w", padx=4, pady=2
    )
    ttk.Entry(extract_frame, textvariable=tools_ext_out).grid(
        row=1, column=1, sticky="ew", padx=4, pady=2
    )
    ttk.Button(
        extract_frame,
        text="Browse",
        command=lambda: tools_ext_out.set(
            filedialog.askdirectory() or tools_ext_out.get()
        ),
    ).grid(row=1, column=2, padx=4, pady=2)

    ttk.Label(extract_frame, text="Single page:").grid(
        row=2, column=0, sticky="w", padx=4, pady=2
    )
    ttk.Entry(extract_frame, textvariable=ext_single_page, width=8).grid(
        row=2, column=1, sticky="w", padx=4, pady=2
    )

    ttk.Label(extract_frame, text="Range (from–to):").grid(
        row=3, column=0, sticky="w", padx=4, pady=2
    )
    ttk.Entry(extract_frame, textvariable=ext_range_from, width=5).grid(
        row=3, column=1, sticky="w", padx=(4, 0), pady=2
    )
    ttk.Label(extract_frame, text="–").grid(row=3, column=1, sticky="w", padx=(60, 0))
    ttk.Entry(extract_frame, textvariable=ext_range_to, width=5).grid(
        row=3, column=1, sticky="w", padx=(80, 0), pady=2
    )

    ttk.Checkbutton(
        extract_frame,
        text="One page per PDF (for range)",
        variable=ext_per_page,
    ).grid(row=4, column=0, columnspan=3, sticky="w", padx=4, pady=2)

    ttk.Checkbutton(
        extract_frame,
        text="Auto-open output folder when done",
        variable=tools_auto_open,
    ).grid(row=5, column=0, columnspan=3, sticky="w", padx=4, pady=2)

    def do_extract():
        inp = tools_ext_in.get().strip()
        if not inp or not os.path.isfile(inp):
            messagebox.showerror("Error", "Select a valid input PDF.")
            return
        out_dir = tools_ext_out.get().strip()
        if not out_dir:
            out_dir = os.path.dirname(inp)
            tools_ext_out.set(out_dir)

        cfg["tools_ext_in"] = inp
        cfg["tools_ext_out"] = out_dir
        cfg["ext_per_page"] = ext_per_page.get()
        cfg["tools_auto_open"] = tools_auto_open.get()
        save_config(cfg)

        single = ext_single_page.get().strip()
        r_from = ext_range_from.get().strip()
        r_to = ext_range_to.get().strip()

        append_log(f"▶ Extract from: {inp}")
        append_log(f"Output: {out_dir}")
        if single:
            append_log(f"Single page: {single}")
        if r_from and r_to:
            append_log(f"Range: {r_from}–{r_to}")
        append_log(f"Per-page: {ext_per_page.get()}")

        def worker():
            try:
                extract_pages(
                    inp_path=inp,
                    out_dir=out_dir,
                    single_page=single,
                    range_from=r_from,
                    range_to=r_to,
                    per_page=ext_per_page.get(),
                    auto_open=tools_auto_open.get(),
                    log_callback=append_log,
                )
                messagebox.showinfo("Done", "Extract completed.")
            except Exception as e:
                append_log(f"❌ Extract error: {e}")
                messagebox.showerror("Error", str(e))

        threading.Thread(target=worker, daemon=True).start()

    ttk.Button(extract_frame, text="Extract PDF", command=do_extract).grid(
        row=6, column=0, columnspan=3, sticky="w", padx=4, pady=4
    )

    # Right: Merge
    merge_frame = ttk.LabelFrame(tab_tools, text="Merge PDFs")
    merge_frame.grid(row=0, column=2, columnspan=2, sticky="nsew", padx=4, pady=4)
    merge_frame.columnconfigure(1, weight=1)

    tools_merge_files = []

    tools_merge_out = tk.StringVar(value=cfg.get("tools_merge_out", ""))
    merge_name_var = tk.StringVar(value=cfg.get("merge_name", ""))

    ttk.Label(merge_frame, text="Selected files:").grid(
        row=0, column=0, sticky="w", padx=4, pady=2
    )
    merge_list = scrolledtext.ScrolledText(merge_frame, height=8, width=40)
    merge_list.grid(row=1, column=0, columnspan=3, sticky="nsew", padx=4, pady=2)
    merge_frame.rowconfigure(1, weight=1)

    def add_merge_files():
        nonlocal tools_merge_files
        paths = filedialog.askopenfilenames(filetypes=[("PDF files", "*.pdf")])
        if not paths:
            return
        tools_merge_files = list(paths)
        merge_list.delete("1.0", tk.END)
        for p in tools_merge_files:
            merge_list.insert(tk.END, p + "\n")
        if not tools_merge_out.get():
            tools_merge_out.set(os.path.dirname(tools_merge_files[0]))

    ttk.Button(merge_frame, text="Add PDFs...", command=add_merge_files).grid(
        row=2, column=0, sticky="w", padx=4, pady=2
    )

    def clear_merge_files():
        nonlocal tools_merge_files
        tools_merge_files = []
        merge_list.delete("1.0", tk.END)

    ttk.Button(merge_frame, text="Clear List", command=clear_merge_files).grid(
        row=2, column=1, sticky="w", padx=4, pady=2
    )

    ttk.Label(merge_frame, text="Output folder:").grid(
        row=3, column=0, sticky="w", padx=4, pady=2
    )
    ttk.Entry(merge_frame, textvariable=tools_merge_out).grid(
        row=3, column=1, sticky="ew", padx=4, pady=2
    )
    ttk.Button(
        merge_frame,
        text="Browse",
        command=lambda: tools_merge_out.set(
            filedialog.askdirectory() or tools_merge_out.get()
        ),
    ).grid(row=3, column=2, padx=4, pady=2)

    ttk.Label(merge_frame, text="Output filename (optional):").grid(
        row=4, column=0, sticky="w", padx=4, pady=2
    )
    ttk.Entry(merge_frame, textvariable=merge_name_var).grid(
        row=4, column=1, sticky="ew", padx=4, pady=2
    )

    ttk.Checkbutton(
        merge_frame,
        text="Auto-open output folder when done",
        variable=tools_auto_open,
    ).grid(row=5, column=0, columnspan=3, sticky="w", padx=4, pady=2)

    def do_merge():
        if not tools_merge_files:
            messagebox.showerror("Error", "Add at least one PDF to merge.")
            return
        out_dir = tools_merge_out.get().strip()
        if not out_dir:
            out_dir = os.path.dirname(tools_merge_files[0])
            tools_merge_out.set(out_dir)

        cfg["tools_merge_out"] = out_dir
        cfg["merge_name"] = merge_name_var.get()
        cfg["tools_auto_open"] = tools_auto_open.get()
        save_config(cfg)

        append_log(f"▶ Merge {len(tools_merge_files)} PDFs")
        append_log(f"Output folder: {out_dir}")
        if merge_name_var.get().strip():
            append_log(f"Output name: {merge_name_var.get().strip()}")

        def worker():
            try:
                merge_pdfs(
                    files=tools_merge_files,
                    out_dir=out_dir,
                    filename=merge_name_var.get().strip(),
                    auto_open=tools_auto_open.get(),
                    log_callback=append_log,
                )
                messagebox.showinfo("Done", "Merge completed.")
            except Exception as e:
                append_log(f"❌ Merge error: {e}")
                messagebox.showerror("Error", str(e))

        threading.Thread(target=worker, daemon=True).start()

    ttk.Button(merge_frame, text="Merge PDFs", command=do_merge).grid(
        row=6, column=0, columnspan=3, sticky="w", padx=4, pady=4
    )

    # ---------------- On close: save window size ----------------
    def on_close():
        try:
            w = root.winfo_width()
            h = root.winfo_height()
            cfg["window_width"] = w
            cfg["window_height"] = h
            save_config(cfg)
        except Exception:
            pass
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()


if __name__ == "__main__":
    run_gui()
