# SplitPayPDF

SplitPayPDF is a Windows desktop application for splitting payroll PDFs into
per-employee files and for everyday PDF utilities (extract, merge). It has a
clean ttkbootstrap UI, a guided **Pattern Builder**, a safe preview mode, and a
results table + log so you can see exactly what will happen before it does.

The code is split into two modules: `SplitPayPDF.py` (GUI only) and
`splitpay_core.py` (all PDF/config/naming logic, no GUI dependencies).

---

## 📑 Table of Contents

- [✨ Features](#-features)
  - [Payroll Splitter](#payroll-splitter)
  - [Pattern Builder & schema naming](#pattern-builder--schema-naming)
  - [PDF Tools](#pdf-tools)
- [🛠️ Requirements](#️-requirements)
- [📥 Installation](#-installation)
- [🧪 Running the tests](#-running-the-tests)
- [📂 Folder structure](#-folder-structure)
- [📜 License](#-license)

---

## ✨ Features

### Payroll Splitter

- Splits a multi-page payroll PDF into **one output PDF per page**.
- Names each file and (optionally) each employee folder from **line-based
  tokens** read off the page — e.g. `[LINE 1]_[LINE 43(17/26)].pdf`.
- Routes pages it can't name to a **`!manual_review`** folder instead of saving
  junk filenames.
- **SAFE debug mode** simulates the whole run — no folders, no PDFs, no audit
  CSV — so you can review the results table and log first.
- Colour-coded **results table** plus a live **log** of every page.
- Writes a UTF-8 **audit CSV** of the run (skipped in SAFE mode).
- Duplicate-safe output names, employee-folder routing, and a schema **lock**
  to prevent accidental edits before a run.

### Pattern Builder & schema naming

A guided helper for building the naming patterns:

- Load any page and see its numbered lines (matching SAFE-mode output).
- Click a line, optionally set a **character range** (From/To), and insert the
  token **at the cursor** in a normal editable field.
- Type literal separators/text, use Backspace/Delete, paste, and **Ctrl+Z /
  Ctrl+Y** undo/redo.
- **Live preview** of the resulting filename and folder for the loaded page.
- Save/load named **schemas** (stored in `%APPDATA%\SplitPayPDF\Schemas`).

### PDF Tools

- **Extract** a single page, a page range, or one file per page.
- **Merge** multiple PDFs into one.
- Output names are operation-specific and derived from the source file, e.g.
  `payroll_page_5.pdf`, `payroll_pages_5-10.pdf`, `merged_2026-07-08.pdf`.
- A compact progress bar with a **Cancel** button appears for longer jobs and
  stays hidden while idle.

Other niceties: light/dark **themes** (ttkbootstrap), **drag-and-drop** a PDF
onto the window, and window size / last-used settings persisted between runs.

---

## 🛠️ Requirements

```bash
pip install -r requirements.txt
```

`requirements.txt` contains:

```
pymupdf>=1.24.0
ttkbootstrap>=1.10.1
tkinterdnd2>=0.4.0
```

`tkinter` ships with Python. `ttkbootstrap` and `tkinterdnd2` are optional at
runtime — without them the app falls back to the classic theme and disables
drag-and-drop, but everything else works.

---

## 📥 Installation

### Option 1 — Run from source

1. Install Python 3.10+ (from python.org, with the Tcl/Tk option).
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run:
   ```bash
   python SplitPayPDF.py
   ```

### Option 2 — Portable folder (no install, no admin, no pip on target)

For locked-down environments (e.g. Defender ASR blocking `.exe` files), build a
copy-and-run folder with a bundled Python runtime:

```powershell
powershell -ExecutionPolicy Bypass -File .\build_portable.ps1
```

Users then copy `SplitPayPDF_Portable\` and double-click `Run_SplitPayPDF.cmd`.
See [BUILD_PORTABLE.md](BUILD_PORTABLE.md) for full details. (The generated
`SplitPayPDF_Portable/` folder is git-ignored because it embeds a full Python
runtime.)

---

## 🧪 Running the tests

The core logic has unit tests that need neither a GUI nor PyMuPDF:

```bash
python -m unittest discover tests -v
```

---

## 📂 Folder structure

```
SplitPayPDF/
│
├── SplitPayPDF.py          # GUI layer
├── splitpay_core.py        # PDF / config / naming logic (no GUI)
├── build_portable.ps1      # Builds the portable, bundled-Python folder
├── requirements.txt
├── README.md
├── BUILD_PORTABLE.md
├── LICENSE
├── .gitignore
│
├── images/
│   └── icon.png
│
├── packaging/
│   ├── Run_SplitPayPDF.cmd
│   ├── README_PORTABLE.txt
│   └── IT_SECURITY_NOTES.txt
│
└── tests/
    └── test_core.py
```

---

## 📜 License

This project is open-source under the MIT License. See the `LICENSE` file for
full details.
