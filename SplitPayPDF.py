"""SplitPayPDF — GUI layer.

All PDF/config logic lives in splitpay_core.py. This file is UI only.
Optional niceties degrade gracefully: ttkbootstrap (theme) and
tkinterdnd2 (drag & drop) are used only if importable.
"""

import os
import sys
import threading
import tkinter as tk
from datetime import datetime
from tkinter import (
    filedialog,
    messagebox,
    scrolledtext,
    ttk,
    simpledialog,
)

# The portable build runs on embeddable Python, whose ._pth file means the
# script's own directory is NOT added to sys.path automatically. Ensure it is,
# so "import splitpay_core" works whether launched from source or the bundle.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import splitpay_core as core

try:
    import ttkbootstrap as tb

    HAS_TTKB = True
except Exception:
    HAS_TTKB = False

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD

    HAS_DND = True
except Exception:
    HAS_DND = False


THEMES_LIGHT_DEFAULT = "flatly"
THEMES_DARK_DEFAULT = "darkly"


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

    win.bind("<Escape>", lambda e: win.destroy())
    win.focus_set()


# -------------------- GUI --------------------


def run_gui():
    cfg = core.load_config()

    default_width = cfg.get("window_width", 940)
    default_height = cfg.get("window_height", 620)

    if HAS_DND:
        root = TkinterDnD.Tk()
    else:
        root = tk.Tk()

    initial_theme = (
        THEMES_DARK_DEFAULT if cfg.get("dark_mode", False) else THEMES_LIGHT_DEFAULT
    )
    style = None
    if HAS_TTKB:
        try:
            style = tb.Style(theme=initial_theme)
        except Exception:
            style = None

    root.title(f"{core.APP_NAME} {core.APP_VERSION} — Payroll Splitter + PDF Tools")

    # App icon (optional)
    try:
        icon_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "images", "icon.png"
        )
        if os.path.exists(icon_path):
            root.iconphoto(True, tk.PhotoImage(file=icon_path))
    except Exception:
        pass

    root.update_idletasks()
    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()
    w = default_width
    h = default_height
    x = (sw - w) // 2
    y = (sh - h) // 2
    root.geometry(f"{w}x{h}+{x}+{y}")

    # ---- thread-safe UI helper: schedule any call onto the main thread ----
    def ui(fn, *args, **kwargs):
        root.after(0, lambda: fn(*args, **kwargs))

    # ---------------- Menu bar (Help ▸ About) ----------------
    def show_about():
        text = (
            f"{core.APP_NAME} {core.APP_VERSION}\n\n"
            f"{core.APP_DESCRIPTION}\n\n"
            "Runs fully offline. No installation, no admin rights, and no "
            "network access required."
        )
        show_help_dialog(root, f"About {core.APP_NAME}", text)

    try:
        menubar = tk.Menu(root)
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label=f"About {core.APP_NAME}", command=show_about)
        menubar.add_cascade(label="Help", menu=help_menu)
        root.config(menu=menubar)
    except Exception:
        pass

    main = ttk.Frame(root)
    main.pack(fill="both", expand=True, padx=8, pady=8)
    # The notebook (row 1) sizes to its content; the results/log pane (row 3)
    # absorbs any extra vertical space. This keeps the primary workflow compact
    # instead of leaving a large empty area under the Run button.
    main.rowconfigure(1, weight=0)
    main.rowconfigure(3, weight=1)
    main.columnconfigure(0, weight=1)

    # ---------------- Top bar (theme picker) ----------------
    topbar = ttk.Frame(main)
    topbar.grid(row=0, column=0, sticky="ew", pady=(0, 4))
    topbar.columnconfigure(0, weight=1)

    ttk.Label(
        topbar, text="SplitPayPDF", font=("Segoe UI", 12, "bold")
    ).grid(row=0, column=0, sticky="w")

    if style is not None:
        dark_mode = tk.BooleanVar(value=cfg.get("dark_mode", False))

        def apply_theme():
            name = THEMES_DARK_DEFAULT if dark_mode.get() else THEMES_LIGHT_DEFAULT
            try:
                style.theme_use(name)
                cfg["dark_mode"] = dark_mode.get()
                cfg["theme"] = name
                core.save_config(cfg)
            except Exception:
                pass

        ttk.Checkbutton(
            topbar,
            text="🌙 Dark mode",
            variable=dark_mode,
            command=apply_theme,
        ).grid(row=0, column=1, sticky="e")

    notebook = ttk.Notebook(main)
    notebook.grid(row=1, column=0, sticky="nsew")

    # ---------------- Progress row (hidden while idle) ----------------
    prog_frame = ttk.Frame(main)
    prog_frame.grid(row=2, column=0, sticky="ew", pady=(6, 2))
    prog_frame.columnconfigure(1, weight=1)

    status_var = tk.StringVar(value="")
    ttk.Label(prog_frame, textvariable=status_var, width=22, anchor="w").grid(
        row=0, column=0, padx=(0, 6)
    )

    progress = ttk.Progressbar(prog_frame, mode="determinate")
    progress.grid(row=0, column=1, sticky="ew", padx=(0, 6))

    cancel_event = threading.Event()

    def do_cancel():
        cancel_event.set()
        status_var.set("Cancelling…")

    cancel_btn = ttk.Button(prog_frame, text="Cancel", command=do_cancel)
    cancel_btn.grid(row=0, column=2)

    # Buttons that kick off a job — disabled while any job runs. Populated as
    # the action buttons are created further down.
    action_buttons = []

    def set_busy(busy: bool, cancelable: bool = False):
        for b in action_buttons:
            try:
                b.config(state="disabled" if busy else "normal")
            except Exception:
                pass
        if busy:
            progress["value"] = 0
            if cancelable:
                cancel_btn.grid()
                cancel_btn.config(state="normal")
            else:
                cancel_btn.grid_remove()
            prog_frame.grid()
        else:
            progress["value"] = 0
            status_var.set("")
            prog_frame.grid_remove()

    # Start hidden — the progress area only appears while something is running.
    prog_frame.grid_remove()

    # ---------------- Bottom pane: Results / Log ----------------
    bottom = ttk.Notebook(main)
    bottom.grid(row=3, column=0, sticky="ew", pady=(4, 0))

    results_tab = ttk.Frame(bottom)
    bottom.add(results_tab, text="Results")
    results_tab.columnconfigure(0, weight=1)

    tree_cols = ("page", "status", "filename", "folder", "note")
    tree = ttk.Treeview(
        results_tab, columns=tree_cols, show="headings", height=7
    )
    for col, text, width, anchor in (
        ("page", "Page", 50, "center"),
        ("status", "Status", 130, "w"),
        ("filename", "Filename", 280, "w"),
        ("folder", "Folder", 140, "w"),
        ("note", "Note", 220, "w"),
    ):
        tree.heading(col, text=text)
        tree.column(col, width=width, anchor=anchor, stretch=(col in ("filename", "note")))
    tree.grid(row=0, column=0, sticky="nsew")
    tree_scroll = ttk.Scrollbar(results_tab, orient="vertical", command=tree.yview)
    tree_scroll.grid(row=0, column=1, sticky="ns")
    tree.configure(yscrollcommand=tree_scroll.set)

    tree.tag_configure("ok", foreground="#1a7f37")
    tree.tag_configure("fail", foreground="#c62828")
    tree.tag_configure("safe", foreground="#5a6b7b")

    def clear_results():
        for item in tree.get_children():
            tree.delete(item)

    def show_results(rows):
        clear_results()
        for r in rows:
            status = str(r.get("Status", ""))
            if status.startswith("OK (SAFE") or status.startswith("Failed (SAFE"):
                tag = "safe" if status.startswith("OK") else "fail"
            elif status.startswith("OK"):
                tag = "ok"
            else:
                tag = "fail"
            tree.insert(
                "",
                "end",
                values=(
                    r.get("Page", ""),
                    status,
                    r.get("Filename", ""),
                    r.get("FolderName", ""),
                    r.get("Note", ""),
                ),
                tags=(tag,),
            )
        if rows:
            bottom.select(results_tab)

    log_tab = ttk.Frame(bottom)
    bottom.add(log_tab, text="Log")
    log_tab.columnconfigure(0, weight=1)
    log_box = scrolledtext.ScrolledText(log_tab, wrap=tk.WORD, height=7)
    log_box.grid(row=0, column=0, sticky="nsew")

    def append_log(msg: str):
        log_box.insert(tk.END, f"{datetime.now().strftime('%H:%M:%S')}  {msg}\n")
        log_box.see(tk.END)
        core.write_app_log(msg)

    def update_progress(cur: int, total: int, noun: str = "page"):
        progress["maximum"] = total
        progress["value"] = cur
        status_var.set(f"Processing {noun} {cur} of {total}")

    # ============ TAB 1: Payroll Splitter ============
    tab_pay = ttk.Frame(notebook)
    notebook.add(tab_pay, text="Payroll Splitter")

    for c in range(3):
        tab_pay.columnconfigure(c, weight=1 if c == 1 else 0)

    ttk.Label(tab_pay, text="1 · Input PDF").grid(
        row=0, column=0, sticky="w", padx=4, pady=(6, 2)
    )
    pay_in = tk.StringVar(value=cfg.get("last_input", ""))
    ttk.Entry(tab_pay, textvariable=pay_in, width=70).grid(
        row=0, column=1, sticky="ew", padx=4, pady=(6, 2)
    )
    ttk.Button(
        tab_pay,
        text="Browse",
        command=lambda: pay_in.set(
            filedialog.askopenfilename(filetypes=[("PDF files", "*.pdf")])
            or pay_in.get()
        ),
    ).grid(row=0, column=2, padx=4, pady=(6, 2))

    ttk.Label(tab_pay, text="2 · Output folder").grid(
        row=1, column=0, sticky="w", padx=4, pady=2
    )
    pay_out = tk.StringVar(value=cfg.get("last_output", ""))
    ttk.Entry(tab_pay, textvariable=pay_out, width=70).grid(
        row=1, column=1, sticky="ew", padx=4, pady=2
    )
    ttk.Button(
        tab_pay,
        text="Browse",
        command=lambda: pay_out.set(
            filedialog.askdirectory() or pay_out.get()
        ),
    ).grid(row=1, column=2, padx=4, pady=2)

    auto_open = tk.BooleanVar(value=cfg.get("auto_open", True))
    save_to_folders = tk.BooleanVar(value=cfg.get("save_to_folders", True))
    debug_safe = tk.BooleanVar(value=cfg.get("debug_safe", True))

    # Options grouped compactly on two rows instead of three full-width rows.
    opts = ttk.Frame(tab_pay)
    opts.grid(row=2, column=0, columnspan=3, sticky="ew", padx=4, pady=(4, 0))

    ttk.Checkbutton(
        opts, text="Auto-open output folder", variable=auto_open
    ).grid(row=0, column=0, sticky="w", padx=(0, 16))
    ttk.Checkbutton(
        opts, text="Save to employee folders", variable=save_to_folders
    ).grid(row=0, column=1, sticky="w")

    safe_cb = ttk.Checkbutton(
        opts, text="Preview mode (no files written)", variable=debug_safe
    )
    safe_cb.grid(row=1, column=0, sticky="w", pady=(2, 0))

    def safe_help():
        text = (
            "Preview Mode\n\n"
            "In Preview mode, the splitter simulates the entire process "
            "without changing anything on disk:\n"
            "- No folders are created\n"
            "- No PDFs are written\n"
            "- No audit CSV is saved\n\n"
            "You can review everything in the Results table and the log first.\n"
            "Turn Preview mode OFF to actually split and save the files."
        )
        show_help_dialog(root, "Preview Mode", text)

    ttk.Button(opts, text="?", width=2, command=safe_help).grid(
        row=1, column=1, sticky="w", padx=(4, 0), pady=(2, 0)
    )

    schema_frame = ttk.LabelFrame(tab_pay, text="3 · Naming pattern & schema")
    schema_frame.grid(row=5, column=0, columnspan=3, sticky="ew", padx=4, pady=8)
    schema_frame.columnconfigure(1, weight=1)

    selected_schema = tk.StringVar(value=cfg.get("last_schema", "None"))
    existing_schemas = ["None"] + core.list_schemas()
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
        core.save_schema(name, file_pattern_var.get(), folder_pattern_var.get())
        vals = ["None"] + core.list_schemas()
        schema_combo["values"] = vals
        selected_schema.set(name)
        schema_combo.set(name)
        cfg["last_schema"] = name
        core.save_config(cfg)
        messagebox.showinfo("Saved", f"Schema '{name}' saved.")

    def do_remove_schema():
        name = selected_schema.get()
        if not name or name == "None":
            messagebox.showinfo("Remove Schema", "No schema selected.")
            return
        if not messagebox.askyesno("Confirm", f"Delete schema '{name}'?"):
            return
        core.delete_schema(name)
        vals = ["None"] + core.list_schemas()
        schema_combo["values"] = vals
        selected_schema.set("None")
        schema_combo.set("None")
        cfg["last_schema"] = "None"
        core.save_config(cfg)
        messagebox.showinfo("Removed", f"Schema '{name}' removed.")

    save_btn = ttk.Button(schema_frame, text="💾 Save", command=do_save_schema)
    save_btn.grid(row=0, column=2, sticky="w", padx=4, pady=4)

    remove_btn = ttk.Button(schema_frame, text="🗑 Remove", command=do_remove_schema)
    remove_btn.grid(row=0, column=3, sticky="w", padx=(0, 4), pady=4)

    # Patterns live directly in the schema frame (no extra nested box).
    ttk.Label(schema_frame, text="File naming pattern:").grid(
        row=1, column=0, sticky="w", padx=4, pady=2
    )
    file_entry = ttk.Entry(schema_frame, textvariable=file_pattern_var)
    file_entry.grid(row=1, column=1, sticky="ew", padx=4, pady=2)

    def file_pattern_help():
        text = (
            "Naming Pattern Help\n\n"
            "Build names using line-based tokens from the PDF:\n"
            "[LINE X]         → whole line X\n"
            "[LINE X(Y)]      → from character Y\n"
            "[LINE X(Y/Z)]    → characters Y–Z\n\n"
            "Examples:\n"
            "[LINE 1][LINE 2]_[LINE 3].pdf\n"
            "[LINE 43(17/26)]_neto.pdf\n\n"
            "Mix tokens with literal text freely.\n\n"
            "Folder patterns use the same tokens; folder names are\n"
            "normalized (specials/spaces removed, lowercased).\n\n"
            "Tip: use the Pattern Builder to click lines instead of\n"
            "typing tokens by hand."
        )
        show_help_dialog(root, "Naming Pattern Help", text)

    ttk.Button(schema_frame, text="?", width=2, command=file_pattern_help).grid(
        row=1, column=2, columnspan=2, sticky="e", padx=4, pady=2
    )

    folder_label = ttk.Label(schema_frame, text="Folder naming pattern:")
    folder_label.grid(row=2, column=0, sticky="w", padx=4, pady=2)
    folder_entry = ttk.Entry(schema_frame, textvariable=folder_pattern_var)
    folder_entry.grid(row=2, column=1, sticky="ew", padx=4, pady=2)

    def apply_lock_state():
        locked = lock_patterns.get()
        base_state = "readonly" if locked else "normal"
        file_entry.config(state=base_state)
        # The folder pattern only matters when routing to employee folders is
        # on — disable it (and its label) otherwise so it recedes visually.
        if save_to_folders.get():
            folder_entry.config(state=base_state)
            folder_label.config(state="normal")
        else:
            folder_entry.config(state="disabled")
            folder_label.config(state="disabled")
        save_btn.config(state="disabled" if locked else "normal")
        remove_btn.config(state="disabled" if locked else "normal")
        cfg["pattern_locked"] = locked
        core.save_config(cfg)

    lock_cb = ttk.Checkbutton(
        schema_frame,
        text="Lock patterns",
        variable=lock_patterns,
        command=apply_lock_state,
    )
    lock_cb.grid(row=3, column=0, sticky="w", padx=4, pady=(4, 6))

    # Re-evaluate folder-pattern state whenever the routing option changes.
    save_to_folders.trace_add("write", lambda *a: apply_lock_state())
    apply_lock_state()

    def on_schema_selected(event=None):
        name = selected_schema.get()
        if not name or name == "None":
            return
        data = core.load_schema(name)
        if data is None:
            messagebox.showwarning(
                "Preset",
                f"Could not read the preset '{name}'. It may be corrupted or "
                "unreadable. Your current patterns were kept.",
            )
            return
        if not lock_patterns.get():
            fp = data.get("file_pattern")
            if fp:
                file_pattern_var.set(fp)
            fp2 = data.get("folder_pattern")
            if fp2 is not None:
                folder_pattern_var.set(fp2)

    schema_combo.bind("<<ComboboxSelected>>", on_schema_selected)

    # ---------------- Pattern Builder ----------------

    def open_pattern_builder():
        inp = pay_in.get().strip()
        if not inp or not os.path.isfile(inp):
            messagebox.showerror(
                "Pattern Builder", "Select a valid input PDF first (top of the tab)."
            )
            return

        win = tk.Toplevel(root)
        win.title("Pattern Builder")
        win.transient(root)
        win.geometry("860x620")
        win.columnconfigure(0, weight=1)
        win.rowconfigure(2, weight=1)

        lines = []

        # -- Row 0: page selection --
        top = ttk.Frame(win, padding=(8, 8, 8, 0))
        top.grid(row=0, column=0, sticky="ew")
        ttk.Label(top, text="Page:").pack(side="left")
        page_var = tk.StringVar(value="1")
        ttk.Spinbox(top, from_=1, to=9999, textvariable=page_var, width=6).pack(
            side="left", padx=4
        )
        info_var = tk.StringVar(value="")
        ttk.Label(top, textvariable=info_var).pack(side="right")

        # -- Row 1: hint --
        ttk.Label(
            win,
            padding=(8, 4),
            text=(
                "1. Click a line   2. (optional) set character From/To   "
                "3. Insert token at the cursor   4. Type separators/text normally."
            ),
            wraplength=820,
            justify="left",
        ).grid(row=1, column=0, sticky="ew")

        # -- Row 2: line list --
        list_frame = ttk.Frame(win, padding=(8, 0))
        list_frame.grid(row=2, column=0, sticky="nsew")
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)

        line_list = tk.Listbox(list_frame, font=("Consolas", 10), activestyle="none")
        line_list.grid(row=0, column=0, sticky="nsew")
        lb_scroll = ttk.Scrollbar(
            list_frame, orient="vertical", command=line_list.yview
        )
        lb_scroll.grid(row=0, column=1, sticky="ns")
        line_list.configure(yscrollcommand=lb_scroll.set)

        # -- Row 3: token controls --
        ctrl = ttk.Frame(win, padding=(8, 4))
        ctrl.grid(row=3, column=0, sticky="ew")

        target_var = tk.StringVar(value="file")
        ttk.Label(ctrl, text="Editing:").grid(row=0, column=0, padx=(0, 4))
        ttk.Radiobutton(
            ctrl, text="File", variable=target_var, value="file"
        ).grid(row=0, column=1)
        ttk.Radiobutton(
            ctrl, text="Folder", variable=target_var, value="folder"
        ).grid(row=0, column=2, padx=(0, 14))

        ttk.Label(ctrl, text="Chars from:").grid(row=0, column=3)
        from_var = tk.StringVar()
        ttk.Entry(ctrl, textvariable=from_var, width=5).grid(row=0, column=4, padx=2)
        ttk.Label(ctrl, text="to:").grid(row=0, column=5)
        to_var = tk.StringVar()
        ttk.Entry(ctrl, textvariable=to_var, width=5).grid(row=0, column=6, padx=2)

        token_prev_var = tk.StringVar(value="Token: — (select a line)")
        ttk.Label(ctrl, textvariable=token_prev_var).grid(
            row=1, column=0, columnspan=8, sticky="w", pady=(4, 0)
        )

        def selected_index():
            sel = line_list.curselection()
            return sel[0] if sel else None

        def make_token():
            idx = selected_index()
            if idx is None:
                return None
            f = from_var.get().strip()
            t = to_var.get().strip()
            if f and t:
                return f"[LINE {idx}({f}/{t})]"
            if f:
                return f"[LINE {idx}({f})]"
            return f"[LINE {idx}]"

        def active_var():
            return (
                file_pattern_var if target_var.get() == "file" else folder_pattern_var
            )

        def update_token_preview(event=None):
            token = make_token()
            if token is None:
                token_prev_var.set("Token: — (select a line)")
                return
            try:
                val = core.build_value_from_line_pattern(lines, token)
            except Exception:
                val = ""
            token_prev_var.set(f"Token: {token}  →  '{val}'")

        line_list.bind("<<ListboxSelect>>", update_token_preview)
        # Double-click a line to insert it immediately at the cursor.
        line_list.bind("<Double-Button-1>", lambda e: insert_token())
        from_var.trace_add("write", lambda *a: update_token_preview())
        to_var.trace_add("write", lambda *a: update_token_preview())

        # -- Row 4: editable pattern field --
        edit_frame = ttk.Frame(win, padding=(8, 0))
        edit_frame.grid(row=4, column=0, sticky="ew")
        edit_frame.columnconfigure(0, weight=1)

        ttk.Label(
            edit_frame,
            text="Pattern (type freely; Ctrl+Z undo / Ctrl+Y redo):",
        ).grid(row=0, column=0, columnspan=2, sticky="w")
        pattern_edit = ttk.Entry(edit_frame, font=("Consolas", 10))
        pattern_edit.grid(row=1, column=0, sticky="ew", pady=(2, 6))

        # ---- undo/redo history, kept per target while the builder is open ----
        history = {
            "file": [file_pattern_var.get()],
            "folder": [folder_pattern_var.get()],
        }
        hpos = {"file": 0, "folder": 0}
        suppress = {"on": False}

        def record(target):
            if suppress["on"]:
                return
            val = (
                file_pattern_var if target == "file" else folder_pattern_var
            ).get()
            h = history[target]
            del h[hpos[target] + 1:]
            if h and h[-1] == val:
                return
            h.append(val)
            hpos[target] = len(h) - 1

        def do_undo(event=None):
            t = target_var.get()
            if hpos[t] > 0:
                hpos[t] -= 1
                suppress["on"] = True
                active_var().set(history[t][hpos[t]])
                suppress["on"] = False
            return "break"

        def do_redo(event=None):
            t = target_var.get()
            if hpos[t] < len(history[t]) - 1:
                hpos[t] += 1
                suppress["on"] = True
                active_var().set(history[t][hpos[t]])
                suppress["on"] = False
            return "break"

        pattern_edit.bind("<Control-z>", do_undo)
        pattern_edit.bind("<Control-Z>", do_undo)
        pattern_edit.bind("<Control-y>", do_redo)
        pattern_edit.bind("<Control-Y>", do_redo)

        def refresh_edit_target():
            # Point the editable entry at the active pattern variable and
            # honour the lock state.
            pattern_edit.config(textvariable=active_var())
            pattern_edit.config(
                state="readonly" if lock_patterns.get() else "normal"
            )

        def insert_token():
            if lock_patterns.get():
                messagebox.showwarning(
                    "Locked", "Naming patterns are locked. Unlock them first."
                )
                return
            token = make_token()
            if token is None:
                messagebox.showinfo("Pattern Builder", "Select a line first.")
                return
            try:
                pos = pattern_edit.index(tk.INSERT)
            except Exception:
                pos = tk.END
            # Inserting via the widget updates the bound variable and fires the
            # preview/history traces automatically.
            pattern_edit.insert(pos, token)
            pattern_edit.icursor(pos + len(token))
            pattern_edit.focus_set()

        ttk.Button(
            ctrl, text="⬇ Insert token at cursor", command=insert_token
        ).grid(row=0, column=7, padx=(14, 0))

        def clear_pattern():
            if lock_patterns.get():
                return
            active_var().set("")
            pattern_edit.focus_set()

        ttk.Button(edit_frame, text="Clear", width=7, command=clear_pattern).grid(
            row=1, column=1, padx=(6, 0), pady=(2, 6)
        )

        # -- Row 5: live preview --
        prev = ttk.LabelFrame(win, text="Live preview (using loaded page)", padding=8)
        prev.grid(row=5, column=0, sticky="ew", padx=8, pady=(0, 8))
        prev.columnconfigure(1, weight=1)

        file_prev_var = tk.StringVar()
        folder_prev_var = tk.StringVar()
        ttk.Label(prev, text="Filename:").grid(row=0, column=0, sticky="w")
        ttk.Label(prev, textvariable=file_prev_var).grid(row=0, column=1, sticky="w")
        ttk.Label(prev, text="Folder:").grid(row=1, column=0, sticky="w")
        ttk.Label(prev, textvariable=folder_prev_var).grid(row=1, column=1, sticky="w")

        def update_preview(*args):
            if not lines:
                file_prev_var.set("(load a page first)")
                folder_prev_var.set("(load a page first)")
                return
            try:
                fname = core.build_filename_from_line_pattern(
                    lines, file_pattern_var.get()
                )
            except Exception:
                fname = "(error)"
            try:
                raw = core.build_value_from_line_pattern(
                    lines, folder_pattern_var.get()
                )
                folder = core.normalize_folder_name(raw) if raw else ""
            except Exception:
                folder = "(error)"
            file_prev_var.set(fname or "(empty → page would go to !manual_review)")
            folder_prev_var.set(folder or "(empty → 'unknown' folder)")

        def on_file_change(*a):
            record("file")
            update_preview()

        def on_folder_change(*a):
            record("folder")
            update_preview()

        def on_target_change(*a):
            refresh_edit_target()
            update_token_preview()

        trace_ids = [
            (file_pattern_var, file_pattern_var.trace_add("write", on_file_change)),
            (folder_pattern_var, folder_pattern_var.trace_add("write", on_folder_change)),
            (target_var, target_var.trace_add("write", on_target_change)),
        ]

        def on_close():
            for var, tid in trace_ids:
                try:
                    var.trace_remove("write", tid)
                except Exception:
                    pass
            win.destroy()

        win.protocol("WM_DELETE_WINDOW", on_close)

        def load_page():
            nonlocal lines
            try:
                pno = int(page_var.get())
                lines = core.get_page_lines(inp, pno)
            except Exception as e:
                messagebox.showerror("Pattern Builder", f"Could not load page:\n{e}")
                return
            line_list.delete(0, tk.END)
            for i, line in enumerate(lines):
                line_list.insert(tk.END, f"{i:>3} │ {line}")
            info_var.set(f"{os.path.basename(inp)} — page {pno}, {len(lines)} lines")
            update_preview()
            update_token_preview()

        ttk.Button(top, text="Load page", command=load_page).pack(side="left", padx=4)

        refresh_edit_target()
        load_page()

    builder_btn = ttk.Button(
        schema_frame, text="🔧 Pattern Builder…", command=open_pattern_builder
    )
    builder_btn.grid(row=3, column=1, columnspan=3, sticky="e", padx=4, pady=(4, 6))

    # ---------------- Run splitter ----------------

    def run_splitter():
        inp = pay_in.get().strip()
        if not inp or not os.path.isfile(inp):
            messagebox.showerror("Error", "Please select a valid payroll PDF.")
            return

        # Pre-flight: friendly handling of password-protected / corrupt PDFs,
        # and a clear warning for scanned / image-only PDFs (no selectable text).
        try:
            info = core.preflight_pdf(inp)
        except core.PdfError as e:
            messagebox.showwarning("Cannot open PDF", str(e))
            return
        except Exception as e:
            core.write_app_log(f"[preflight] {inp}: {e!r}")
            messagebox.showerror(
                "Cannot open PDF",
                "This PDF could not be opened. It may be corrupted or in an "
                "unsupported format.",
            )
            return
        if not info["has_text"]:
            if not messagebox.askyesno(
                "No selectable text",
                "No selectable text was found in this PDF. It may be scanned "
                "or image-only. SplitPayPDF needs selectable text to build "
                "filenames automatically.\n\nContinue anyway?",
            ):
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
        core.save_config(cfg)

        file_pat = file_pattern_var.get()
        folder_pat = folder_pattern_var.get()
        schema_name = selected_schema.get()
        if schema_name and schema_name != "None":
            data = core.load_schema(schema_name)
            if data is None:
                messagebox.showwarning(
                    "Preset",
                    f"Could not read the preset '{schema_name}'. It may be "
                    "corrupted. Continuing with the patterns shown on screen.",
                )
            elif not lock_patterns.get():
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

        clear_results()
        cancel_event.clear()
        set_busy(True, cancelable=True)

        def finish_split(res):
            show_results(res["rows"])
            if res["total"] == 0:
                messagebox.showwarning("Done", "PDF had no pages.")
                return
            msg = (
                f"Split {'cancelled' if res['cancelled'] else 'completed'}.\n\n"
                f"Pages: {res['total']}\n"
                f"Success: {res['success']}\n"
                f"Manual review: {res['failed']}\n"
            )
            if not debug_safe.get() and res["audit_path"]:
                msg += f"\nAudit log:\n{res['audit_path']}"
            if res["cancelled"]:
                messagebox.showwarning("Cancelled", msg)
            else:
                messagebox.showinfo("Done", msg)

        def worker():
            try:
                res = core.split_pdf_full(
                    inp_path=inp,
                    out_dir=out_dir,
                    file_pattern=file_pat,
                    folder_pattern=folder_pat,
                    save_to_folders=save_to_folders.get(),
                    safe_mode=debug_safe.get(),
                    auto_open=auto_open.get(),
                    log_callback=lambda m: ui(append_log, m),
                    progress_callback=lambda p, t: ui(update_progress, p, t),
                    cancel_event=cancel_event,
                )
                ui(finish_split, res)
            except core.PdfError as e:
                ui(append_log, f"⚠ {e}")
                ui(messagebox.showwarning, "Cannot open PDF", str(e))
            except Exception as e:
                ui(append_log, f"❌ ERROR during split: {e}")
                ui(messagebox.showerror, "Error", f"An error occurred:\n{e}")
            finally:
                ui(set_busy, False)

        threading.Thread(target=worker, daemon=True).start()

    run_btn = ttk.Button(
        tab_pay, text="4 · ▶ Split & save files", command=run_splitter
    )
    run_btn.grid(row=6, column=0, columnspan=3, sticky="ew", padx=4, pady=(4, 6))
    action_buttons.append(run_btn)

    def refresh_run_label(*_):
        if debug_safe.get():
            run_btn.config(text="4 · ▶ Preview (no files written)")
        else:
            run_btn.config(text="4 · ▶ Split & save files")

    debug_safe.trace_add("write", refresh_run_label)
    refresh_run_label()

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
        core.save_config(cfg)

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

        cancelable = ext_per_page.get() and bool(r_from and r_to)
        cancel_event.clear()
        set_busy(True, cancelable=cancelable)

        def worker():
            try:
                core.extract_pages(
                    inp_path=inp,
                    out_dir=out_dir,
                    single_page=single,
                    range_from=r_from,
                    range_to=r_to,
                    per_page=ext_per_page.get(),
                    auto_open=tools_auto_open.get(),
                    log_callback=lambda m: ui(append_log, m),
                    progress_callback=lambda c, t: ui(update_progress, c, t),
                    cancel_event=cancel_event,
                )
                ui(messagebox.showinfo, "Done", "Extract completed.")
            except core.PdfError as e:
                ui(append_log, f"⚠ {e}")
                ui(messagebox.showwarning, "Cannot open PDF", str(e))
            except Exception as e:
                ui(append_log, f"❌ Extract error: {e}")
                ui(messagebox.showerror, "Error", str(e))
            finally:
                ui(set_busy, False)

        threading.Thread(target=worker, daemon=True).start()

    extract_btn = ttk.Button(extract_frame, text="Extract PDF", command=do_extract)
    extract_btn.grid(row=6, column=0, columnspan=3, sticky="w", padx=4, pady=4)
    action_buttons.append(extract_btn)

    # Right: Merge
    merge_frame = ttk.LabelFrame(tab_tools, text="Merge PDFs")
    merge_frame.grid(row=0, column=2, columnspan=2, sticky="nsew", padx=4, pady=4)
    merge_frame.columnconfigure(1, weight=1)

    tools_merge_files = []

    tools_merge_out = tk.StringVar(value=cfg.get("tools_merge_out", ""))
    merge_name_var = tk.StringVar(value=cfg.get("merge_name", ""))

    ttk.Label(merge_frame, text="Files to merge (top → bottom order):").grid(
        row=0, column=0, columnspan=4, sticky="w", padx=4, pady=(2, 0)
    )
    merge_listbox = tk.Listbox(
        merge_frame, height=8, activestyle="none", selectmode=tk.SINGLE
    )
    merge_listbox.grid(row=1, column=0, columnspan=3, sticky="nsew", padx=(4, 0), pady=2)
    merge_scroll = ttk.Scrollbar(
        merge_frame, orient="vertical", command=merge_listbox.yview
    )
    merge_scroll.grid(row=1, column=3, sticky="ns", pady=2)
    merge_listbox.configure(yscrollcommand=merge_scroll.set)
    merge_frame.rowconfigure(1, weight=1)

    def refresh_merge_listbox(select_index=None):
        merge_listbox.delete(0, tk.END)
        for p in tools_merge_files:
            merge_listbox.insert(tk.END, os.path.basename(p))
        if select_index is not None and 0 <= select_index < len(tools_merge_files):
            merge_listbox.selection_clear(0, tk.END)
            merge_listbox.selection_set(select_index)
            merge_listbox.activate(select_index)
            merge_listbox.see(select_index)

    def merge_selected_index():
        sel = merge_listbox.curselection()
        return sel[0] if sel else None

    def add_merge_files():
        nonlocal tools_merge_files
        paths = filedialog.askopenfilenames(filetypes=[("PDF files", "*.pdf")])
        if not paths:
            return
        # Append (don't replace) so users can build up a list from several picks.
        tools_merge_files = tools_merge_files + list(paths)
        refresh_merge_listbox(len(tools_merge_files) - 1)
        if not tools_merge_out.get():
            tools_merge_out.set(os.path.dirname(tools_merge_files[0]))

    def remove_merge_file():
        nonlocal tools_merge_files
        idx = merge_selected_index()
        if idx is None:
            return
        tools_merge_files = tools_merge_files[:idx] + tools_merge_files[idx + 1:]
        refresh_merge_listbox(idx if tools_merge_files else None)

    def move_merge_up():
        nonlocal tools_merge_files
        tools_merge_files, new_idx = core.move_item(
            tools_merge_files, merge_selected_index(), -1
        )
        refresh_merge_listbox(new_idx)

    def move_merge_down():
        nonlocal tools_merge_files
        tools_merge_files, new_idx = core.move_item(
            tools_merge_files, merge_selected_index(), +1
        )
        refresh_merge_listbox(new_idx)

    def clear_merge_files():
        nonlocal tools_merge_files
        tools_merge_files = []
        refresh_merge_listbox()

    merge_btnbar = ttk.Frame(merge_frame)
    merge_btnbar.grid(row=2, column=0, columnspan=4, sticky="w", padx=4, pady=(2, 4))
    ttk.Button(merge_btnbar, text="Add…", command=add_merge_files).pack(side="left")
    ttk.Button(merge_btnbar, text="Remove", command=remove_merge_file).pack(
        side="left", padx=(6, 0)
    )
    ttk.Button(merge_btnbar, text="↑ Up", command=move_merge_up).pack(
        side="left", padx=(6, 0)
    )
    ttk.Button(merge_btnbar, text="↓ Down", command=move_merge_down).pack(
        side="left", padx=(6, 0)
    )
    ttk.Button(merge_btnbar, text="Clear", command=clear_merge_files).pack(
        side="left", padx=(6, 0)
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
        core.save_config(cfg)

        append_log(f"▶ Merge {len(tools_merge_files)} PDFs")
        append_log(f"Output folder: {out_dir}")
        if merge_name_var.get().strip():
            append_log(f"Output name: {merge_name_var.get().strip()}")

        cancelable = len(tools_merge_files) > 1
        cancel_event.clear()
        set_busy(True, cancelable=cancelable)

        def worker():
            try:
                core.merge_pdfs(
                    files=tools_merge_files,
                    out_dir=out_dir,
                    filename=merge_name_var.get().strip(),
                    auto_open=tools_auto_open.get(),
                    log_callback=lambda m: ui(append_log, m),
                    progress_callback=lambda c, t: ui(update_progress, c, t, "file"),
                    cancel_event=cancel_event,
                )
                ui(messagebox.showinfo, "Done", "Merge completed.")
            except core.PdfError as e:
                ui(append_log, f"⚠ {e}")
                ui(messagebox.showwarning, "Cannot open PDF", str(e))
            except Exception as e:
                ui(append_log, f"❌ Merge error: {e}")
                ui(messagebox.showerror, "Error", str(e))
            finally:
                ui(set_busy, False)

        threading.Thread(target=worker, daemon=True).start()

    merge_btn = ttk.Button(merge_frame, text="Merge PDFs", command=do_merge)
    merge_btn.grid(row=6, column=0, columnspan=3, sticky="w", padx=4, pady=4)
    action_buttons.append(merge_btn)

    # ---------------- Drag & drop (optional) ----------------
    if HAS_DND:
        def on_drop(event):
            try:
                items = root.tk.splitlist(event.data)
            except Exception:
                items = [event.data]
            pdfs = [i.strip("{}") for i in items if i.lower().strip("{}").endswith(".pdf")]
            if not pdfs:
                return
            if notebook.index(notebook.select()) == 0:
                pay_in.set(pdfs[0])
                append_log(f"📥 Dropped PDF → Payroll input: {pdfs[0]}")
            else:
                tools_ext_in.set(pdfs[0])
                append_log(f"📥 Dropped PDF → Extract input: {pdfs[0]}")

        try:
            root.drop_target_register(DND_FILES)
            root.dnd_bind("<<Drop>>", on_drop)
        except Exception:
            pass

    # ---------------- On close: save window size ----------------
    def on_close():
        try:
            cfg["window_width"] = root.winfo_width()
            cfg["window_height"] = root.winfo_height()
            core.save_config(cfg)
        except Exception:
            pass
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()


if __name__ == "__main__":
    run_gui()
